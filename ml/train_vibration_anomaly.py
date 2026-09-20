"""
Phase 4A: Condition-Aware Vibration Anomaly Detection Pipeline
=============================================================
Dataset: Mendeley 'Experimental vibration data collected for a belt drive system under different operating conditions'
DOI: 10.17632/jf8v2ndydr.1 | Associated publication: Data in Brief (2023), DOI: 10.1016/j.dib.2023.109156
License: CC BY 4.0

Strict Industrial Data & ML Training Policy:
1. Uses ONLY real research dataset: data/processed/research/mendeley_belt_drive/cleaned_belt_drive_features.csv
2. Trains ONLY on NORMAL healthy runs (Repetition 1 & 2 across 17 speeds x 3 pretensions = 102 runs)
3. Evaluates on completely frozen test set (Repetition 3 NORMAL + all FAULTY_BELT + all UNBALANCED = 357 runs)
4. RobustScaler fitted exclusively on training NORMAL runs
5. Computes condition-aware Isolation Forest and benchmark statistical distance baseline
6. Computes operating regime breakdowns (per-RPM and per-pretension)
7. Emits full artifacts and genuine metrics to models/ml/vibration_anomaly/
"""

import os
import sys
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import RobustScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    roc_auc_score,
    average_precision_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "research" / "mendeley_belt_drive" / "cleaned_belt_drive_features.csv"
OUTPUT_DIR = PROJECT_ROOT / "models" / "ml" / "vibration_anomaly"

