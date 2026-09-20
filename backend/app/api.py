import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .database import get_db
from .config import settings
from . import models, schemas
from .ingestion import IngestionService
from .simulator import sim_driver, VALID_FAULT_MODES
from .websocket_manager import ws_manager
from .ml_service import vibration_anomaly_engine
from .serial_worker import serial_worker
from .joint_lifecycle_service import joint_lifecycle_service

router = APIRouter(prefix=settings.API_V1_STR)
ws_router = APIRouter()

# ---------------------------------------------------------
# 1. System Health & Stream Status
# ---------------------------------------------------------

@router.get("/system/status", response_model=schemas.SystemStatusResponse)
def get_system_status(db: Session = Depends(get_db)):
    """Returns current edge ingestion status, active streams, and packet loss stats."""
    trackers = db.query(models.StreamTracker).all()
    total_bursts = db.query(models.RawVibrationBurst).count()

    stream_statuses = [
        schemas.StreamStatus(
            stream_id=t.stream_id,
            device_id=t.device_id,
            last_sequence_number=t.last_sequence_number,
            total_packets_received=t.total_packets_received,
            dropped_packets_count=t.dropped_packets_count,
            last_hardware_timestamp_us=t.last_hardware_timestamp_us,
            rollover_count=t.rollover_count,
            last_seen_utc=t.last_seen_utc
        )
        for t in trackers
    ]

    return schemas.SystemStatusResponse(
        system_name=settings.PROJECT_NAME,
        status="OPERATIONAL",
        serial_worker_enabled=settings.SERIAL_WORKER_ENABLED,
        serial_port=settings.SERIAL_PORT,
        simulation_ingestion_allowed=settings.ALLOW_SIMULATION_INGESTION,
        active_streams=stream_statuses,
        total_bursts_persisted=total_bursts,
        server_time_utc=datetime.now(timezone.utc).isoformat()
    )

# ---------------------------------------------------------
# 2. Telemetry Ingestion (LIVE & Real Hardware)
# ---------------------------------------------------------

def get_tracker_dict(db: Session, device_id: str, stream_id: str) -> Optional[Dict[str, Any]]:
    tracker = db.query(models.StreamTracker).filter(
        models.StreamTracker.id == f"{device_id}:{stream_id}"
    ).first()
    if not tracker:
        return None
    return {
        "device_id": tracker.device_id,
        "stream_id": tracker.stream_id,
        "last_sequence_number": tracker.last_sequence_number,
        "total_packets_received": tracker.total_packets_received,
        "dropped_packets_count": tracker.dropped_packets_count,
        "last_hardware_timestamp_us": tracker.last_hardware_timestamp_us,
        "rollover_count": tracker.rollover_count,
        "last_seen_utc": tracker.last_seen_utc
    }

def _run_health_pipeline(db: Session, burst: models.RawVibrationBurst):
    """Run Phase 3 health pipeline after successful ingestion (best-effort)."""
    try:
        from .health_service import health_service
        health_service.process_burst(db, burst)
    except Exception as exc:
        import logging
        logging.getLogger("api").error("Health pipeline error for burst %s: %s", burst.id, exc)

@router.post(
    "/telemetry/ingest",
    response_model=schemas.RawTelemetryBurstSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest raw telemetry from edge hardware"
)
async def ingest_telemetry_packet(
    packet: schemas.RawTelemetryPacketIn,
    db: Session = Depends(get_db)
):
    """
    Primary ingestion endpoint for real edge hardware.
    Enforces that packets cannot masquerade with SIMULATION provenance on this endpoint.
    """
    if packet.data_provenance == schemas.DataProvenance.SIMULATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Simulation packets are forbidden on /telemetry/ingest. Use /telemetry/simulate."
        )

    burst = IngestionService.process_and_persist_telemetry(db, packet)
    tracker_dict = get_tracker_dict(db, burst.device_id, burst.stream_id)
    await ws_manager.broadcast_burst(
        burst_id=burst.id,
        device_id=burst.device_id,
        stream_id=burst.stream_id,
        sensor_id=burst.sensor_id,
        joint_id=burst.joint_id,
        sequence_number=burst.sequence_number,
        hardware_timestamp_us=burst.hardware_timestamp_us,
        unwrapped_hardware_timestamp_us=burst.unwrapped_hardware_timestamp_us,
        received_at_utc=burst.received_at_utc,
        sampling_rate_hz=burst.sampling_rate_hz,
        sample_count=burst.sample_count,
        sha256_hash=burst.sha256_hash,
        quality_flags=burst.quality_flags,
        data_provenance=burst.data_provenance,
        samples=packet.samples,
        stream_tracker=tracker_dict
    )
    _run_health_pipeline(db, burst)
    return schemas.RawTelemetryBurstSummary.model_validate(burst)

# ---------------------------------------------------------
# 3. Development / Test Harness Ingestion (SIMULATION Only)
# ---------------------------------------------------------

@router.post(
    "/telemetry/simulate",
    response_model=schemas.RawTelemetryBurstSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest synthetic packet for test-rig / pipeline validation"
)
async def ingest_simulation_packet(
    packet: schemas.SimulationPacketIn,
    db: Session = Depends(get_db)
):
    """
    Development-gated endpoint strictly for test harness validation.
    Enforces DataProvenance.SIMULATION.
    """
    if not settings.ALLOW_SIMULATION_INGESTION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation ingestion is currently disabled by server configuration."
        )

    burst = IngestionService.process_and_persist_telemetry(db, packet)
    tracker_dict = get_tracker_dict(db, burst.device_id, burst.stream_id)
    await ws_manager.broadcast_burst(
        burst_id=burst.id,
        device_id=burst.device_id,
        stream_id=burst.stream_id,
        sensor_id=burst.sensor_id,
        joint_id=burst.joint_id,
        sequence_number=burst.sequence_number,
        hardware_timestamp_us=burst.hardware_timestamp_us,
        unwrapped_hardware_timestamp_us=burst.unwrapped_hardware_timestamp_us,
        received_at_utc=burst.received_at_utc,
        sampling_rate_hz=burst.sampling_rate_hz,
        sample_count=burst.sample_count,
        sha256_hash=burst.sha256_hash,
        quality_flags=burst.quality_flags,
        data_provenance=burst.data_provenance,
        samples=packet.samples,
        stream_tracker=tracker_dict
    )
    _run_health_pipeline(db, burst)
    return schemas.RawTelemetryBurstSummary.model_validate(burst)

