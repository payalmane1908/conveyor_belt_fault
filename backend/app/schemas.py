from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

class DataProvenance(str, Enum):
    LIVE = "LIVE"
    SIMULATION = "SIMULATION"
    HISTORICAL = "HISTORICAL"

class QualityFlag(str, Enum):
    OK = "OK"
    CLIPPED = "CLIPPED"
    DROPPED_FRAMES = "DROPPED_FRAMES"
    NOISY = "NOISY"
    DUPLICATE = "DUPLICATE"

class OperatingState(str, Enum):
    IDLE = "IDLE"
    STARTING = "STARTING"
    STEADY_EMPTY = "STEADY_EMPTY"
    STEADY_LOADED = "STEADY_LOADED"
    STOPPING = "STOPPING"

class RawTelemetryPacketIn(BaseModel):
    device_id: str = Field(..., description="Unique ID of edge device (e.g. esp32-node-01)")
    stream_id: str = Field(..., description="Sensor stream identifier (e.g. accel-z)")
    sensor_id: str = Field(..., description="Foreign key to registered sensor")
    joint_id: Optional[str] = Field(None, description="Nullable joint ID if passage triggered")
    sequence_number: int = Field(..., ge=0, description="Monotonic sequence number per stream")
    hardware_timestamp_us: int = Field(..., ge=0, description="Device-local microsecond counter")
    sampling_rate_hz: float = Field(..., gt=0, description="Sampling rate in Hertz")
    samples: List[float] = Field(..., min_length=1, description="Raw vibration sample array")
    quality_flags: str = Field("OK", description="Quality flag: OK | CLIPPED | DROPPED_FRAMES | NOISY")
    data_provenance: DataProvenance = Field(..., description="Hard provenance tag: LIVE | SIMULATION | HISTORICAL")
    drive_rpm: Optional[float] = Field(None, description="Drive shaft/pulley rotational speed in RPM")
    pretension_n: Optional[float] = Field(None, description="Belt static/dynamic pretension in Newtons")
    motor_current_a: Optional[float] = Field(None, description="Drive motor electrical current in Amperes")
    belt_speed_mps: Optional[float] = Field(None, description="Linear belt surface velocity in m/s")

    @field_validator("samples")
    @classmethod
    def validate_samples(cls, v):
        if len(v) == 0:
            raise ValueError("Sample array cannot be empty")
        return v

class SimulationPacketIn(BaseModel):
    """Schema for test harness packets. Explicitly rejects any provenance other than SIMULATION."""
    device_id: str = Field(..., description="Device ID")
    stream_id: str = Field(..., description="Stream ID")
    sensor_id: str = Field(..., description="Sensor ID")
    joint_id: Optional[str] = Field(None, description="Optional joint ID")
    sequence_number: int = Field(..., ge=0)
    hardware_timestamp_us: int = Field(..., ge=0)
    sampling_rate_hz: float = Field(default=1000.0, gt=0)
    samples: List[float] = Field(..., min_length=1)
    quality_flags: str = Field("OK")
    data_provenance: DataProvenance = Field(default=DataProvenance.SIMULATION)
    drive_rpm: Optional[float] = Field(None, description="Drive shaft/pulley rotational speed in RPM")
    pretension_n: Optional[float] = Field(None, description="Belt static/dynamic pretension in Newtons")
    motor_current_a: Optional[float] = Field(None, description="Drive motor electrical current in Amperes")
    belt_speed_mps: Optional[float] = Field(None, description="Linear belt surface velocity in m/s")

    @field_validator("data_provenance")
    @classmethod
    def validate_simulation_provenance(cls, v):
        if v != DataProvenance.SIMULATION:
            raise ValueError("Simulation packets must explicitly have data_provenance='SIMULATION'")
        return v

class RawTelemetryBurstSummary(BaseModel):
    id: str
    device_id: str
    stream_id: str
    sensor_id: str
    joint_id: Optional[str]
    sequence_number: int
    hardware_timestamp_us: int
    unwrapped_hardware_timestamp_us: int
    received_at_utc: str
    sampling_rate_hz: float
    sample_count: int
    sha256_hash: str
    quality_flags: str
    data_provenance: DataProvenance

    class Config:
        from_attributes = True

class RawTelemetryBurstDetail(RawTelemetryBurstSummary):
    samples: List[float]
    integrity_verified: bool

class StreamStatus(BaseModel):
    stream_id: str
    device_id: str
    last_sequence_number: int
    total_packets_received: int
    dropped_packets_count: int
    last_hardware_timestamp_us: int
    rollover_count: int
    last_seen_utc: str

class SystemStatusResponse(BaseModel):
    system_name: str
    status: str
    serial_worker_enabled: bool
    serial_port: str
    simulation_ingestion_allowed: bool
    active_streams: List[StreamStatus]
    total_bursts_persisted: int
    server_time_utc: str

