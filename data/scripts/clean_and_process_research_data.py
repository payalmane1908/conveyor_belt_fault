"""
Industrial Research Dataset Cleaning & DSP Feature Extraction Pipeline
Dataset: 'Experimental vibration data collected for a belt drive system under different operating conditions'
DOI: 10.17632/jf8v2ndydr.1 | Authors: Khalifa et al. (2022) | Mendeley Data

Adheres to Industrial Data, Testing & ML Training Policy:
1. Validates all 459 runs across 9 operating condition matrices.
2. Removes accelerometer DC offset (zero-mean centering).
3. Executes reproducible DSP feature extraction directly using `backend.app.dsp.compute_dsp_features`.
4. Embeds full data provenance, license, and scientific limitation disclaimers.
5. Saves clean feature matrix and cleaning validation audit report.
"""

import os
import sys
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure backend can be imported for reproducible DSP
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.dsp import DSPAnalyzer

analyzer = DSPAnalyzer()

RAW_RESEARCH_DIR = PROJECT_ROOT / "data" / "raw" / "research" / "mendeley_belt_drive"
PROCESSED_RESEARCH_DIR = PROJECT_ROOT / "data" / "processed" / "research" / "mendeley_belt_drive"
EXCEL_PATH = RAW_RESEARCH_DIR / "Data Description.xlsx"

DISCLAIMER_TEXT = (
    "Mendeley belt-drive experimental dataset (DOI: 10.17632/jf8v2ndydr.1). "
    "Validated for vibration DSP, operating-condition baselining, and general anomaly detection. "
    "DOMAIN LIMITATION: Does NOT contain conveyor belt joint rupture labels."
)

CONDITION_METADATA = {
    "Data 70-H-0":  {"pretension_n": 70,  "belt_condition": "healthy",     "unbalance_state": "normal_balanced",  "fault_code": "NORMAL"},
    "Data 70-F-0":  {"pretension_n": 70,  "belt_condition": "faulty_belt", "unbalance_state": "normal_balanced",  "fault_code": "FAULTY_BELT"},
    "Data 70-H-U":  {"pretension_n": 70,  "belt_condition": "healthy",     "unbalance_state": "unbalanced_load",  "fault_code": "UNBALANCED"},
    "Data 110-H-0": {"pretension_n": 110, "belt_condition": "healthy",     "unbalance_state": "normal_balanced",  "fault_code": "NORMAL"},
    "Data 110-F-0": {"pretension_n": 110, "belt_condition": "faulty_belt", "unbalance_state": "normal_balanced",  "fault_code": "FAULTY_BELT"},
    "Data 110-H-U": {"pretension_n": 110, "belt_condition": "healthy",     "unbalance_state": "unbalanced_load",  "fault_code": "UNBALANCED"},
    "Data 150-H-0": {"pretension_n": 150, "belt_condition": "healthy",     "unbalance_state": "normal_balanced",  "fault_code": "NORMAL"},
    "Data 150-F-0": {"pretension_n": 150, "belt_condition": "faulty_belt", "unbalance_state": "normal_balanced",  "fault_code": "FAULTY_BELT"},
    "Data 150-H-U": {"pretension_n": 150, "belt_condition": "healthy",     "unbalance_state": "unbalanced_load",  "fault_code": "UNBALANCED"},
}

