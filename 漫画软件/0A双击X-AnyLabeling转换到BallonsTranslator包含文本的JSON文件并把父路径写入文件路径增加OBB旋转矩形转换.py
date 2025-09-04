import os
import sys
import json
import math

# ==============================================================================
# --- 配置区: 在这里设置你要过滤掉的标签 ---
LABELS_TO_EXCLUDE = {} # 默认不过滤任何标签
# ==============================================================================

def convert_xal_shape_to_balloon_obj(shape):
    """
    将单个 X-AnyLabeling shape 对象转换为 BallonsTranslator 的 object 格式。
    *** 最终修正版: 对旋转框使用 OBB (定向包围盒) 计算，确保所有几何信息
    (位置, 尺寸, 角度, 顶点) 都精确无误，以适配目标软件的渲染逻辑。***
    """
    if 'points' not in shape or not shape['points']:
        return None

    description_text = shape.get('description') or ''
    points = shape['points']

    # --- 核心改动: 根据形状类型选择不同的计算方法 ---
    # 默认值，用于非旋转形状
    angle_deg = 0.0
    final_lines = [points]
    
    # 如果是旋转框，进行精确的 OBB 计算
    if shape.get('shape_type') == 'rotation' and len(points) == 4:
        p1, p2, p3, p4 = points[0], points[1], points[2], points[3]
        
        # 计算真实的宽度和高度 (即矩形的两条邻边长度)
        true_width = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        true_height = math.hypot(p4[0] - p1[0], p4[1] - p1[1])
        
        # 计算真实的旋转角度
        angle_rad = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        angle_deg = math.degrees(angle_rad) % 360
        
        # 计算中心点
        center_x = (p1[0] + p3[0]) / 2
        center_y = (p1[1] + p3[1]) / 2
        
        # 反推未旋转时的左上角坐标 (x, y)
        unrotated_x = center_x - true_width / 2
        unrotated_y = center_y - true_height / 2
        
        # 用 OBB 的结果填充几何信息
        x1, y1 = math.floor(unrotated_x), math.floor(unrotated_y)
        w, h = math.floor(true_width), math.floor(true_height)
        x2, y2 = x1 + w, y1 + h

    else:
        # 对于普通矩形、多边形，使用旧的 AABB (水平外接矩形) 方法
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]
        x_min, y_min = min(x_coords), min(y_coords)
        x_max, y_max = max(x_coords), max(y_coords)
        
        x1, y1 = math.floor(x_min), math.floor(y_min)
        x2, y2 = math.ceil(x_max), math.ceil(y_max)
        w, h = x2 - x1, y2 - y1
        # 对于非旋转形状，确保 lines 也是 AABB 的四个角点
        final_lines = [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]

    # 判断文字方向 (基于最终计算的宽高)
    is_vertical = h >= w

    # 组装最终的对象
    obj = {
        "xyxy": [x1, y1, x2, y2],
        "lines": final_lines,
        "language": "unknown",
        "distance": None,
        "angle": angle_deg,
        "vec": None,
        "norm": -1,
        "merged": False,
        "text": [description_text],
        "translation": "", "rich_text": "",
        "_bounding_rect": [x1, y1, w, h],
        "src_is_vertical": is_vertical,
        "det_model": "XAL_Import",
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

# --- main 函数部分保持不变 ---
def main():
    try:
        script_path = os.path.abspath(__file__)
        work_dir = os.path.dirname(script_path)
    except NameError:
        work_dir = os.getcwd()

    print(f"正在扫描工作目录: {work_dir}")
    if LABELS_TO_EXCLUDE:
        print(f"将过滤掉以下标签: {list(LABELS_TO_EXCLUDE)}")
    else:
        print("未设置标签过滤器，将转换所有找到的标签。")
    
    output_filename = "output_ballons.json"
    output_json_path = os.path.join(work_dir, output_filename)

    all_data = {
        "directory": work_dir,
        "pages": {},
        "current_img": ""
    }

    json_files = sorted([f for f in os.listdir(work_dir) if f.lower().endswith('.json') and f.lower() != output_filename.lower()])
    
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