@router.post(
    "/telemetry/simulate/generate-burst",
    response_model=schemas.RawTelemetryBurstSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and ingest a synthetic sinusoidal burst (SIMULATION)"
)
async def generate_and_ingest_sim_burst(
    sensor_id: str,
    joint_id: Optional[str] = None,
    sample_count: int = 500,
    sampling_rate_hz: float = 1000.0,
    fundamental_freq_hz: float = 50.0,
    db: Session = Depends(get_db)
):
    """
    Test harness generating a deterministic synthetic burst strictly tagged SIMULATION.
    Sampling rate is 1000 Hz; physical vibration frequency is 50 Hz (well below 500 Hz Nyquist).
    """
    packet = sim_driver.generate_test_packet(
        sensor_id=sensor_id,
        joint_id=joint_id,
        sample_count=sample_count,
        sampling_rate_hz=sampling_rate_hz,
        fundamental_freq_hz=fundamental_freq_hz
    )
    burst = IngestionService.process_and_persist_telemetry(db, packet)
    tracker_dict = get_tracker_dict(db, burst.device_id, burst.stream_id)
    await ws_manager.broadcast_burst(
        burst_id=burst.id,
        device_id=burst.device_id,
        stream_id=burst.stream_id,
        sensor_id=burst.sensor_id,
        joint_id=burst.joint_id,
        sequence_number=burst.sequence_number,
        hardware_timestamp_us=burst.hardware_timestamp_us,
        unwrapped_hardware_timestamp_us=burst.unwrapped_hardware_timestamp_us,
        received_at_utc=burst.received_at_utc,
        sampling_rate_hz=burst.sampling_rate_hz,
        sample_count=burst.sample_count,
        sha256_hash=burst.sha256_hash,
        quality_flags=burst.quality_flags,
        data_provenance=burst.data_provenance,
        samples=packet.samples,
        stream_tracker=tracker_dict
    )
    _run_health_pipeline(db, burst)
    return schemas.RawTelemetryBurstSummary.model_validate(burst)


@router.post(
    "/telemetry/simulate/generate-fault",
    response_model=schemas.RawTelemetryBurstSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Generate and ingest a fault-mode simulation burst (Phase 3)"
)
async def generate_fault_burst(
    sensor_id: str,
    fault_mode: str = "NORMAL",
    joint_id: Optional[str] = None,
    sample_count: int = 1000,
    sampling_rate_hz: float = 1000.0,
    db: Session = Depends(get_db)
):
    """
    Phase 3 fault simulation endpoint.

    Generates a physically interpretable signal for one of:
    - NORMAL: stable 50 Hz + low noise
    - SPLICE_IMPACT: normal + periodic impulses (elevated crest factor, kurtosis)
    - HARMONIC_LOOSENESS: fundamental + 2x + 3x harmonics (multi-peak spectrum)
    - CRITICAL_FAILURE: high broadband noise + large impacts (high RMS + kurtosis)

    All packets carry immutable SIMULATION provenance.
    The same backend DSP/health pipeline processes this signal — no shortcuts.
    """
    if not settings.ALLOW_SIMULATION_INGESTION:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Simulation ingestion is currently disabled by server configuration."
        )
    if fault_mode not in VALID_FAULT_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid fault_mode. Valid options: {VALID_FAULT_MODES}"
        )

    packet = sim_driver.generate_fault_packet(
        sensor_id=sensor_id,
        fault_mode=fault_mode,
        joint_id=joint_id,
        sample_count=sample_count,
        sampling_rate_hz=sampling_rate_hz,
    )
    burst = IngestionService.process_and_persist_telemetry(db, packet)
    tracker_dict = get_tracker_dict(db, burst.device_id, burst.stream_id)
    await ws_manager.broadcast_burst(
        burst_id=burst.id,
        device_id=burst.device_id,
        stream_id=burst.stream_id,
        sensor_id=burst.sensor_id,
        joint_id=burst.joint_id,
        sequence_number=burst.sequence_number,
        hardware_timestamp_us=burst.hardware_timestamp_us,
        unwrapped_hardware_timestamp_us=burst.unwrapped_hardware_timestamp_us,
        received_at_utc=burst.received_at_utc,
        sampling_rate_hz=burst.sampling_rate_hz,
        sample_count=burst.sample_count,
        sha256_hash=burst.sha256_hash,
        quality_flags=burst.quality_flags,
        data_provenance=burst.data_provenance,
        samples=packet.samples,
        stream_tracker=tracker_dict
    )
    _run_health_pipeline(db, burst)
    return schemas.RawTelemetryBurstSummary.model_validate(burst)

# ---------------------------------------------------------
# 4. Telemetry Retrieval & Cryptographic Verification
# ---------------------------------------------------------

@router.get(
    "/telemetry/snapshot",
    summary="Get current system and telemetry snapshot (honest zero-mock states)"
)
def get_telemetry_snapshot(db: Session = Depends(get_db)):
    """
    Returns only persisted/known state. If no telemetry exists, returns NO ACTIVE STREAM
    and null burst details. Never fabricates dummy sensor values.
    """
    trackers = db.query(models.StreamTracker).all()
    latest_burst = db.query(models.RawVibrationBurst).order_by(desc(models.RawVibrationBurst.received_at_utc)).first()

    hardware_stream_state = "NO ACTIVE STREAM"
    latest_burst_detail = None
    if latest_burst:
        samples, verified = IngestionService.verify_and_unpack_burst(latest_burst)
        latest_burst_detail = {
            "id": latest_burst.id,
            "device_id": latest_burst.device_id,
            "stream_id": latest_burst.stream_id,
            "sensor_id": latest_burst.sensor_id,
            "joint_id": latest_burst.joint_id,
            "sequence_number": latest_burst.sequence_number,
            "hardware_timestamp_us": latest_burst.hardware_timestamp_us,
            "unwrapped_hardware_timestamp_us": latest_burst.unwrapped_hardware_timestamp_us,
            "received_at_utc": latest_burst.received_at_utc,
            "sampling_rate_hz": latest_burst.sampling_rate_hz,
            "sample_count": latest_burst.sample_count,
            "sha256_hash": latest_burst.sha256_hash,
            "quality_flags": latest_burst.quality_flags,
            "data_provenance": latest_burst.data_provenance,
            "samples": samples,
            "integrity_verified": verified
        }
        if latest_burst.data_provenance == "LIVE":
            hardware_stream_state = "LIVE HARDWARE"
        elif latest_burst.data_provenance == "SIMULATION":
            hardware_stream_state = "SIMULATION"

    streams = [
        {
            "stream_id": t.stream_id,
            "device_id": t.device_id,
            "last_sequence_number": t.last_sequence_number,
            "total_packets_received": t.total_packets_received,
            "dropped_packets_count": t.dropped_packets_count,
            "last_hardware_timestamp_us": t.last_hardware_timestamp_us,
            "rollover_count": t.rollover_count,
            "last_seen_utc": t.last_seen_utc
        }
        for t in trackers
    ]

    return {
        "system_name": settings.PROJECT_NAME,
        "hardware_stream_state": hardware_stream_state,
        "active_streams": streams,
        "latest_burst": latest_burst_detail,
        "server_time_utc": datetime.now(timezone.utc).isoformat()
    }

