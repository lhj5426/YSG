import os
import sys
import json
import math

# ==============================================================================
# --- 配置区: 在这里设置你要过滤掉的标签 ---
#
# 将所有你不想转换的标签名称添加到下面的集合中。
# 例如: {"other", "background", "ignore"}
#
LABELS_TO_EXCLUDE = {"other"}
#
# --- 使用说明 ---
# 1. 将此脚本文件 (`convert_xal_to_ballons.py`) 放在一个文件夹中。
# 2. 将你所有的图片文件 (如 .jpg, .png) 和对应的 X-AnyLabeling 生成的 .json 文件
#    也放在同一个文件夹中。
# 3. 直接双击运行此脚本。
# 4. 脚本会自动扫描当前目录，进行转换，并在同一目录下生成一个名为
#    `output_ballons.json` 的文件，这个文件就是 BallonsTranslator 的项目文件。
# ==============================================================================

def convert_xal_shape_to_balloon_obj(shape):
    """
    将单个 X-AnyLabeling shape 对象转换为 BallonsTranslator 的 object 格式。
    """
    if 'points' not in shape or not shape['points']:
        return None

    # 【修正】确保即使 description 字段的值为 null，也能正确处理为空字符串 ""
    # 旧代码: description_text = shape.get('description', '')
    # 这行代码在 "description": null 的情况下会返回 None，导致错误。
    description_text = shape.get('description') or ''

    points = shape['points']
    
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    x_min, y_min = min(x_coords), min(y_coords)
    x_max, y_max = max(x_coords), max(y_coords)
    
    abs_w = x_max - x_min
    abs_h = y_max - y_min
    
    x1, y1 = math.floor(x_min), math.floor(y_min)
    x2, y2 = math.ceil(x_max), math.ceil(y_max)
    int_w, int_h = x2 - x1, y2 - y1

    is_vertical = abs_h >= abs_w

    obj = {
        "xyxy": [x1, y1, x2, y2],
        "lines": [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]],
        "language": "unknown",
        "distance": [abs_h], "angle": 0, "vec": [0.0, abs_h], "norm": abs_h,
        "merged": False,
        "text": [description_text], # 现在这里永远是字符串
        "translation": "", "rich_text": "",
        "_bounding_rect": [x1, y1, int_w, int_h],
        "src_is_vertical": is_vertical, "det_model": "XAL_Import",
        "region_mask": None, "region_inpaint_dict": None,
        "fontformat": {
            "font_family": "", "font_size": 24.0, "stroke_width": 0.0,
            "frgb": [0, 0, 0], "srgb": [0, 0, 0], "bold": False,
            "underline": False, "italic": False, "alignment": 0,
            "vertical": is_vertical, "font_weight": 400, "line_spacing": 1.2,
            "letter_spacing": 1.15, "opacity": 1.0, "shadow_radius": 0.0,
            "shadow_strength": 1.0, "shadow_color": [0, 0, 0],
            "shadow_offset": [0.0, 0.0], "gradient_enabled": False,
            "gradient_start_color": [0, 0, 0], "gradient_end_color": [255, 255, 255],
            "gradient_angle": 0.0, "gradient_size": 1.0, "_style_name": "",
            "line_spacing_type": 0, "deprecated_attributes": {}
        }
    }
    return obj

def main():
    try:
        script_path = os.path.abspath(__file__)
        work_dir = os.path.dirname(script_path)
    except NameError:
        work_dir = os.getcwd()

    print(f"正在扫描工作目录: {work_dir}")
    print(f"将过滤掉以下标签: {list(LABELS_TO_EXCLUDE)}")
    
    output_filename = "output_ballons.json"
    output_json_path = os.path.join(work_dir, output_filename)

    all_data = {
        "directory": work_dir,
        "pages": {},
        "current_img": ""
    }

    json_files = sorted([f for f in os.listdir(work_dir) if f.lower().endswith('.json') and f != output_filename])
    
    if not json_files:
        print("\n错误：在当前目录下未找到任何 .json 标注文件。")
        input("按 Enter 键退出...")
        return

    print(f"扫描到 {len(json_files)} 个 JSON 文件，开始转换...\n")
    
    processed_file_count = 0

    for filename in json_files:
        json_path = os.path.join(work_dir, filename)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                xal_data = json.load(f)
        except Exception as e:
            print(f"  - 警告: 无法读取或解析 {filename}，已跳过。错误: {e}")
            continue

        if 'imagePath' not in xal_data or 'shapes' not in xal_data:
            continue

        img_name = xal_data['imagePath']
        img_path = os.path.join(work_dir, img_name)

        if not os.path.exists(img_path):
            print(f"  - 警告: 找不到 {filename} 对应的图片 '{img_name}'，已跳过。")
            continue

        page_objects = []
        filtered_count = 0
        for shape in xal_data['shapes']:
            if 'label' in shape and shape['label'] in LABELS_TO_EXCLUDE:
                filtered_count += 1
                continue

            balloon_obj = convert_xal_shape_to_balloon_obj(shape)
            if balloon_obj:
                page_objects.append(balloon_obj)
        
        info_str = f"转换了 {len(page_objects)} 个标注"
        if filtered_count > 0:
            info_str += f"，过滤了 {filtered_count} 个"
        print(f"  - 已处理: {filename} -> '{img_name}' ({info_str})")

        if page_objects:
            all_data["pages"][img_name] = page_objects
            if not all_data["current_img"]:
                all_data["current_img"] = img_name
            processed_file_count += 1

    if not all_data["pages"]:
        print("\n转换完成，但没有生成任何有效的页面数据（或所有标注均被过滤）。")
        input("按 Enter 键退出...")
        return

    try:
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print("\n转换成功！")
        print(f"项目文件已保存为: {output_json_path}")
        print(f"总计成功转换了 {processed_file_count} 个文件中的标注。")
    except Exception as e:
        print(f"\n错误: 保存文件失败。错误: {e}")

    input("\n按 Enter 键退出...")

if __name__ == "__main__":
    main()