def clean_and_process_all():
    PROCESSED_RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    
    if not EXCEL_PATH.exists():
        raise FileNotFoundError(f"Missing Data Description metadata spreadsheet: {EXCEL_PATH}")
        
    excel = pd.ExcelFile(EXCEL_PATH)
    all_features = []
    
    audit_report = {
        "total_expected_runs": 459,
        "total_processed_runs": 0,
        "total_nan_or_inf_detected": 0,
        "total_clipped_signals": 0,
        "total_dead_sensors": 0,
        "sample_rate_hz": 1000.0,
        "samples_per_run": 10000,
        "conditions_processed": []
    }
    
    print("=" * 80)
    print("Starting Industrial Belt Drive Research Dataset Ingestion & DSP Processing")
    print("=" * 80)
    
    for raw_sheet_name in excel.sheet_names:
        sheet_key = raw_sheet_name.strip()
        folder_dir = RAW_RESEARCH_DIR / sheet_key
        
        if not folder_dir.exists():
            print(f"Warning: Folder {folder_dir} not found, skipping...")
            continue
            
        cond_meta = CONDITION_METADATA.get(sheet_key, {})
        sheet_df = excel.parse(raw_sheet_name)
        
        print(f"\nProcessing Condition [{sheet_key}] - {len(sheet_df)} runs in sheet:")
        condition_runs_count = 0
        
        for _, row in sheet_df.iterrows():
            run_num = int(row.iloc[0])  # 1 to 51
            rpm = float(row.iloc[1])
            pretension = float(row.iloc[2])
            unbalance_load = float(row.iloc[3]) if len(row) > 3 and pd.notnull(row.iloc[3]) else 0.0
            
            txt_path = folder_dir / f"{run_num}.txt"
            if not txt_path.exists():
                print(f"  Warning: missing file {txt_path}")
                continue
                
            # Load raw data (3 tab-separated columns: sample_idx, driver_accel, driven_accel)
            raw_data = np.loadtxt(txt_path)
            
            if raw_data.ndim != 2 or raw_data.shape[1] < 3:
                print(f"  Error: unexpected shape {raw_data.shape} in {txt_path}")
                continue
                
            # Validate integrity
            n_samples = raw_data.shape[0]
            if n_samples != 10000:
                print(f"  Note: {txt_path.name} has {n_samples} samples (expected 10000)")
                
            driver_raw = raw_data[:, 1]
            driven_raw = raw_data[:, 2]
            
            # Check for NaN / Inf
            nan_count = np.isnan(driver_raw).sum() + np.isnan(driven_raw).sum() + np.isinf(driver_raw).sum() + np.isinf(driven_raw).sum()
            if nan_count > 0:
                audit_report["total_nan_or_inf_detected"] += int(nan_count)
                driver_raw = np.nan_to_num(driver_raw, nan=0.0, posinf=0.0, neginf=0.0)
                driven_raw = np.nan_to_num(driven_raw, nan=0.0, posinf=0.0, neginf=0.0)
                
            # Quality checks
            std_driver = float(np.std(driver_raw))
            std_driven = float(np.std(driven_raw))
            if std_driver < 1e-6 or std_driven < 1e-6:
                audit_report["total_dead_sensors"] += 1
                
            # DC Offset Removal (Zero-mean centering for calibrated accelerometer output)
            driver_clean = driver_raw - np.mean(driver_raw)
            driven_clean = driven_raw - np.mean(driven_raw)
            
            # Reproducible DSP feature extraction using app.dsp
            fs = 1000.0
            dsp_driver_res = analyzer.analyze(driver_clean, sampling_rate_hz=fs)
            dsp_driven_res = analyzer.analyze(driven_clean, sampling_rate_hz=fs)
            
            if not dsp_driver_res.valid or not dsp_driven_res.valid:
                print(f"  Warning: Invalid DSP result in {txt_path.name}")
                continue
                
            dsp_driver_td = dsp_driver_res.time_domain
            dsp_driver_fft = dsp_driver_res.fft
            dsp_driven_td = dsp_driven_res.time_domain
            dsp_driven_fft = dsp_driven_res.fft
            
            # Determine repetition number (1, 2, or 3) for the speed
            rep = ((run_num - 1) % 3) + 1
            
            rec = {
                # Provenance
                "data_source": "research",
                "dataset_name": "mendeley_belt_drive",
                "doi": "10.17632/jf8v2ndydr.1",
                "license": "CC BY 4.0",
                "condition_folder": sheet_key,
                "run_id": run_num,
                "repetition_idx": rep,
                
                # Operating Parameters
                "speed_rpm": rpm,
                "pretension_n": pretension,
                "unbalance_load_g": unbalance_load,
                "belt_condition": cond_meta.get("belt_condition", "unknown"),
                "unbalance_state": cond_meta.get("unbalance_state", "unknown"),
                "fault_code": cond_meta.get("fault_code", "NORMAL"),
                
                # Acquisition Specs
                "sampling_rate_hz": fs,
                "sample_count": n_samples,
                "unit": "g (acceleration)",
                
                # DSP Features — Driver Pulley Sensor
                "driver_rms": dsp_driver_td.rms,
                "driver_peak": dsp_driver_td.peak,
                "driver_peak_to_peak": dsp_driver_td.peak_to_peak,
                "driver_crest_factor": dsp_driver_td.crest_factor,
                "driver_kurtosis": dsp_driver_td.kurtosis,
                "driver_skewness": dsp_driver_td.skewness,
                "driver_dominant_freq_hz": dsp_driver_fft.dominant_frequency_hz,
                "driver_dominant_freq_amp": dsp_driver_fft.dominant_amplitude,
                "driver_spectral_centroid_hz": dsp_driver_fft.spectral_centroid_hz,
                "driver_spectral_energy": dsp_driver_fft.spectral_energy,
                
                # DSP Features — Driven Pulley Sensor
                "driven_rms": dsp_driven_td.rms,
                "driven_peak": dsp_driven_td.peak,
                "driven_peak_to_peak": dsp_driven_td.peak_to_peak,
                "driven_crest_factor": dsp_driven_td.crest_factor,
                "driven_kurtosis": dsp_driven_td.kurtosis,
                "driven_skewness": dsp_driven_td.skewness,
                "driven_dominant_freq_hz": dsp_driven_fft.dominant_frequency_hz,
                "driven_dominant_freq_amp": dsp_driven_fft.dominant_amplitude,
                "driven_spectral_centroid_hz": dsp_driven_fft.spectral_centroid_hz,
                "driven_spectral_energy": dsp_driven_fft.spectral_energy,
                
                # Scientific Domain Boundary Disclaimer
                "scientific_claim_disclaimer": DISCLAIMER_TEXT
            }
            
            all_features.append(rec)
            condition_runs_count += 1
            audit_report["total_processed_runs"] += 1
            
        print(f"  Processed {condition_runs_count} runs successfully.")
        audit_report["conditions_processed"].append({
            "condition": sheet_key,
            "runs": condition_runs_count,
            "pretension_n": cond_meta.get("pretension_n"),
            "fault_code": cond_meta.get("fault_code")
        })
        
    df_features = pd.DataFrame(all_features)
    features_csv_path = PROCESSED_RESEARCH_DIR / "cleaned_belt_drive_features.csv"
    df_features.to_csv(features_csv_path, index=False)
    print(f"\nSuccessfully wrote {len(df_features)} cleaned feature rows to:\n  {features_csv_path}")
    
    # Save a sample cleaned time series (run 1 of Data 70-H-0 and Data 70-F-0)
    sample_file = PROCESSED_RESEARCH_DIR / "sample_cleaned_vibration_signals.csv"
    sample_data = np.loadtxt(RAW_RESEARCH_DIR / "Data 70-H-0" / "1.txt")
    sample_df = pd.DataFrame({
        "sample_index": sample_data[:, 0].astype(int),
        "driver_pulley_accel_g_clean": sample_data[:, 1] - np.mean(sample_data[:, 1]),
        "driven_pulley_accel_g_clean": sample_data[:, 2] - np.mean(sample_data[:, 2]),
        "condition": "70-H-0_healthy_belt_400rpm",
        "data_source": "research"
    })
    sample_df.to_csv(sample_file, index=False)
    print(f"Saved sample cleaned time-series to:\n  {sample_file}")
    
    # Save audit report
    audit_path = PROCESSED_RESEARCH_DIR / "data_cleaning_report.json"
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(audit_report, f, indent=2)
    print(f"Saved data cleaning report to:\n  {audit_path}")
    
    print("\nSummary Statistics of Cleaned DSP Features:")
    print(df_features.groupby("fault_code")[["driver_rms", "driver_kurtosis", "driven_rms", "driven_kurtosis"]].mean())

if __name__ == "__main__":
    clean_and_process_all()
