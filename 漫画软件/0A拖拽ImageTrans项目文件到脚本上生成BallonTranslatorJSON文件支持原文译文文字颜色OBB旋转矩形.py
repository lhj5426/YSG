import os
import sys
import json
import math

def convert_ipt_box_to_balloon_obj(ipt_box):
    """
    将单个 .ipt (格式B) 的 box 对象转换为 balloons.json (格式A) 的 object 格式。
    *** 新版本: 现在会提取翻译文本并生成 rich_text ***
    """
    geometry = ipt_box.get('geometry', {})
    x = geometry.get('X', 0)
    y = geometry.get('Y', 0)
    w = geometry.get('width', 0)
    h = geometry.get('height', 0)
    degree = ipt_box.get('degree', 0)
    
    # --- 核心几何计算 (与之前相同) ---
    center_x, center_y = x + w / 2, y + h / 2
    angle_rad = math.radians(degree)
    cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
    half_w, half_h = w / 2, h / 2
    corners = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    
    rotated_corners = []
    for cx, cy in corners:
        rotated_x = cx * cos_a - cy * sin_a
        rotated_y = cx * sin_a + cy * cos_a
        rotated_corners.append([center_x + rotated_x, center_y + rotated_y])
        
    x_coords = [p[0] for p in rotated_corners]
    y_coords = [p[1] for p in rotated_corners]
    x_min, y_min, x_max, y_max = min(x_coords), min(y_coords), max(x_coords), max(y_coords)
    
    # --- 文本和颜色提取 ---
    text_content = ipt_box.get('text', '')
    translation_text = ipt_box.get('target', '') # <-- 新增：获取翻译文本
    try:
        frgb = [int(c) for c in ipt_box.get('textColor', '0,0,0').split(',')]
    except (ValueError, AttributeError):
        frgb = [0, 0, 0]
        
    # --- 新增：生成 rich_text HTML ---
    hex_color = f"#{frgb[0]:02x}{frgb[1]:02x}{frgb[2]:02x}"
    # 使用一个标准的HTML模板，插入颜色和翻译文本
    rich_text_html = (
        '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">'
        '<html><head><meta name="qrichtext" content="1" /><meta charset="utf-8" /><style type="text/css">'
        'p, li { white-space: pre-wrap; } hr { height: 1px; border-width: 0; }'
        'li.unchecked::marker { content: "\\2610"; } li.checked::marker { content: "\\2612"; }'
        '</style></head><body style=" font-family:\'新兰圆-B\'; font-size:18pt; font-weight:400; font-style:normal;">'
        f'<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">'
        f'<span style=" color:{hex_color};">{translation_text}</span></p></body></html>'
    )
    
    is_vertical = h >= w

    # --- 组装最终对象 ---
    obj = {
        "xyxy": [x_min, y_min, x_max, y_max],
        "lines": [rotated_corners],
        "language": "unknown", "distance": None, "angle": degree, "vec": None,
        "norm": -1, "merged": False,
        "text": [text_content],
        "translation": translation_text,    # <-- 新增：填充翻译字段
        "rich_text": rich_text_html,        # <-- 新增：填充富文本字段
        "_bounding_rect": [x, y, w, h],
        "src_is_vertical": is_vertical,
        "det_model": "IPT_Import",
        "region_mask": None, "region_inpaint_dict": None,
        "fontformat": {
            "font_family": "新兰圆-B", "font_size": 24.0, "stroke_width": 0.0, "frgb": frgb,
            "srgb": [0, 0, 0], "bold": False, "underline": False, "italic": False,
            "alignment": 0, "vertical": is_vertical, "font_weight": 400, "line_spacing": 1.2,
            "letter_spacing": 1.15, "opacity": 1.0, "shadow_radius": 0.0, "shadow_strength": 1.0,
            "shadow_color": [0, 0, 0], "shadow_offset": [0.0, 0.0], "gradient_enabled": False,
            "gradient_start_color": [0, 0, 0], "gradient_end_color": [255, 255, 255],
            "gradient_angle": 0.0, "gradient_size": 1.0, "_style_name": "",
            "line_spacing_type": 0, "deprecated_attributes": {}
        }
    }
    return obj

def main():
    if len(sys.argv) < 2:
        print("错误：请将一个 .ipt 或 .itp 文件拖放到此脚本上运行。")
        input("\n按 Enter 键退出...")
        return

    input_path = sys.argv[1]
    
    if not os.path.exists(input_path) or not input_path.lower().endswith(('.ipt', '.itp')):
        print(f"错误: 文件 '{input_path}' 不是有效的 .ipt 或 .itp 文件。")
        input("\n按 Enter 键退出...")
        return
        
    work_dir = os.path.dirname(input_path)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_filename = f"{base_name}_balloons.json"
    output_path = os.path.join(work_dir, output_filename)

    try:
        print(f"正在读取项目文件 (格式B): {os.path.basename(input_path)}...")
        with open(input_path, 'r', encoding='utf-8') as f:
            ipt_data = json.load(f)

        balloons_data = {
            "directory": ipt_data.get("dirPath", work_dir),
            "pages": {},
            "current_img": ""
        }

        print("开始转换文本框数据...")
        for img_name, page_data in ipt_data.get("images", {}).items():
            page_objects = []
            for box in page_data.get("boxes", []):
                balloon_obj = convert_ipt_box_to_balloon_obj(box)
                if balloon_obj:
                    page_objects.append(balloon_obj)
            
            if page_objects:
                balloons_data["pages"][img_name] = page_objects
                if not balloons_data["current_img"]:
                    balloons_data["current_img"] = img_name
            print(f"  - 已处理页面 '{img_name}'，转换了 {len(page_objects)} 个文本框。")
        
        if not balloons_data["pages"]:
            print("\n警告：在输入文件中没有找到任何有效的文本框数据。")
            input("\n按 Enter 键退出...")
            return

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(balloons_data, f, indent=4, ensure_ascii=False)
            
        print("\n转换成功！")
        print(f"文件已保存为: {output_path}")

    except Exception as e:
        print(f"\n发生错误: {e}")
    
    input("\n按 Enter 键退出...")

if __name__ == "__main__":
    main()