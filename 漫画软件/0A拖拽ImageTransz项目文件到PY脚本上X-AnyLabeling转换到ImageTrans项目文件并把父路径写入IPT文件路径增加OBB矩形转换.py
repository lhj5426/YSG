import os
import sys
import json
import math
from math import floor

# ==============================================================================
# --- 配置区: 在这里设置你要过滤掉的标签 ---
#
# 默认不过滤任何标签，如需过滤，请添加，例如: {"other", "ignore"}
#
LABELS_TO_EXCLUDE = {}
#
# --- 配置区结束 ---
# ==============================================================================


def convert_xal_to_itrans(xal_shapes):
    """
    将 X-AnyLabeling 的 shapes 列表转换为 ImageTrans 的 boxes 列表。
    *** 新版本: 对旋转框使用 OBB (定向包围盒) 计算，确保位置、大小、角度精确。***
    对非旋转框，继续使用 AABB (水平外接矩形) 计算。
    """
    itrans_boxes = []
    filtered_count = 0
    for shape in xal_shapes:
        if 'label' not in shape or 'points' not in shape or not shape['points']:
            continue

        label = shape['label']
        
        if label in LABELS_TO_EXCLUDE:
            filtered_count += 1
            continue

        points = shape['points']
        itrans_box = None

        # *** 核心改动: 根据形状类型选择不同的计算方法 ***
        # 如果是旋转框 (通常是4个点)，我们进行精确的 OBB 计算
        if shape.get('shape_type') == 'rotation' and len(points) == 4:
            # 直接从四个顶点计算真实的宽度、高度和角度
            p1, p2, p3, p4 = points[0], points[1], points[2], points[3]
            
            # 计算相邻两边的向量
            # 假设点是按顺序排列的 (例如，顺时针 p1 -> p2 -> p3 -> p4)
            # 边1: 从 p1 到 p2
            vec1_x, vec1_y = p2[0] - p1[0], p2[1] - p1[1]
            # 边2: 从 p1 到 p4
            vec2_x, vec2_y = p4[0] - p1[0], p4[1] - p1[1]

            # 真实的宽度和高度是这两个向量的长度
            true_width = math.hypot(vec1_x, vec1_y)
            true_height = math.hypot(vec2_x, vec2_y)
            
            # 真实的旋转角度是第一条边的角度
            # 使用 atan2 可以精确处理所有象限
            angle_rad = math.atan2(vec1_y, vec1_x)
            angle_deg = math.degrees(angle_rad) % 360
            
            # 计算旋转框的中心点
            center_x = (p1[0] + p3[0]) / 2
            center_y = (p1[1] + p3[1]) / 2
            
            # ImageTrans 的 (X, Y) 是未旋转时的左上角坐标
            # 我们可以从中心点和真实宽高反推出来
            unrotated_x = center_x - true_width / 2
            unrotated_y = center_y - true_height / 2

            itrans_box = {
                "fontstyle": label,
                "degree": floor(angle_deg), # 应用精确计算的角度
                "geometry": {
                    "X": floor(unrotated_x),
                    "Y": floor(unrotated_y),
                    "width": floor(true_width),
                    "height": floor(true_height)
                },
                "text": ""
            }

        else:
            # 对于普通矩形、多边形或无法精确计算的形状，使用旧的 AABB (水平外接矩形) 方法
            x_coords = [p[0] for p in points]
            y_coords = [p[1] for p in points]
            
            x_min, y_min = min(x_coords), min(y_coords)
            x_max, y_max = max(x_coords), max(y_coords)
            
            width = x_max - x_min
            height = y_max - y_min
            
            itrans_box = {
                "fontstyle": label,
                "geometry": {
                    "X": floor(x_min),
                    "Y": floor(y_min),
                    "width": floor(width),
                    "height": floor(height)
                },
                "text": ""
            }

        if itrans_box:
            itrans_boxes.append(itrans_box)
        
    return itrans_boxes, filtered_count

# --- main 函数部分保持不变 ---
def main():
    if len(sys.argv) < 2:
        print("错误：请将一个 .itp 模板文件拖拽到此脚本上。")
        input("按 Enter 键退出...")
        return

    template_itp_path = sys.argv[1]
    
    if not template_itp_path.lower().endswith('.itp'):
        print(f"错误：'{os.path.basename(template_itp_path)}' 不是一个 .itp 文件。")
        input("按 Enter 键退出...")
        return
        
    directory = os.path.dirname(template_itp_path)
    print(f"正在扫描目录: {directory}")
    
    if LABELS_TO_EXCLUDE:
        print(f"将过滤掉以下标签: {list(LABELS_TO_EXCLUDE)}")
    else:
        print("未设置标签过滤器，将转换所有找到的标签。")

    try:
        json_files = [f for f in os.listdir(directory) if f.lower().endswith('.json')]
        print(f"扫描到 {len(json_files)} 个 JSON 文件。\n")
    except FileNotFoundError:
        print(f"错误：找不到目录 '{directory}'")
        input("按 Enter 键退出...")
        return

    all_images_data = {}
    processed_file_count = 0

    for filename in json_files:
        json_path = os.path.join(directory, filename)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                xal_data = json.load(f)

            if 'imagePath' in xal_data and 'shapes' in xal_data:
                image_filename = xal_data['imagePath']
                shapes = xal_data['shapes']
                
                itrans_boxes, filtered_count = convert_xal_to_itrans(shapes)
                
                info_str = f"转换了 {len(itrans_boxes)} 个标注"
                if filtered_count > 0:
                    info_str += f"，过滤了 {filtered_count} 个"
                print(f"  - 已处理: {filename} ({info_str})")

                if itrans_boxes:
                    all_images_data[image_filename] = {"boxes": itrans_boxes}
                    processed_file_count += 1

        except json.JSONDecodeError:
            print(f"  - 警告: 无法解析JSON文件 {filename}，已跳过。")
        except Exception as e:
            print(f"  - 错误: 处理文件 {filename} 时发生错误: {e}")

    if not all_images_data:
        print("\n未找到任何有效的标注信息进行转换（或所有标注均被过滤）。")
        input("按 Enter 键退出...")
        return

    try:
        with open(template_itp_path, 'r', encoding='utf-8') as f:
            template_data = json.load(f)
    except Exception as e:
        print(f"错误：无法读取模板文件 '{template_itp_path}': {e}")
        input("按 Enter 键退出...")
        return

    template_data['images'] = all_images_data

    base, ext = os.path.splitext(template_itp_path)
    output_itp_path = f"{base}_converted{ext}"

    absolute_output_path = os.path.abspath(output_itp_path)
    parent_dir = os.path.dirname(absolute_output_path)
    template_data['dirPath'] = parent_dir
    print(f"\n已更新项目图片路径 (dirPath) 为: {parent_dir}\n")
    
    try:
        with open(output_itp_path, 'w', encoding='utf-8') as f:
            json.dump(template_data, f, indent=4, ensure_ascii=False)
        
        print("转换完成！")
        print(f"新的 ImageTrans 项目文件已保存为: {output_itp_path}")
        print(f"总计成功转换了 {processed_file_count} 个文件中的标注。")

    except Exception as e:
        print(f"错误：保存新文件时发生错误: {e}")

    input("\n按 Enter 键退出...")

if __name__ == '__main__':
    main()