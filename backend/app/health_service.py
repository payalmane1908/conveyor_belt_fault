"""
Health Assessment Service — Phase 3 Intelligence Layer
=======================================================
Converts raw vibration bursts into joint-specific condition intelligence:

    Raw Burst
        → DSP Feature Extraction
        → Baseline / Deviation Analysis
        → Health Score (multi-factor, configurable)
        → Risk State Machine (with hysteresis)
        → Anomaly Detection
        → AlertEvent Generation
        → JointObservation Persistence
        → WebSocket Broadcast

Design principles
-----------------
- All thresholds are labeled as engineering_threshold or baseline_derived_threshold.
- No ISO compliance is claimed.
- Temperature contribution is DISABLED — no temperature telemetry exists.
- Kurtosis: Fisher/excess convention throughout (Gaussian ≈ 0).
- Baseline uses rolling median + MAD (robust against single outliers).
- Only NORMAL observations update the baseline (prevents contamination).
- One noisy sample cannot flip NORMAL → CRITICAL in a single step.
- Every alert message is evidence-based and avoids claiming physical damage.
"""

import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Deque

import numpy as np
from sqlalchemy.orm import Session

from . import models
from .config import settings
from .dsp import DSPAnalyzer, DSPResult, TimeDomainFeatures, FFTFeatures
from .ingestion import deserialize_samples

logger = logging.getLogger("health_service")

# ---------------------------------------------------------------------------
# Baseline Status Labels
# ---------------------------------------------------------------------------
BASELINE_LEARNING = "LEARNING"          # Fewer than MIN_BASELINE_OBSERVATIONS
BASELINE_ACTIVE = "ACTIVE"              # Baseline is reliable
BASELINE_INSUFFICIENT = "INSUFFICIENT"  # Corrupted or too few normal obs

# ---------------------------------------------------------------------------
# Risk States
# ---------------------------------------------------------------------------
RISK_NORMAL = "NORMAL"
RISK_WATCH = "WATCH"
RISK_WARNING = "WARNING"
RISK_CRITICAL = "CRITICAL"

RISK_ORDER = [RISK_NORMAL, RISK_WATCH, RISK_WARNING, RISK_CRITICAL]

# ---------------------------------------------------------------------------
# Alert Types
# ---------------------------------------------------------------------------
ALERT_VIBRATION_SPIKE = "VIBRATION_SPIKE"
ALERT_SPLICE_FATIGUE = "SPLICE_FATIGUE_IMPACT"
ALERT_HARMONIC = "HARMONIC_RESONANCE"
ALERT_CONSECUTIVE = "CONSECUTIVE_ABNORMAL"


# ---------------------------------------------------------------------------
# Per-Joint Baseline State (in-memory rolling window)
# ---------------------------------------------------------------------------

@dataclass
class JointBaseline:
    """
    Rolling baseline state for a single joint.

    Uses rolling median + MAD as robust estimators:
        baseline_median = median(last N normal observations)
        baseline_MAD    = median(|x_i - median|)
        robust_sigma    = MAD * 1.4826  (consistent with Gaussian σ)

    Only observations with risk_state == NORMAL are admitted to the window.
    This prevents a run of critical anomalies from immediately redefining
    what is "normal" for this joint.
    """
    joint_id: str
    rms_window: Deque[float] = field(default_factory=lambda: deque(maxlen=settings.BASELINE_ROLLING_WINDOW))
    crest_factor_window: Deque[float] = field(default_factory=lambda: deque(maxlen=settings.BASELINE_ROLLING_WINDOW))
    kurtosis_window: Deque[float] = field(default_factory=lambda: deque(maxlen=settings.BASELINE_ROLLING_WINDOW))
    dominant_freq_window: Deque[float] = field(default_factory=lambda: deque(maxlen=settings.BASELINE_ROLLING_WINDOW))

    @property
    def n_observations(self) -> int:
        return len(self.rms_window)

    @property
    def status(self) -> str:
        if self.n_observations < settings.BASELINE_MIN_OBSERVATIONS:
            return BASELINE_LEARNING
        return BASELINE_ACTIVE

    def update(self, rms: float, crest_factor: float, kurtosis: float, dominant_freq: Optional[float]):
        """Add a new NORMAL observation to the rolling window."""
        self.rms_window.append(rms)
        self.crest_factor_window.append(crest_factor)
        self.kurtosis_window.append(kurtosis)
        if dominant_freq is not None:
            self.dominant_freq_window.append(dominant_freq)

    def get_median_mad(self, window: Deque[float]) -> Tuple[Optional[float], Optional[float]]:
        """Return (median, MAD) for a window. Returns (None, None) if insufficient data."""
        if len(window) < settings.BASELINE_MIN_OBSERVATIONS:
            return None, None
        arr = np.array(list(window))
        median = float(np.median(arr))
        mad = float(np.median(np.abs(arr - median)))
        return median, mad

    def compute_deviation(self, value: float, median: Optional[float], mad: Optional[float]) -> Optional[float]:
        """
        Compute robust z-score (σ-equivalent deviation):
            deviation = (value - median) / (MAD * 1.4826)

        The factor 1.4826 makes MAD-based scale consistent with Gaussian σ.
        Returns None when baseline is insufficient.
        Returns 0.0 when MAD is zero and value equals median.
        Returns a capped large finite value (99.0) when MAD is zero but value differs,
        to prevent JSON serialization failures with float('inf').
        """
        if median is None or mad is None:
            return None
        scale = mad * 1.4826
        if scale < 1e-10:
            # MAD is zero: all baseline values are identical.
            # If value matches, deviation = 0; otherwise cap at large sentinel.
            return 0.0 if abs(value - median) < 1e-10 else 99.0
        deviation = float((value - median) / scale)
        # Cap to prevent JSON serialization of inf/-inf
        return max(-99.0, min(99.0, deviation))


