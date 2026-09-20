import json
import logging
import threading
import time
from typing import Optional, Dict, Any

from .config import settings
from .database import SessionLocal
from .schemas import RawTelemetryPacketIn
from .ingestion import IngestionService
from .health_service import health_service
from .websocket_manager import ws_manager
from . import models

logger = logging.getLogger("serial_worker")
logging.basicConfig(level=logging.INFO)

class SerialAcquisitionWorker:
    """
    Background worker that ingests raw telemetry frames from a hardware serial COM port.
    Frames are expected as newline-delimited JSON packets emitted by the microcontroller (ESP32).
    """
    def __init__(self, port: Optional[str] = None, baudrate: Optional[int] = None):
        self.port = port or settings.SERIAL_PORT
        self.baudrate = baudrate or settings.SERIAL_BAUDRATE
        self.running = False
        self.connected = False
        self.thread: Optional[threading.Thread] = None
        self.serial_handle = None
        self.packets_read = 0
        self.bytes_read = 0
        self.errors_count = 0
        self.last_packet_utc: Optional[str] = None
        self.last_device_id: Optional[str] = None

    def parse_frame(self, line_bytes: bytes) -> Optional[RawTelemetryPacketIn]:
        """Parses a raw serial frame into a validated RawTelemetryPacketIn."""
        try:
            line_str = line_bytes.decode("utf-8").strip()
            if not line_str:
                return None
            data = json.loads(line_str)
            return RawTelemetryPacketIn(**data)
        except Exception as e:
            self.errors_count += 1
            logger.warning(f"Malformed serial frame received: {e}")
            return None

    def _worker_loop(self):
        logger.info(f"Serial acquisition worker started on {self.port} @ {self.baudrate} baud.")
        try:
            import serial
        except ImportError:
            logger.error("pyserial is not installed. Serial acquisition worker cannot open real COM port.")
            self.running = False
            return

        while self.running:
            try:
                if self.serial_handle is None or not self.serial_handle.is_open:
                    try:
                        self.serial_handle = serial.Serial(
                            port=self.port,
                            baudrate=self.baudrate,
                            timeout=settings.SERIAL_TIMEOUT_SECONDS
                        )
                        self.connected = True
                        logger.info(f"Connected to serial port {self.port}.")
                    except serial.SerialException:
                        self.connected = False
                        # Port not yet plugged in or openable
                        time.sleep(2.0)
                        continue

                line = self.serial_handle.readline()
                if not line:
                    continue

                packet = self.parse_frame(line)
                if packet is not None:
                    db = SessionLocal()
                    try:
                        burst = IngestionService.process_and_persist_telemetry(db, packet)
                        self.packets_read += 1
                        self.bytes_read += len(line)
                        self.last_packet_utc = burst.received_at_utc
                        self.last_device_id = burst.device_id

                        # Query tracker for sequence and loss status
                        tracker = db.query(models.StreamTracker).filter(
                            models.StreamTracker.id == f"{burst.device_id}:{burst.stream_id}"
                        ).first()
                        tracker_dict = {
                            "device_id": tracker.device_id,
                            "stream_id": tracker.stream_id,
                            "last_sequence_number": tracker.last_sequence_number,
                            "total_packets_received": tracker.total_packets_received,
                            "dropped_packets_count": tracker.dropped_packets_count,
                            "last_hardware_timestamp_us": tracker.last_hardware_timestamp_us,
                            "rollover_count": tracker.rollover_count,
                            "last_seen_utc": tracker.last_seen_utc
                        } if tracker else None

                        # Broadcast to SCADA WebSockets
                        ws_manager.dispatch_burst(
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

                        # Run health & DSP intelligence pipeline
                        try:
                            health_service.process_burst(db, burst)
                        except Exception as h_err:
                            logger.error(f"Health pipeline error for serial burst {burst.id}: {h_err}")

                    except Exception as e:
                        self.errors_count += 1
                        logger.error(f"Failed to persist serial telemetry packet: {e}")
                    finally:
                        db.close()

            except Exception as e:
                self.errors_count += 1
                logger.error(f"Serial worker read error: {e}")
                self.connected = False
                if self.serial_handle:
                    try:
                        self.serial_handle.close()
                    except Exception:
                        pass
                    self.serial_handle = None
                time.sleep(1.0)

        self.connected = False
        logger.info("Serial acquisition worker loop exited.")

    def start(self):
        """Starts the serial worker in a background daemon thread."""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.thread.start()

    def stop(self):
        """Stops the worker gracefully."""
        self.running = False
        self.connected = False
        if self.serial_handle:
            try:
                self.serial_handle.close()
            except Exception:
                pass
            self.serial_handle = None
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)

    def get_status(self) -> Dict[str, Any]:
        """Returns runtime status and acquisition metrics of the serial worker."""
        return {
            "worker_enabled": settings.SERIAL_WORKER_ENABLED,
            "running": self.running,
            "connected": self.connected,
            "port": self.port,
            "baudrate": self.baudrate,
            "packets_read": self.packets_read,
            "bytes_read": self.bytes_read,
            "errors_count": self.errors_count,
            "last_packet_utc": self.last_packet_utc,
            "last_device_id": self.last_device_id
        }

serial_worker = SerialAcquisitionWorker()
