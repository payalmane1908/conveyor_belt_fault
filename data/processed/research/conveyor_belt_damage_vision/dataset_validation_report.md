# Conveyor Belt Damage Detection Dataset — Validation Report

**Date Analyzed**: 2026-09-20
**Source**: Roboflow Universe (https://universe.roboflow.com/test-yfiry/conveyor-belt-damage-ucjlj)
**License**: CC BY 4.0

> [!IMPORTANT]
> **Scientific Integrity Notice**: The dataset contains categories: Belt Joint, Large Tear, Small Tear, Large Hole, Small Hole, damage. It does NOT contain an explicit class called 'Crack'.

## Dataset Summary

- **Total Images**: 651
  - Train: 489 (1245 annotations)
  - Validation: 97 (271 annotations)
  - Held-out Test: 65 (192 annotations)
- **Total Annotations**: 1708

## Class Distribution

| Category ID | Class Name | Train Annotations | Valid Annotations | Test Annotations | Total Annotations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 0 | **damage** | 0 | 0 | 0 | 0 |
| 1 | **Belt Joint** | 60 | 14 | 7 | 81 |
| 2 | **Large Hole** | 300 | 62 | 43 | 405 |
| 3 | **Large Tear** | 255 | 60 | 43 | 358 |
| 4 | **Small Hole** | 339 | 64 | 55 | 458 |
| 5 | **Small Tear** | 291 | 71 | 44 | 406 |

## Integrity & Data Quality Checks

- `duplicate_image_ids`: PASSED (0 errors)
- `missing_image_files`: PASSED (0 errors)
- `invalid_bounding_boxes`: PASSED (0 errors)
- `zero_area_boxes`: PASSED (0 errors)
- `out_of_bound_boxes`: PASSED (0 errors)