# ---------------------------------------------------------------------------
# Per-Joint Risk State Tracker (in-memory)
# ---------------------------------------------------------------------------

@dataclass
class JointRiskState:
    """
    Tracks consecutive anomaly and recovery counts for risk state hysteresis.

    Escalation requires consecutive anomalous observations above threshold.
    Recovery requires consecutive healthy observations to step down one level.

    One noisy sample cannot flip NORMAL → CRITICAL in a single step.
    """
    joint_id: str
    current_risk: str = RISK_NORMAL
    consecutive_abnormal: int = 0
    consecutive_healthy: int = 0

    def update(self, anomaly_detected: bool, health_score: float) -> str:
        """
        Apply hysteresis rules and return the new risk state.

        Escalation path: NORMAL → WATCH → WARNING → CRITICAL
        Recovery path:   CRITICAL → WARNING → WATCH → NORMAL

        Parameters
        ----------
        anomaly_detected : bool
        health_score : float  (0–100)

        Returns
        -------
        str : new risk state after applying hysteresis
        """
        if anomaly_detected:
            self.consecutive_abnormal += 1
            self.consecutive_healthy = 0  # reset recovery streak
        else:
            self.consecutive_healthy += 1
            self.consecutive_abnormal = 0  # reset escalation streak

        # ── Escalation ──────────────────────────────────────────────────────
        # Determine target state purely from health score bands
        target_from_score = self._health_to_risk(health_score)
        current_idx = RISK_ORDER.index(self.current_risk)
        target_idx = RISK_ORDER.index(target_from_score)

        if target_idx > current_idx:
            # Check if we've hit the escalation threshold
            if target_idx - current_idx == 1:
                # Step up one level
                if self.consecutive_abnormal >= settings.WARNING_CONSECUTIVE_ANOMALIES:
                    self.current_risk = RISK_ORDER[current_idx + 1]
            else:
                # Jump multiple levels — still needs consecutive threshold
                if self.consecutive_abnormal >= settings.CRITICAL_CONSECUTIVE_ANOMALIES:
                    self.current_risk = target_from_score
                elif self.consecutive_abnormal >= settings.WARNING_CONSECUTIVE_ANOMALIES:
                    self.current_risk = RISK_ORDER[min(current_idx + 1, len(RISK_ORDER) - 1)]

        # ── Recovery ─────────────────────────────────────────────────────────
        elif target_idx < current_idx and not anomaly_detected:
            if self.consecutive_healthy >= settings.RECOVERY_OBSERVATIONS_REQUIRED:
                # Step down one level (gradual recovery)
                new_idx = max(0, current_idx - 1)
                self.current_risk = RISK_ORDER[new_idx]
                self.consecutive_healthy = 0  # reset after step-down

        return self.current_risk

    @staticmethod
    def _health_to_risk(health_score: float) -> str:
        """Map a health score to the corresponding risk band."""
        if health_score >= settings.HEALTH_BAND_NORMAL_MIN:
            return RISK_NORMAL
        elif health_score >= settings.HEALTH_BAND_WATCH_MIN:
            return RISK_WATCH
        elif health_score >= settings.HEALTH_BAND_WARNING_MIN:
            return RISK_WARNING
        else:
            return RISK_CRITICAL


# ---------------------------------------------------------------------------
# In-memory joint state registry
# ---------------------------------------------------------------------------

