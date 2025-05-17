import os
import sys
import json
from PIL import Image

def yolo_txt_to_json_folder(txt_dir, images_dir, output_json_path):
    all_data = {
        "directory": txt_dir,
        "pages": {},
        "current_img": ""
    }

    for filename in sorted(os.listdir(txt_dir)):
        if not filename.endswith(".txt"):
            continue
        txt_path = os.path.join(txt_dir, filename)
        name, _ = os.path.splitext(filename)
        img_name = name + ".jpg"
        img_path = os.path.join(images_dir, img_name)

        # 自动读取图片宽高
        if not os.path.exists(img_path):
            print(f"警告：找不到对应图片 {img_path}，跳过该文件")
            continue
        with Image.open(img_path) as img:
            image_width, image_height = img.width, img.height

        all_data["current_img"] = img_name  # 最后一个作为 current_img

        with open(txt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        objects = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            class_id, cx, cy, w, h = map(float, parts)
            abs_w = w * image_width
            abs_h = h * image_height
            abs_x = cx * image_width - abs_w / 2
            abs_y = cy * image_height - abs_h / 2

            x1, y1 = int(abs_x), int(abs_y)
            x2, y2 = int(abs_x + abs_w), int(abs_y + abs_h)

            obj = {
                "xyxy": [x1, y1, x2, y2],
                "lines": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]],
                "language": "unknown",
                "distance": [abs_h],
                "angle": 0,
                "vec": [0.0, abs_h],
                "norm": abs_h,
                "merged": False,
                "text": [""],
                "translation": "",
                "rich_text": "",
                "_bounding_rect": [x1, y1, int(abs_w), int(abs_h)],
                "src_is_vertical": True,
                "_detected_font_size": -1.0,
                "det_model": "ysgyolo",
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
            objects.append(obj)

        all_data["pages"][img_name] = objects

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("请将YOLO TXT文件夹拖拽到本脚本上")
        sys.exit(1)

    txt_folder = sys.argv[1]
    if not os.path.isdir(txt_folder):
        print(f"错误：{txt_folder} 不是有效的文件夹路径")
        sys.exit(1)

    # 脚本所在目录即图片目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(script_dir, "output_ballons.json")

    yolo_txt_to_json_folder(txt_folder, script_dir, out_path)
    print("转换完成，生成文件：", out_path)
