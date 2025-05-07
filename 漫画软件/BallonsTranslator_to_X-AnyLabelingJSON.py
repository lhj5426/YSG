import sys
import os
import json
from pathlib import Path

def convert_ballons_to_anylabel(ballons_json_path):
    base_dir = Path(ballons_json_path).parent
    with open(ballons_json_path, 'r', encoding='utf-8') as f:
        ballons_data = json.load(f)

    pages = ballons_data.get('pages', {})
    for img_name, items in pages.items():
        image_path = base_dir / img_name
        if not image_path.exists():
            print(f"[跳过] 图片不存在：{img_name}")
            continue

        # 默认图片大小，如果需要精确可使用 PIL 获取
        from PIL import Image
        with Image.open(image_path) as img:
            width, height = img.size

        shapes = []
        for item in items:
            text_list = item.get('text', [])
            if not text_list:
                continue
            description = ''.join(text_list)
            xyxy = item.get('xyxy', None)
            if xyxy and len(xyxy) == 4:
                x1, y1, x2, y2 = xyxy
                shape_points = [
                    [x1, y1],
                    [x2, y1],
                    [x2, y2],
                    [x1, y2]
                ]
            else:
                lines = item.get('lines', [])
                if lines and isinstance(lines[0], list):
                    shape_points = lines[0]
                else:
                    print(f"[警告] 无效坐标数据: {img_name}")
                    continue

            shape = {
                "label": "balloon",
                "score": None,
                "points": shape_points,
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
        print("请将 BallonsTranslator 的 JSON 文件拖到这个脚本上运行。")
        sys.exit(1)
    convert_ballons_to_anylabel(sys.argv[1])
