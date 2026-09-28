"""
Live Camera & Joint Passage Optical Capture Service
===================================================
Manages physical USB camera acquisition, continuous live MJPEG video streaming,
and triggered frame analysis when a conveyor belt splice passes the optical station.

Key Design & Scientific Integrity Principles:
1. Physical Camera Support: Attempts capture via OpenCV VideoCapture on device index.
2. Live MJPEG Video Streaming: Delivers true continuous industrial video feed for SCADA HMI.
3. Thread-Safe Camera Access: Single acquisition thread prevents Windows DirectShow device collisions.
4. Honest Provenance:
   - When captured from physical USB camera: source_type = "LIVE_CAMERA"
   - When physical camera is unavailable / in lab test: source_type = "RESEARCH_DATASET"
5. Joint Passage Synchronization:
   - Triggered automatically by Hall-effect sensor / tachometer pulse or manual SCADA command.
6. Real-time Inference & WebSocket Push:
   - Feeds frame into YOLOv8 VisionEngine, records observation in SQLite WAL,
     and broadcasts VISION_UPDATE and correlated ALERT_TRIGGERED over WebSockets.
"""

import os
import time
import json
import uuid
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Generator
from datetime import datetime, timezone
import cv2
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import desc

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
VISION_TEST_DIR = PROJECT_ROOT / "data" / "raw" / "research" / "conveyor_belt_damage_vision" / "test"
ANALYSIS_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "research" / "conveyor_belt_damage_vision" / "analyzed_frames"

from .config import settings
from .database import SessionLocal, get_db_context
from .vision_service import vision_engine
from .websocket_manager import ws_manager
from . import models

logger = logging.getLogger("camera_service")


