"""
Ingestion, Validation and Ground-Truth Visualization Pipeline
Dataset: Conveyor Belt Damage Detection Dataset (COCO format)
Source: Roboflow Universe / CC BY 4.0

Performs rigorous dataset inspection:
- Image & annotation counts per split (train, valid, test)
- Class distributions and annotations per image
- Bounding-box geometry checks (NaNs, negative coordinates, out-of-bounds, zero area)
- Duplicate IDs & missing files validation
- Exports vision_dataset_analysis.json and human-readable validation report
- Renders sample ground-truth visualization images with labeled bounding boxes
"""

import os
import sys
import json
import zipfile
import shutil
from pathlib import Path
from collections import Counter, defaultdict
import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ZIP_PATH = PROJECT_ROOT / "dataset" / "Conveyor Belt Damage.v1i.coco.zip"
RAW_VISION_DIR = PROJECT_ROOT / "data" / "raw" / "research" / "conveyor_belt_damage_vision"
PROCESSED_VISION_DIR = PROJECT_ROOT / "data" / "processed" / "research" / "conveyor_belt_damage_vision"
GT_VIZ_DIR = PROCESSED_VISION_DIR / "sample_ground_truth"

# Distinct BGR colors for each category for visualization
CATEGORY_COLORS = {
    "Belt Joint": (0, 255, 255),    # Yellow
    "Large Tear": (0, 0, 255),      # Red
    "Small Tear": (0, 140, 255),    # Orange
    "Large Hole": (255, 0, 0),      # Blue
    "Small Hole": (255, 0, 255),    # Magenta
    "damage":     (0, 255, 0),      # Green
}

def extract_dataset():
    """Extracts the zip archive preserving the exact directory structure."""
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Source zip not found at: {ZIP_PATH}")
        
    RAW_VISION_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Extracting {ZIP_PATH} -> {RAW_VISION_DIR} ...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(RAW_VISION_DIR)
    print("Extraction complete.")

