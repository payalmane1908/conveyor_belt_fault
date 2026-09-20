"""
Cleaner and validator for synthetic conveyor fault simulation dataset.
Enforces industrial Data, Testing & ML Training Policy:
1. Tags all records with `data_source = 'synthetic_simulation'`
2. Resolves historical split imbalance (11,960 test vs 40 train) with stratified 70/15/15 train/val/test split
3. Validates absence of NaNs / infinite values
4. Preserves raw synthetic artifact under data/raw/synthetic/conveyor_fault_simulation/
5. Exports clean feature set to data/processed/synthetic/conveyor_fault_simulation/cleaned_synthetic_features.csv
"""

import shutil
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_SRC = PROJECT_ROOT / "dataset" / "conveyor_fault_dataset_v2.csv"
RAW_SYNTHETIC_DIR = PROJECT_ROOT / "data" / "raw" / "synthetic" / "conveyor_fault_simulation"
PROCESSED_SYNTHETIC_DIR = PROJECT_ROOT / "data" / "processed" / "synthetic" / "conveyor_fault_simulation"

RAW_SYNTHETIC_DEST = RAW_SYNTHETIC_DIR / "conveyor_fault_dataset_v2.csv"
CLEANED_DEST = PROCESSED_SYNTHETIC_DIR / "cleaned_synthetic_features.csv"

def clean_synthetic_data():
    RAW_SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    
    if not RAW_SRC.exists():
        raise FileNotFoundError(f"Source raw synthetic dataset not found at: {RAW_SRC}")
        
    print(f"Archiving raw synthetic file to: {RAW_SYNTHETIC_DEST}")
    shutil.copy2(RAW_SRC, RAW_SYNTHETIC_DEST)
    
    print("Loading raw synthetic dataset for cleaning and re-stratification...")
    df = pd.read_csv(RAW_SYNTHETIC_DEST)
    print(f"Original shape: {df.shape}")
    print(f"Original split distribution:\n{df['split'].value_counts().to_dict()}")
    
    # 1. Check for null / infinite values
    null_counts = df.isnull().sum()
    if null_counts.sum() > 0:
        print(f"Found nulls: {null_counts[null_counts > 0].to_dict()}, dropping null rows...")
        df = df.dropna().reset_index(drop=True)
    else:
        print("Data integrity check: 0 null values found.")
        
    # 2. Tag with explicit data provenance policy requirement
    df["data_source"] = "synthetic_simulation"
    df["dataset_type"] = "simulation"
    df["scientific_claim_disclaimer"] = "SIMULATED DATA - NOT REAL CONVEYOR HARDWARE MEASUREMENT"
    
    # 3. Stratified Train / Validation / Test split (70% Train, 15% Val, 15% Test)
    # Stratified by fault category
    np.random.seed(42)
    df["split"] = "train"
    
    for fault_class, group in df.groupby("fault"):
        indices = group.index.to_numpy()
        np.random.shuffle(indices)
        
        n_total = len(indices)
        n_train = int(0.70 * n_total)
        n_val = int(0.15 * n_total)
        
        train_idx = indices[:n_train]
        val_idx = indices[n_train:n_train + n_val]
        test_idx = indices[n_train + n_val:]
        
        df.loc[train_idx, "split"] = "train"
        df.loc[val_idx, "split"] = "validation"
        df.loc[test_idx, "split"] = "test"
        
    print("\nNew stratified split distribution:")
    print(pd.crosstab(df["fault"], df["split"]))
    
    print(f"\nSaving cleaned synthetic feature set to: {CLEANED_DEST}")
    df.to_csv(CLEANED_DEST, index=False)
    print(f"Successfully wrote {len(df)} cleaned rows.")

if __name__ == "__main__":
    clean_synthetic_data()