class CameraCaptureService:
    def __init__(self, device_index: int = settings.CAMERA_DEVICE_INDEX):
        self.device_index = device_index
        self.last_capture_utc: Optional[str] = None
        self.total_captures = 0
        self.last_observation_id: Optional[str] = None
        self.camera_hardware_available = False
        self._is_live_stream = False
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._acquisition_loop, daemon=True)
        self._thread.start()

    def _acquisition_loop(self):
        """Continuous background thread that grabs frames from USB camera or benchmark catalogue."""
        logger.info(f"CameraCaptureService: acquisition loop started (index={self.device_index}).")
        cap = None
        benchmark_files = sorted(list(VISION_TEST_DIR.glob("*.jpg"))) if VISION_TEST_DIR.exists() else []
        bench_idx = 0
        last_bench_switch = time.time()

        while self._running:
            frame = None
            is_live = False

            if settings.CAMERA_ENABLED:
                if cap is None or not cap.isOpened():
                    try:
                        cap = cv2.VideoCapture(self.device_index)
                        if cap.isOpened():
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            self.camera_hardware_available = True
                    except Exception as e:
                        logger.warning(f"Failed to open camera on index {self.device_index}: {e}")
                        cap = None
                        self.camera_hardware_available = False

                if cap and cap.isOpened():
                    try:
                        ret, raw_frame = cap.read()
                        if ret and raw_frame is not None and raw_frame.size > 0:
                            frame = raw_frame
                            is_live = True
                            self.camera_hardware_available = True
                        else:
                            self.camera_hardware_available = False
                            try:
                                cap.release()
                            except Exception:
                                pass
                            cap = None
                    except Exception as e:
                        logger.warning(f"Camera read error: {e}")
                        self.camera_hardware_available = False
                        cap = None

            # Fallback to cycling benchmark frames if hardware not active
            if frame is None:
                self.camera_hardware_available = False
                now = time.time()
                if benchmark_files:
                    # Switch frame every 3 seconds for active motion simulation
                    if now - last_bench_switch > 3.0:
                        bench_idx = (bench_idx + 1) % len(benchmark_files)
                        last_bench_switch = now
                    sample_path = benchmark_files[bench_idx]
                    frame = cv2.imread(str(sample_path))

            if frame is None:
                # Synthetic canvas pattern
                frame = np.full((480, 640, 3), 32, dtype=np.uint8)
                cv2.putText(frame, "CONVEYOR OPTICAL FEED - STANDBY", (80, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)

            with self._frame_lock:
                self._latest_raw_frame = frame
                self._is_live_stream = is_live

            time.sleep(0.04)  # ~25 FPS acquisition

        if cap:
            try:
                cap.release()
            except Exception:
                pass
        logger.info("CameraCaptureService: acquisition loop exited.")

    def generate_mjpeg_stream(self) -> Generator[bytes, None, None]:
        """Yields multipart MJPEG byte stream for live web SCADA video element."""
        while self._running:
            frame_to_send = None
            is_live = False
            with self._frame_lock:
                if self._latest_raw_frame is not None:
                    frame_to_send = self._latest_raw_frame.copy()
                    is_live = self._is_live_stream

            if frame_to_send is not None:
                # Draw live industrial camera HUD overlay
                h, w = frame_to_send.shape[:2]
                now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
                cam_label = "CAM-01 [HEAD HOOD] · LIVE USB" if is_live else "CAM-01 [HEAD HOOD] · BENCHMARK STREAM"
                status_color = (0, 255, 0) if is_live else (0, 200, 255)

                # Header bar overlay
                cv2.rectangle(frame_to_send, (0, 0), (w, 24), (15, 17, 23), -1)
                cv2.circle(frame_to_send, (12, 12), 4, status_color, -1)
                cv2.putText(frame_to_send, cam_label, (22, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(frame_to_send, now_str, (w - 210, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1, cv2.LINE_AA)

                # Reticle crosshair in center
                cx, cy = w // 2, h // 2
                cv2.line(frame_to_send, (cx - 12, cy), (cx + 12, cy), (0, 255, 255), 1)
                cv2.line(frame_to_send, (cx, cy - 12), (cx, cy + 12), (0, 255, 255), 1)

                ret, jpeg = cv2.imencode(".jpg", frame_to_send, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if ret:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")

            time.sleep(0.05)  # ~20 FPS stream

    def capture_frame(self) -> Tuple[Optional[np.ndarray], str, str, str]:
        """
        Captures the current optical frame from the acquisition worker buffer.
        """
        for _ in range(15):
            with self._frame_lock:
                if self._latest_raw_frame is not None:
                    break
            time.sleep(0.05)

        with self._frame_lock:
            if self._latest_raw_frame is not None:
                frame = self._latest_raw_frame.copy()
                is_live = self._is_live_stream
            else:
                frame = None
                is_live = False

        if frame is not None and is_live:
            frame_name = f"cam_live_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.jpg"
            return (
                frame,
                "LIVE_CAMERA",
                f"Captured from physical USB camera (device index {self.device_index})",
                frame_name
            )

        if frame is not None:
            return (
                frame,
                "RESEARCH_DATASET",
                "Captured from active benchmark optical stream",
                f"benchmark_frame_{uuid.uuid4().hex[:6]}.jpg"
            )

        # Fallback clean gray calibration card
        blank = np.full((480, 640, 3), 128, dtype=np.uint8)
        return (blank, "SIMULATION_TEST", "Generated synthetic optical calibration frame", "calibration_card.jpg")

    def trigger_joint_capture(
        self,
        joint_code: str = "J-01",
        camera_id: str = "CAM-SPLICE-01",
        conf_threshold: float = 0.25,
        test_image_name: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Executes an optical inspection cycle triggered at joint passage:
        1. Acquires frame (live hardware camera or benchmark test frame).
        2. Executes YOLOv8 inference (or classical CV baseline).
        3. Persists VisionObservation to SQLite WAL database.
        4. Broadcasts VISION_UPDATE, ALERT_TRIGGERED, and correlated HEALTH_UPDATE over WebSockets.
        """
        frame_input = None
        source_type = "LIVE_CAMERA"
        status_note = ""
        frame_name = "frame.jpg"

        if test_image_name:
            target_path = VISION_TEST_DIR / test_image_name
            if target_path.exists():
                frame_input = cv2.imread(str(target_path))
                source_type = "RESEARCH_DATASET"
                status_note = f"Explicit benchmark sample '{test_image_name}' selected"
                frame_name = test_image_name
            else:
                frame_input, source_type, status_note, frame_name = self.capture_frame()
        else:
            frame_input, source_type, status_note, frame_name = self.capture_frame()

        # Run vision inference
        analysis_res = vision_engine.analyze_frame(
            image_input=frame_input,
            camera_id=camera_id,
            joint_code=joint_code,
            source_type=source_type,
            conf_threshold=conf_threshold,
            frame_name=frame_name
        )

        self.last_capture_utc = datetime.now(timezone.utc).isoformat()
        self.total_captures += 1
        self.last_observation_id = analysis_res.get("observation_id")

        # Database persistence
        def _persist(session: Session):
            # Resolve joint_id from joint_code
            resolved_joint_id = None
            target_joint = None
            if joint_code:
                target_joint = session.query(models.Joint).filter(
                    (models.Joint.joint_code == joint_code) | (models.Joint.id == joint_code)
                ).first()
                if target_joint:
                    resolved_joint_id = target_joint.id

            provenance = "LIVE" if source_type == "LIVE_CAMERA" else ("HISTORICAL" if source_type == "RESEARCH_DATASET" else "SIMULATION")

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
                    "frame_name": frame_name,
                    "capture_note": status_note
                })
            )
            session.add(vis_obs)

            # If damage detected, generate an alert event
            if analysis_res.get("has_damage"):
                alert_sev = analysis_res.get("prototype_severity", "WARNING")
                alert_id = f"alert-vis-{uuid.uuid4().hex[:8]}"
                tj_id = resolved_joint_id or "joint-001"
                vis_alert = models.AlertEvent(
                    id=alert_id,
                    joint_id=tj_id,
                    conveyor_id="cv-main-01",
                    severity=alert_sev,
                    alert_type="SPLICE_FATIGUE_IMPACT",
                    message=f"Optical camera detected {analysis_res['total_detections']} surface defect(s). Primary: {analysis_res['primary_damage_type']} ({analysis_res['max_confidence']*100:.1f}% confidence). Immediate splice inspection recommended.",
                    metrics_snapshot_json=json.dumps({
                        "detections": analysis_res["detections"],
                        "max_confidence": analysis_res["max_confidence"],
                        "camera_id": camera_id,
                        "frame_name": frame_name
                    }),
                    data_provenance=provenance
                )
                session.add(vis_alert)

                if target_joint:
                    target_joint.current_risk = alert_sev
                    session.add(target_joint)

                # Query latest operational RPM/tension for correlated telemetry
                latest_obs = (
                    session.query(models.JointObservation)
                    .filter(models.JointObservation.joint_id == tj_id)
                    .order_by(desc(models.JointObservation.timestamp_utc))
                    .first()
                )
                live_rpm = getattr(latest_obs, "drive_rpm", None)
                live_tension = getattr(latest_obs, "pretension_n", None)

                # Dispatch Alert over WebSocket
                ws_manager.dispatch_json({
                    "type": "ALERT_TRIGGERED",
                    "alert": {
                        "id": vis_alert.id,
                        "joint_id": vis_alert.joint_id,
                        "severity": vis_alert.severity,
                        "alert_type": vis_alert.alert_type,
                        "message": vis_alert.message,
                        "triggered_at_utc": vis_alert.triggered_at_utc,
                        "is_acknowledged": False
                    }
                })

                # Correlated Health Update
                health_score = 28.0 if alert_sev == "CRITICAL" else 64.0
                ws_manager.dispatch_json({
                    "type": "HEALTH_UPDATE",
                    "joint_id": tj_id,
                    "timestamp_utc": analysis_res["timestamp_utc"],
                    "health_score": health_score,
                    "risk_state": alert_sev,
                    "overall_status": alert_sev,
                    "rpm": live_rpm,
                    "tension": live_tension,
                    "data_provenance": provenance,
                    "explanation": f"Optical inspection confirmed surface defect: {analysis_res['primary_damage_type']} ({analysis_res['total_detections']} detections flagged)."
                })

            session.commit()

        if db is not None:
            _persist(db)
        else:
            with get_db_context() as session:
                _persist(session)

        # Dispatch VISION_UPDATE WebSocket payload
        ws_payload = {
            "type": "VISION_UPDATE",
            "observation_id": analysis_res["observation_id"],
            "camera_id": camera_id,
            "joint_code": joint_code,
            "timestamp_utc": analysis_res["timestamp_utc"],
            "model_status": analysis_res["model_status"],
            "model_version": analysis_res["model_version"],
            "source_type": source_type,
            "image_reference": analysis_res["image_reference"],
            "has_damage": analysis_res["has_damage"],
            "primary_damage_type": analysis_res["primary_damage_type"],
            "max_confidence": analysis_res["max_confidence"],
            "prototype_severity": analysis_res["prototype_severity"],
            "total_detections": analysis_res["total_detections"],
            "detections": analysis_res["detections"],
            "status_note": status_note
        }
        ws_manager.dispatch_json(ws_payload)

        analysis_res["capture_mode"] = source_type
        analysis_res["status_note"] = status_note
        return analysis_res

    def get_status(self) -> Dict[str, Any]:
        """Returns camera subsystem operational status."""
        return {
            "hardware_camera_available": self.camera_hardware_available,
            "device_index": self.device_index,
            "camera_enabled": settings.CAMERA_ENABLED,
            "auto_trigger_on_joint": settings.CAMERA_AUTO_TRIGGER_ON_JOINT,
            "last_capture_utc": self.last_capture_utc,
            "total_captures": self.total_captures,
            "last_observation_id": self.last_observation_id,
            "stream_url": "/api/v1/vision/camera/stream",
            "mode": "PHYSICAL_USB_CAMERA" if self.camera_hardware_available else "BENCHMARK_TEST_SPLIT"
        }

    def stop(self):
        """Stops background acquisition thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)


# Global singleton instance
camera_service = CameraCaptureService()
