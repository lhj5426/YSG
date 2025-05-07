import os
import sys
import json

def convert_ipt_to_ballonstranslator(ipt_path, output_path):
    with open(ipt_path, 'r', encoding='utf-8') as f:
        ipt_data = json.load(f)

    result = {
        "directory": os.path.dirname(ipt_path),
        "pages": {},
        "current_img": ""
    }

    images = ipt_data.get("images", {})

    for img_name, img_info in images.items():
        boxes = img_info.get("boxes", [])
        output_boxes = []

        for box in boxes:
            # 直接处理所有框，不检查 fontstyle
            geo = box.get("geometry", {})
            x, y = geo.get("X", 0), geo.get("Y", 0)
            w, h = geo.get("width", 0), geo.get("height", 0)

            x1, y1 = x, y
            x2, y2 = x + w, y + h

            new_box = {
                "xyxy": [x1, y1, x2, y2],
                "lines": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]],
                "language": "unknown",
                "distance": [h],
                "angle": 0,
                "vec": [0.0, float(h)],
                "norm": float(h),
                "merged": False,
                "text": [box.get("text", "")],
                "translation": "",
                "rich_text": "",
                "_bounding_rect": [x1, y1, w, h],
                "src_is_vertical": True,
                "_detected_font_size": -1.0,
                "det_model": "ipt",
                "region_mask": None,
                "region_inpaint_dict": None,
                "fontformat": {
                    "font_family": "",
                    "font_size": 24.0,
                    "stroke_width": 0.0,
                    "frgb": [0, 0, 0],
                    "srgb": [0, 0, 0],
                    "bold": False,
                    "underline": False,
                    "italic": False,
                    "alignment": 0,
                    "vertical": True,
                    "font_weight": 400,
                    "line_spacing": 1.2,
                    "letter_spacing": 1.15,
                    "opacity": 1.0,
                    "shadow_radius": 0.0,
                    "shadow_strength": 1.0,
                    "shadow_color": [0, 0, 0],
                    "shadow_offset": [0.0, 0.0],
                    "gradient_enabled": False,
                    "gradient_start_color": [0, 0, 0],
                    "gradient_end_color": [255, 255, 255],
                    "gradient_angle": 0.0,
                    "gradient_size": 1.0,
                    "_style_name": "",
                    "line_spacing_type": 0,
                    "deprecated_attributes": {}
                }
            }

            output_boxes.append(new_box)

        if output_boxes:
            result["pages"][img_name] = output_boxes
            result["current_img"] = img_name  # 记录最后一个作为当前

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"转换完成，生成：{output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("请将 .ipt 文件拖拽到本脚本上")
        sys.exit(1)

    ipt_file = sys.argv[1]
    output_file = os.path.join(os.path.dirname(ipt_file), "output_from_ipt.json")
    convert_ipt_to_ballonstranslator(ipt_file, output_file)