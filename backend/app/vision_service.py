"""
Vision Engine & Analysis Service
=================================
Provides genuine computer vision inference for conveyor belt damage detection.
Strictly adheres to Industrial Data, Testing & ML Training Policy:
1. Detects ONLY classes present in the dataset:
   - Belt Joint, Large Tear, Small Tear, Large Hole, Small Hole, damage
   - NEVER claims to detect 'crack' without a crack-labeled dataset.
2. Clearly distinguishes between:
   - TRAINED_MODEL (actual trained YOLO weights)
   - CLASSICAL_CV_BASELINE (baseline edge/morphology analysis for image QA)
   - MODEL_NOT_TRAINED / MODEL_NOT_INSTALLED
3. Normalizes detections into structured detection records (multiple objects per frame).
4. Maintains strict provenance (RESEARCH_DATASET, LIVE_CAMERA, SIMULATION_TEST).
5. Exposes independent vision evidence for the Joint Passport without arbitrary weighting.
"""

import os
import sys
import json
import uuid
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import cv2
import numpy as np

# Ensure root paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_WEIGHTS_PATH = PROJECT_ROOT / "models" / "vision" / "conveyor_damage" / "best_model.pt"
ANALYSIS_OUTPUT_DIR = PROJECT_ROOT / "data" / "processed" / "research" / "conveyor_belt_damage_vision" / "analyzed_frames"

logger = logging.getLogger("vision_service")

CLASS_NAMES = {
    0: "damage",
    1: "Belt Joint",
    2: "Large Hole",
    3: "Large Tear",
    4: "Small Hole",
    5: "Small Tear"
}

CATEGORY_COLORS = {
    "Belt Joint": (0, 255, 255),    # Yellow
    "Large Tear": (0, 0, 255),      # Red
    "Small Tear": (0, 140, 255),    # Orange
    "Large Hole": (255, 0, 0),      # Blue
    "Small Hole": (255, 0, 255),    # Magenta
    "damage":     (0, 255, 0),      # Green
}

class BaselineCVAnalyzer:
    """
    Classical computer-vision baseline for preprocessing validation,
    contrast checking, and edge/contour experimentation.
    Status is strictly: CLASSICAL_CV_BASELINE.
    Must NEVER be presented as the final trained detector.
    """
    STATUS = "CLASSICAL_CV_BASELINE"
    VERSION = "classical-cv-morphology-baseline-v1.0"

    @classmethod
    def analyze_surface(cls, image: np.ndarray) -> Dict[str, Any]:
        """Analyzes surface gradients and contour anomalies."""
        if image is None:
            return {"valid": False, "error": "Empty image"}

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        # Morphological dilation to group adjacent gradients
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        total_pixels = float(gray.shape[0] * gray.shape[1])
        anomalous_pixels = float(np.count_nonzero(dilated))
        surface_gradient_ratio = anomalous_pixels / total_pixels

        candidate_regions = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > 150:  # Ignore microscopic speckles
                x, y, w, h = cv2.boundingRect(c)
                candidate_regions.append({
                    "class_name": "damage_candidate",
                    "confidence": 0.50,
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "area_px": float(area),
                    "aspect_ratio": float(w) / max(1.0, float(h)),
                    "detection_method": "classical_edge_contour_gradient"
                })

        return {
            "valid": True,
            "analyzer_status": cls.STATUS,
            "model_version": cls.VERSION,
            "surface_gradient_ratio": surface_gradient_ratio,
            "total_candidates": len(candidate_regions),
            "candidates": candidate_regions[:10],
            "disclaimer": "CLASSICAL CV BASELINE - NOT LEARNED AI DETECTIONS"
        }


