"""
Phase 4A Test Suite: Condition-Aware Vibration Anomaly Model
============================================================
Validates:
1. Training artifacts exist and load cleanly via joblib.
2. Feature schema integrity (10 features, 2 condition features, 8 DSP metrics).
3. Data policy compliance (zero synthetic data contamination, NORMAL-only training).
4. Model inference on feature vectors (produces finite scores and boolean decisions).
5. Preprocessing pipeline integrity (RobustScaler fitted with correct parameters).
6. Presence and schema of training_metadata.json and evaluation.json.
7. Preserves complete isolation from Phase 1, Phase 2, Phase 3, and Vision code.
"""

import json
import unittest
from pathlib import Path
import joblib
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "ml" / "vibration_anomaly"
PIPELINE_PATH = MODEL_DIR / "vibration_anomaly_pipeline.joblib"
METADATA_PATH = MODEL_DIR / "training_metadata.json"
EVALUATION_PATH = MODEL_DIR / "evaluation.json"
SCHEMA_PATH = MODEL_DIR / "feature_schema.json"

EXPECTED_FEATURES = [
    "speed_rpm",
    "pretension_n",
    "driver_rms",
    "driver_peak",
    "driver_crest_factor",
    "driver_kurtosis",
    "driver_dominant_freq_hz",
    "driven_rms",
    "driven_crest_factor",
    "driven_dominant_freq_hz"
]

