"""
Data Provenance & Policy Enforcement Module
===========================================
Enforces strict architectural separation across:
  - SOFTWARE TEST DATA
  - SIMULATION DATA
  - RESEARCH / TRAINING DATA
  - REAL HARDWARE / FIELD DATA

Guarantees scientific honesty, prevents synthetic data from masquerading
as empirical field measurements, and exposes dataset provenance to APIs.
"""

import json
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

class DataSourceCategory(str, Enum):
    RESEARCH = "RESEARCH"
    FIELD_HARDWARE = "FIELD_HARDWARE"
    SIMULATION = "SIMULATION"
    SOFTWARE_TEST = "SOFTWARE_TEST"

class ProvenanceEnforcer:
    """Enforces industrial policy rules against data mixing and fabricated claims."""
    
    @staticmethod
    def validate_category(category: str) -> bool:
        return category.upper() in {c.value for c in DataSourceCategory}
        
    @staticmethod
    def assert_no_silent_mixing(source_type: str, allowed_category: DataSourceCategory) -> None:
        """Raises ValueError if synthetic/simulation data is mixed into research or field data."""
        cat_upper = source_type.upper()
        if allowed_category in {DataSourceCategory.RESEARCH, DataSourceCategory.FIELD_HARDWARE}:
            if cat_upper in {DataSourceCategory.SIMULATION.value, DataSourceCategory.SOFTWARE_TEST.value, "SYNTHETIC"}:
                raise ValueError(
                    f"DATA POLICY VIOLATION: Cannot mix synthetic/simulation data ({source_type}) "
                    f"into production research/field pipeline ({allowed_category.value})."
                )

def get_dataset_manifest() -> Dict[str, Any]:
    """Reads the global dataset manifest file."""
    manifest_path = METADATA_DIR / "dataset_manifest.json"
    if not manifest_path.exists():
        return {"error": "Manifest not found", "path": str(manifest_path)}
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_provenance_metadata(dataset_name: str) -> Optional[Dict[str, Any]]:
    """Loads dataset-specific provenance metadata."""
    mapping = {
        "mendeley_belt_drive": "mendeley_belt_drive_provenance.json",
        "conveyor_fault_simulation": "conveyor_fault_synthetic_provenance.json",
    }
    filename = mapping.get(dataset_name)
    if not filename:
        return None
    file_path = METADATA_DIR / filename
    if not file_path.exists():
        return None
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def get_all_dataset_provenance() -> Dict[str, Any]:
    """Returns aggregated provenance information for all cataloged datasets."""
    manifest = get_dataset_manifest()
    mendeley = get_provenance_metadata("mendeley_belt_drive")
    synthetic = get_provenance_metadata("conveyor_fault_simulation")
    return {
        "manifest": manifest,
        "datasets": {
            "mendeley_belt_drive": mendeley,
            "conveyor_fault_simulation": synthetic,
        }
    }