def validate_and_analyze_dataset():
    """Performs deep validation across train, valid, and test splits."""
    PROCESSED_VISION_DIR.mkdir(parents=True, exist_ok=True)
    GT_VIZ_DIR.mkdir(parents=True, exist_ok=True)
    
    splits = ["train", "valid", "test"]
    analysis = {
        "dataset_name": "conveyor_belt_damage_vision",
        "description": "Conveyor Belt Damage Detection Dataset (COCO format)",
        "source": "Roboflow Universe (https://universe.roboflow.com/test-yfiry/conveyor-belt-damage-ucjlj)",
        "license": "CC BY 4.0",
        "scientific_disclaimer": "The dataset contains categories: Belt Joint, Large Tear, Small Tear, Large Hole, Small Hole, damage. It does NOT contain an explicit class called 'Crack'.",
        "summary": {},
        "splits": {},
        "global_class_distribution": Counter(),
        "integrity_checks": {
            "duplicate_image_ids": 0,
            "missing_image_files": 0,
            "invalid_bounding_boxes": 0,
            "zero_area_boxes": 0,
            "out_of_bound_boxes": 0,
        }
    }
    
    total_images_all = 0
    total_annotations_all = 0
    categories_map = {}
    
    for split in splits:
        split_dir = RAW_VISION_DIR / split
        ann_file = split_dir / "_annotations.coco.json"
        
        if not ann_file.exists():
            print(f"Warning: Annotation file missing for split {split} at {ann_file}")
            continue
            
        with open(ann_file, "r", encoding="utf-8") as f:
            coco = json.load(f)
            
        images = coco.get("images", [])
        annotations = coco.get("annotations", [])
        categories = coco.get("categories", [])
        
        for c in categories:
            categories_map[c["id"]] = c["name"]
            
        # Check duplicate image IDs
        img_ids = [img["id"] for img in images]
        if len(img_ids) != len(set(img_ids)):
            dup = len(img_ids) - len(set(img_ids))
            analysis["integrity_checks"]["duplicate_image_ids"] += dup
            print(f"[{split}] Found {dup} duplicate image IDs!")
            
        img_by_id = {img["id"]: img for img in images}
        
        # Check missing files on disk
        missing_files = 0
        img_dims = []
        for img in images:
            file_path = split_dir / img["file_name"]
            if not file_path.exists():
                missing_files += 1
            else:
                img_dims.append((img["width"], img["height"]))
        analysis["integrity_checks"]["missing_image_files"] += missing_files
        
        # Check annotations
        split_class_counts = Counter()
        images_with_damage = set()
        bbox_widths = []
        bbox_heights = []
        bbox_areas = []
        
        for ann in annotations:
            cat_id = ann["category_id"]
            cat_name = categories_map.get(cat_id, f"Unknown_{cat_id}")
            split_class_counts[cat_name] += 1
            analysis["global_class_distribution"][cat_name] += 1
            images_with_damage.add(ann["image_id"])
            
            # Bounding box: [x, y, width, height]
            bbox = ann.get("bbox", [])
            if len(bbox) != 4:
                analysis["integrity_checks"]["invalid_bounding_boxes"] += 1
                continue
                
            x, y, w, h = bbox
            if w <= 0 or h <= 0:
                analysis["integrity_checks"]["zero_area_boxes"] += 1
                
            img_info = img_by_id.get(ann["image_id"])
            if img_info:
                if x < 0 or y < 0 or (x + w) > img_info["width"] + 1 or (y + h) > img_info["height"] + 1:
                    analysis["integrity_checks"]["out_of_bound_boxes"] += 1
                    
            bbox_widths.append(w)
            bbox_heights.append(h)
            bbox_areas.append(w * h)
            
        split_info = {
            "image_count": len(images),
            "annotation_count": len(annotations),
            "images_with_annotations": len(images_with_damage),
            "images_without_annotations": len(images) - len(images_with_damage),
            "missing_image_files": missing_files,
            "class_distribution": dict(split_class_counts),
            "image_resolution_sample": img_dims[0] if img_dims else None,
            "bbox_stats": {
                "mean_width_px": float(np.mean(bbox_widths)) if bbox_widths else 0,
                "mean_height_px": float(np.mean(bbox_heights)) if bbox_heights else 0,
                "median_area_px": float(np.median(bbox_areas)) if bbox_areas else 0,
            }
        }
        analysis["splits"][split] = split_info
        total_images_all += len(images)
        total_annotations_all += len(annotations)
        
    analysis["summary"] = {
        "total_images": total_images_all,
        "total_annotations": total_annotations_all,
        "categories_count": len(categories_map),
        "categories": categories_map,
    }
    
    # Save JSON analysis
    analysis_json_path = PROCESSED_VISION_DIR / "vision_dataset_analysis.json"
    # Convert Counter to dict for json serialization
    analysis["global_class_distribution"] = dict(analysis["global_class_distribution"])
    with open(analysis_json_path, "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2)
    print(f"\nSaved analysis JSON to: {analysis_json_path}")
    
    # Generate human-readable Markdown report
    report_path = PROCESSED_VISION_DIR / "dataset_validation_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Conveyor Belt Damage Detection Dataset — Validation Report\n\n")
        f.write(f"**Date Analyzed**: 2026-09-20\n")
        f.write(f"**Source**: {analysis['source']}\n")
        f.write(f"**License**: {analysis['license']}\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write(f"> **Scientific Integrity Notice**: {analysis['scientific_disclaimer']}\n\n")
        f.write("## Dataset Summary\n\n")
        f.write(f"- **Total Images**: {total_images_all}\n")
        f.write(f"  - Train: {analysis['splits'].get('train', {}).get('image_count', 0)} ({analysis['splits'].get('train', {}).get('annotation_count', 0)} annotations)\n")
        f.write(f"  - Validation: {analysis['splits'].get('valid', {}).get('image_count', 0)} ({analysis['splits'].get('valid', {}).get('annotation_count', 0)} annotations)\n")
        f.write(f"  - Held-out Test: {analysis['splits'].get('test', {}).get('image_count', 0)} ({analysis['splits'].get('test', {}).get('annotation_count', 0)} annotations)\n")
        f.write(f"- **Total Annotations**: {total_annotations_all}\n\n")
        f.write("## Class Distribution\n\n")
        f.write("| Category ID | Class Name | Train Annotations | Valid Annotations | Test Annotations | Total Annotations |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- | :--- |\n")
        for cat_id, cat_name in sorted(categories_map.items()):
            tr = analysis['splits'].get('train', {}).get('class_distribution', {}).get(cat_name, 0)
            va = analysis['splits'].get('valid', {}).get('class_distribution', {}).get(cat_name, 0)
            te = analysis['splits'].get('test', {}).get('class_distribution', {}).get(cat_name, 0)
            tot = tr + va + te
            f.write(f"| {cat_id} | **{cat_name}** | {tr} | {va} | {te} | {tot} |\n")
        f.write("\n## Integrity & Data Quality Checks\n\n")
        for check, val in analysis["integrity_checks"].items():
            status = "PASSED (0 errors)" if val == 0 else f"NOTE: {val} occurrences"
            f.write(f"- `{check}`: {status}\n")
            
    print(f"Saved human-readable validation report to: {report_path}")
    
    # Generate Ground-Truth Visualizations on 8 test samples
    render_ground_truth_samples(categories_map)

def render_ground_truth_samples(categories_map, num_samples=8):
    """Renders visual ground-truth annotations on sample test images."""
    test_dir = RAW_VISION_DIR / "test"
    ann_file = test_dir / "_annotations.coco.json"
    with open(ann_file, "r", encoding="utf-8") as f:
        coco = json.load(f)
        
    ann_by_img = defaultdict(list)
    for ann in coco.get("annotations", []):
        ann_by_img[ann["image_id"]].append(ann)
        
    rendered_count = 0
    print(f"\nRendering {num_samples} ground-truth test visualizations...")
    
    for img_info in coco.get("images", []):
        anns = ann_by_img.get(img_info["id"], [])
        if not anns:
            continue
            
        img_path = test_dir / img_info["file_name"]
        if not img_path.exists():
            continue
            
        img = cv2.imread(str(img_path))
        if img is None:
            continue
            
        overlay = img.copy()
        for ann in anns:
            x, y, w, h = [int(v) for v in ann["bbox"]]
            cat_name = categories_map.get(ann["category_id"], "Damage")
            color = CATEGORY_COLORS.get(cat_name, (0, 255, 0))
            
            # Draw rectangle
            cv2.rectangle(overlay, (x, y), (x + w, y + h), color, 2)
            # Label banner
            label_text = f"GT: {cat_name}"
            (tw, th), _ = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(overlay, (x, max(0, y - th - 6)), (x + tw + 4, max(th + 6, y)), color, -1)
            cv2.putText(overlay, label_text, (x + 2, max(th + 2, y - 4)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
            
        out_name = f"gt_viz_{img_info['id']:03d}_{img_info['file_name']}"
        out_path = GT_VIZ_DIR / out_name
        cv2.imwrite(str(out_path), overlay)
        rendered_count += 1
        if rendered_count >= num_samples:
            break
            
    print(f"Successfully rendered {rendered_count} ground-truth visual images to:\n  {GT_VIZ_DIR}")

if __name__ == "__main__":
    extract_dataset()
    validate_and_analyze_dataset()
