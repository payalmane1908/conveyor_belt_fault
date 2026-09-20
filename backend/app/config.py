import os
from pathlib import Path
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Information
    PROJECT_NAME: str = "Conveyor Joint Health & Failure Prevention System"
    API_V1_STR: str = "/api/v1"

    # Workspace & Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    DB_PATH: Path = DATA_DIR / "telemetry.db"

    # SQLite Performance & Integrity Settings
    SQLITE_WAL_MODE: bool = True
    SQLITE_BUSY_TIMEOUT_MS: int = 5000

    # Provenance & Simulation Isolation Gates
    ALLOW_SIMULATION_INGESTION: bool = True
    ALLOW_DEVELOPMENT_DRIVERS: bool = True

    # Hardware & Serial Acquisition Settings
    SERIAL_PORT: str = "COM3"
    SERIAL_BAUDRATE: int = 115200
    SERIAL_TIMEOUT_SECONDS: float = 1.0
    SERIAL_WORKER_ENABLED: bool = False  # Disabled by default until physical serial port connected

    # Sensor & Trigger Calibration Defaults
    DEFAULT_SAMPLING_RATE_HZ: float = 1000.0
    DEFAULT_TRIGGER_OFFSET_METERS: float = 0.50  # Distance from RFID/Hall sensor to accelerometer
    DEFAULT_TRIGGER_DELAY_MS: float = 200.0      # Calibration delay before sampling window

    # Sequence & Rollover Settings
    TIMESTAMP_32BIT_ROLLOVER_THRESHOLD_US: int = 1_000_000  # Jump backward > 1s flags rollover

    # =========================================================================
    # PHASE 3 — DSP & HEALTH SCORING CONFIGURATION
    #
    # All thresholds below are ENGINEERING THRESHOLDS or CONFIGURABLE PLANT
    # THRESHOLDS. They are NOT universal industrial standards or ISO compliance
    # values. They must be calibrated against actual plant data after deployment.
    # =========================================================================

    # ── Baseline System ──────────────────────────────────────────────────────
    # Minimum observations before a baseline is considered "active"
    BASELINE_MIN_OBSERVATIONS: int = 5
    # Rolling window size for baseline calculation (number of normal observations)
    BASELINE_ROLLING_WINDOW: int = 20

    # ── Anomaly Detection: Baseline Deviation Thresholds ─────────────────────
    # Threshold in robust σ-equivalent units (MAD-based z-score)
    # A deviation > this value triggers a baseline-deviation anomaly
    # Label: baseline_derived_threshold
    BASELINE_SIGMA_ALERT_THRESHOLD: float = 3.0   # RMS deviation
    BASELINE_CREST_SIGMA_THRESHOLD: float = 3.0   # Crest factor deviation
    BASELINE_KURTOSIS_SIGMA_THRESHOLD: float = 3.0

    # ── Anomaly Detection: Absolute Engineering Thresholds ───────────────────
    # These are initial engineering thresholds for absolute (non-baseline) checks.
    # Label: engineering_threshold — must be calibrated per plant/machine class.
    ABS_RMS_ALERT_THRESHOLD: float = 5.0          # Acceleration units (g or m/s² — matches input)
    ABS_CREST_FACTOR_THRESHOLD: float = 4.0       # Unitless ratio
    ABS_KURTOSIS_THRESHOLD: float = 3.0           # Fisher/excess kurtosis
    ABS_FREQ_DEVIATION_PCT_THRESHOLD: float = 20.0  # % deviation from baseline dominant freq

    # ── Health Score Weights ──────────────────────────────────────────────────
    # Must sum to 1.0. Adjust per application priority.
    HEALTH_WEIGHT_VIBRATION: float = 0.35   # RMS / vibration severity component
    HEALTH_WEIGHT_SHOCK: float = 0.30       # Crest factor + kurtosis impulsive component
    HEALTH_WEIGHT_FREQUENCY: float = 0.15  # Frequency / spectral anomaly component
    HEALTH_WEIGHT_PERSISTENCE: float = 0.20  # Consecutive abnormal count component

    # ── Health Score Interpretation Bands ────────────────────────────────────
    # Configurable engineering application thresholds.
    # NOT universal industrial standards — must be calibrated per plant.
    HEALTH_BAND_NORMAL_MIN: float = 90.0    # 90–100 = NORMAL
    HEALTH_BAND_WATCH_MIN: float = 75.0     # 75–89 = WATCH
    HEALTH_BAND_WARNING_MIN: float = 50.0   # 50–74 = WARNING
    # 0–49 = CRITICAL

    # ── Risk State Machine Hysteresis ────────────────────────────────────────
    # Configurable initial engineering parameters — not scientifically universal.
    # Escalation: consecutive abnormal observations needed to promote state
    WARNING_CONSECUTIVE_ANOMALIES: int = 2
    CRITICAL_CONSECUTIVE_ANOMALIES: int = 3
    # Recovery: consecutive healthy observations needed to step down one level
    RECOVERY_OBSERVATIONS_REQUIRED: int = 3

    # ── Persistence Penalty Scaling ───────────────────────────────────────────
    # At CRITICAL_CONSECUTIVE_ANOMALIES consecutive anomalies, persistence penalty = 100%
    # Scales linearly below that.
    MAX_CONSECUTIVE_FOR_FULL_PENALTY: int = 5

    class Config:
        env_prefix = "SIH_"
        case_sensitive = True

settings = Settings()

# Ensure data directory exists
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