class DeviceCreate(BaseModel):
    id: str = Field(..., description="Unique hardware/device ID (e.g. esp32-node-01)")
    name: str = Field(..., description="Human-readable device name")
    device_type: str = Field(..., description="ESP32 | RASPBERRY_PI | INDUSTRIAL_GATEWAY | TEST_RIG_EMULATOR")
    serial_number: Optional[str] = None
    is_trusted_hardware: int = Field(default=1, description="1=Trusted physical hardware, 0=Untrusted/quarantined")
    status: str = Field(default="ACTIVE", description="ACTIVE | QUARANTINED | DECOMMISSIONED")

class DeviceOut(DeviceCreate):
    registered_at_utc: str

    class Config:
        from_attributes = True

class SensorCreate(BaseModel):
    id: str
    sensor_type: str
    model_number: Optional[str] = None
    serial_number: Optional[str] = None
    sampling_rate_hz: Optional[float] = None
    output_protocol: str
    calibration_data_json: Optional[str] = None
    status: str = "ACTIVE"

class SensorOut(SensorCreate):
    class Config:
        from_attributes = True

class JointCreate(BaseModel):
    id: str
    joint_code: str
    belt_id: str
    physical_position_meters: float
    identifier_type: str
    identifier_token: str
    splice_type: str
    installation_date: str

class JointOut(JointCreate):
    current_risk: str
    last_passage_timestamp_utc: Optional[str]
    consecutive_abnormal_count: int
    total_revolutions_count: int

    class Config:
        from_attributes = True

class ConveyorCreate(BaseModel):
    id: str
    name: str
    location: str
    length_meters: float
    nominal_speed_mps: float

class ConveyorOut(ConveyorCreate):
    created_at_utc: str

    class Config:
        from_attributes = True

class BeltCreate(BaseModel):
    id: str
    conveyor_id: str
    belt_identifier: str
    splice_standard: str
    installation_date: str

class BeltOut(BeltCreate):
    status: str

    class Config:
        from_attributes = True

class SensorAttachmentCreate(BaseModel):
    id: str
    sensor_id: str
    conveyor_id: str
    joint_id: Optional[str] = None
    physical_location: str
    trigger_offset_meters: float = 0.50
    trigger_delay_ms: float = 200.0

class SensorAttachmentOut(SensorAttachmentCreate):
    mounted_at_utc: str
    status: str

    class Config:
        from_attributes = True

# ── Phase 5: Joint Lifecycle & Maintenance Schemas ──────────────────────────

class MaintenanceActionType(str, Enum):
    INSPECTION = "INSPECTION"
    SPLICE_REPAIR = "SPLICE_REPAIR"
    RETENSIONING = "RETENSIONING"
    REPLACEMENT = "REPLACEMENT"
    RECALIBRATION = "RECALIBRATION"

class MaintenanceLogCreate(BaseModel):
    joint_id: str = Field(..., description="Target joint ID or joint code (e.g. J-01)")
    technician_id: str = Field(..., min_length=1, description="Technician badge or ID")
    action_type: MaintenanceActionType = Field(..., description="Type of maintenance performed")
    notes: Optional[str] = Field(None, description="Detailed mechanical/electrical observations")
    baseline_reset: bool = Field(False, description="Whether to reset baseline window after mechanical splice work")
    data_provenance: DataProvenance = Field(DataProvenance.LIVE, description="LIVE or SIMULATION")

class MaintenanceLogResponse(BaseModel):
    id: str
    joint_id: str
    timestamp_utc: str
    technician_id: str
    action_type: str
    notes: Optional[str]
    risk_state_before: str
    risk_state_after: str
    baseline_reset: int
    data_provenance: str
    record_hash: str

    class Config:
        from_attributes = True

class JointDegradationTrend(BaseModel):
    trend_status: str  # INSUFFICIENT_HISTORY | ESTIMATED_OBSERVED_TREND
    revolutions_observed: int
    min_revolutions_required: int
    rms_change_per_revolution: Optional[float] = None
    kurtosis_change_per_revolution: Optional[float] = None
    trend_direction: str  # STABLE | INCREASING_MODERATE | ACCELERATING | DECREASING_SETTLING | INSUFFICIENT_DATA
    message: str

class JointOperationalExposure(BaseModel):
    accumulated_revolutions: int
    estimated_runtime_hours: float
    cycle_stress_class: str  # LOW | NOMINAL | ELEVATED

class JointLifecycleResponse(BaseModel):
    joint_id: str
    joint_code: str
    splice_type: str
    installation_date: str
    total_revolutions_count: int
    current_risk: str
    consecutive_abnormal_count: int
    last_passage_timestamp_utc: Optional[str]
    baseline_status: Optional[str] = "LEARNING"
    degradation_trend: JointDegradationTrend
    operational_exposure: JointOperationalExposure
    evidence_synthesis: Dict[str, Any]
    safety_and_integrity_guardrails: Dict[str, Any]