class JointStateRegistry:
    """
    Maintains in-memory per-joint baseline and risk state objects.

    Thread safety note: FastAPI uses asyncio — these are accessed from
    async routes which run in a single event loop thread, so no lock is
    required for the registry itself. The SQLite session is the authoritative
    persistent store; this registry is a performance cache for the rolling
    window and hysteresis state.
    """
    def __init__(self):
        self._baselines: Dict[str, JointBaseline] = {}
        self._risks: Dict[str, JointRiskState] = {}

    def get_baseline(self, joint_id: str) -> JointBaseline:
        if joint_id not in self._baselines:
            self._baselines[joint_id] = JointBaseline(joint_id=joint_id)
        return self._baselines[joint_id]

    def get_risk(self, joint_id: str, db_risk: str = RISK_NORMAL) -> JointRiskState:
        if joint_id not in self._risks:
            self._risks[joint_id] = JointRiskState(joint_id=joint_id, current_risk=db_risk)
        return self._risks[joint_id]

    def bootstrap_from_db(self, joint_id: str, db: Session):
        """
        On first access for a joint, pre-populate the rolling baseline window
        from the most recent NORMAL observations stored in the database.
        Called lazily on first health assessment for a joint.
        """
        if joint_id in self._baselines:
            return  # Already loaded

        baseline = JointBaseline(joint_id=joint_id)
        recent_normal = (
            db.query(models.JointObservation)
            .filter(
                models.JointObservation.joint_id == joint_id,
                models.JointObservation.risk_state == RISK_NORMAL,
                models.JointObservation.rms_acceleration.isnot(None),
            )
            .order_by(models.JointObservation.revolution_index.desc())
            .limit(settings.BASELINE_ROLLING_WINDOW)
            .all()
        )
        # Load in chronological order (oldest first into window)
        for obs in reversed(recent_normal):
            if obs.rms_acceleration and obs.crest_factor and obs.kurtosis:
                baseline.update(
                    rms=obs.rms_acceleration,
                    crest_factor=obs.crest_factor,
                    kurtosis=obs.kurtosis,
                    dominant_freq=obs.dominant_frequency_hz,
                )
        self._baselines[joint_id] = baseline

        # Restore risk state from DB
        joint = db.query(models.Joint).filter(models.Joint.id == joint_id).first()
        if joint:
            self._risks[joint_id] = JointRiskState(
                joint_id=joint_id,
                current_risk=joint.current_risk,
                consecutive_abnormal=joint.consecutive_abnormal_count,
            )

    def reset_joint(self, joint_id: str):
        """Clears rolling baseline and resets risk state following mechanical splice maintenance."""
        self._baselines[joint_id] = JointBaseline(joint_id=joint_id)
        self._risks[joint_id] = JointRiskState(joint_id=joint_id, current_risk=RISK_NORMAL)


# Module-level singleton registry
_registry = JointStateRegistry()


# ---------------------------------------------------------------------------
# Health Score Calculator
# ---------------------------------------------------------------------------

