"""
Core Ingestion Engine
Handles physical telemetry parsing, canonical SHA-256 integrity verification,
strict device/sensor registration validation, sequence loss detection, and
ESP32 microsecond timer unwrapping.
"""

import struct
import hashlib
import uuid
from typing import List, Tuple, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from . import models, schemas
from .config import settings
from .websocket_manager import ws_manager

# =========================================================================
# CANONICAL SHA-256 PAYLOAD DEFINITION
# =========================================================================
# Format: IEEE 754 64-bit Floating-Point (double precision)
# Endianness: Little-Endian ('<d')
# Length: 8 bytes per sample (e.g. 500 samples = exactly 4000 raw bytes)
#
# The cryptographic hash is computed strictly on these canonical raw bytes:
#   sha256_hash = hashlib.sha256(raw_samples_blob).hexdigest()
#
# Verification recomputes hashlib.sha256(burst.raw_samples_blob).hexdigest()
# directly from SQLite blob storage and compares with stored sha256_hash.
# =========================================================================

def serialize_samples(samples: List[float]) -> bytes:
    """
    Pack float samples into canonical binary representation:
    IEEE 754 double-precision little-endian bytes ('<d').
    """
    return struct.pack(f"<{len(samples)}d", *samples)

def deserialize_samples(blob: bytes) -> List[float]:
    """
    Unpack canonical binary bytes back into a list of Python floats.
    """
    count = len(blob) // 8
    return list(struct.unpack(f"<{count}d", blob))

def compute_sha256(raw_bytes: bytes) -> str:
    """Calculate cryptographic SHA-256 hash of canonical raw payload bytes."""
    return hashlib.sha256(raw_bytes).hexdigest()

