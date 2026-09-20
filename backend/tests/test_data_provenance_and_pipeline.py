"""
Test Suite: Data Provenance, Architectural Separation & Research Pipeline
========================================================================
Validates compliance with the Industrial Data, Testing & ML Training Policy:
1. Strict separation of SOFTWARE TEST, SIMULATION, RESEARCH, and FIELD data.
2. Prevention of silent mixing of synthetic data into research/field pipelines.
3. Integrity and completeness of Mendeley belt-drive research dataset (459 runs).
4. Stratification and isolation of synthetic conveyor fault simulation dataset.
5. Reproducibility of DSP feature extraction between offline processing and live engine.
6. Verification of REST API dataset provenance endpoints.
"""

import os
import sys
import unittest
import pandas as pd
import numpy as np
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from main import app
from app.provenance import (
    DataSourceCategory, ProvenanceEnforcer,
    get_dataset_manifest, get_provenance_metadata, get_all_dataset_provenance
)
from app.dsp import DSPAnalyzer

PROJECT_ROOT = backend_dir.parent
DATA_DIR = PROJECT_ROOT / "data"

class TestDataProvenanceAndPolicy(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.analyzer = DSPAnalyzer()

    # -------------------------------------------------------------------------
    # 1. Architectural Separation & Policy Enforcement Tests
    # -------------------------------------------------------------------------
    def test_provenance_category_validation(self):
        """Verify valid categories and rejection of unregistered categories."""
        self.assertTrue(ProvenanceEnforcer.validate_category("RESEARCH"))
        self.assertTrue(ProvenanceEnforcer.validate_category("FIELD_HARDWARE"))
        self.assertTrue(ProvenanceEnforcer.validate_category("SIMULATION"))
        self.assertTrue(ProvenanceEnforcer.validate_category("SOFTWARE_TEST"))
        self.assertFalse(ProvenanceEnforcer.validate_category("ARBITRARY_UNVERIFIED"))

    def test_prevent_synthetic_masquerading_as_field_or_research(self):
        """Enforces that synthetic/simulation data CANNOT be silently passed to field/research."""
        with self.assertRaises(ValueError) as ctx:
            ProvenanceEnforcer.assert_no_silent_mixing("SIMULATION", DataSourceCategory.FIELD_HARDWARE)
        self.assertIn("DATA POLICY VIOLATION", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            ProvenanceEnforcer.assert_no_silent_mixing("SYNTHETIC", DataSourceCategory.RESEARCH)
        self.assertIn("DATA POLICY VIOLATION", str(ctx.exception))

        # Allowed cases (no exception)
        ProvenanceEnforcer.assert_no_silent_mixing("FIELD_HARDWARE", DataSourceCategory.FIELD_HARDWARE)
        ProvenanceEnforcer.assert_no_silent_mixing("RESEARCH", DataSourceCategory.RESEARCH)

    # -------------------------------------------------------------------------
    # 2. Dataset Metadata & Provenance Manifest Tests
    # -------------------------------------------------------------------------
    def test_global_manifest_integrity(self):
        """Verify manifest defines all 4 required data categories."""
        manifest = get_dataset_manifest()
        self.assertIn("data_categories", manifest)
        cats = manifest["data_categories"]
        for required in ["RESEARCH", "SIMULATION", "FIELD_HARDWARE", "SOFTWARE_TEST"]:
            self.assertIn(required, cats, f"Missing required data category {required}")

    def test_mendeley_research_provenance_metadata(self):
        """Verify research dataset provenance contains DOI, license, and domain disclaimer."""
        meta = get_provenance_metadata("mendeley_belt_drive")
        self.assertIsNotNone(meta, "Mendeley provenance metadata not found")
        identity = meta.get("dataset_identity", {})
        self.assertEqual(identity.get("doi"), "10.17632/jf8v2ndydr.1")
        self.assertIn("CC BY 4.0", identity.get("license", ""))
        self.assertEqual(identity.get("source_type"), "RESEARCH")

        # Scientific domain boundary check
        domain = meta.get("scientific_domain_limitations", {})
        self.assertFalse(domain.get("is_conveyor_joint_rupture_data"))
        self.assertIn("NOT equivalent to conveyor belt joint rupture", domain.get("disclaimer", ""))

    def test_synthetic_simulation_provenance_metadata(self):
        """Verify synthetic dataset is explicitly flagged and not claimed as real."""
        meta = get_provenance_metadata("conveyor_fault_simulation")
        self.assertIsNotNone(meta, "Synthetic provenance metadata not found")
        self.assertEqual(meta["dataset_identity"]["source_type"], "SYNTHETIC_SIMULATION")
        domain = meta.get("scientific_domain_limitations", {})
        self.assertFalse(domain.get("is_real_field_data"))
        self.assertIn("synthetically generated", domain.get("disclaimer", ""))

    # -------------------------------------------------------------------------
    # 3. Cleaned Research Dataset Integrity Tests
    # -------------------------------------------------------------------------
    def test_mendeley_cleaned_features_table(self):
        """Verify that all 459 runs are processed with zero NaNs and valid DSP metrics."""
        features_csv = DATA_DIR / "processed" / "research" / "mendeley_belt_drive" / "cleaned_belt_drive_features.csv"
        self.assertTrue(features_csv.exists(), f"Missing cleaned features CSV: {features_csv}")

        df = pd.read_csv(features_csv)
        self.assertEqual(len(df), 459, f"Expected 459 runs, found {len(df)}")
        self.assertEqual(df.isnull().sum().sum(), 0, "Cleaned research dataset contains NaN values")

        # Verify DSP metric reasonableness
        self.assertTrue((df["driver_rms"] > 0).all(), "Driver RMS should be positive")
        self.assertTrue((df["driven_rms"] > 0).all(), "Driven RMS should be positive")
        self.assertTrue((df["driver_peak"] >= df["driver_rms"]).all(), "Peak must be >= RMS")
        self.assertTrue((df["driven_peak"] >= df["driven_rms"]).all(), "Peak must be >= RMS")
        self.assertTrue((df["driver_crest_factor"] >= 1.0).all(), "Crest factor must be >= 1.0")

        # Verify all 9 conditions are present (51 runs each)
        condition_counts = df["condition_folder"].value_counts()
        self.assertEqual(len(condition_counts), 9)
        self.assertTrue((condition_counts == 51).all(), "Each condition must have exactly 51 runs")

    # -------------------------------------------------------------------------
    # 4. Cleaned Synthetic Dataset Integrity Tests
    # -------------------------------------------------------------------------
    def test_cleaned_synthetic_features_table(self):
        """Verify synthetic dataset has stratified train/val/test splits and explicit provenance."""
        synth_csv = DATA_DIR / "processed" / "synthetic" / "conveyor_fault_simulation" / "cleaned_synthetic_features.csv"
        self.assertTrue(synth_csv.exists(), f"Missing cleaned synthetic features CSV: {synth_csv}")

        df = pd.read_csv(synth_csv)
        self.assertEqual(len(df), 12000)
        self.assertEqual(df.isnull().sum().sum(), 0)

        # Verify data_source tagging
        self.assertTrue((df["data_source"] == "synthetic_simulation").all())

        # Verify train / val / test split balance
        splits = df["split"].value_counts()
        self.assertGreaterEqual(splits.get("train", 0), 8000, "Train split should be ~70% (8400)")
        self.assertGreaterEqual(splits.get("validation", 0), 1700, "Val split should be ~15% (1800)")
        self.assertGreaterEqual(splits.get("test", 0), 1700, "Test split should be ~15% (1800)")

    # -------------------------------------------------------------------------
    # 5. DSP Feature Reproducibility Test
    # -------------------------------------------------------------------------
    def test_dsp_feature_reproducibility(self):
        """Verify that offline research DSP extraction matches live inference DSP exactly."""
        sample_csv = DATA_DIR / "processed" / "research" / "mendeley_belt_drive" / "sample_cleaned_vibration_signals.csv"
        self.assertTrue(sample_csv.exists(), "Sample vibration file not found")

        df = pd.read_csv(sample_csv)
        driver_sig = df["driver_pulley_accel_g_clean"].to_numpy()

        # Compute with DSP engine
        dsp_res = self.analyzer.analyze(driver_sig, sampling_rate_hz=1000.0)
        self.assertTrue(dsp_res.valid)

        # Load precomputed feature for run 1 of Data 70-H-0
        features_csv = DATA_DIR / "processed" / "research" / "mendeley_belt_drive" / "cleaned_belt_drive_features.csv"
        df_feat = pd.read_csv(features_csv)
        run1 = df_feat[(df_feat["condition_folder"] == "Data 70-H-0") & (df_feat["run_id"] == 1)].iloc[0]

        # Assert equality to within floating point tolerance
        self.assertAlmostEqual(dsp_res.time_domain.rms, run1["driver_rms"], places=5)
        self.assertAlmostEqual(dsp_res.time_domain.kurtosis, run1["driver_kurtosis"], places=5)
        self.assertAlmostEqual(dsp_res.time_domain.crest_factor, run1["driver_crest_factor"], places=5)
        self.assertAlmostEqual(dsp_res.fft.dominant_frequency_hz, run1["driver_dominant_freq_hz"], places=2)

    # -------------------------------------------------------------------------
    # 6. REST API Provenance Endpoint Tests
    # -------------------------------------------------------------------------
    def test_api_dataset_provenance_endpoints(self):
        """Verify /api/v1/datasets/provenance endpoints return valid JSON metadata."""
        resp = self.client.get("/api/v1/datasets/provenance")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("manifest", data)
        self.assertIn("datasets", data)
        self.assertIn("mendeley_belt_drive", data["datasets"])

        # Test specific dataset route
        resp_mendeley = self.client.get("/api/v1/datasets/provenance/mendeley_belt_drive")
        self.assertEqual(resp_mendeley.status_code, 200)
        self.assertEqual(resp_mendeley.json()["dataset_identity"]["doi"], "10.17632/jf8v2ndydr.1")

        # Test 404 on nonexistent dataset
        resp_404 = self.client.get("/api/v1/datasets/provenance/nonexistent_dummy")
        self.assertEqual(resp_404.status_code, 404)

if __name__ == "__main__":
    unittest.main()