def calculate_health_score(
    td: TimeDomainFeatures,
    fft: Optional[FFTFeatures],
    baseline: JointBaseline,
    rms_deviation: Optional[float],
    crest_deviation: Optional[float],
    kurtosis_deviation: Optional[float],
    consecutive_abnormal: int,
) -> float:
    """
    Multi-factor health score calculation.

    Health Score = 100 - vibration_penalty - shock_penalty - frequency_penalty - persistence_penalty
    Clipped to [0, 100].

    All penalties are in range [0, 100] before weighting.

    Component weights (configurable in settings):
        vibration:   35%  — RMS / vibration severity
        shock:       30%  — crest factor + kurtosis impulsive content
        frequency:   15%  — spectral / dominant frequency deviation
        persistence: 20%  — consecutive abnormal count

    Temperature: DISABLED — no temperature telemetry; will not fabricate data.
    """
    # ── 1. Vibration Severity Component ──────────────────────────────────────
    vibration_raw = 0.0
    if baseline.status == BASELINE_ACTIVE and rms_deviation is not None:
        # Baseline-derived penalty: scales from 0 at 0σ to 100 at 5σ
        vibration_raw = min(100.0, max(0.0, (abs(rms_deviation) / 5.0) * 100.0))
    else:
        # No baseline yet — use absolute engineering threshold
        # Scale: 0 at 0, 100 at ABS_RMS_ALERT_THRESHOLD
        vibration_raw = min(100.0, (td.rms / settings.ABS_RMS_ALERT_THRESHOLD) * 100.0)

    # ── 2. Shock / Impulsive Behavior Component ───────────────────────────────
    # Uses crest factor and kurtosis relative to engineering thresholds
    crest_norm = min(1.0, td.crest_factor / settings.ABS_CREST_FACTOR_THRESHOLD)
    kurtosis_norm = min(1.0, max(0.0, td.kurtosis) / settings.ABS_KURTOSIS_THRESHOLD)

    if baseline.status == BASELINE_ACTIVE:
        if crest_deviation is not None:
            crest_component = min(1.0, abs(crest_deviation) / 5.0)
        else:
            crest_component = crest_norm
        if kurtosis_deviation is not None:
            kurt_component = min(1.0, abs(kurtosis_deviation) / 5.0)
        else:
            kurt_component = kurtosis_norm
    else:
        crest_component = crest_norm
        kurt_component = kurtosis_norm

    shock_raw = min(100.0, ((crest_component + kurt_component) / 2.0) * 100.0)

    # ── 3. Frequency Component ─────────────────────────────────────────────────
    frequency_raw = 0.0
    if fft is not None:
        baseline_med, baseline_mad = baseline.get_median_mad(baseline.dominant_freq_window)
        if baseline_med is not None and baseline_med > 0.0:
            pct_dev = abs(fft.dominant_frequency_hz - baseline_med) / baseline_med * 100.0
            # Scale: 0 at 0%, 100 at ABS_FREQ_DEVIATION_PCT_THRESHOLD%
            frequency_raw = min(100.0, (pct_dev / settings.ABS_FREQ_DEVIATION_PCT_THRESHOLD) * 100.0)
        # If no baseline yet, frequency component is 0 (no penalty)

    # ── 4. Persistence Component ─────────────────────────────────────────────
    max_for_full = settings.MAX_CONSECUTIVE_FOR_FULL_PENALTY
    persistence_raw = min(100.0, (consecutive_abnormal / max_for_full) * 100.0)

    # ── Weighted Sum ──────────────────────────────────────────────────────────
    w = settings
    total_penalty = (
        vibration_raw * w.HEALTH_WEIGHT_VIBRATION +
        shock_raw * w.HEALTH_WEIGHT_SHOCK +
        frequency_raw * w.HEALTH_WEIGHT_FREQUENCY +
        persistence_raw * w.HEALTH_WEIGHT_PERSISTENCE
    )

    health = max(0.0, min(100.0, 100.0 - total_penalty))
    return round(health, 2)


# ---------------------------------------------------------------------------
# Anomaly Classification
# ---------------------------------------------------------------------------

def classify_anomaly(
    td: TimeDomainFeatures,
    fft: Optional[FFTFeatures],
    baseline: JointBaseline,
    rms_deviation: Optional[float],
    crest_deviation: Optional[float],
    kurtosis_deviation: Optional[float],
    consecutive_abnormal: int,
) -> Tuple[bool, List[str]]:
    """
    Determine if this observation is anomalous, and explain why.

    Returns (anomaly_detected, list_of_triggered_reasons).

    Anomaly triggers (any ONE is sufficient):
    A. Absolute RMS exceeds engineering threshold
    B. Baseline RMS deviation exceeds σ threshold (baseline_derived_threshold)
    C. Shock: both crest factor AND kurtosis exceed engineering thresholds
    D. Frequency deviation from baseline exceeds threshold
    E. Persistence: consecutive_abnormal already at WARNING level
    """
    reasons = []

    # A. Absolute RMS engineering threshold
    if td.rms > settings.ABS_RMS_ALERT_THRESHOLD:
        reasons.append(
            f"RMS {td.rms:.3f} exceeds engineering_threshold {settings.ABS_RMS_ALERT_THRESHOLD}"
        )

    # B. Baseline RMS deviation
    if rms_deviation is not None and abs(rms_deviation) > settings.BASELINE_SIGMA_ALERT_THRESHOLD:
        reasons.append(
            f"RMS deviation +{rms_deviation:.2f}σ exceeds baseline_derived_threshold "
            f"±{settings.BASELINE_SIGMA_ALERT_THRESHOLD}σ"
        )

    # C. Shock behavior (both metrics must be elevated to reduce false positives)
    if (td.crest_factor > settings.ABS_CREST_FACTOR_THRESHOLD and
            td.kurtosis > settings.ABS_KURTOSIS_THRESHOLD):
        reasons.append(
            f"Impulsive vibration anomaly: crest_factor={td.crest_factor:.2f} "
            f"(threshold {settings.ABS_CREST_FACTOR_THRESHOLD}), "
            f"kurtosis={td.kurtosis:.2f} (threshold {settings.ABS_KURTOSIS_THRESHOLD})"
        )

    # D. Frequency deviation
    if fft is not None and baseline.status == BASELINE_ACTIVE:
        baseline_med, _ = baseline.get_median_mad(baseline.dominant_freq_window)
        if baseline_med is not None and baseline_med > 0.0:
            pct_dev = abs(fft.dominant_frequency_hz - baseline_med) / baseline_med * 100.0
            if pct_dev > settings.ABS_FREQ_DEVIATION_PCT_THRESHOLD:
                reasons.append(
                    f"Dominant frequency {fft.dominant_frequency_hz:.1f} Hz deviates "
                    f"{pct_dev:.1f}% from baseline {baseline_med:.1f} Hz "
                    f"(threshold {settings.ABS_FREQ_DEVIATION_PCT_THRESHOLD}%)"
                )

    # NOTE: Persistence (consecutive_abnormal_count) is NOT used as an anomaly trigger here.
    # It contributes to the health score via the persistence weight component, which lowers the
    # health score during active anomaly runs. Using it as a direct anomaly trigger creates a
    # feedback loop: a healthy signal would be flagged anomalous solely because previous signals
    # were anomalous, preventing recovery. Persistence severity is captured in risk state escalation.

    return len(reasons) > 0, reasons