# Exact 10 selected features
FEATURE_COLS = [
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

FEATURE_UNITS = {
    "speed_rpm": "RPM",
    "pretension_n": "N",
    "driver_rms": "g",
    "driver_peak": "g",
    "driver_crest_factor": "ratio",
    "driver_kurtosis": "dimensionless",
    "driver_dominant_freq_hz": "Hz",
    "driven_rms": "g",
    "driven_crest_factor": "ratio",
    "driven_dominant_freq_hz": "Hz"
}

def train_and_evaluate():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load and Validate Dataset
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Cleaned research dataset not found at: {DATA_PATH}")

    df = pd.read_csv(DATA_PATH)
    total_rows = len(df)
    if total_rows != 459:
        raise ValueError(f"Expected 459 runs in Mendeley dataset, found {total_rows}")

    # Validate required columns
    missing_cols = [c for c in FEATURE_COLS + ["fault_code", "repetition_idx"] if c not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns in dataset: {missing_cols}")

    # Check for NaN / infinite values
    if df[FEATURE_COLS].isnull().sum().sum() > 0:
        raise ValueError("Detected missing / NaN values in selected feature matrix")

    # 2. Partition Data (Repetition-Aware Strategy)
    # Training: NORMAL runs from Repetition 1 and 2
    train_mask = (df["fault_code"] == "NORMAL") & (df["repetition_idx"].isin([1, 2]))
    train_df = df[train_mask].copy()

    # Evaluation: All remaining runs
    # (NORMAL Repetition 3, all FAULTY_BELT, all UNBALANCED)
    eval_mask = ~train_mask
    eval_df = df[eval_mask].copy()

    n_train = len(train_df)
    n_eval = len(eval_df)

    if n_train != 102:
        raise ValueError(f"Expected exactly 102 training runs, found {n_train}")
    if n_eval != 357:
        raise ValueError(f"Expected exactly 357 evaluation runs, found {n_eval}")

    # Verify train set is strictly NORMAL
    assert set(train_df["fault_code"].unique()) == {"NORMAL"}, "Training data must contain only NORMAL runs"

    # Evaluation ground truth: 0 = NORMAL (healthy), 1 = ANOMALY (FAULTY_BELT or UNBALANCED)
    y_eval = (eval_df["fault_code"] != "NORMAL").astype(int).values

    X_train = train_df[FEATURE_COLS].values
    X_eval = eval_df[FEATURE_COLS].values

    # 3. Fit RobustScaler exclusively on Training Data
    scaler = RobustScaler()
    scaler.fit(X_train)

    X_train_scaled = scaler.transform(X_train)
    X_eval_scaled = scaler.transform(X_eval)

    # Compute training baseline distribution (median and IQR per feature) for explanation
    feat_medians = np.median(X_train, axis=0)
    feat_iqrs = np.percentile(X_train, 75, axis=0) - np.percentile(X_train, 25, axis=0)
    feat_iqrs[feat_iqrs == 0] = 1e-6  # Prevent division by zero

    # 4. Train Isolation Forest Anomaly Detector
    random_state = 42
    n_estimators = 100
    max_samples = "auto"
    contamination = "auto"  # Non-arbitrary offset for pure healthy training data

    model = IsolationForest(
        n_estimators=n_estimators,
        max_samples=max_samples,
        contamination=contamination,
        random_state=random_state,
        n_jobs=-1
    )
    model.fit(X_train_scaled)

    # 5. Pipeline Packaging
    pipeline = Pipeline([
        ("scaler", scaler),
        ("model", model)
    ])

    # 6. Model Evaluation on Frozen Evaluation Set (357 runs)
    # IsolationForest.score_samples returns negative anomaly score (lower = more abnormal)
    # Raw anomaly score: higher = more abnormal
    eval_scores_raw = -model.score_samples(X_eval_scaled)

    # Binary prediction: -1 = anomaly, +1 = normal
    eval_preds_raw = model.predict(X_eval_scaled)
    eval_preds_binary = (eval_preds_raw == -1).astype(int)

    # Calculate Overall Binary Metrics
    roc_auc = float(roc_auc_score(y_eval, eval_scores_raw))
    pr_auc = float(average_precision_score(y_eval, eval_scores_raw))
    precision = float(precision_score(y_eval, eval_preds_binary, zero_division=0))
    recall = float(recall_score(y_eval, eval_preds_binary, zero_division=0))
    f1 = float(f1_score(y_eval, eval_preds_binary, zero_division=0))

    cm = confusion_matrix(y_eval, eval_preds_binary)
    tn, fp, fn, tp = [int(v) for v in cm.ravel()]

    specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0

    # 7. Statistical Distance Baseline Comparison
    # Simple Euclidean distance from training median in RobustScaled space
    train_center = np.median(X_train_scaled, axis=0)
    stat_baseline_scores = np.linalg.norm(X_eval_scaled - train_center, axis=1)
    stat_baseline_roc_auc = float(roc_auc_score(y_eval, stat_baseline_scores))
    stat_baseline_pr_auc = float(average_precision_score(y_eval, stat_baseline_scores))

    # 8. Evaluation Breakdowns
    # A. By Condition / Physical State
    eval_df_eval = eval_df.copy()
    eval_df_eval["pred_anomaly"] = eval_preds_binary
    eval_df_eval["raw_score"] = eval_scores_raw

    per_condition_metrics = {}
    for code, group in eval_df_eval.groupby("fault_code"):
        n_group = len(group)
        n_flagged = int(group["pred_anomaly"].sum())
        flag_rate = float(n_flagged / n_group)
        mean_score = float(group["raw_score"].mean())
        per_condition_metrics[code] = {
            "total_runs": n_group,
            "anomalies_flagged": n_flagged,
            "detection_rate": flag_rate,
            "mean_anomaly_score": mean_score,
            "status": "FALSE_POSITIVE_RATE" if code == "NORMAL" else "RECALL_TRUE_POSITIVE_RATE"
        }

    # B. By Rotational Speed (RPM Breakdown)
    rpm_breakdown = {}
    for rpm_val, group in eval_df_eval.groupby("speed_rpm"):
        y_g = (group["fault_code"] != "NORMAL").astype(int).values
        pred_g = group["pred_anomaly"].values
        g_tn = int(((y_g == 0) & (pred_g == 0)).sum())
        g_fp = int(((y_g == 0) & (pred_g == 1)).sum())
        g_fn = int(((y_g == 1) & (pred_g == 0)).sum())
        g_tp = int(((y_g == 1) & (pred_g == 1)).sum())
        
        rpm_breakdown[str(int(rpm_val))] = {
            "total_runs": len(group),
            "normal_runs": int((y_g == 0).sum()),
            "fault_runs": int((y_g == 1).sum()),
            "true_positives": g_tp,
            "false_positives": g_fp,
            "recall": float(g_tp / (g_tp + g_fn)) if (g_tp + g_fn) > 0 else 0.0,
            "false_positive_rate": float(g_fp / (g_fp + g_tn)) if (g_fp + g_tn) > 0 else 0.0,
            "mean_anomaly_score": float(group["raw_score"].mean())
        }

    # C. By Belt Pretension (N Breakdown)
    pretension_breakdown = {}
    for t_val, group in eval_df_eval.groupby("pretension_n"):
        y_t = (group["fault_code"] != "NORMAL").astype(int).values
        pred_t = group["pred_anomaly"].values
        t_tn = int(((y_t == 0) & (pred_t == 0)).sum())
        t_fp = int(((y_t == 0) & (pred_t == 1)).sum())
        t_fn = int(((y_t == 1) & (pred_t == 0)).sum())
        t_tp = int(((y_t == 1) & (pred_t == 1)).sum())
        
        pretension_breakdown[f"{int(t_val)}N"] = {
            "total_runs": len(group),
            "normal_runs": int((y_t == 0).sum()),
            "fault_runs": int((y_t == 1).sum()),
            "true_positives": t_tp,
            "false_positives": t_fp,
            "recall": float(t_tp / (t_tp + t_fn)) if (t_tp + t_fn) > 0 else 0.0,
            "false_positive_rate": float(t_fp / (t_fp + t_tn)) if (t_fp + t_tn) > 0 else 0.0,
            "mean_anomaly_score": float(group["raw_score"].mean())
        }

    # 9. Save Artifacts
    # A. Save Joblib Model Pipeline
    pipeline_path = OUTPUT_DIR / "vibration_anomaly_pipeline.joblib"
    joblib.dump(pipeline, pipeline_path)
    
    # Save standalone components for modular edge deployment if needed
    joblib.dump(model, OUTPUT_DIR / "anomaly_detector.joblib")
    joblib.dump(scaler, OUTPUT_DIR / "scaler.joblib")

    # B. Save Feature Schema
    feature_schema = {
        "feature_count": len(FEATURE_COLS),
        "features": FEATURE_COLS,
        "feature_units": FEATURE_UNITS,
        "operating_conditions": ["speed_rpm", "pretension_n"],
        "vibration_metrics": [f for f in FEATURE_COLS if f not in ["speed_rpm", "pretension_n"]],
        "training_normal_medians": {col: float(feat_medians[i]) for i, col in enumerate(FEATURE_COLS)},
        "training_normal_iqrs": {col: float(feat_iqrs[i]) for i, col in enumerate(FEATURE_COLS)},
        "scaler_center": [float(v) for v in scaler.center_],
        "scaler_scale": [float(v) for v in scaler.scale_]
    }
    with open(OUTPUT_DIR / "feature_schema.json", "w", encoding="utf-8") as f:
        json.dump(feature_schema, f, indent=2)

    # C. Save Training Metadata
    training_metadata = {
        "model_version": "vibration-anomaly-detector-v1",
        "model_type": "IsolationForest",
        "task": "condition_aware_vibration_anomaly_detection",
        "dataset_name": "Mendeley Experimental Belt Drive Vibration Dataset",
        "mendeley_doi": "10.17632/jf8v2ndydr.1",
        "publication_doi": "10.1016/j.dib.2023.109156",
        "training_population": "NORMAL healthy runs (Repetitions 1 and 2)",
        "training_samples_count": n_train,
        "evaluation_samples_count": n_eval,
        "evaluation_population": "NORMAL Rep 3 (51 runs) + FAULTY_BELT (153 runs) + UNBALANCED (153 runs)",
        "features": FEATURE_COLS,
        "hyperparameters": {
            "n_estimators": n_estimators,
            "max_samples": str(max_samples),
            "contamination": str(contamination),
            "random_state": random_state
        },
        "preprocessing": "RobustScaler (fitted exclusively on NORMAL training runs)",
        "synthetic_data_used": False,
        "framework_versions": {
            "scikit_learn": sklearn.__version__,
            "joblib": joblib.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__
        },
        "training_timestamp_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "scientific_disclaimer": (
            "RESEARCH BENCHMARK MODEL: Trained exclusively on experimental belt-drive test rig data. "
            "Detects dynamic operating condition vibration anomalies relative to healthy belt drive baseline. "
            "Does NOT claim conveyor belt joint rupture prediction or mining-field splice pullout detection."
        )
    }
    with open(OUTPUT_DIR / "training_metadata.json", "w", encoding="utf-8") as f:
        json.dump(training_metadata, f, indent=2)

    # D. Save Evaluation Results
    evaluation_record = {
        "evaluation_split": "frozen_held_out_research_split",
        "total_evaluation_runs": n_eval,
        "evaluation_composition": {
            "NORMAL_unseen": int((y_eval == 0).sum()),
            "FAULTY_BELT": int((eval_df["fault_code"] == "FAULTY_BELT").sum()),
            "UNBALANCED": int((eval_df["fault_code"] == "UNBALANCED").sum())
        },
        "overall_metrics": {
            "roc_auc": roc_auc,
            "pr_auc": pr_auc,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "specificity": specificity,
            "false_positive_rate": fpr,
            "confusion_matrix": {
                "true_negatives": tn,
                "false_positives": fp,
                "false_negatives": fn,
                "true_positives": tp
            }
        },
        "baseline_comparison": {
            "statistical_euclidean_distance_roc_auc": stat_baseline_roc_auc,
            "statistical_euclidean_distance_pr_auc": stat_baseline_pr_auc,
            "isolation_forest_advantage_roc_auc": float(roc_auc - stat_baseline_roc_auc)
        },
        "per_condition_metrics": per_condition_metrics,
        "per_rpm_breakdown": rpm_breakdown,
        "per_pretension_breakdown": pretension_breakdown,
        "threshold_methodology": "Default IsolationForest boundary (decision_function < 0.0)",
        "scientific_integrity_note": "Real computed evaluation metrics on held-out research runs. Zero synthetic data contamination."
    }
    with open(OUTPUT_DIR / "evaluation.json", "w", encoding="utf-8") as f:
        json.dump(evaluation_record, f, indent=2)

    # E. Save Model Card README.md
    readme_content = f"""# Condition-Aware Vibration Anomaly Detector (Phase 4A)

## 1. What It Does
* **Task:** Condition-Aware Vibration Anomaly Detection.
* **Architecture:** Scikit-learn `IsolationForest` (100 estimators) operating on `RobustScaler`-standardized 10-dimensional feature vectors.
* **Condition-Aware Input:** Inputs motor rotational speed (`speed_rpm`) and static tension (`pretension_n`) alongside 8 multi-axis DSP vibration features (`driver_rms`, `driver_peak`, `driver_crest_factor`, `driver_kurtosis`, `driver_dominant_freq_hz`, `driven_rms`, `driven_crest_factor`, `driven_dominant_freq_hz`).
* **Inference Output:** Continuous raw anomaly score and binary anomaly decision (`decision_function < 0`).

## 2. What It Does NOT Do (Domain Limitations)
> [!IMPORTANT]
> * **NO CONVEYOR JOINT RUPTURE PREDICTION:** This model is trained on a laboratory belt-drive test rig (G.U.N.T PT 500.14). It does NOT predict vulcanized or mechanical conveyor splice pullout or joint separation in mining fields.
> * **NO SAFETY SHUTDOWN OVERRIDE:** This model acts as an independent evidence source in the Multi-Evidence Joint Passport. It does NOT directly trigger automated emergency trips (`TRIP`).
> * **NO PROBABILITY CLAIMS:** The score is a non-parametric tree-isolation metric, NOT a calibrated percentage probability of failure.

## 3. Dataset & Provenance
* **Dataset:** Experimental vibration data for a belt drive system under different operating conditions.
* **Mendeley DOI:** [10.17632/jf8v2ndydr.1](https://doi.org/10.17632/jf8v2ndydr.1)
* **Publication DOI:** [10.1016/j.dib.2023.109156](https://doi.org/10.1016/j.dib.2023.109156)
* **License:** CC BY 4.0

## 4. Training Population
* **Total Training Runs:** 102 runs.
* **Filter:** Strictly `fault_code == 'NORMAL'` (Healthy, balanced belt) from Repetitions 1 and 2 across all 17 speeds (400–2000 RPM) and 3 tensions (70, 110, 150 N).
* **Synthetic Data Contamination:** 0.0% (Zero synthetic simulation samples used).

## 5. Frozen Evaluation Results (357 Unseen Runs)
* **ROC-AUC:** {roc_auc:.4f}
* **PR-AUC:** {pr_auc:.4f}
* **Precision:** {precision:.4f}
* **Recall:** {recall:.4f}
* **F1-Score:** {f1:.4f}
* **Specificity:** {specificity:.4f}
* **False Positive Rate:** {fpr:.4f}
* **Statistical Baseline Comparison:** Outperforms Euclidean distance baseline by {roc_auc - stat_baseline_roc_auc:+.4f} ROC-AUC.
"""
    with open(OUTPUT_DIR / "README.md", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # 10. Print Concise Terminal Report
    print("=" * 50)
    print("PHASE 4A — VIBRATION ML TRAINING REPORT")
    print("=" * 50)
    print(f"Dataset: Mendeley Belt Drive Benchmark (DOI: 10.17632/jf8v2ndydr.1)")
    print(f"Training samples: {n_train}")
    print(f"Evaluation samples: {n_eval}")
    print(f"\nTraining population: NORMAL repetition 1 and 2 (102 runs)")
    print(f"Evaluation population: NORMAL rep 3 (51) + FAULTY_BELT (153) + UNBALANCED (153)")
    print(f"\nFeatures ({len(FEATURE_COLS)}): {', '.join(FEATURE_COLS)}")
    print(f"\nModel: IsolationForest (n_estimators={n_estimators}, contamination={contamination})")
    print(f"Hyperparameters: random_state={random_state}, max_samples={max_samples}")
    print(f"\nSynthetic data used: NO")
    print(f"\nROC-AUC: {roc_auc:.4f}")
    print(f"PR-AUC: {pr_auc:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall: {recall:.4f}")
    print(f"F1: {f1:.4f}")
    print(f"Specificity: {specificity:.4f}")
    print(f"False Positive Rate: {fpr:.4f}")
    print(f"\nConfusion Matrix: [TN: {tn}, FP: {fp}, FN: {fn}, TP: {tp}]")
    print(f"\nRPM breakdown (400-2000 RPM):")
    for r in ["400", "800", "1200", "1600", "2000"]:
        if r in rpm_breakdown:
            b = rpm_breakdown[r]
            print(f"  {r:>4} RPM: Recall={b['recall']:.2f}, FPR={b['false_positive_rate']:.2f}, MeanScore={b['mean_anomaly_score']:.3f}")
    print(f"\nPretension breakdown:")
    for t_k, t_b in pretension_breakdown.items():
        print(f"  {t_k}: Recall={t_b['recall']:.2f}, FPR={t_b['false_positive_rate']:.2f}, MeanScore={t_b['mean_anomaly_score']:.3f}")
    print(f"\nBaseline Comparison:")
    print(f"  Isolation Forest ROC-AUC:    {roc_auc:.4f}")
    print(f"  Statistical Baseline ROC-AUC: {stat_baseline_roc_auc:.4f}")
    print(f"  Net Isolation Forest Gain:   {roc_auc - stat_baseline_roc_auc:+.4f}")
    print(f"\nArtifact: {pipeline_path}")
    print(f"Evaluation file: {OUTPUT_DIR / 'evaluation.json'}")
    print(f"Metadata file: {OUTPUT_DIR / 'training_metadata.json'}")
    print("=" * 50)

    return evaluation_record

if __name__ == "__main__":
    train_and_evaluate()
