import sys
import os
import json
from pathlib import Path
from PIL import Image

def convert_itp_to_anylabel(itp_json_path):
    base_dir = Path(itp_json_path).parent
    with open(itp_json_path, 'r', encoding='utf-8') as f:
        itp_data = json.load(f)

    images = itp_data.get("images", {})
    for img_name, data in images.items():
        image_path = base_dir / img_name
        if not image_path.exists():
            print(f"[跳过] 图片不存在：{img_name}")
            continue

        with Image.open(image_path) as img:
            width, height = img.size

        shapes = []
        for box in data.get("boxes", []):
            geo = box.get("geometry", {})
            x, y = geo.get("X", 0), geo.get("Y", 0)
            w, h = geo.get("width", 0), geo.get("height", 0)

            points = [
                [x, y],
                [x + w, y],
                [x + w, y + h],
                [x, y + h]
            ]
            description = box.get("text", "")
            label = box.get("fontstyle", "balloon")  # 这里改成读取 fontstyle 字段

            shape = {
                "label": label,
                "score": None,
                "points": points,
                "group_id": None,
                "description": description,
                "difficult": False,
                "shape_type": "rectangle",
                "flags": {},
                "attributes": {},
                "kie_linking": []
            }
            shapes.append(shape)

        anylabel_data = {
            "version": "2.5.0",
            "flags": {},
            "shapes": shapes,
            "imagePath": img_name,
            "imageData": None,
            "imageHeight": height,
            "imageWidth": width,
            "description": ""
        }

        output_path = base_dir / f"{Path(img_name).stem}.json"
        with open(output_path, 'w', encoding='utf-8') as out_f:
            json.dump(anylabel_data, out_f, ensure_ascii=False, indent=2)
        print(f"[完成] 生成标注：{output_path.name}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("请将 ITP 项目的 JSON 文件拖到这个脚本上运行。")
        sys.exit(1)
    convert_itp_to_anylabel(sys.argv[1])