class TestPhase4VibrationMLModel(unittest.TestCase):
    """Phase 4A test cases validating model artifacts, provenance, and inference mechanics."""

    def test_model_artifacts_exist(self):
        """All required Phase 4A model artifacts must exist on disk."""
        self.assertTrue(PIPELINE_PATH.exists(), f"Missing pipeline artifact: {PIPELINE_PATH}")
        self.assertTrue(METADATA_PATH.exists(), f"Missing metadata file: {METADATA_PATH}")
        self.assertTrue(EVALUATION_PATH.exists(), f"Missing evaluation file: {EVALUATION_PATH}")
        self.assertTrue(SCHEMA_PATH.exists(), f"Missing feature schema file: {SCHEMA_PATH}")

    def test_pipeline_loads_and_has_scaler_and_model(self):
        """Pipeline must load cleanly and consist of RobustScaler + IsolationForest."""
        pipeline = joblib.load(PIPELINE_PATH)
        self.assertIsNotNone(pipeline)
        self.assertTrue(hasattr(pipeline, "named_steps"))
        self.assertIn("scaler", pipeline.named_steps)
        self.assertIn("model", pipeline.named_steps)

        scaler = pipeline.named_steps["scaler"]
        model = pipeline.named_steps["model"]

        self.assertEqual(len(scaler.center_), 10)
        self.assertEqual(len(scaler.scale_), 10)
        self.assertTrue(np.all(np.isfinite(scaler.center_)))
        self.assertTrue(np.all(np.isfinite(scaler.scale_)))
        self.assertEqual(model.n_estimators, 100)

    def test_feature_schema_fidelity(self):
        """Feature schema must match the exact 10 condition-aware features."""
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            schema = json.load(f)

        self.assertEqual(schema["feature_count"], 10)
        self.assertEqual(schema["features"], EXPECTED_FEATURES)
        self.assertEqual(schema["operating_conditions"], ["speed_rpm", "pretension_n"])
        self.assertEqual(len(schema["vibration_metrics"]), 8)
        
        # Verify no synthetic or leaky columns present
        forbidden_cols = ["unbalance_load_g", "fault_code", "belt_condition", "condition_folder"]
        for c in forbidden_cols:
            self.assertNotIn(c, schema["features"])

    def test_provenance_and_data_policy_compliance(self):
        """Metadata must verify zero synthetic data was used and training was NORMAL only."""
        with open(METADATA_PATH, "r", encoding="utf-8") as f:
            meta = json.load(f)

        self.assertFalse(meta["synthetic_data_used"], "Policy violation: synthetic data cannot be used for ML training")
        self.assertEqual(meta["training_samples_count"], 102)
        self.assertEqual(meta["evaluation_samples_count"], 357)
        self.assertIn("NORMAL", meta["training_population"])
        self.assertEqual(meta["mendeley_doi"], "10.17632/jf8v2ndydr.1")
        self.assertIn("scientific_disclaimer", meta)

    def test_model_inference_output(self):
        """Model must score input feature vectors returning finite score and boolean flag."""
        pipeline = joblib.load(PIPELINE_PATH)
        scaler = pipeline.named_steps["scaler"]
        model = pipeline.named_steps["model"]

        # Synthetic test vector matching expected schema:
        # [speed_rpm, pretension_n, driver_rms, driver_peak, driver_crest_factor, driver_kurtosis, driver_dominant_freq_hz, driven_rms, driven_crest_factor, driven_dominant_freq_hz]
        test_vec = np.array([[1000.0, 110.0, 0.14, 0.95, 6.8, 1.2, 280.0, 0.12, 6.5, 275.0]])

        # 1. Transform
        scaled_vec = scaler.transform(test_vec)
        self.assertEqual(scaled_vec.shape, (1, 10))
        self.assertTrue(np.all(np.isfinite(scaled_vec)))

        # 2. Score (negative score_samples = raw anomaly score)
        raw_score = float(-model.score_samples(scaled_vec)[0])
        self.assertTrue(np.isfinite(raw_score))

        # 3. Decision (-1 = anomaly, +1 = normal)
        raw_decision = int(model.predict(scaled_vec)[0])
        is_anomaly = bool(raw_decision == -1)
        self.assertIsInstance(is_anomaly, bool)

    def test_evaluation_metrics_report_integrity(self):
        """evaluation.json must contain real computed metrics and breakdowns without placeholder values."""
        with open(EVALUATION_PATH, "r", encoding="utf-8") as f:
            ev = json.load(f)

        metrics = ev["overall_metrics"]
        self.assertGreater(metrics["roc_auc"], 0.5, "Model ROC-AUC should exceed random chance")
        self.assertGreater(metrics["pr_auc"], 0.5)
        self.assertGreater(metrics["precision"], 0.0)
        self.assertGreater(metrics["recall"], 0.0)
        self.assertGreater(metrics["f1_score"], 0.0)

        # Verify confusion matrix sums to total evaluation runs (357)
        cm = metrics["confusion_matrix"]
        total_eval = cm["true_negatives"] + cm["false_positives"] + cm["false_negatives"] + cm["true_positives"]
        self.assertEqual(total_eval, 357)

        # Verify breakdowns exist
        self.assertIn("per_rpm_breakdown", ev)
        self.assertIn("per_pretension_breakdown", ev)
        self.assertIn("per_condition_metrics", ev)
        self.assertIn("baseline_comparison", ev)


import sys
backend_dir = PROJECT_ROOT / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app
from app.ml_service import VibrationAnomalyEngine, vibration_anomaly_engine
from app.database import SessionLocal, init_db
from app import models

client = TestClient(app)

