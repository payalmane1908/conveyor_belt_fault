import sqlite3
import logging
from typing import Generator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from .config import settings

logger = logging.getLogger("database")

# SQLite connection URL
SQLALCHEMY_DATABASE_URL = f"sqlite:///{settings.DB_PATH.as_posix()}"

# Engine with thread-safe pooling for SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    echo=False
)

# Enforce SQLite WAL mode, busy timeout, and foreign key constraints on every connection
@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        if settings.SQLITE_WAL_MODE:
            cursor.execute("PRAGMA journal_mode = WAL;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute(f"PRAGMA busy_timeout = {settings.SQLITE_BUSY_TIMEOUT_MS};")
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and safely closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Create all tables in the database with configured pragmas, run migrations, and seed initial entities."""
    from . import models  # Ensure all models are registered with Base
    Base.metadata.create_all(bind=engine)
    migrate_db()
    seed_initial_data()

def seed_initial_data():
    """Ensure baseline industrial demonstration entities exist."""
    from . import models
    with SessionLocal() as db:
        if not db.query(models.Conveyor).filter_by(id="CV-MINE-01").first():
            cv = models.Conveyor(
                id="CV-MINE-01",
                name="Main Overland Drift Conveyor",
                location="Underground Sector 4",
                length_meters=850.0,
                nominal_speed_mps=3.2
            )
            db.add(cv)
            db.flush()

        if not db.query(models.Belt).filter_by(id="BELT-01").first():
            belt = models.Belt(
                id="BELT-01",
                conveyor_id="CV-MINE-01",
                belt_identifier="EP-800-4P",
                splice_standard="DIN-22102",
                installation_date="2026-01-15"
            )
            db.add(belt)
            db.flush()

        for j_id, j_code, pos, tok, revs in [
            ("joint-001", "J-01", 120.0, "OPT-J01", 45),
            ("test-joint-vis-01", "J-VIS-01", 340.0, "OPT-VIS-01", 120)
        ]:
            if not db.query(models.Joint).filter((models.Joint.id == j_id) | (models.Joint.joint_code == j_code)).first():
                j = models.Joint(
                    id=j_id,
                    joint_code=j_code,
                    belt_id="BELT-01",
                    physical_position_meters=pos,
                    identifier_type="OPTICAL",
                    identifier_token=tok,
                    splice_type="Finger Splice",
                    installation_date="2026-01-20",
                    total_revolutions_count=revs,
                    current_risk="NORMAL",
                    consecutive_abnormal_count=0
                )
                db.add(j)

        if not db.query(models.Device).filter_by(id="test-rig-simulator-01").first():
            dev = models.Device(
                id="test-rig-simulator-01",
                name="SCADA Sim Device",
                device_type="TEST_RIG_EMULATOR",
                serial_number="SIM-DEV-001",
                is_trusted_hardware=0,
                status="ACTIVE"
            )
            db.add(dev)

        if not db.query(models.Device).filter_by(id="esp32-node-01").first():
            esp_dev = models.Device(
                id="esp32-node-01",
                name="ESP32 Physical DAQ Node",
                device_type="ESP32_WROOM_32D",
                serial_number="ESP32-HW-001",
                is_trusted_hardware=1,
                status="ACTIVE"
            )
            db.add(esp_dev)

        if not db.query(models.Sensor).filter_by(id="sim-accel-p3-01").first():
            sens = models.Sensor(
                id="sim-accel-p3-01",
                sensor_type="ACCELEROMETER",
                sampling_rate_hz=1000.0,
                output_protocol="SPI",
                status="ACTIVE"
            )
            db.add(sens)

        if not db.query(models.Sensor).filter_by(id="sens-vibe-01").first():
            sens_hw = models.Sensor(
                id="sens-vibe-01",
                sensor_type="ACCELEROMETER",
                sampling_rate_hz=1000.0,
                output_protocol="SPI",
                status="ACTIVE"
            )
            db.add(sens_hw)

        db.commit()
        logger.info("seed_initial_data() idempotent seeding completed.")

def migrate_db():
    """
    Safe, idempotent schema migration for Phase 3 and Phase 5 additions.

    SQLite does not support adding columns with non-constant defaults via
    ALTER TABLE, but it does support adding nullable columns. This function
    runs ALTER TABLE ADD COLUMN for each new column, catching
    OperationalError when the column already exists (idempotent).
    """
    # ---- Phase 3 & 5 columns for joint_observations ----
    new_joint_obs_columns = [
        ("conveyor_id",                          "TEXT"),
        ("observation_timestamp_utc",            "TEXT"),
        ("sampling_rate_hz",                     "REAL"),
        ("rms_acceleration",                     "REAL"),
        ("peak_acceleration",                    "REAL"),
        ("peak_to_peak_acceleration",            "REAL"),
        ("crest_factor",                         "REAL"),
        ("kurtosis",                             "REAL"),
        ("skewness",                             "REAL"),
        ("dominant_frequency_hz",                "REAL"),
        ("dominant_frequency_amplitude",         "REAL"),
        ("spectral_centroid_hz",                 "REAL"),
        ("spectral_energy",                      "REAL"),
        ("health_score",                         "REAL"),
        ("anomaly_detected",                     "INTEGER"),
        ("risk_state",                           "TEXT"),
        ("baseline_rms",                         "REAL"),
        ("baseline_crest_factor",                "REAL"),
        ("baseline_kurtosis",                    "REAL"),
        ("baseline_dominant_freq",               "REAL"),
        ("baseline_status",                      "TEXT"),
        ("rms_deviation",                        "REAL"),
        ("crest_factor_deviation",               "REAL"),
        ("kurtosis_deviation",                   "REAL"),
        ("consecutive_abnormal_count_snapshot",  "INTEGER"),
        ("pretension_n",                         "REAL"),
    ]

    new_burst_columns = [
        ("drive_rpm",     "REAL"),
        ("pretension_n",  "REAL"),
    ]

    with engine.connect() as conn:
        for col_name, col_type in new_joint_obs_columns:
            try:
                conn.execute(text(f"ALTER TABLE joint_observations ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                logger.info("Migration: added column joint_observations.%s", col_name)
            except Exception:
                pass

        for col_name, col_type in new_burst_columns:
            try:
                conn.execute(text(f"ALTER TABLE raw_vibration_bursts ADD COLUMN {col_name} {col_type}"))
                conn.commit()
                logger.info("Migration: added column raw_vibration_bursts.%s", col_name)
            except Exception:
                pass

        # Verify tables exist
        for tbl in ["alert_events", "vision_observations", "maintenance_logs"]:
            try:
                conn.execute(text(f"SELECT 1 FROM {tbl} LIMIT 1"))
            except Exception:
                logger.info("Migration: %s table will be created by init_db()", tbl)

    logger.info("migrate_db() complete.")
