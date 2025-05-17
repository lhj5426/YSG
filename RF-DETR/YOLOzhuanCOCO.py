#!/usr/bin/env python
import os
import sys
import json
import glob
import shutil
import random
import argparse
from PIL import Image

try:
    import yaml
except ImportError:
    yaml = None

def convert_yolo_to_coco(image_paths, labels_dir, class_name="custom", add_dummy=False, categories=None):
    if categories is None:
        if add_dummy:
            categories = [
                {"id": 0, "name": "background", "supercategory": "none"},
                {"id": 1, "name": class_name, "supercategory": class_name}
            ]
        else:
            categories = [{"id": 1, "name": class_name, "supercategory": "none"}]
        use_multiclass = False
    else:
        use_multiclass = True

    coco = {
        "images": [],
        "annotations": [],
        "categories": categories
    }
    
    annotation_id = 1
    image_id = 1
    for img_path in image_paths:
        filename = os.path.basename(img_path)
        with Image.open(img_path) as img:
            width, height = img.size
        
        coco["images"].append({
            "id": image_id,
            "file_name": filename,
            "width": width,
            "height": height
        })

        base, _ = os.path.splitext(filename)

        # For labels, check subfolders in labels_dir to match images in subfolders.
        label_file = None
        # Try to find label file by matching relative path after images_dir
        rel_path = os.path.relpath(img_path, os.path.commonpath([img_path, labels_dir]))
        # rel_path might be e.g. train/QCSP00001.jpg
        # Replace extension and join with labels_dir to find label path
        label_file_candidate = os.path.join(labels_dir, os.path.splitext(rel_path)[0] + ".txt")
        if os.path.exists(label_file_candidate):
            label_file = label_file_candidate
        else:
            # fallback: try label in root labels_dir (for flat structure)
            label_file = os.path.join(labels_dir, base + ".txt")
            if not os.path.exists(label_file):
                label_file = None

        if label_file and os.path.exists(label_file):
            with open(label_file, "r") as f:
                lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    continue
                if use_multiclass:
                    cls_idx = int(parts[0])
                    category_id = cls_idx + 1
                else:
                    category_id = 1
                _, x_center, y_center, w_norm, h_norm = map(float, parts)
                x_center_abs = x_center * width
                y_center_abs = y_center * height
                w_abs = w_norm * width
                h_abs = h_norm * height
                x_min = x_center_abs - (w_abs / 2)
                y_min = y_center_abs - (h_abs / 2)

                annotation = {
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": category_id,
                    "bbox": [x_min, y_min, w_abs, h_abs],
                    "area": w_abs * h_abs,
                    "iscrowd": 0
                }
                coco["annotations"].append(annotation)
                annotation_id += 1
        image_id += 1
    
    return coco

def create_coco_dataset_from_yolo(yolo_dataset_dir, output_dir, class_name="custom",
                                  add_dummy=False, categories=None, split_ratios=(0.8, 0.1, 0.1)):
    images_dir = os.path.join(yolo_dataset_dir, "images")
    labels_dir = os.path.join(yolo_dataset_dir, "labels")

    if not os.path.exists(images_dir) or not os.path.exists(labels_dir):
        raise FileNotFoundError(f"在目录 {yolo_dataset_dir} 中未找到 images 或 labels 文件夹。")

    image_extensions = ("*.jpg", "*.jpeg", "*.png")
    if sys.platform != "win32":
        image_extensions += tuple(ext.upper() for ext in image_extensions)

    image_paths = []
    for ext in image_extensions:
        image_paths.extend(glob.glob(os.path.join(images_dir, "**", ext), recursive=True))

    if not image_paths:
        raise ValueError(f"在 {images_dir} 目录及子目录中未找到任何图片文件。")

    random.shuffle(image_paths)
    num_images = len(image_paths)
    train_end = int(split_ratios[0] * num_images)
    valid_end = train_end + int(split_ratios[1] * num_images)

    splits = {
        "train": image_paths[:train_end],
        "valid": image_paths[train_end:valid_end],
        "test": image_paths[valid_end:]
    }

    os.makedirs(output_dir, exist_ok=True)

    for split_name, paths in splits.items():
        split_dir = os.path.join(output_dir, split_name)
        os.makedirs(split_dir, exist_ok=True)

        # 复制图片
        for img_path in paths:
            shutil.copy(img_path, os.path.join(split_dir, os.path.basename(img_path)))

        # 生成 COCO 注释文件
        coco_annotations = convert_yolo_to_coco(paths, labels_dir, class_name=class_name,
                                                add_dummy=add_dummy, categories=categories)
        json_path = os.path.join(split_dir, "_annotations.coco.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(coco_annotations, f, indent=4, ensure_ascii=False)
        print(f"已创建 {json_path}：共 {len(coco_annotations['images'])} 张图片，{len(coco_annotations['annotations'])} 个标注。")

    return output_dir

def main():
    if len(sys.argv) < 2:
        print("用法示例: python YOLOzhuanCOCO.py <yolo_dataset_root_dir>")
        print("注意：该目录应包含 'images' 和 'labels' 子目录，及多类别时的 yaml 文件。")
        sys.exit(1)

    yolo_dataset_dir = sys.argv[1]
    if not os.path.isdir(yolo_dataset_dir):
        print(f"错误：传入的目录不存在：{yolo_dataset_dir}")
        sys.exit(1)

    # 自动找 yaml 文件（假设目录下只有一个 .yaml 或 .yml 文件）
    yaml_files = [f for f in os.listdir(yolo_dataset_dir) if f.endswith((".yaml", ".yml"))]
    yaml_file = None
    if yaml_files:
        yaml_file = os.path.join(yolo_dataset_dir, yaml_files[0])
        print(f"✔ 已找到 YAML 文件：{yaml_file}")
    else:
        print("⚠️ 未找到 YAML 文件，将按单类别处理")

    categories = None
    if yaml_file:
        if yaml is None:
            print("请安装 pyyaml：pip install pyyaml")
            sys.exit(1)
        with open(yaml_file, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        names = yaml_data.get("names")
        if not names:
            print(f"YAML 文件 {yaml_file} 中未找到 'names' 键。")
            sys.exit(1)
        categories = [{"id": i + 1, "name": name, "supercategory": "none"} for i, name in enumerate(names)]
        print(f"Loaded {len(categories)} classes from YAML file.")

    # 输出文件夹名：脚本所在目录下的 RFDTREzhuan
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "RFDTREzhuan")

    print("开始转换 YOLO 格式数据集到 COCO 格式...")
    create_coco_dataset_from_yolo(
        yolo_dataset_dir=yolo_dataset_dir,
        output_dir=output_dir,
        add_dummy=False,
        categories=categories
    )
    print("转换完成，结果保存在：", output_dir)

if __name__ == "__main__":
    main()