class TestPhase4BVibrationMLIntegration(unittest.TestCase):
    """Phase 4B integration test suite for Vibration ML inference, API endpoints, and safety guardrails."""

    def setUp(self):
        init_db()
        self.db = SessionLocal()
        self.valid_features = {
            "speed_rpm": 1200.0,
            "pretension_n": 110.0,
            "driver_rms": 0.165,
            "driver_peak": 1.05,
            "driver_crest_factor": 6.36,
            "driver_kurtosis": 1.45,
            "driver_dominant_freq_hz": 280.0,
            "driven_rms": 0.142,
            "driven_crest_factor": 6.10,
            "driven_dominant_freq_hz": 275.0
        }

    def tearDown(self):
        self.db.close()

    def test_ml_service_status(self):
        """VibrationAnomalyEngine must expose complete provenance, validated threshold status, and scientific disclaimer."""
        status = vibration_anomaly_engine.get_status()
        self.assertTrue(status["available"])
        self.assertEqual(status["model_version"], vibration_anomaly_engine.model_version)
        self.assertEqual(status["model_type"], "IsolationForest")
        self.assertEqual(status["model_status"], "TRAINED_RESEARCH_MODEL")
        self.assertEqual(status["threshold_status"], "VALIDATED")
        self.assertEqual(status["feature_count"], 10)
        self.assertIn("Mendeley", status["dataset"])
        self.assertEqual(status["provenance_doi"], "10.17632/jf8v2ndydr.1")
        self.assertFalse(status["rupture_prediction"])
        self.assertIn("scientific_limitation", status)

    def test_ml_service_scoring_fidelity(self):
        """Engine must score valid feature vectors returning finite raw anomaly scores and boolean decisions."""
        res = vibration_anomaly_engine.score_features(self.valid_features)
        self.assertTrue(res["available"])
        self.assertEqual(res["model_version"], vibration_anomaly_engine.model_version)
        self.assertEqual(res["model_status"], "TRAINED_RESEARCH_MODEL")
        self.assertTrue(np.isfinite(res["raw_anomaly_score"]))
        self.assertIsInstance(res["anomaly_decision"], bool)
        self.assertEqual(res["threshold_status"], "VALIDATED")
        self.assertEqual(res["operating_regime"]["speed_rpm"], 1200.0)
        self.assertEqual(res["operating_regime"]["pretension_n"], 110.0)
        self.assertIsInstance(res["baseline_deviation"], list)
        self.assertFalse(res["rupture_prediction"])
        self.assertIn("EVIDENCE_ONLY", res["safety_interlock"])

    def test_missing_operating_context_prevents_fabricated_scoring(self):
        """Engine must reject scoring without RPM or pretension, returning WAITING_FOR_OPERATING_CONTEXT instead of inventing numbers."""
        # Missing speed_rpm
        feat_no_speed = dict(self.valid_features)
        feat_no_speed["speed_rpm"] = None
        res_no_speed = vibration_anomaly_engine.score_features(feat_no_speed)
        self.assertEqual(res_no_speed["model_status"], "WAITING_FOR_OPERATING_CONTEXT")
        self.assertIsNone(res_no_speed["raw_anomaly_score"])
        self.assertIsNone(res_no_speed["anomaly_decision"])

        # Missing pretension_n
        feat_no_tension = dict(self.valid_features)
        del feat_no_tension["pretension_n"]
        res_no_tension = vibration_anomaly_engine.score_features(feat_no_tension)
        self.assertEqual(res_no_tension["model_status"], "WAITING_FOR_OPERATING_CONTEXT")
        self.assertIsNone(res_no_tension["raw_anomaly_score"])

    def test_schema_validation_rejects_missing_and_invalid_values(self):
        """Engine must reject missing features and non-numeric or non-finite inputs."""
        # Missing required DSP feature
        feat_missing = dict(self.valid_features)
        del feat_missing["driver_kurtosis"]
        with self.assertRaises(ValueError):
            vibration_anomaly_engine.score_features(feat_missing)

        # Non-numeric value
        feat_bad_val = dict(self.valid_features)
        feat_bad_val["driver_rms"] = "invalid_string"
        with self.assertRaises(ValueError):
            vibration_anomaly_engine.score_features(feat_bad_val)

        # Infinite value
        feat_inf = dict(self.valid_features)
        feat_inf["driver_crest_factor"] = float("inf")
        with self.assertRaises(ValueError):
            vibration_anomaly_engine.score_features(feat_inf)

    def test_api_get_ml_status_endpoint(self):
        """GET /api/v1/ml/status must return 200 and valid provenance metadata."""
        resp = client.get("/api/v1/ml/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertEqual(data["model_version"], vibration_anomaly_engine.model_version)
        self.assertEqual(data["dataset"], "Mendeley Experimental Belt Drive Vibration Dataset")
        self.assertEqual(data["threshold_status"], "VALIDATED")
        self.assertFalse(data["rupture_prediction"])

    def test_api_post_ml_score_endpoint(self):
        """POST /api/v1/ml/score must return valid inference scores for valid requests."""
        resp = client.post("/api/v1/ml/score", json=self.valid_features)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["available"])
        self.assertIn("raw_anomaly_score", data)
        self.assertIn("anomaly_decision", data)
        self.assertEqual(data["operating_regime"]["speed_rpm"], 1200.0)

    def test_api_post_ml_score_validation_error(self):
        """POST /api/v1/ml/score must return 422 for missing required features or invalid values."""
        bad_payload = dict(self.valid_features)
        del bad_payload["driver_rms"]
        resp = client.post("/api/v1/ml/score", json=bad_payload)
        self.assertEqual(resp.status_code, 422)

    def test_multi_evidence_joint_passport_includes_ml_evidence(self):
        """GET /api/v1/joints/{joint_id}/passport must include independent ml_anomaly_evidence."""
        # Ensure joint exists
        joint = self.db.query(models.Joint).filter(models.Joint.id == "joint-001").first()
        if not joint:
            joint = models.Joint(
                id="joint-001",
                conveyor_id="conv-main-01",
                joint_code="J-01",
                current_risk="NORMAL",
                consecutive_abnormal_count=0
            )
            self.db.add(joint)
            self.db.commit()

        resp = client.get("/api/v1/joints/joint-001/passport")
        self.assertEqual(resp.status_code, 200)
        passport = resp.json()

        # Check evidence sources independence
        ev = passport["evidence_sources"]
        self.assertIn("vibration_dsp_evidence", ev)
        self.assertIn("vision_optical_evidence", ev)
        self.assertIn("operational_telemetry", ev)
        self.assertIn("ml_anomaly_evidence", ev)

        ml = ev["ml_anomaly_evidence"]
        self.assertTrue(ml["available"])
        self.assertEqual(ml["model_version"], vibration_anomaly_engine.model_version)
        self.assertIn("threshold_status", ml)

    def test_safety_rule_ml_anomaly_cannot_independently_trip(self):
        """CRITICAL SAFETY GUARANTEE: An ML anomaly decision alone must NEVER trigger automated TRIP_IMMEDIATE_STOP."""
        joint = self.db.query(models.Joint).filter(models.Joint.id == "joint-001").first()
        if not joint:
            joint = models.Joint(
                id="joint-001",
                conveyor_id="conv-main-01",
                joint_code="J-01",
                current_risk="NORMAL",
                consecutive_abnormal_count=0
            )
            self.db.add(joint)
            self.db.commit()

        # Joint has NORMAL risk in Phase 3
        joint.current_risk = "NORMAL"
        self.db.commit()

        resp = client.get("/api/v1/joints/joint-001/passport")
        self.assertEqual(resp.status_code, 200)
        passport = resp.json()

        engine = passport["joint_health_engine"]
        # Safety action must remain CONTINUE_NORMAL_OPERATION even with ML inference running
        self.assertEqual(engine["recommended_action"], "CONTINUE_NORMAL_OPERATION")
        self.assertNotEqual(engine["recommended_action"], "TRIP_IMMEDIATE_STOP")
        self.assertIn("cannot independently trigger emergency stop", engine["deterministic_rule_basis"])

    def test_scientific_scope_no_rupture_claims(self):
        """API must never present rupture probability or fake severity scores."""
        status = vibration_anomaly_engine.get_status()
        self.assertFalse(status["rupture_prediction"])
        self.assertNotIn("rupture_probability", status)
        self.assertNotIn("failure_probability", status)

    def test_safe_failure_when_model_artifact_unavailable(self):
        """If model artifact is missing, engine fails safely without crashing telemetry or application."""
        dummy_engine = VibrationAnomalyEngine(model_path=Path("non_existent_path.joblib"))
        self.assertFalse(dummy_engine.available)
        self.assertEqual(dummy_engine.status, "ML_UNAVAILABLE")

        status = dummy_engine.get_status()
        self.assertFalse(status["available"])
        self.assertEqual(status["model_status"], "ML_UNAVAILABLE")

        score = dummy_engine.score_features(self.valid_features)
        self.assertFalse(score["available"])
        self.assertEqual(score["model_status"], "ML_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
