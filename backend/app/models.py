from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey,
    LargeBinary, Index, CheckConstraint, Text
)
from sqlalchemy.orm import relationship
from .database import Base

def utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO 8601 string format."""
    return datetime.now(timezone.utc).isoformat()

class Device(Base):
    __tablename__ = "devices"

    id = Column(String, primary_key=True, index=True)  # e.g., "esp32-node-01"
    name = Column(String, nullable=False)
    device_type = Column(String, nullable=False)  # ESP32 | RASPBERRY_PI | INDUSTRIAL_GATEWAY | TEST_RIG_EMULATOR
    serial_number = Column(String, unique=True, nullable=True)
    is_trusted_hardware = Column(Integer, default=1, nullable=False)  # 1 = True, 0 = False
    status = Column(String, default="ACTIVE", nullable=False)  # ACTIVE | QUARANTINED | DECOMMISSIONED
    registered_at_utc = Column(String, default=utc_now_iso, nullable=False)

class Conveyor(Base):
    __tablename__ = "conveyors"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    length_meters = Column(Float, nullable=False)
    nominal_speed_mps = Column(Float, nullable=False)
    created_at_utc = Column(String, default=utc_now_iso, nullable=False)

    belts = relationship("Belt", back_populates="conveyor", cascade="all, delete-orphan")
    attachments = relationship("SensorAttachment", back_populates="conveyor")

class Belt(Base):
    __tablename__ = "belts"

    id = Column(String, primary_key=True, index=True)
    conveyor_id = Column(String, ForeignKey("conveyors.id", ondelete="CASCADE"), nullable=False)
    belt_identifier = Column(String, nullable=False)
    splice_standard = Column(String, nullable=False)
    installation_date = Column(String, nullable=False)
    status = Column(String, default="ACTIVE", nullable=False)

    conveyor = relationship("Conveyor", back_populates="belts")
    joints = relationship("Joint", back_populates="belt", cascade="all, delete-orphan")

class Joint(Base):
    __tablename__ = "joints"

    id = Column(String, primary_key=True, index=True)
    joint_code = Column(String, unique=True, nullable=False, index=True)  # e.g., J-01, J-02
    belt_id = Column(String, ForeignKey("belts.id", ondelete="CASCADE"), nullable=False)
    physical_position_meters = Column(Float, nullable=False)
    identifier_type = Column(String, nullable=False)  # RFID | MAGNETIC | OPTICAL
    identifier_token = Column(String, nullable=False, index=True)  # UID or code
    splice_type = Column(String, nullable=False)
    installation_date = Column(String, nullable=False)
    current_risk = Column(String, default="NORMAL", nullable=False)
    last_passage_timestamp_utc = Column(String, nullable=True)
    consecutive_abnormal_count = Column(Integer, default=0, nullable=False)
    total_revolutions_count = Column(Integer, default=0, nullable=False)

    belt = relationship("Belt", back_populates="joints")
    vibration_bursts = relationship("RawVibrationBurst", back_populates="joint")
    observations = relationship("JointObservation", back_populates="joint")
    attachments = relationship("SensorAttachment", back_populates="joint")
    alerts = relationship("AlertEvent", back_populates="joint")
    vision_observations = relationship("VisionObservation", back_populates="joint")
    maintenance_logs = relationship("MaintenanceLog", back_populates="joint")

class Sensor(Base):
    __tablename__ = "sensors"

    id = Column(String, primary_key=True, index=True)  # e.g., "SENS-ACCEL-01"
    sensor_type = Column(String, nullable=False)  # ACCELEROMETER | PYROMETER | ENCODER | CURRENT_TRANSFORMER | RFID_READER
    model_number = Column(String, nullable=True)
    serial_number = Column(String, nullable=True)
    sampling_rate_hz = Column(Float, nullable=True)
    output_protocol = Column(String, nullable=False)  # ANALOG | SPI | I2C | UART_SERIAL | MODBUS
    calibration_data_json = Column(String, nullable=True)
    status = Column(String, default="ACTIVE", nullable=False)

    attachments = relationship("SensorAttachment", back_populates="sensor")
    vibration_bursts = relationship("RawVibrationBurst", back_populates="sensor")

class SensorAttachment(Base):
    __tablename__ = "sensor_attachments"

    id = Column(String, primary_key=True, index=True)
    sensor_id = Column(String, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False)
    conveyor_id = Column(String, ForeignKey("conveyors.id", ondelete="CASCADE"), nullable=False)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="SET NULL"), nullable=True)
    physical_location = Column(String, nullable=False)  # e.g., "IDLER_TRANSITION_ZONE"
    trigger_offset_meters = Column(Float, default=0.50, nullable=False)
    trigger_delay_ms = Column(Float, default=200.0, nullable=False)
    mounted_at_utc = Column(String, default=utc_now_iso, nullable=False)
    status = Column(String, default="ACTIVE", nullable=False)

    sensor = relationship("Sensor", back_populates="attachments")
    conveyor = relationship("Conveyor", back_populates="attachments")
    joint = relationship("Joint", back_populates="attachments")

class RawVibrationBurst(Base):
    __tablename__ = "raw_vibration_bursts"

    id = Column(String, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.id", ondelete="RESTRICT"), nullable=False, index=True)
    stream_id = Column(String, nullable=False, index=True)
    sensor_id = Column(String, ForeignKey("sensors.id", ondelete="RESTRICT"), nullable=False)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="SET NULL"), nullable=True)

    sequence_number = Column(Integer, nullable=False)
    hardware_timestamp_us = Column(Integer, nullable=False)
    unwrapped_hardware_timestamp_us = Column(Integer, nullable=False)
    received_at_utc = Column(String, default=utc_now_iso, nullable=False, index=True)

    sampling_rate_hz = Column(Float, nullable=False)
    sample_count = Column(Integer, nullable=False)
    raw_samples_blob = Column(LargeBinary, nullable=False)
    sha256_hash = Column(String(64), nullable=False)

    quality_flags = Column(String, default="OK", nullable=False)  # OK | CLIPPED | DROPPED_FRAMES | NOISY | DUPLICATE
    data_provenance = Column(String, nullable=False)  # LIVE | SIMULATION | HISTORICAL
    drive_rpm = Column(Float, nullable=True)
    pretension_n = Column(Float, nullable=True)

    __table_args__ = (
        CheckConstraint("data_provenance IN ('LIVE', 'SIMULATION', 'HISTORICAL')", name="check_provenance_valid"),
        Index("idx_device_stream_seq", "device_id", "stream_id", "sequence_number"),
    )

    device = relationship("Device")
    sensor = relationship("Sensor", back_populates="vibration_bursts")
    joint = relationship("Joint", back_populates="vibration_bursts")


class JointObservation(Base):
    """
    One observation record per joint passage through the sensor.

    Phase 3 adds DSP features, baseline values, health scoring,
    anomaly detection, and risk state tracking. All new Phase 3
    columns are nullable for backwards compatibility with pre-Phase 3
    rows already persisted in the database.
    """
    __tablename__ = "joint_observations"

    # ── Identity ─────────────────────────────────────────────────────────────
    id = Column(String, primary_key=True, index=True)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="CASCADE"), nullable=False, index=True)
    conveyor_id = Column(String, nullable=True)          # Phase 3 (nullable for old rows)
    revolution_index = Column(Integer, nullable=False)   # Monotonically increasing per joint
    observation_timestamp_utc = Column(String, nullable=True)  # Phase 3 (legacy: use timestamp_utc)
    timestamp_utc = Column(String, default=utc_now_iso, nullable=False)  # Phase 1/2 compat

    # ── Operating Conditions ────────────────────────────────────────────────
    belt_speed_mps = Column(Float, nullable=True)
    drive_rpm = Column(Float, nullable=True)
    pretension_n = Column(Float, nullable=True)
    motor_current_a = Column(Float, nullable=True)
    operating_state = Column(String, nullable=False)  # IDLE | STARTING | STEADY_EMPTY | STEADY_LOADED | STOPPING
    sampling_rate_hz = Column(Float, nullable=True)   # Phase 3

    surface_temperature_c = Column(Float, nullable=True)
    ambient_temperature_c = Column(Float, nullable=True)
    raw_burst_id = Column(String, ForeignKey("raw_vibration_bursts.id", ondelete="SET NULL"), nullable=True)
    data_provenance = Column(String, nullable=False)

    # ── Time-Domain DSP Features (Phase 3) ──────────────────────────────────
    rms_acceleration = Column(Float, nullable=True)
    peak_acceleration = Column(Float, nullable=True)
    peak_to_peak_acceleration = Column(Float, nullable=True)
    crest_factor = Column(Float, nullable=True)
    kurtosis = Column(Float, nullable=True)
    skewness = Column(Float, nullable=True)

    # ── Frequency-Domain Features (Phase 3) ─────────────────────────────────
    dominant_frequency_hz = Column(Float, nullable=True)
    dominant_frequency_amplitude = Column(Float, nullable=True)
    spectral_centroid_hz = Column(Float, nullable=True)
    spectral_energy = Column(Float, nullable=True)

    # ── Health & Anomaly (Phase 3) ───────────────────────────────────────────
    health_score = Column(Float, nullable=True)
    anomaly_detected = Column(Integer, nullable=True)   # 1 = True, 0 = False
    risk_state = Column(String, nullable=True)          # NORMAL | WATCH | WARNING | CRITICAL

    # ── Baseline Reference Values (Phase 3) ──────────────────────────────────
    # Labeled as "baseline_derived_threshold" — derived from historical observations
    baseline_rms = Column(Float, nullable=True)
    baseline_crest_factor = Column(Float, nullable=True)
    baseline_kurtosis = Column(Float, nullable=True)
    baseline_dominant_freq = Column(Float, nullable=True)
    baseline_status = Column(String, nullable=True)     # LEARNING | ACTIVE | INSUFFICIENT

    # ── Normalised Deviations (Phase 3) ──────────────────────────────────────
    # deviation = (current - baseline_median) / (baseline_MAD * 1.4826)
    # units: σ-equivalent (robust z-score)
    rms_deviation = Column(Float, nullable=True)
    crest_factor_deviation = Column(Float, nullable=True)
    kurtosis_deviation = Column(Float, nullable=True)

    # ── Persistence Counter Snapshot ─────────────────────────────────────────
    consecutive_abnormal_count_snapshot = Column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint("data_provenance IN ('LIVE', 'SIMULATION', 'HISTORICAL')", name="check_obs_provenance_valid"),
    )

    joint = relationship("Joint", back_populates="observations")


class AlertEvent(Base):
    """
    Industrial alert record generated when anomaly thresholds are crossed.

    Every alert is evidence-based and answers:
      WHAT happened, WHERE, WHEN, WHY, WHICH metrics triggered it.

    Alert messages use language such as "anomaly detected" and
    "investigation required" — never "failure confirmed".
    """
    __tablename__ = "alert_events"

    id = Column(String, primary_key=True, index=True)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="CASCADE"), nullable=False, index=True)
    conveyor_id = Column(String, nullable=True)

    # ── Classification ────────────────────────────────────────────────────────
    severity = Column(String, nullable=False)    # WATCH | WARNING | CRITICAL
    alert_type = Column(String, nullable=False)  # VIBRATION_SPIKE | SPLICE_FATIGUE_IMPACT | HARMONIC_RESONANCE | CONSECUTIVE_ABNORMAL
    message = Column(Text, nullable=False)       # Human-readable evidence-based alert text

    # ── Supporting Evidence ───────────────────────────────────────────────────
    metrics_snapshot_json = Column(Text, nullable=True)  # JSON snapshot of metrics at alert time

    # ── Data Source ───────────────────────────────────────────────────────────
    data_provenance = Column(String, nullable=False, default="LIVE")  # LIVE | SIMULATION | HISTORICAL

    # ── Acknowledgement ───────────────────────────────────────────────────────
    is_acknowledged = Column(Integer, default=0, nullable=False)  # 0 = unacknowledged, 1 = acknowledged
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at_utc = Column(String, nullable=True)

    # ── Timestamps ────────────────────────────────────────────────────────────
    triggered_at_utc = Column(String, default=utc_now_iso, nullable=False, index=True)

    __table_args__ = (
        CheckConstraint("severity IN ('WATCH', 'WARNING', 'CRITICAL')", name="check_alert_severity_valid"),
        CheckConstraint(
            "alert_type IN ('VIBRATION_SPIKE', 'SPLICE_FATIGUE_IMPACT', 'HARMONIC_RESONANCE', 'CONSECUTIVE_ABNORMAL')",
            name="check_alert_type_valid"
        ),
        CheckConstraint("data_provenance IN ('LIVE', 'SIMULATION', 'HISTORICAL')", name="check_alert_provenance_valid"),
    )

    joint = relationship("Joint", back_populates="alerts")


class StreamTracker(Base):
    """Tracks sequence continuity, dropped packets, and rollover per (device_id, stream_id)."""
    __tablename__ = "stream_trackers"

    id = Column(String, primary_key=True)  # "{device_id}:{stream_id}"
    device_id = Column(String, nullable=False, index=True)
    stream_id = Column(String, nullable=False, index=True)
    last_sequence_number = Column(Integer, nullable=False)
    total_packets_received = Column(Integer, default=0, nullable=False)
    dropped_packets_count = Column(Integer, default=0, nullable=False)
    last_hardware_timestamp_us = Column(Integer, nullable=False)
    rollover_count = Column(Integer, default=0, nullable=False)
    last_seen_utc = Column(String, default=utc_now_iso, nullable=False)


class VisionObservation(Base):
    """
    Persistent record of a computer-vision surface inspection frame.
    Capable of storing multiple damage instances per frame (normalized detections[]).
    Associated with an optional physical joint and timestamp.
    """
    __tablename__ = "vision_observations"

    id = Column(String, primary_key=True, index=True)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="SET NULL"), nullable=True, index=True)
    joint_code = Column(String, nullable=True, index=True)
    camera_id = Column(String, nullable=False, default="CAM-SPLICE-01", index=True)
    timestamp_utc = Column(String, default=utc_now_iso, nullable=False, index=True)

    model_version = Column(String, nullable=False, default="conveyor-damage-detector-v1")
    source_type = Column(String, nullable=False)  # RESEARCH_DATASET | LIVE_CAMERA | SIMULATION_TEST
    image_reference = Column(String, nullable=True)  # File path or reference identifier

    total_detections_count = Column(Integer, default=0, nullable=False)
    primary_damage_type = Column(String, nullable=True)  # Highest-severity or first detected damage class
    max_confidence = Column(Float, nullable=True)        # Highest confidence score among detections
    detections_json = Column(Text, nullable=False, default="[]")  # JSON list of {class_name, confidence, bbox: [x,y,w,h]}
    processing_metadata_json = Column(Text, nullable=True)         # JSON metadata (inference_time_ms, resolution, etc.)

    __table_args__ = (
        CheckConstraint("source_type IN ('RESEARCH_DATASET', 'LIVE_CAMERA', 'SIMULATION_TEST')", name="check_vision_source_type_valid"),
    )

    joint = relationship("Joint", back_populates="vision_observations")


class MaintenanceLog(Base):
    """
    Tamper-evident log of physical maintenance operations on belt joints.
    Includes maintenance actions (splice repairs, retensioning, recalibration),
    technician identification, notes, before/after risk states, and SHA-256 integrity hash.
    """
    __tablename__ = "maintenance_logs"

    id = Column(String, primary_key=True, index=True)
    joint_id = Column(String, ForeignKey("joints.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp_utc = Column(String, default=utc_now_iso, nullable=False, index=True)
    technician_id = Column(String, nullable=False)
    action_type = Column(String, nullable=False)  # INSPECTION | SPLICE_REPAIR | RETENSIONING | REPLACEMENT | RECALIBRATION
    notes = Column(Text, nullable=True)
    risk_state_before = Column(String, nullable=False)
    risk_state_after = Column(String, nullable=False)
    baseline_reset = Column(Integer, default=0, nullable=False)  # 1 = True (resets baseline window)
    data_provenance = Column(String, default="LIVE", nullable=False)
    record_hash = Column(String(64), nullable=False)  # SHA-256 over canonical record content

    joint = relationship("Joint", back_populates="maintenance_logs")

