"""
Converts COCO JSON annotations to YOLO format labels for reproducible training.
Preserves original COCO annotations in data/raw/research/conveyor_belt_damage_vision/
Creates data/processed/research/conveyor_belt_damage_vision/yolo_dataset/
"""

import json
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RAW_VISION_DIR = PROJECT_ROOT / "data" / "raw" / "research" / "conveyor_belt_damage_vision"
YOLO_DIR = PROJECT_ROOT / "data" / "processed" / "research" / "conveyor_belt_damage_vision" / "yolo_dataset"

CATEGORIES = {
    0: "damage",
    1: "Belt Joint",
    2: "Large Hole",
    3: "Large Tear",
    4: "Small Hole",
    5: "Small Tear"
}

def prepare_yolo_structure():
    YOLO_DIR.mkdir(parents=True, exist_ok=True)
    splits = ["train", "valid", "test"]
    
    print("Converting COCO JSON annotations to YOLO format...")
    
    for split in splits:
        src_split_dir = RAW_VISION_DIR / split
        dst_img_dir = YOLO_DIR / split / "images"
        dst_lbl_dir = YOLO_DIR / split / "labels"
        dst_img_dir.mkdir(parents=True, exist_ok=True)
        dst_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        coco_file = src_split_dir / "_annotations.coco.json"
        if not coco_file.exists():
            print(f"Warning: {coco_file} not found")
            continue
            
        with open(coco_file, "r", encoding="utf-8") as f:
            coco = json.load(f)
            
        images = {img["id"]: img for img in coco["images"]}
        img_annotations = {img["id"]: [] for img in coco["images"]}
        
        for ann in coco.get("annotations", []):
            img_id = ann["image_id"]
            if img_id in img_annotations:
                img_annotations[img_id].append(ann)
                
        # Copy images and write normalized YOLO label files
        count = 0
        for img_id, img_info in images.items():
            src_img_path = src_split_dir / img_info["file_name"]
            dst_img_path = dst_img_dir / img_info["file_name"]
            
            # Copy or symlink image
            if not dst_img_path.exists() and src_img_path.exists():
                shutil.copy2(src_img_path, dst_img_path)
                
            # Write labels
            label_name = Path(img_info["file_name"]).stem + ".txt"
            label_path = dst_lbl_dir / label_name
            
            W = float(img_info["width"])
            H = float(img_info["height"])
            
            with open(label_path, "w", encoding="utf-8") as lf:
                for ann in img_annotations[img_id]:
                    cat_id = ann["category_id"]
                    x, y, w, h = ann["bbox"]
                    
                    # Normalize to 0..1
                    xc = (x + w / 2.0) / W
                    yc = (y + h / 2.0) / H
                    wn = w / W
                    hn = h / H
                    
                    # Clamp
                    xc = max(0.0, min(1.0, xc))
                    yc = max(0.0, min(1.0, yc))
                    wn = max(0.0, min(1.0, wn))
                    hn = max(0.0, min(1.0, hn))
                    
                    lf.write(f"{cat_id} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}\n")
            count += 1
            
        print(f"  [{split}] Prepared {count} images and label files.")
        
    # Write dataset YAML for YOLO
    yaml_path = YOLO_DIR / "conveyor_damage.yaml"
    # Use relative or posix paths for portability
    yaml_content = f"""path: {YOLO_DIR.as_posix()}
train: train/images
val: valid/images
test: test/images

names:
  0: damage
  1: Belt Joint
  2: Large Hole
  3: Large Tear
  4: Small Hole
  5: Small Tear
"""
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print(f"Created YOLO dataset configuration at: {yaml_path}")
    return yaml_path

if __name__ == "__main__":
    prepare_yolo_structure()