class VisionEngine:
    """
    Industrial Computer Vision Inference Engine for Conveyor Belt Damage Detection.
    Loads actual trained YOLO weights when available, with fallback to BaselineCVAnalyzer.
    """

    def __init__(self, weights_path: Path = MODEL_WEIGHTS_PATH):
        self.weights_path = weights_path
        self._model = None
        self._load_model()
        ANALYSIS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def _load_model(self):
        """Attempts to load the trained YOLO model weights."""
        if self.weights_path.exists():
            try:
                from ultralytics import YOLO
                self._model = YOLO(str(self.weights_path))
                self.model_status = "TRAINED_MODEL"
                self.model_version = "conveyor-damage-detector-v1"
                logger.info("VisionEngine: Loaded trained YOLO model from %s", self.weights_path)
            except Exception as e:
                logger.warning("VisionEngine: Failed to load YOLO weights (%s). Reverting to baseline.", e)
                self._model = None
                self.model_status = "CLASSICAL_CV_BASELINE"
                self.model_version = BaselineCVAnalyzer.VERSION
        else:
            self._model = None
            self.model_status = "CLASSICAL_CV_BASELINE"
            self.model_version = BaselineCVAnalyzer.VERSION
            logger.info("VisionEngine: No trained weights found at %s. Operating in CLASSICAL_CV_BASELINE mode.", self.weights_path)

    def refresh_model(self):
        """Reloads model weights if a new training run has finished."""
        self._load_model()

    def analyze_frame(
        self,
        image_input: Any,
        camera_id: str = "CAM-SPLICE-01",
        joint_code: Optional[str] = None,
        source_type: str = "RESEARCH_DATASET",
        conf_threshold: float = 0.20,
        frame_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes an inspection frame and returns structured detections.

        Parameters:
        - image_input: np.ndarray, file Path, or bytes
        - camera_id: Identifier of the camera
        - joint_code: Joint code if camera is at a known joint position
        - source_type: RESEARCH_DATASET | LIVE_CAMERA | SIMULATION_TEST
        - conf_threshold: Minimum detection confidence
        - frame_name: Optional original filename of the frame
        """
        # 1. Decode / Load image
        img = None
        orig_filename = frame_name or "frame.jpg"
        if isinstance(image_input, (str, Path)):
            p = Path(image_input)
            orig_filename = frame_name or p.name
            img = cv2.imread(str(p))
        elif isinstance(image_input, bytes):
            nparr = np.frombuffer(image_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_input, np.ndarray):
            img = image_input

        if img is None:
            return {"error": "Failed to decode image"}

        h_orig, w_orig = img.shape[:2]
        timestamp_utc = datetime.now(timezone.utc).isoformat()
        obs_id = f"vis-obs-{uuid.uuid4().hex[:12]}"

        detections = []
        annotated_img = img.copy()

        # 2. Check model status & run detection
        if self._model is not None and self.model_status == "TRAINED_MODEL":
            # Run actual YOLO inference
            results = self._model.predict(img, conf=conf_threshold, verbose=False)
            res = results[0]

            for box in res.boxes:
                bx1, by1, bx2, by2 = [int(v) for v in box.xyxy[0]]
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                cls_name = CLASS_NAMES.get(cls_id, "damage")
                col = CATEGORY_COLORS.get(cls_name, (0, 255, 0))

                w_box = bx2 - bx1
                h_box = by2 - by1

                detections.append({
                    "class_name": cls_name,
                    "class_id": cls_id,
                    "confidence": round(conf, 4),
                    "bbox": [bx1, by1, w_box, h_box],
                    "area_px": w_box * h_box
                })

                # Draw bounding box & label on annotated frame
                cv2.rectangle(annotated_img, (bx1, by1), (bx2, by2), col, 2)
                label_text = f"{cls_name} {conf:.2f}"
                (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated_img, (bx1, max(0, by1 - th - 6)), (bx1 + tw + 4, max(th + 6, by1)), col, -1)
                cv2.putText(annotated_img, label_text, (bx1 + 2, max(th + 2, by1 - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

        else:
            # Run classical CV baseline
            baseline_res = BaselineCVAnalyzer.analyze_surface(img)
            for cand in baseline_res.get("candidates", []):
                x, y, w, h = cand["bbox"]
                detections.append({
                    "class_name": "damage_candidate",
                    "confidence": cand["confidence"],
                    "bbox": [x, y, w, h],
                    "area_px": cand["area_px"]
                })
                cv2.rectangle(annotated_img, (x, y), (x + w, y + h), (0, 165, 255), 2)
                cv2.putText(annotated_img, "BASELINE_GRADIENT", (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 165, 255), 1)

        # 3. Save annotated image frame
        annotated_filename = f"{obs_id}_{orig_filename}"
        annotated_path = ANALYSIS_OUTPUT_DIR / annotated_filename
        cv2.imwrite(str(annotated_path), annotated_img)

        # 4. Synthesize summary statistics (WITHOUT claiming crack or fake severity)
        total_detections = len(detections)
        has_damage = total_detections > 0
        primary_damage = "NORMAL_SURFACE"
        max_conf = 0.0

        if has_damage:
            # Sort by severity hierarchy or confidence: Large Tear > Large Hole > Small Tear > Small Hole > Belt Joint > damage
            severity_order = {"Large Tear": 5, "Large Hole": 4, "Small Tear": 3, "Small Hole": 2, "damage": 1, "Belt Joint": 0}
            sorted_dets = sorted(detections, key=lambda d: (severity_order.get(d["class_name"], 0), d["confidence"]), reverse=True)
            primary_damage = sorted_dets[0]["class_name"]
            max_conf = sorted_dets[0]["confidence"]

        # Prototype engineering threshold (transparently labeled)
        prototype_severity = "NORMAL"
        if has_damage:
            if primary_damage in {"Large Tear", "Large Hole"}:
                prototype_severity = "WARNING" if max_conf < 0.70 else "CRITICAL"
            elif primary_damage in {"Small Tear", "Small Hole"}:
                prototype_severity = "WATCH" if max_conf < 0.70 else "WARNING"
            elif primary_damage == "damage":
                prototype_severity = "WATCH"

        return {
            "observation_id": obs_id,
            "joint_code": joint_code,
            "camera_id": camera_id,
            "timestamp_utc": timestamp_utc,
            "model_status": self.model_status,
            "model_version": self.model_version,
            "source_type": source_type,
            "frame_name": orig_filename,
            "image_reference": f"/api/v1/vision/frame/{obs_id}",
            "local_frame_path": str(annotated_path),
            "total_detections": total_detections,
            "has_damage": has_damage,
            "primary_damage_type": primary_damage,
            "max_confidence": max_conf,
            "prototype_severity": prototype_severity,
            "severity_label": "PROTOTYPE ENGINEERING THRESHOLD — NOT ISO STANDARD",
            "detections": detections,
            "scientific_disclaimer": "Classes limited to COCO dataset annotations. Does not claim crack detection."
        }


# Global singleton instance
vision_engine = VisionEngine()
