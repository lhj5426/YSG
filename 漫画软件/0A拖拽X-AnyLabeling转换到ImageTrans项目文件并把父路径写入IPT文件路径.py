import os
import sys
import json
from math import floor

# ==============================================================================
# --- 配置区: 在这里设置你要过滤掉的标签 ---
#
# 将所有你不想转换的标签名称添加到下面的集合中。
# 例如: {"other", "background", "ignore"}
#
LABELS_TO_EXCLUDE = {"other"}
#
# --- 配置区结束 ---
# ==============================================================================


def convert_xal_to_itrans(xal_shapes):
    """
    将 X-AnyLabeling 的 shapes 列表转换为 ImageTrans 的 boxes 列表。
    在转换过程中会根据 LABELS_TO_EXCLUDE 集合过滤掉指定的标签。
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
        itrans_boxes.append(itrans_box)
        
    return itrans_boxes, filtered_count

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
    print(f"将过滤掉以下标签: {list(LABELS_TO_EXCLUDE)}")

    # *** 新增功能: 预先扫描并统计JSON文件数量 ***
    try:
        json_files = [f for f in os.listdir(directory) if f.lower().endswith('.json')]
        print(f"扫描到 {len(json_files)} 个 JSON 文件。\n")
    except FileNotFoundError:
        print(f"错误：找不到目录 '{directory}'")
        input("按 Enter 键退出...")
        return

    all_images_data = {}
    processed_file_count = 0  # 用于统计最终成功转换的文件数

    # 遍历预先扫描到的JSON文件列表
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

                # 只有当文件包含有效（未被过滤的）标注时，才将其计入最终结果
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
        # *** 新增功能: 输出最终转换的文件总数 ***
        print(f"总计成功转换了 {processed_file_count} 个文件中的标注。")

    except Exception as e:
        print(f"错误：保存新文件时发生错误: {e}")

    input("\n按 Enter 键退出...")

if __name__ == '__main__':
    main()