# ---------------------------------------------------------------------------
# Alert Message Builder
# ---------------------------------------------------------------------------

def determine_alert_types(
    td: TimeDomainFeatures,
    fft: Optional[FFTFeatures],
    anomaly_reasons: List[str],
) -> List[Tuple[str, str]]:
    """
    Map triggered anomaly reasons to alert types.
    Returns list of (alert_type, severity) pairs.
    """
    alerts = []
    reason_text = " ".join(anomaly_reasons).lower()

    if "rms" in reason_text and ("exceeds engineering_threshold" in reason_text or "deviation" in reason_text):
        alerts.append((ALERT_VIBRATION_SPIKE, RISK_WARNING))

    if "impulsive vibration anomaly" in reason_text:
        alerts.append((ALERT_SPLICE_FATIGUE, RISK_WARNING))

    if "dominant frequency" in reason_text and "deviates" in reason_text:
        alerts.append((ALERT_HARMONIC, RISK_WARNING))

    if "consecutive abnormal" in reason_text:
        alerts.append((ALERT_CONSECUTIVE, RISK_WARNING))

    return alerts


def build_alert_message(
    joint: models.Joint,
    td: TimeDomainFeatures,
    fft: Optional[FFTFeatures],
    alert_type: str,
    risk_state: str,
    revolution_index: int,
    anomaly_reasons: List[str],
    rms_deviation: Optional[float],
    consecutive_abnormal: int,
    data_provenance: str,
) -> str:
    """
    Build an evidence-based, explainable alert message.

    Uses language that conveys anomaly detection without claiming physical damage.
    """
    provenance_tag = f"[{data_provenance}]" if data_provenance != "LIVE" else ""
    header = f"{provenance_tag} Joint {joint.joint_code} — {alert_type.replace('_', ' ')}"

    lines = [header, ""]

    if alert_type == ALERT_VIBRATION_SPIKE:
        lines.append(f"Elevated vibration amplitude detected.")
        lines.append(f"  RMS: {td.rms:.4f}")
        if rms_deviation is not None:
            lines.append(f"  RMS deviation from baseline: +{rms_deviation:.2f}σ (baseline_derived_threshold ±{settings.BASELINE_SIGMA_ALERT_THRESHOLD}σ)")
        lines.append(f"  Peak: {td.peak:.4f}")
        lines.append(f"  Crest factor: {td.crest_factor:.2f}")

    elif alert_type == ALERT_SPLICE_FATIGUE:
        lines.append("Persistent impulsive vibration anomaly detected.")
        lines.append("  This is consistent with impact/shock behavior at the splice.")
        lines.append("  Physical inspection is recommended — this is NOT proof of physical damage.")
        lines.append(f"  Crest factor: {td.crest_factor:.2f} (engineering_threshold {settings.ABS_CREST_FACTOR_THRESHOLD})")
        lines.append(f"  Kurtosis (Fisher): {td.kurtosis:.2f} (engineering_threshold {settings.ABS_KURTOSIS_THRESHOLD})")
        if rms_deviation is not None:
            lines.append(f"  RMS deviation: +{rms_deviation:.2f}σ")

    elif alert_type == ALERT_HARMONIC:
        dom_freq = fft.dominant_frequency_hz if fft else "N/A"
        lines.append("Unexpected frequency content detected.")
        lines.append(f"  Dominant frequency: {dom_freq} Hz")
        lines.append("  Spectral deviation from baseline pattern observed.")
        lines.append("  May indicate mechanical looseness, resonance, or belt slip.")

    elif alert_type == ALERT_CONSECUTIVE:
        lines.append(f"Persistent abnormal condition: {consecutive_abnormal} consecutive abnormal passages.")
        lines.append(f"  RMS: {td.rms:.4f}")
        lines.append(f"  Crest factor: {td.crest_factor:.2f}")
        lines.append(f"  Kurtosis: {td.kurtosis:.2f}")

    lines.append("")
    lines.append(f"  Revolution #{revolution_index} | Risk state escalated to: {risk_state}")
    lines.append(f"  Investigation required — ANOMALY DETECTED, not failure confirmed.")
    lines.append("")
    lines.append("  Triggered conditions:")
    for r in anomaly_reasons:
        lines.append(f"    • {r}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main Health Assessment Service
# ---------------------------------------------------------------------------

class HealthAssessmentService:
    """
    Orchestrates the complete Phase 3 health intelligence pipeline.

    Call process_burst() after a RawVibrationBurst has been persisted.
    """

    def __init__(self):
        self._dsp = DSPAnalyzer()

    def process_burst(
        self,
        db: Session,
        burst: models.RawVibrationBurst,
    ) -> Optional[models.JointObservation]:
        """
        Full health pipeline for one RawVibrationBurst.

        Returns the created JointObservation, or None if:
        - No joint_id on the burst
        - DSP analysis failed on malformed data
        - Database errors

        Never raises an exception — logs errors and returns None to prevent
        crashing the ingestion pipeline.
        """
        try:
            return self._run_pipeline(db, burst)
        except Exception as exc:
            logger.error(
                "HealthAssessmentService: pipeline error for burst %s: %s",
                burst.id, exc, exc_info=True
            )
            return None

    def _run_pipeline(
        self,
        db: Session,
        burst: models.RawVibrationBurst,
    ) -> Optional[models.JointObservation]:
        """Internal pipeline — exceptions propagate to process_burst for logging."""

        # ── 1. Load + validate joint ──────────────────────────────────────────
        joint = None
        if burst.joint_id:
            joint = db.query(models.Joint).filter(
                (models.Joint.id == burst.joint_id) |
                (models.Joint.joint_code == burst.joint_id)
            ).first()
        if joint is None:
            # Fallback to first registered joint if any exists
            joint = db.query(models.Joint).first()

        # ── 2. Unpack raw samples ─────────────────────────────────────────────
        try:
            samples = deserialize_samples(burst.raw_samples_blob)
        except Exception as e:
            logger.error("Health pipeline: cannot deserialize samples for burst %s: %s", burst.id, e)
            return None

        if not samples or len(samples) < 2:
            logger.warning("Health pipeline: burst %s has too few samples (%d).", burst.id, len(samples))
            return None

        # ── 3. DSP Analysis ───────────────────────────────────────────────────
        dsp_result: DSPResult = self._dsp.analyze(samples, burst.sampling_rate_hz)
        if not dsp_result.valid:
            logger.warning(
                "Health pipeline: DSP rejected burst %s: %s",
                burst.id, dsp_result.rejection_reason
            )
            return None

        td: TimeDomainFeatures = dsp_result.time_domain
        fft: Optional[FFTFeatures] = dsp_result.fft

        if joint is None:
            # Broadcast unassociated burst DSP so UI FFT & metrics update live
            from .websocket_manager import ws_manager
            ws_manager.dispatch_json({
                "type": "HEALTH_UPDATE",
                "joint_id": "UNASSIGNED",
                "joint_code": "GENERAL_STREAM",
                "health_score": 100.0,
                "risk_state": "NORMAL",
                "revolution_index": burst.sequence_number,
                "anomaly_detected": False,
                "data_provenance": burst.data_provenance,
                "baseline_status": "INSUFFICIENT",
                "metrics": {
                    "rms": td.rms,
                    "peak": td.peak,
                    "crest_factor": td.crest_factor,
                    "kurtosis": td.kurtosis,
                    "skewness": td.skewness,
                    "dominant_frequency_hz": fft.dominant_frequency_hz if fft else None,
                    "spectral_energy": fft.spectral_energy if fft else None,
                    "rms_deviation": None,
                    "consecutive_abnormal": 0,
                },
                "fft_bins": {
                    "frequencies": fft.frequency_bins_hz[:256] if fft else [],
                    "amplitudes": fft.amplitude_spectrum[:256] if fft else [],
                    "dominant_hz": fft.dominant_frequency_hz if fft else None,
                    "dominant_amplitude": fft.dominant_amplitude if fft else None,
                    "spectral_centroid_hz": fft.spectral_centroid_hz if fft else None,
                } if fft else None,
                "timestamp_utc": burst.received_at_utc,
            })
            return None

        # ── 4. Bootstrap + obtain baseline ────────────────────────────────────
        _registry.bootstrap_from_db(joint.id, db)
        baseline: JointBaseline = _registry.get_baseline(joint.id)

        # ── 5. Compute deviations ─────────────────────────────────────────────
        rms_med, rms_mad = baseline.get_median_mad(baseline.rms_window)
        cf_med, cf_mad = baseline.get_median_mad(baseline.crest_factor_window)
        krt_med, krt_mad = baseline.get_median_mad(baseline.kurtosis_window)

        rms_deviation = baseline.compute_deviation(td.rms, rms_med, rms_mad)
        crest_deviation = baseline.compute_deviation(td.crest_factor, cf_med, cf_mad)
        kurtosis_deviation = baseline.compute_deviation(td.kurtosis, krt_med, krt_mad)

        # ── 6. Load risk state tracker ────────────────────────────────────────
        risk_tracker: JointRiskState = _registry.get_risk(joint.id, joint.current_risk)

        # ── 7. Anomaly detection ──────────────────────────────────────────────
        anomaly_detected, anomaly_reasons = classify_anomaly(
            td, fft, baseline,
            rms_deviation, crest_deviation, kurtosis_deviation,
            risk_tracker.consecutive_abnormal,
        )

        # ── 8. Health score ───────────────────────────────────────────────────
        health_score = calculate_health_score(
            td, fft, baseline,
            rms_deviation, crest_deviation, kurtosis_deviation,
            risk_tracker.consecutive_abnormal,
        )

        # ── 9. Risk state machine ─────────────────────────────────────────────
        new_risk = risk_tracker.update(anomaly_detected, health_score)

        # ── 10. Update baseline (only from NORMAL observations) ───────────────
        if new_risk == RISK_NORMAL:
            baseline.update(
                rms=td.rms,
                crest_factor=td.crest_factor,
                kurtosis=td.kurtosis,
                dominant_freq=fft.dominant_frequency_hz if fft else None,
            )

        # ── 11. Increment revolution counter ─────────────────────────────────
        joint.total_revolutions_count += 1
        revolution_index = joint.total_revolutions_count
        joint.last_passage_timestamp_utc = datetime.now(timezone.utc).isoformat()
        joint.current_risk = new_risk
        joint.consecutive_abnormal_count = risk_tracker.consecutive_abnormal

        # ── 12. Determine conveyor_id from belt relationship ──────────────────
        conveyor_id = None
        if joint.belt_id:
            belt = db.query(models.Belt).filter(models.Belt.id == joint.belt_id).first()
            if belt:
                conveyor_id = belt.conveyor_id

        # ── 13. Persist JointObservation ──────────────────────────────────────
        now_utc = datetime.now(timezone.utc).isoformat()
        obs = models.JointObservation(
            id=str(uuid.uuid4()),
            joint_id=joint.id,
            conveyor_id=conveyor_id,
            revolution_index=revolution_index,
            observation_timestamp_utc=now_utc,
            timestamp_utc=now_utc,
            operating_state="STEADY_LOADED",
            sampling_rate_hz=burst.sampling_rate_hz,
            data_provenance=burst.data_provenance,
            raw_burst_id=burst.id,
            drive_rpm=burst.drive_rpm,
            pretension_n=burst.pretension_n,
            # Time-domain
            rms_acceleration=td.rms,
            peak_acceleration=td.peak,
            peak_to_peak_acceleration=td.peak_to_peak,
            crest_factor=td.crest_factor,
            kurtosis=td.kurtosis,
            skewness=td.skewness,
            # Frequency-domain
            dominant_frequency_hz=fft.dominant_frequency_hz if fft else None,
            dominant_frequency_amplitude=fft.dominant_amplitude if fft else None,
            spectral_centroid_hz=fft.spectral_centroid_hz if fft else None,
            spectral_energy=fft.spectral_energy if fft else None,
            # Health
            health_score=health_score,
            anomaly_detected=1 if anomaly_detected else 0,
            risk_state=new_risk,
            # Baseline
            baseline_rms=rms_med,
            baseline_crest_factor=cf_med,
            baseline_kurtosis=krt_med,
            baseline_dominant_freq=(
                baseline.get_median_mad(baseline.dominant_freq_window)[0]
                if len(baseline.dominant_freq_window) >= settings.BASELINE_MIN_OBSERVATIONS
                else None
            ),
            baseline_status=baseline.status,
            # Deviations
            rms_deviation=rms_deviation,
            crest_factor_deviation=crest_deviation,
            kurtosis_deviation=kurtosis_deviation,
            # Persistence
            consecutive_abnormal_count_snapshot=risk_tracker.consecutive_abnormal,
        )
        db.add(obs)

        # ── 14. Generate alerts ───────────────────────────────────────────────
        created_alerts: List[models.AlertEvent] = []
        if anomaly_detected:
            alert_type_severities = determine_alert_types(td, fft, anomaly_reasons)
            for alert_type, _ in alert_type_severities:
                # Map risk state to alert severity
                severity = new_risk if new_risk != RISK_NORMAL else RISK_WATCH
                msg = build_alert_message(
                    joint=joint,
                    td=td,
                    fft=fft,
                    alert_type=alert_type,
                    risk_state=new_risk,
                    revolution_index=revolution_index,
                    anomaly_reasons=anomaly_reasons,
                    rms_deviation=rms_deviation,
                    consecutive_abnormal=risk_tracker.consecutive_abnormal,
                    data_provenance=burst.data_provenance,
                )
                metrics_snap = {
                    "rms": td.rms,
                    "peak": td.peak,
                    "crest_factor": td.crest_factor,
                    "kurtosis": td.kurtosis,
                    "skewness": td.skewness,
                    "health_score": health_score,
                    "rms_deviation": rms_deviation,
                    "risk_state": new_risk,
                    "revolution_index": revolution_index,
                    "dominant_frequency_hz": fft.dominant_frequency_hz if fft else None,
                    "consecutive_abnormal": risk_tracker.consecutive_abnormal,
                    "data_provenance": burst.data_provenance,
                }
                alert = models.AlertEvent(
                    id=str(uuid.uuid4()),
                    joint_id=joint.id,
                    conveyor_id=conveyor_id,
                    severity=severity,
                    alert_type=alert_type,
                    message=msg,
                    metrics_snapshot_json=json.dumps(metrics_snap),
                    data_provenance=burst.data_provenance,
                    is_acknowledged=0,
                    triggered_at_utc=now_utc,
                )
                db.add(alert)
                created_alerts.append(alert)

        # ── 15. Commit everything ─────────────────────────────────────────────
        db.commit()
        db.refresh(obs)

        # ── 16. WebSocket broadcasts (best-effort, never raise) ───────────────
        self._broadcast_health(burst, joint, obs, fft, created_alerts)

        return obs

    def _broadcast_health(
        self,
        burst: models.RawVibrationBurst,
        joint: models.Joint,
        obs: models.JointObservation,
        fft: Optional[FFTFeatures],
        alerts: List[models.AlertEvent],
    ):
        """Non-blocking WebSocket broadcast — failures are logged, not raised."""
        try:
            from .websocket_manager import ws_manager

            health_payload = {
                "type": "HEALTH_UPDATE",
                "joint_id": joint.id,
                "joint_code": joint.joint_code,
                "health_score": obs.health_score,
                "risk_state": obs.risk_state,
                "revolution_index": obs.revolution_index,
                "anomaly_detected": bool(obs.anomaly_detected),
                "data_provenance": burst.data_provenance,
                "baseline_status": obs.baseline_status,
                "metrics": {
                    "rms": obs.rms_acceleration,
                    "peak": obs.peak_acceleration,
                    "crest_factor": obs.crest_factor,
                    "kurtosis": obs.kurtosis,
                    "skewness": obs.skewness,
                    "dominant_frequency_hz": obs.dominant_frequency_hz,
                    "spectral_energy": obs.spectral_energy,
                    "rms_deviation": obs.rms_deviation,
                    "consecutive_abnormal": obs.consecutive_abnormal_count_snapshot,
                },
                "fft_bins": (
                    {
                        "frequencies": fft.frequency_bins_hz[:256],  # Limit for WS payload size
                        "amplitudes": fft.amplitude_spectrum[:256],
                        "dominant_hz": fft.dominant_frequency_hz,
                        "dominant_amplitude": fft.dominant_amplitude,
                        "spectral_centroid_hz": fft.spectral_centroid_hz,
                    }
                    if fft else None
                ),
                "timestamp_utc": obs.observation_timestamp_utc,
            }
            ws_manager.dispatch_json(health_payload)

            for alert in alerts:
                try:
                    snap = json.loads(alert.metrics_snapshot_json) if alert.metrics_snapshot_json else {}
                except Exception:
                    snap = {}
                alert_payload = {
                    "type": "ALERT_TRIGGERED",
                    "alert_id": alert.id,
                    "joint_id": joint.id,
                    "joint_code": joint.joint_code,
                    "severity": alert.severity,
                    "alert_type": alert.alert_type,
                    "message": alert.message,
                    "metrics_snapshot": snap,
                    "data_provenance": alert.data_provenance,
                    "triggered_at_utc": alert.triggered_at_utc,
                }
                ws_manager.dispatch_json(alert_payload)

        except Exception as exc:
            logger.warning("Health broadcast failed (non-critical): %s", exc)

    def reset_joint_baseline(self, joint_id: str):
        """Reset rolling baseline and risk state for a specific joint (used after maintenance)."""
        _registry.reset_joint(joint_id)
        logger.info(f"HealthAssessmentService: reset baseline and risk state for joint {joint_id}")


# Module-level singleton
health_service = HealthAssessmentService()