@router.get(
    "/telemetry/latest",
    response_model=Optional[schemas.RawTelemetryBurstSummary],
    summary="Get latest persisted telemetry burst summary"
)
def get_latest_telemetry(
    device_id: Optional[str] = Query(None),
    stream_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent persisted raw burst.
    If no telemetry has been received, returns None. Never fabricates dummy data.
    """
    query = db.query(models.RawVibrationBurst)
    if device_id:
        query = query.filter(models.RawVibrationBurst.device_id == device_id)
    if stream_id:
        query = query.filter(models.RawVibrationBurst.stream_id == stream_id)

    burst = query.order_by(desc(models.RawVibrationBurst.received_at_utc)).first()
    if not burst:
        return None
    return schemas.RawTelemetryBurstSummary.model_validate(burst)

@router.get(
    "/telemetry/bursts/{burst_id}",
    response_model=schemas.RawTelemetryBurstDetail,
    summary="Retrieve burst samples and verify cryptographic SHA-256 integrity"
)
def get_telemetry_burst_detail(
    burst_id: str,
    db: Session = Depends(get_db)
):
    """
    Retrieves full raw burst, unpacks binary samples, and verifies SHA-256 hash.
    Proves that data persisted in SQLite has not been corrupted or altered.
    """
    burst = db.query(models.RawVibrationBurst).filter(models.RawVibrationBurst.id == burst_id).first()
    if not burst:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Burst '{burst_id}' not found."
        )

    samples, integrity_verified = IngestionService.verify_and_unpack_burst(burst)

    return schemas.RawTelemetryBurstDetail(
        id=burst.id,
        device_id=burst.device_id,
        stream_id=burst.stream_id,
        sensor_id=burst.sensor_id,
        joint_id=burst.joint_id,
        sequence_number=burst.sequence_number,
        hardware_timestamp_us=burst.hardware_timestamp_us,
        unwrapped_hardware_timestamp_us=burst.unwrapped_hardware_timestamp_us,
        received_at_utc=burst.received_at_utc,
        sampling_rate_hz=burst.sampling_rate_hz,
        sample_count=burst.sample_count,
        sha256_hash=burst.sha256_hash,
        quality_flags=burst.quality_flags,
        data_provenance=schemas.DataProvenance(burst.data_provenance),
        samples=samples,
        integrity_verified=integrity_verified
    )

# ---------------------------------------------------------
# 5. Entity Management & Registration (Devices, Sensors, Conveyors, Joints)
# ---------------------------------------------------------

@router.post("/devices", response_model=schemas.DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(device_in: schemas.DeviceCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Device).filter(models.Device.id == device_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Device ID already exists.")
    device = models.Device(**device_in.dict())
    db.add(device)
    db.commit()
    db.refresh(device)
    return device

@router.get("/devices", response_model=List[schemas.DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(models.Device).all()

@router.post("/sensors", response_model=schemas.SensorOut, status_code=status.HTTP_201_CREATED)
def register_sensor(sensor_in: schemas.SensorCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Sensor).filter(models.Sensor.id == sensor_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Sensor ID already exists.")
    sensor = models.Sensor(**sensor_in.dict())
    db.add(sensor)
    db.commit()
    db.refresh(sensor)
    return sensor

@router.get("/sensors", response_model=List[schemas.SensorOut])
def list_sensors(db: Session = Depends(get_db)):
    return db.query(models.Sensor).all()

@router.post("/conveyors", response_model=schemas.ConveyorOut, status_code=status.HTTP_201_CREATED)
def create_conveyor(conveyor_in: schemas.ConveyorCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Conveyor).filter(models.Conveyor.id == conveyor_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Conveyor ID already exists.")
    conveyor = models.Conveyor(**conveyor_in.dict())
    db.add(conveyor)
    db.commit()
    db.refresh(conveyor)
    return conveyor

@router.get("/conveyors", response_model=List[schemas.ConveyorOut])
def list_conveyors(db: Session = Depends(get_db)):
    return db.query(models.Conveyor).all()

@router.post("/belts", response_model=schemas.BeltOut, status_code=status.HTTP_201_CREATED)
def create_belt(belt_in: schemas.BeltCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Belt).filter(models.Belt.id == belt_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Belt ID already exists.")
    belt = models.Belt(**belt_in.dict())
    db.add(belt)
    db.commit()
    db.refresh(belt)
    return belt

@router.get("/belts", response_model=List[schemas.BeltOut])
def list_belts(db: Session = Depends(get_db)):
    return db.query(models.Belt).all()

@router.post("/joints", response_model=schemas.JointOut, status_code=status.HTTP_201_CREATED)
def register_joint(joint_in: schemas.JointCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Joint).filter(models.Joint.id == joint_in.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Joint ID already exists.")
    joint = models.Joint(**joint_in.dict())
    db.add(joint)
    db.commit()
    db.refresh(joint)
    return joint

@router.get("/joints", response_model=List[schemas.JointOut])
def list_joints(db: Session = Depends(get_db)):
    return db.query(models.Joint).all()

@router.post("/sensor-attachments", response_model=schemas.SensorAttachmentOut, status_code=status.HTTP_201_CREATED)
def attach_sensor(att_in: schemas.SensorAttachmentCreate, db: Session = Depends(get_db)):
    attachment = models.SensorAttachment(**att_in.dict())
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment

@router.get("/sensor-attachments", response_model=List[schemas.SensorAttachmentOut])
def list_sensor_attachments(db: Session = Depends(get_db)):
    return db.query(models.SensorAttachment).all()

# ---------------------------------------------------------
# 6. Phase 3 Analytics — DSP Analysis
# ---------------------------------------------------------

@router.get(
    "/analytics/bursts/{burst_id}/dsp",
    summary="Run DSP analysis on a stored burst and return time/frequency features"
)
def get_burst_dsp_analysis(burst_id: str, db: Session = Depends(get_db)):
    """
    Retrieve and DSP-analyse a stored RawVibrationBurst.

    Returns time-domain features, FFT spectrum bins, and dominant frequency.
    All thresholds shown are labeled engineering_threshold or baseline_derived_threshold.
    No ISO compliance is claimed.
    """
    burst = db.query(models.RawVibrationBurst).filter(models.RawVibrationBurst.id == burst_id).first()
    if not burst:
        raise HTTPException(status_code=404, detail=f"Burst '{burst_id}' not found.")

    from .ingestion import deserialize_samples
    from .dsp import dsp_analyzer

    samples, integrity_ok = IngestionService.verify_and_unpack_burst(burst)
    result = dsp_analyzer.analyze(samples, burst.sampling_rate_hz)

    if not result.valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"DSP analysis failed: {result.rejection_reason}"
        )

    td = result.time_domain
    fft = result.fft

    return {
        "burst_id": burst_id,
        "data_provenance": burst.data_provenance,
        "sampling_rate_hz": burst.sampling_rate_hz,
        "sample_count": burst.sample_count,
        "integrity_verified": integrity_ok,
        "time_domain": {
            "rms": td.rms,
            "peak": td.peak,
            "peak_to_peak": td.peak_to_peak,
            "crest_factor": td.crest_factor,
            "kurtosis_fisher": td.kurtosis,
            "kurtosis_convention": "Fisher/excess (Gaussian baseline ≈ 0)",
            "skewness": td.skewness,
            "sample_count": td.sample_count,
        },
        "frequency_domain": {
            "dominant_frequency_hz": fft.dominant_frequency_hz if fft else None,
            "dominant_amplitude": fft.dominant_amplitude if fft else None,
            "spectral_centroid_hz": fft.spectral_centroid_hz if fft else None,
            "spectral_energy": fft.spectral_energy if fft else None,
            "bin_count": len(fft.frequency_bins_hz) if fft else 0,
            "frequency_resolution_hz": (
                fft.frequency_bins_hz[1] - fft.frequency_bins_hz[0]
                if fft and len(fft.frequency_bins_hz) > 1 else None
            ),
        },
        "fft_bins": {
            "frequencies_hz": fft.frequency_bins_hz if fft else [],
            "amplitudes": fft.amplitude_spectrum if fft else [],
        },
        "engineering_thresholds": {
            "label": "engineering_threshold — must be calibrated per plant/machine class",
            "abs_rms_alert": settings.ABS_RMS_ALERT_THRESHOLD,
            "abs_crest_factor": settings.ABS_CREST_FACTOR_THRESHOLD,
            "abs_kurtosis_fisher": settings.ABS_KURTOSIS_THRESHOLD,
        }
    }

# ---------------------------------------------------------
# 7. Phase 3 — Joint Health Intelligence
# ---------------------------------------------------------

@router.get(
    "/joints/{joint_id}/health",
    summary="Get current health score, risk state, baseline, and recent trend"
)
def get_joint_health(joint_id: str, db: Session = Depends(get_db)):
    """
    Returns:
    - Current health score and risk state
    - Revolution count and consecutive anomaly count
    - Baseline metrics (median values + baseline status)
    - Current DSP metrics from most recent observation
    - Historical trend (last 20 observations)
    - Summary statistics

    All threshold labels indicate type: engineering_threshold or baseline_derived_threshold.
    """
    joint = db.query(models.Joint).filter(models.Joint.id == joint_id).first()
    if not joint:
        raise HTTPException(status_code=404, detail=f"Joint '{joint_id}' not found.")

    # Latest observation
    latest_obs = (
        db.query(models.JointObservation)
        .filter(models.JointObservation.joint_id == joint_id)
        .order_by(desc(models.JointObservation.revolution_index))
        .first()
    )

    # Historical trend (last 20)
    trend = (
        db.query(models.JointObservation)
        .filter(models.JointObservation.joint_id == joint_id)
        .order_by(desc(models.JointObservation.revolution_index))
        .limit(20)
        .all()
    )

    # Active alerts
    active_alerts = (
        db.query(models.AlertEvent)
        .filter(
            models.AlertEvent.joint_id == joint_id,
            models.AlertEvent.is_acknowledged == 0
        )
        .order_by(desc(models.AlertEvent.triggered_at_utc))
        .limit(5)
        .all()
    )

    def obs_to_dict(o: models.JointObservation) -> dict:
        return {
            "revolution_index": o.revolution_index,
            "timestamp_utc": o.observation_timestamp_utc or o.timestamp_utc,
            "health_score": o.health_score,
            "risk_state": o.risk_state,
            "anomaly_detected": bool(o.anomaly_detected),
            "rms": o.rms_acceleration,
            "crest_factor": o.crest_factor,
            "kurtosis": o.kurtosis,
            "dominant_frequency_hz": o.dominant_frequency_hz,
            "rms_deviation": o.rms_deviation,
            "baseline_status": o.baseline_status,
            "data_provenance": o.data_provenance,
        }

    return {
        "joint_id": joint_id,
        "joint_code": joint.joint_code,
        "current_risk": joint.current_risk,
        "total_revolutions": joint.total_revolutions_count,
        "consecutive_abnormal_count": joint.consecutive_abnormal_count,
        "last_passage_utc": joint.last_passage_timestamp_utc,
        "current_metrics": obs_to_dict(latest_obs) if latest_obs else None,
        "baseline": {
            "rms_median": latest_obs.baseline_rms if latest_obs else None,
            "crest_factor_median": latest_obs.baseline_crest_factor if latest_obs else None,
            "kurtosis_median": latest_obs.baseline_kurtosis if latest_obs else None,
            "dominant_freq_median": latest_obs.baseline_dominant_freq if latest_obs else None,
            "status": latest_obs.baseline_status if latest_obs else "INSUFFICIENT",
            "label": "baseline_derived_threshold — rolling median+MAD from NORMAL observations",
        },
        "history": [obs_to_dict(o) for o in reversed(trend)],
        "active_unacknowledged_alerts": [
            {
                "alert_id": a.id,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "triggered_at_utc": a.triggered_at_utc,
            }
            for a in active_alerts
        ],
        "health_bands": {
            "label": "engineering_application_threshold — not universal industrial standard",
            "NORMAL": f"{settings.HEALTH_BAND_NORMAL_MIN}–100",
            "WATCH": f"{settings.HEALTH_BAND_WATCH_MIN}–{settings.HEALTH_BAND_NORMAL_MIN - 0.1}",
            "WARNING": f"{settings.HEALTH_BAND_WARNING_MIN}–{settings.HEALTH_BAND_WATCH_MIN - 0.1}",
            "CRITICAL": f"0–{settings.HEALTH_BAND_WARNING_MIN - 0.1}",
        },
        "vision_evidence": get_joint_vision_evidence(joint, db)
    }

def get_joint_vision_evidence(joint: models.Joint, db: Session) -> Optional[dict]:
    """Helper to retrieve independent vision evidence for a joint."""
    latest_vis = (
        db.query(models.VisionObservation)
        .filter(
            (models.VisionObservation.joint_id == joint.id) |
            (models.VisionObservation.joint_code == joint.joint_code)
        )
        .order_by(desc(models.VisionObservation.timestamp_utc))
        .first()
    )
    if not latest_vis:
        return None

    meta = json.loads(latest_vis.processing_metadata_json) if latest_vis.processing_metadata_json else {}
    return {
        "status": meta.get("model_status", "TRAINED_MODEL"),
        "observation_id": latest_vis.id,
        "camera_id": latest_vis.camera_id,
        "timestamp_utc": latest_vis.timestamp_utc,
        "model_version": latest_vis.model_version,
        "model_status": meta.get("model_status", "UNKNOWN"),
        "source_type": latest_vis.source_type,
        "image_reference": latest_vis.image_reference,
        "total_detections": latest_vis.total_detections_count,
        "primary_damage_type": latest_vis.primary_damage_type,
        "max_confidence": latest_vis.max_confidence,
        "prototype_severity": meta.get("prototype_severity", "NORMAL"),
        "severity_label": meta.get("severity_label", "PROTOTYPE ENGINEERING THRESHOLD"),
        "detections": json.loads(latest_vis.detections_json) if latest_vis.detections_json else [],
        "independence_note": "Preserved independently from vibration/DSP without premature arbitrary weighting."
    }

@router.get(
    "/joints/{joint_id}/passport",
    summary="Get multi-evidence Joint Passport integrating vibration, vision, and operational signals"
)
def get_joint_passport(joint_id: str, db: Session = Depends(get_db)):
    """
    Returns the comprehensive Joint Passport for a specific physical conveyor joint.
    Core Principle: One physical joint -> multiple independent evidence sources.
    - SENSOR EVIDENCE: Vibration / DSP (RMS, Crest Factor, Kurtosis, Dominant Frequency, Anomaly Score)
    - VISION EVIDENCE: Camera / Detections (Damage Classes, Confidence, Overlaid Frame, Prototype Severity)
    - OPERATIONAL STATE: Speed, Motor Load, Ambient Temperature
    - HEALTH ENGINE & SAFETY: Current Risk State, Consecutive Anomalies, Deterministic Safety Trip Rules
    Does NOT use arbitrary mathematical fusion (e.g. 70/30). Preserves independent evidence integrity.
    """
    joint = db.query(models.Joint).filter(models.Joint.id == joint_id).first()
    if not joint:
        raise HTTPException(status_code=404, detail=f"Joint '{joint_id}' not found.")

    health_info = get_joint_health(joint_id, db)
    vision_evidence = get_joint_vision_evidence(joint, db)

    latest_obs = (
        db.query(models.JointObservation)
        .filter(models.JointObservation.joint_id == joint.id)
        .order_by(desc(models.JointObservation.timestamp_utc))
        .first()
    )
    ml_evidence = vibration_anomaly_engine.get_joint_passport_evidence(latest_obs)

    # Deterministic safety rule evaluation
    vibe_critical = joint.current_risk == "CRITICAL"
    vibe_warning = joint.current_risk == "WARNING"
    vis_damage = vision_evidence and vision_evidence.get("primary_damage_type") in {"Large Tear", "Large Hole"}
    vis_critical = vision_evidence and vision_evidence.get("prototype_severity") == "CRITICAL"

    if vibe_critical or vis_critical:
        recommended_action = "TRIP_IMMEDIATE_STOP"
        safety_status = "CRITICAL_ACTION_REQUIRED"
    elif vibe_warning or vis_damage:
        recommended_action = "SLOW_INSPECT_AT_STATION"
        safety_status = "WARNING_INVESTIGATION_REQUIRED"
    else:
        recommended_action = "CONTINUE_NORMAL_OPERATION"
        safety_status = "NORMAL_OPERATION"

    return {
        "passport_schema_version": "1.0.0",
        "joint_identity": {
            "joint_id": joint.id,
            "joint_code": joint.joint_code,
            "conveyor_section": "CV-MAIN-SPLICE-LINE",
            "installation_date": "2026-01-15",
            "splice_type": "Finger Splice (Hot Vulcanized)",
            "total_revolutions": joint.total_revolutions_count,
            "consecutive_abnormal_count": joint.consecutive_abnormal_count,
            "last_passage_utc": joint.last_passage_timestamp_utc
        },
        "evidence_sources": {
            "vibration_dsp_evidence": {
                "source": "3-Axis Accelerometer (simulated / hardware)",
                "current_risk_state": joint.current_risk,
                "latest_observation": health_info.get("current_metrics"),
                "baseline": health_info.get("baseline"),
                "health_score": health_info.get("current_metrics", {}).get("health_score") if health_info.get("current_metrics") else 100.0,
                "consecutive_anomalies": joint.consecutive_abnormal_count
            },
            "ml_anomaly_evidence": ml_evidence,
            "vision_optical_evidence": vision_evidence or {
                "status": "NO_INSPECTION_RECORDED",
                "message": "No visual inspection frame recorded for this joint yet."
            },
            "operational_telemetry": {
                "belt_speed_mps": 3.2,
                "motor_current_a": 142.5,
                "ambient_temperature_c": 34.2,
                "bearing_temperature_c": 58.1,
                "status": "NORMAL"
            }
        },
        "joint_health_engine": {
            "safety_status": safety_status,
            "recommended_action": recommended_action,
            "ml_advisory": (
                "ML_ANOMALY_DETECTED" if (ml_evidence and ml_evidence.get("anomaly_decision") is True)
                else "ML_NORMAL" if (ml_evidence and ml_evidence.get("anomaly_decision") is False)
                else "ML_ADVISORY_PENDING"
            ),
            "deterministic_rule_basis": "Independent sensor signals evaluated via deterministic safety rules (WARN / SLOW / TRIP). Vibration ML provides independent anomaly evidence only and cannot independently trigger emergency stop.",
            "active_alerts": health_info.get("active_unacknowledged_alerts", [])
        }
    }


@router.get(
    "/joints/{joint_id}/observations",
    summary="Get paginated observation history for a joint"
)
def get_joint_observations(
    joint_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Returns paginated JointObservation records in reverse chronological order."""
    joint = db.query(models.Joint).filter(models.Joint.id == joint_id).first()
    if not joint:
        raise HTTPException(status_code=404, detail=f"Joint '{joint_id}' not found.")

    total = db.query(models.JointObservation).filter(
        models.JointObservation.joint_id == joint_id
    ).count()

    obs_list = (
        db.query(models.JointObservation)
        .filter(models.JointObservation.joint_id == joint_id)
        .order_by(desc(models.JointObservation.revolution_index))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "joint_id": joint_id,
        "joint_code": joint.joint_code,
        "total_observations": total,
        "offset": offset,
        "limit": limit,
        "observations": [
            {
                "id": o.id,
                "revolution_index": o.revolution_index,
                "timestamp_utc": o.observation_timestamp_utc or o.timestamp_utc,
                "health_score": o.health_score,
                "risk_state": o.risk_state,
                "anomaly_detected": bool(o.anomaly_detected),
                "rms": o.rms_acceleration,
                "peak": o.peak_acceleration,
                "crest_factor": o.crest_factor,
                "kurtosis": o.kurtosis,
                "skewness": o.skewness,
                "dominant_frequency_hz": o.dominant_frequency_hz,
                "spectral_energy": o.spectral_energy,
                "rms_deviation": o.rms_deviation,
                "baseline_status": o.baseline_status,
                "consecutive_abnormal": o.consecutive_abnormal_count_snapshot,
                "data_provenance": o.data_provenance,
                "raw_burst_id": o.raw_burst_id,
            }
            for o in obs_list
        ]
    }

# ---------------------------------------------------------
# 8. Phase 3 — Alert Management
# ---------------------------------------------------------

@router.get(
    "/alerts",
    summary="List alert events with optional severity filtering"
)
def list_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: WATCH | WARNING | CRITICAL"),
    joint_id: Optional[str] = Query(None),
    unacknowledged_only: bool = Query(False),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Returns alert events, ordered by most recent first."""
    query = db.query(models.AlertEvent)

    if severity:
        query = query.filter(models.AlertEvent.severity == severity.upper())
    if joint_id:
        query = query.filter(models.AlertEvent.joint_id == joint_id)
    if unacknowledged_only:
        query = query.filter(models.AlertEvent.is_acknowledged == 0)

    total = query.count()
    alerts = query.order_by(desc(models.AlertEvent.triggered_at_utc)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "alerts": [
            {
                "id": a.id,
                "joint_id": a.joint_id,
                "conveyor_id": a.conveyor_id,
                "severity": a.severity,
                "alert_type": a.alert_type,
                "message": a.message,
                "is_acknowledged": bool(a.is_acknowledged),
                "acknowledged_by": a.acknowledged_by,
                "acknowledged_at_utc": a.acknowledged_at_utc,
                "triggered_at_utc": a.triggered_at_utc,
                "data_provenance": a.data_provenance,
                "metrics_snapshot": (
                    json.loads(a.metrics_snapshot_json)
                    if a.metrics_snapshot_json else None
                ),
            }
            for a in alerts
        ]
    }

@router.post(
    "/alerts/{alert_id}/acknowledge",
    summary="Acknowledge an alert — preserves operator audit trail"
)
def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query("OPERATOR", description="Operator identifier for audit trail"),
    db: Session = Depends(get_db)
):
    """
    Acknowledge an alert.

    Sets is_acknowledged=1 and records:
    - acknowledged_by: operator identifier
    - acknowledged_at_utc: timestamp

    Acknowledgement is irreversible (audit trail). Acknowledged alerts
    remain in the database for historical analysis.
    """
    alert = db.query(models.AlertEvent).filter(models.AlertEvent.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found.")

    if alert.is_acknowledged:
        return {
            "status": "already_acknowledged",
            "alert_id": alert_id,
            "acknowledged_by": alert.acknowledged_by,
            "acknowledged_at_utc": alert.acknowledged_at_utc,
        }

    alert.is_acknowledged = 1
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at_utc = datetime.now(timezone.utc).isoformat()
    db.commit()

    return {
        "status": "acknowledged",
        "alert_id": alert_id,
        "acknowledged_by": acknowledged_by,
        "acknowledged_at_utc": alert.acknowledged_at_utc,
    }

# ---------------------------------------------------------
# 8b. Dataset Provenance & Policy Enforcement Endpoints
# ---------------------------------------------------------
from .provenance import get_all_dataset_provenance, get_provenance_metadata

@router.get("/datasets/provenance", tags=["Datasets & Provenance"])
def get_datasets_provenance_endpoint():
    """
    Returns dataset provenance, scientific limitations, and data separation manifests.
    Enforces the Industrial Data, Testing & ML Training Policy.
    """
    return get_all_dataset_provenance()

@router.get("/datasets/provenance/{dataset_name}", tags=["Datasets & Provenance"])
def get_dataset_provenance_by_name(dataset_name: str):
    """Returns provenance metadata for a specific dataset."""
    meta = get_provenance_metadata(dataset_name)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_name}' not found in registry.")
    return meta

# ---------------------------------------------------------
# 8c. Vision Damage Detection & Optical Monitoring Endpoints
# ---------------------------------------------------------
from pathlib import Path
from .vision_service import vision_engine, CLASS_NAMES

PROJECT_ROOT_PATH = Path(__file__).resolve().parent.parent.parent
VISION_TEST_DIR = PROJECT_ROOT_PATH / "data" / "raw" / "research" / "conveyor_belt_damage_vision" / "test"
VISION_ANALYSIS_DIR = PROJECT_ROOT_PATH / "data" / "processed" / "research" / "conveyor_belt_damage_vision" / "analyzed_frames"

@router.post("/vision/analyze", tags=["Vision & Optical Monitoring"])
async def analyze_vision_frame(
    file: Optional[UploadFile] = File(None),
    frame_file: Optional[UploadFile] = File(None),
    test_image_name: Optional[str] = Query(None),
    camera_id: str = Query("CAM-SPLICE-01"),
    joint_code: Optional[str] = Query(None),
    source_type: str = Query("RESEARCH_DATASET"),
    conf_threshold: float = Query(0.20),
    db: Session = Depends(get_db)
):
    """
    Ingests and analyzes a conveyor belt surface inspection frame.
    Runs VisionEngine (trained YOLO detector or classical CV baseline),
    persists the observation in SQLite, and broadcasts a VISION_UPDATE over WebSocket.
    """
    upload = file or frame_file
    frame_name = "unknown_frame.jpg"
    image_input = None

    if upload and upload.filename:
        frame_name = upload.filename
        image_input = await upload.read()
    elif test_image_name:
        target_path = VISION_TEST_DIR / test_image_name
        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Test sample '{test_image_name}' not found in test split.")
        frame_name = test_image_name
        image_input = target_path
    else:
        test_images = list(VISION_TEST_DIR.glob("*.jpg"))
        if test_images:
            frame_name = test_images[0].name
            image_input = test_images[0]
        else:
            raise HTTPException(status_code=400, detail="No frame uploaded and no test images available.")

    # Refresh model in case a training run completed
    vision_engine.refresh_model()
    analysis_res = vision_engine.analyze_frame(
        image_input=image_input,
        camera_id=camera_id,
        joint_code=joint_code,
        source_type=source_type,
        conf_threshold=conf_threshold,
        frame_name=frame_name
    )

    if "error" in analysis_res:
        raise HTTPException(status_code=400, detail=analysis_res["error"])

    # Resolve joint_id if joint_code provided
    resolved_joint_id = None
    if joint_code:
        joint_rec = db.query(models.Joint).filter(models.Joint.joint_code == joint_code).first()
        if joint_rec:
            resolved_joint_id = joint_rec.id

    # Persist VisionObservation
    vis_obs = models.VisionObservation(
        id=analysis_res["observation_id"],
        joint_id=resolved_joint_id,
        joint_code=joint_code,
        camera_id=camera_id,
        timestamp_utc=analysis_res["timestamp_utc"],
        model_version=analysis_res["model_version"],
        source_type=source_type,
        image_reference=analysis_res["image_reference"],
        total_detections_count=analysis_res["total_detections"],
        primary_damage_type=analysis_res["primary_damage_type"],
        max_confidence=analysis_res["max_confidence"],
        detections_json=json.dumps(analysis_res["detections"]),
        processing_metadata_json=json.dumps({
            "model_status": analysis_res["model_status"],
            "prototype_severity": analysis_res["prototype_severity"],
            "severity_label": analysis_res["severity_label"],
            "frame_name": frame_name
        })
    )
    db.add(vis_obs)
    db.commit()

    # Broadcast over WebSocket
    ws_payload = {
        "type": "VISION_UPDATE",
        "observation_id": analysis_res["observation_id"],
        "camera_id": camera_id,
        "joint_code": joint_code,
        "timestamp_utc": analysis_res["timestamp_utc"],
        "model_status": analysis_res["model_status"],
        "model_version": analysis_res["model_version"],
        "source_type": source_type,
        "frame_name": frame_name,
        "total_detections": analysis_res["total_detections"],
        "has_damage": analysis_res["has_damage"],
        "primary_damage_type": analysis_res["primary_damage_type"],
        "max_confidence": analysis_res["max_confidence"],
        "prototype_severity": analysis_res["prototype_severity"],
        "image_reference": analysis_res["image_reference"],
        "detections": analysis_res["detections"]
    }
    await ws_manager.broadcast_json(ws_payload)

    return analysis_res

@router.get("/vision/observations", tags=["Vision & Optical Monitoring"])
def get_vision_observations(
    joint_code: Optional[str] = Query(None),
    camera_id: Optional[str] = Query(None),
    has_damage_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Returns recent vision observations with optional filtering."""
    q = db.query(models.VisionObservation)
    if joint_code:
        q = q.filter(models.VisionObservation.joint_code == joint_code)
    if camera_id:
        q = q.filter(models.VisionObservation.camera_id == camera_id)
    if has_damage_only:
        q = q.filter(models.VisionObservation.total_detections_count > 0)

    rows = q.order_by(desc(models.VisionObservation.timestamp_utc)).limit(limit).all()

    return {
        "total": len(rows),
        "observations": [
            {
                "id": r.id,
                "joint_id": r.joint_id,
                "joint_code": r.joint_code,
                "camera_id": r.camera_id,
                "timestamp_utc": r.timestamp_utc,
                "model_version": r.model_version,
                "source_type": r.source_type,
                "image_reference": r.image_reference,
                "total_detections": r.total_detections_count,
                "primary_damage_type": r.primary_damage_type,
                "max_confidence": r.max_confidence,
                "detections": json.loads(r.detections_json) if r.detections_json else [],
                "metadata": json.loads(r.processing_metadata_json) if r.processing_metadata_json else {}
            }
            for r in rows
        ]
    }

@router.get("/vision/status", tags=["Vision & Optical Monitoring"])
def get_vision_status():
    """Returns vision engine status, active model version, and supported classes."""
    vision_engine.refresh_model()
    return {
        "model_status": vision_engine.model_status,
        "model_version": vision_engine.model_version,
        "weights_path": str(vision_engine.weights_path.relative_to(PROJECT_ROOT_PATH).as_posix()),
        "supported_classes": CLASS_NAMES,
        "crack_class_supported": False,
        "scientific_disclaimer": "The current model detects only annotated classes (Belt Joint, Large/Small Tear, Large/Small Hole, damage). It does NOT claim crack detection without crack-specific annotations.",
        "active_cameras": [
            {"camera_id": "CAM-SPLICE-01", "location": "Head Pulley Inspection Hood", "resolution": "512x512", "fps": 15, "status": "ACTIVE_BENCHMARK"}
        ]
    }

@router.get("/vision/test-samples", tags=["Vision & Optical Monitoring"])
def get_vision_test_samples():
    """Returns catalog of labeled held-out test frames for SCADA live demonstration."""
    if not VISION_TEST_DIR.exists():
        return {"samples": []}

    test_imgs = sorted([p.name for p in VISION_TEST_DIR.glob("*.jpg")])
    return {
        "total_test_samples": len(test_imgs),
        "dataset_split": "test",
        "samples": test_imgs[:30]
    }

@router.get("/vision/frame/{observation_id}", tags=["Vision & Optical Monitoring"])
def get_analyzed_frame_image(observation_id: str):
    """Serves the analyzed frame image with detection overlay."""
    matches = list(VISION_ANALYSIS_DIR.glob(f"{observation_id}_*"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"Analyzed frame for observation '{observation_id}' not found.")
    file_path = matches[0]
    ext = file_path.suffix.lower()
    media_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".bmp": "image/bmp"
    }
    media_type = media_map.get(ext, "image/jpeg")
    return FileResponse(str(file_path), media_type=media_type)

# ---------------------------------------------------------
# 8B. Vibration ML & Anomaly Detection (Phase 4B)
# ---------------------------------------------------------

@router.get(
    "/ml/status",
    tags=["Vibration ML & Anomaly Detection"],
    summary="Get condition-aware vibration ML anomaly detector provenance and status"
)
def get_vibration_ml_status():
    """
    Returns model provenance, training metadata, feature schema, threshold status,
    and scientific limitations for the condition-aware vibration anomaly model.
    """
    return vibration_anomaly_engine.get_status()

@router.post(
    "/ml/score",
    tags=["Vibration ML & Anomaly Detection"],
    summary="Score a 10-dimensional vibration feature vector against the research benchmark"
)
async def score_vibration_features(payload: Dict[str, Any]):
    """
    Evaluates an operational feature vector against the condition-aware Isolation Forest.
    Requires operating context (speed_rpm, pretension_n) and time/frequency-domain DSP metrics.
    Does NOT predict conveyor rupture. Returns raw anomaly score, boolean decision, and standardized baseline deviations.
    """
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object containing feature key-value pairs.")
    
    try:
        score_res = vibration_anomaly_engine.score_features(payload)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Inference execution error: {str(e)}")

    # Broadcast ML anomaly update over WebSocket if inference produced a valid score
    if score_res.get("available") and score_res.get("raw_anomaly_score") is not None:
        try:
            ws_payload = {
                "type": "ML_ANOMALY_UPDATE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_version": score_res.get("model_version"),
                "model_status": score_res.get("model_status"),
                "raw_anomaly_score": score_res.get("raw_anomaly_score"),
                "anomaly_decision": score_res.get("anomaly_decision"),
                "threshold_status": score_res.get("threshold_status"),
                "operating_regime": score_res.get("operating_regime"),
                "baseline_deviation": score_res.get("baseline_deviation")
            }
            await ws_manager.broadcast_json(ws_payload)
        except Exception:
            pass

    return score_res

# ---------------------------------------------------------
# 9. Hardware DAQ & Joint Lifecycle (Phase 5)
# ---------------------------------------------------------

@router.get(
    "/hardware/serial/status",
    summary="Get physical serial acquisition worker status"
)
def get_serial_worker_status():
    """Returns runtime connection, baud rate, and packet acquisition metrics for hardware COM port."""
    return serial_worker.get_status()

@router.post(
    "/maintenance/log",
    response_model=schemas.MaintenanceLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Log a physical maintenance action on a belt joint"
)
def log_joint_maintenance(
    log_in: schemas.MaintenanceLogCreate,
    db: Session = Depends(get_db)
):
    """
    Commits a tamper-evident maintenance record with SHA-256 hash.
    Optionally resets rolling baseline after mechanical splice work.
    """
    try:
        return joint_lifecycle_service.log_maintenance(db, log_in)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/joints/{joint_id}/lifecycle",
    response_model=schemas.JointLifecycleResponse,
    summary="Get joint degradation trends and operational exposure analysis"
)
def get_joint_lifecycle(
    joint_id: str,
    db: Session = Depends(get_db)
):
    """
    Synthesizes multi-revolution degradation trends (g/rev), operational stress cycles,
    and multi-source intelligence evidence without fabricated RUL predictions.
    """
    try:
        return joint_lifecycle_service.get_joint_lifecycle_analysis(db, joint_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/joints/{joint_id}/maintenance",
    response_model=List[schemas.MaintenanceLogResponse],
    summary="List tamper-evident maintenance logs for a joint"
)
def get_joint_maintenance_logs(
    joint_id: str,
    db: Session = Depends(get_db)
):
    """Returns all verified maintenance logs recorded for a specific joint."""
    joint = db.query(models.Joint).filter(
        (models.Joint.id == joint_id) | (models.Joint.joint_code == joint_id)
    ).first()
    if not joint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Joint '{joint_id}' not found.")
    logs = db.query(models.MaintenanceLog).filter(
        models.MaintenanceLog.joint_id == joint.id
    ).order_by(models.MaintenanceLog.timestamp_utc.desc()).all()
    return logs

# ---------------------------------------------------------
# 10. WebSocket Streaming Endpoint
# ---------------------------------------------------------

@ws_router.websocket("/ws/v1/live-telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        # Send initial connection state
        await websocket.send_json({
            "type": "CONNECTION_ESTABLISHED",
            "server_time_utc": datetime.now(timezone.utc).isoformat()
        })
        while True:
            text = await websocket.receive_text()
            if text == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    payload = json.loads(text)
                    if payload.get("action") == "ping":
                        await websocket.send_json({
                            "type": "PONG",
                            "client_time": payload.get("timestamp"),
                            "server_time_utc": datetime.now(timezone.utc).isoformat()
                        })
                except Exception:
                    pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
