"""
Joint Lifecycle & Degradation Trend Service (Phase 5)
=====================================================
Analyzes multi-revolution splice passage histories and tracks empirical degradation trends.

Core Scientific & Safety Guardrails:
1. No Fabricated RUL: Rupture dates and fatigue percentages are NEVER invented
   without verified longitudinal run-to-failure physical data.
2. Honest Labeling: Trends are strictly labeled "Observed Rate of Change" (g/rev).
3. Insufficient History Guardrail: Minimum 5 revolutions required to compute trend slopes;
   otherwise reports INSUFFICIENT_HISTORY rather than fitting noisy 2-point lines.
4. Tamper-Evident Maintenance Logging: All physical repairs, retensionings, and inspections
   are committed with SHA-256 integrity hashes and optional baseline resetting.
5. Authority Isolation: Deterministic SCADA safety states remain authoritative;
   lifecycle trends and ML inference remain maintenance advisories.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

import numpy as np
from sqlalchemy.orm import Session

from . import models, schemas
from .health_service import health_service
from .ml_service import vibration_anomaly_engine
from .websocket_manager import ws_manager

logger = logging.getLogger("joint_lifecycle_service")

MIN_TREND_REVOLUTIONS = 5

class JointLifecycleService:
    """Service providing joint degradation trend analysis, operational exposure tracking, and maintenance logs."""

    @staticmethod
    def log_maintenance(
        db: Session,
        log_in: schemas.MaintenanceLogCreate
    ) -> models.MaintenanceLog:
        """
        Records a physical maintenance intervention for a joint with cryptographic SHA-256 integrity.
        Optionally resets the rolling baseline if mechanical splice work was performed.
        """
        joint = db.query(models.Joint).filter(
            (models.Joint.id == log_in.joint_id) |
            (models.Joint.joint_code == log_in.joint_id)
        ).first()

        if not joint:
            raise ValueError(f"Joint '{log_in.joint_id}' not found in database.")

        now_utc = datetime.now(timezone.utc).isoformat()
        risk_before = joint.current_risk
        risk_after = "NORMAL" if log_in.baseline_reset else risk_before

        # Canonical content for tamper-evident hash
        canonical_str = (
            f"{joint.id}|{now_utc}|{log_in.technician_id}|{log_in.action_type.value}|"
            f"{log_in.notes or ''}|{risk_before}|{risk_after}|{1 if log_in.baseline_reset else 0}"
        )
        record_hash = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

        # If baseline reset requested, clear baseline in health service and reset joint risk
        if log_in.baseline_reset:
            health_service.reset_joint_baseline(joint.id)
            joint.current_risk = "NORMAL"
            joint.consecutive_abnormal_count = 0
            logger.info(f"Joint '{joint.id}' baseline and risk state reset following maintenance ({log_in.action_type.value})")

        m_log = models.MaintenanceLog(
            id=str(uuid.uuid4()),
            joint_id=joint.id,
            timestamp_utc=now_utc,
            technician_id=log_in.technician_id,
            action_type=log_in.action_type.value,
            notes=log_in.notes,
            risk_state_before=risk_before,
            risk_state_after=risk_after,
            baseline_reset=1 if log_in.baseline_reset else 0,
            data_provenance=log_in.data_provenance.value,
            record_hash=record_hash
        )

        db.add(m_log)
        db.commit()
        db.refresh(m_log)

        # Broadcast maintenance event to live SCADA HMI
        ws_manager.dispatch_json({
            "type": "MAINTENANCE_LOGGED",
            "log_id": m_log.id,
            "joint_id": joint.id,
            "joint_code": joint.joint_code,
            "action_type": m_log.action_type,
            "technician_id": m_log.technician_id,
            "baseline_reset": bool(m_log.baseline_reset),
            "timestamp_utc": m_log.timestamp_utc,
            "record_hash": m_log.record_hash
        })

        return m_log

    @staticmethod
    def get_joint_lifecycle_analysis(
        db: Session,
        joint_id_or_code: str
    ) -> Dict[str, Any]:
        """
        Computes multi-revolution lifecycle metrics, observed degradation rate of change,
        accumulated stress exposure, and synthesized multi-intelligence evidence.
        """
        joint = db.query(models.Joint).filter(
            (models.Joint.id == joint_id_or_code) |
            (models.Joint.joint_code == joint_id_or_code)
        ).first()

        if not joint:
            raise ValueError(f"Joint '{joint_id_or_code}' not found.")

        # Query all observations for this joint ordered by revolution_index
        observations = db.query(models.JointObservation).filter(
            models.JointObservation.joint_id == joint.id
        ).order_by(models.JointObservation.revolution_index.asc()).all()

        obs_count = len(observations)
        latest_obs = observations[-1] if observations else None

        # ── 1. Degradation Trend Analysis ─────────────────────────────────────
        valid_rms_points = [
            (obs.revolution_index, obs.rms_acceleration)
            for obs in observations
            if obs.rms_acceleration is not None and np.isfinite(obs.rms_acceleration)
        ]
        valid_kurt_points = [
            (obs.revolution_index, obs.kurtosis)
            for obs in observations
            if obs.kurtosis is not None and np.isfinite(obs.kurtosis)
        ]

        if len(valid_rms_points) < MIN_TREND_REVOLUTIONS:
            degradation_trend = {
                "trend_status": "INSUFFICIENT_HISTORY",
                "revolutions_observed": len(valid_rms_points),
                "min_revolutions_required": MIN_TREND_REVOLUTIONS,
                "rms_change_per_revolution": None,
                "kurtosis_change_per_revolution": None,
                "trend_direction": "INSUFFICIENT_DATA",
                "message": (
                    f"Minimum {MIN_TREND_REVOLUTIONS} observed revolutions required to calculate "
                    f"a reliable degradation rate without noise. Currently logged: {len(valid_rms_points)}."
                )
            }
        else:
            rev_indices = np.array([p[0] for p in valid_rms_points], dtype=float)
            rms_values = np.array([p[1] for p in valid_rms_points], dtype=float)

            # Linear regression: slope = d(RMS)/d(rev)
            rms_slope, _ = np.polyfit(rev_indices, rms_values, 1)

            # Kurtosis slope if points available
            if len(valid_kurt_points) >= MIN_TREND_REVOLUTIONS:
                kurt_revs = np.array([p[0] for p in valid_kurt_points], dtype=float)
                kurt_vals = np.array([p[1] for p in valid_kurt_points], dtype=float)
                kurt_slope, _ = np.polyfit(kurt_revs, kurt_vals, 1)
            else:
                kurt_slope = 0.0

            # Trend direction categorization
            if rms_slope > 0.005:
                direction = "ACCELERATING"
            elif rms_slope > 0.001:
                direction = "INCREASING_MODERATE"
            elif rms_slope < -0.001:
                direction = "DECREASING_SETTLING"
            else:
                direction = "STABLE"

            degradation_trend = {
                "trend_status": "ESTIMATED_OBSERVED_TREND",
                "revolutions_observed": len(valid_rms_points),
                "min_revolutions_required": MIN_TREND_REVOLUTIONS,
                "rms_change_per_revolution": round(float(rms_slope), 6),
                "kurtosis_change_per_revolution": round(float(kurt_slope), 6),
                "trend_direction": direction,
                "message": (
                    "Empirical vibration change rate per revolution computed across observed passages. "
                    "This is an empirical trend slope, not a physics rupture prediction."
                )
            }

        # ── 2. Operational Exposure ───────────────────────────────────────────
        # Estimate runtime hours based on nominal 850m belt @ 3.2 m/s (~265s = 0.0736h per rev)
        est_hours = round(joint.total_revolutions_count * (850.0 / 3.2 / 3600.0), 2)
        peak_acc = latest_obs.peak_acceleration if latest_obs and latest_obs.peak_acceleration else 0.0
        if peak_acc > 3.0:
            stress_class = "ELEVATED"
        elif peak_acc > 1.5:
            stress_class = "NOMINAL"
        else:
            stress_class = "LOW"

        operational_exposure = {
            "accumulated_revolutions": joint.total_revolutions_count,
            "estimated_runtime_hours": est_hours,
            "cycle_stress_class": stress_class
        }

        # ── 3. Multi-Evidence Synthesis ───────────────────────────────────────
        # A. Vibration DSP evidence
        dsp_evidence = {
            "health_score": latest_obs.health_score if latest_obs else 100.0,
            "risk_state": latest_obs.risk_state if latest_obs else joint.current_risk,
            "anomaly_detected": bool(latest_obs.anomaly_detected) if latest_obs else False,
            "rms_acceleration": latest_obs.rms_acceleration if latest_obs else None,
            "crest_factor": latest_obs.crest_factor if latest_obs else None,
            "kurtosis": latest_obs.kurtosis if latest_obs else None,
            "dominant_frequency_hz": latest_obs.dominant_frequency_hz if latest_obs else None,
            "baseline_status": latest_obs.baseline_status if latest_obs else "LEARNING"
        }

        # B. Phase 4 ML Anomaly Evidence
        ml_evidence = {"model_status": "ML_UNAVAILABLE"}
        if latest_obs and vibration_anomaly_engine.available:
            features = {
                "rms": latest_obs.rms_acceleration or 0.0,
                "peak": latest_obs.peak_acceleration or 0.0,
                "peak_to_peak": latest_obs.peak_to_peak_acceleration or 0.0,
                "crest_factor": latest_obs.crest_factor or 0.0,
                "kurtosis": latest_obs.kurtosis or 0.0,
                "skewness": latest_obs.skewness or 0.0,
                "dominant_freq_hz": latest_obs.dominant_frequency_hz or 0.0,
                "spectral_energy": latest_obs.spectral_energy or 0.0,
                "speed_rpm": latest_obs.drive_rpm,
                "pretension_n": latest_obs.pretension_n,
            }
            try:
                ml_evidence = vibration_anomaly_engine.score_features(features)
            except Exception as e:
                ml_evidence = {"model_status": "SCORING_ERROR", "error": str(e)}

        # C. Vision Evidence
        latest_vis = db.query(models.VisionObservation).filter(
            (models.VisionObservation.joint_id == joint.id) |
            (models.VisionObservation.joint_code == joint.joint_code)
        ).order_by(models.VisionObservation.timestamp_utc.desc()).first()

        vision_evidence = {
            "inspected": latest_vis is not None,
            "primary_damage_type": latest_vis.primary_damage_type if latest_vis else "NONE_DETECTED",
            "max_confidence": latest_vis.max_confidence if latest_vis else 0.0,
            "detections_count": latest_vis.total_detections_count if latest_vis else 0,
            "inspection_timestamp_utc": latest_vis.timestamp_utc if latest_vis else None
        }

        # D. Maintenance History
        maintenance_logs = db.query(models.MaintenanceLog).filter(
            models.MaintenanceLog.joint_id == joint.id
        ).order_by(models.MaintenanceLog.timestamp_utc.desc()).limit(5).all()

        m_history = [
            {
                "id": m.id,
                "timestamp_utc": m.timestamp_utc,
                "technician_id": m.technician_id,
                "action_type": m.action_type,
                "notes": m.notes,
                "baseline_reset": bool(m.baseline_reset),
                "record_hash": m.record_hash
            }
            for m in maintenance_logs
        ]

        # ── 4. Scientific & Safety Guardrails ─────────────────────────────────
        guardrails = {
            "rupture_prediction": False,
            "rul_prediction": "NOT_PREDICTABLE_WITHOUT_LONGITUDINAL_FAILURE_DATA",
            "fatigue_percentage": None,
            "data_provenance": latest_obs.data_provenance if latest_obs else "UNKNOWN",
            "disclaimer": (
                "Deterministic SCADA safety state remains authoritative. Observed degradation "
                "trends and ML scores provide maintenance advisory evidence only and do not replace "
                "mechanical non-destructive testing (NDT)."
            )
        }

        return {
            "joint_id": joint.id,
            "joint_code": joint.joint_code,
            "splice_type": joint.splice_type,
            "installation_date": joint.installation_date,
            "total_revolutions_count": joint.total_revolutions_count,
            "current_risk": joint.current_risk,
            "consecutive_abnormal_count": joint.consecutive_abnormal_count,
            "last_passage_timestamp_utc": joint.last_passage_timestamp_utc,
            "baseline_status": latest_obs.baseline_status if (latest_obs and latest_obs.baseline_status) else "LEARNING",
            "degradation_trend": degradation_trend,
            "operational_exposure": operational_exposure,
            "evidence_synthesis": {
                "vibration_dsp": dsp_evidence,
                "vibration_ml": ml_evidence,
                "vision_inspection": vision_evidence,
                "recent_maintenance": m_history
            },
            "safety_and_integrity_guardrails": guardrails
        }

joint_lifecycle_service = JointLifecycleService()