class IngestionService:
    @staticmethod
    def process_and_persist_telemetry(
        db: Session,
        packet: schemas.RawTelemetryPacketIn
    ) -> models.RawVibrationBurst:
        """
        Processes an incoming raw telemetry packet:
        1. Validates registered Device and Sensor identities.
        2. Enforces LIVE provenance trust constraints (untrusted/unregistered devices rejected).
        3. Enforces Idempotency & Conflict detection on (device_id, stream_id, sequence_number).
        4. Detects sequence gaps, increments dropped frame counts, while persisting the later packet.
        5. Handles ESP32 32-bit hardware timer rollover safely.
        6. Computes canonical SHA-256 hash over raw binary payload.
        7. Commits RawVibrationBurst and updates StreamTracker in SQLite WAL.
        """

        # -----------------------------------------------------------------
        # 1. Device Registration & Trust Validation
        # -----------------------------------------------------------------
        device = db.query(models.Device).filter(models.Device.id == packet.device_id).first()
        if not device:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Device '{packet.device_id}' is not registered in the system. Register device first."
            )

        if packet.data_provenance == schemas.DataProvenance.LIVE:
            if device.is_trusted_hardware != 1 or device.status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Device '{packet.device_id}' is not an active trusted hardware device "
                        f"(status='{device.status}', trusted={device.is_trusted_hardware}). "
                        f"Untrusted devices cannot submit LIVE telemetry."
                    )
                )

        # -----------------------------------------------------------------
        # 2. Sensor & Joint Foreign-Key Validation
        # -----------------------------------------------------------------
        sensor = db.query(models.Sensor).filter(models.Sensor.id == packet.sensor_id).first()
        if not sensor or sensor.status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sensor '{packet.sensor_id}' does not exist or is not active in database."
            )

        if packet.joint_id is not None:
            joint = db.query(models.Joint).filter(
                (models.Joint.id == packet.joint_id) |
                (models.Joint.joint_code == packet.joint_id)
            ).first()
            if not joint:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Joint '{packet.joint_id}' does not exist in database."
                )
            packet.joint_id = joint.id

        # -----------------------------------------------------------------
        # 3. Canonical Binary Serialization & SHA-256 Calculation
        # -----------------------------------------------------------------
        raw_blob = serialize_samples(packet.samples)
        sha256_hash = compute_sha256(raw_blob)

        # -----------------------------------------------------------------
        # 4. Duplicate / Idempotency & Conflict Semantics
        # -----------------------------------------------------------------
        existing_burst = db.query(models.RawVibrationBurst).filter(
            models.RawVibrationBurst.device_id == packet.device_id,
            models.RawVibrationBurst.stream_id == packet.stream_id,
            models.RawVibrationBurst.sequence_number == packet.sequence_number
        ).first()

        if existing_burst:
            if existing_burst.sha256_hash == sha256_hash:
                # Exact duplicate retransmission: Idempotent return
                return existing_burst
            else:
                # Same sequence number with conflicting payload: Data-integrity violation
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Data integrity conflict: sequence {packet.sequence_number} on stream "
                        f"'{packet.stream_id}' already exists with payload hash '{existing_burst.sha256_hash}', "
                        f"conflicting with new hash '{sha256_hash}'."
                    )
                )

        # -----------------------------------------------------------------
        # 5. Per-Stream Sequence & Rollover Tracking
        # -----------------------------------------------------------------
        tracker_id = f"{packet.device_id}:{packet.stream_id}"
        tracker = db.query(models.StreamTracker).filter(models.StreamTracker.id == tracker_id).first()

        now_utc = datetime.now(timezone.utc).isoformat()
        quality_flags = packet.quality_flags

        if tracker is None:
            rollover_count = 0
            unwrapped_hw_ts = packet.hardware_timestamp_us
            tracker = models.StreamTracker(
                id=tracker_id,
                device_id=packet.device_id,
                stream_id=packet.stream_id,
                last_sequence_number=packet.sequence_number,
                total_packets_received=1,
                dropped_packets_count=0,
                last_hardware_timestamp_us=packet.hardware_timestamp_us,
                rollover_count=0,
                last_seen_utc=now_utc
            )
            db.add(tracker)
        else:
            # Check for 32-bit hardware timer rollover (~4,294,967,296 us boundary)
            rollover_count = tracker.rollover_count
            if (
                packet.hardware_timestamp_us < tracker.last_hardware_timestamp_us
                and (tracker.last_hardware_timestamp_us - packet.hardware_timestamp_us) > settings.TIMESTAMP_32BIT_ROLLOVER_THRESHOLD_US
                and packet.sequence_number > tracker.last_sequence_number
            ):
                rollover_count += 1
                tracker.rollover_count = rollover_count

            # Monotonic unwrapped hardware timestamp
            unwrapped_hw_ts = (rollover_count * 4_294_967_296) + packet.hardware_timestamp_us

            # Sequence gap detection
            expected_seq = tracker.last_sequence_number + 1
            if packet.sequence_number == expected_seq:
                # Strict monotonic continuity
                pass
            elif packet.sequence_number > expected_seq:
                # Sequence gap detected! Calculate dropped packet count
                gap = packet.sequence_number - expected_seq
                tracker.dropped_packets_count += gap
                quality_flags = "DROPPED_FRAMES" if quality_flags == "OK" else f"{quality_flags}|DROPPED_FRAMES"
            elif packet.sequence_number < expected_seq:
                # Out-of-order packet (sequence was earlier but different payload not yet seen)
                quality_flags = "OUT_OF_ORDER" if quality_flags == "OK" else f"{quality_flags}|OUT_OF_ORDER"

            # Update tracker state
            tracker.last_sequence_number = max(tracker.last_sequence_number, packet.sequence_number)
            tracker.total_packets_received += 1
            tracker.last_hardware_timestamp_us = packet.hardware_timestamp_us
            tracker.last_seen_utc = now_utc

        # -----------------------------------------------------------------
        # 6. Persistence to SQLite WAL
        # -----------------------------------------------------------------
        burst_id = str(uuid.uuid4())
        burst = models.RawVibrationBurst(
            id=burst_id,
            device_id=packet.device_id,
            stream_id=packet.stream_id,
            sensor_id=packet.sensor_id,
            joint_id=packet.joint_id,
            sequence_number=packet.sequence_number,
            hardware_timestamp_us=packet.hardware_timestamp_us,
            unwrapped_hardware_timestamp_us=unwrapped_hw_ts,
            received_at_utc=now_utc,
            sampling_rate_hz=packet.sampling_rate_hz,
            sample_count=len(packet.samples),
            raw_samples_blob=raw_blob,
            sha256_hash=sha256_hash,
            quality_flags=quality_flags,
            data_provenance=packet.data_provenance.value,
            drive_rpm=getattr(packet, "drive_rpm", None),
            pretension_n=getattr(packet, "pretension_n", None)
        )

        db.add(burst)
        db.commit()
        db.refresh(burst)
        return burst

    @staticmethod
    def verify_and_unpack_burst(burst: models.RawVibrationBurst) -> Tuple[List[float], bool]:
        """
        Unpacks canonical binary samples and validates against stored SHA-256 hash.
        Recomputes hash directly from persisted raw_samples_blob.
        Returns (samples, integrity_verified).
        """
        computed_hash = compute_sha256(burst.raw_samples_blob)
        verified = (computed_hash == burst.sha256_hash)
        samples = deserialize_samples(burst.raw_samples_blob)
        return samples, verified
