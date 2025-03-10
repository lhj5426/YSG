import os
import sys

# 预设值（上下左右分别设置）
EXPAND_TOP = 0      # 向上扩展的像素数（负值缩小）
EXPAND_BOTTOM = 0   # 向下扩展的像素数（负值缩小）
EXPAND_LEFT = -4    # 向左扩展的像素数（负值缩小）
EXPAND_RIGHT = 4   # 向右扩展的像素数（负值缩小）
IMG_WIDTH = 1024    # 默认图片宽度
IMG_HEIGHT = 1024   # 默认图片高度
TARGET_CLASSES = [1]  # # 要调整的类别列表（0 balloon 1 qipao 2 fangkuai 3 changfangtiao 4 kuangwai）

def adjust_bbox(bbox, top, bottom, left, right, img_width, img_height):
    class_id, x_center_norm, y_center_norm, width_norm, height_norm = bbox
    
    # 转换为像素坐标系（精确浮点计算）
    x_center = x_center_norm * img_width
    y_center = y_center_norm * img_height
    half_width = (width_norm * img_width) / 2
    half_height = (height_norm * img_height) / 2

    # 原始边界坐标（精确到亚像素）
    original_top = y_center - half_height
    original_bottom = y_center + half_height
    original_left = x_center - half_width
    original_right = x_center + half_width

    # 应用像素级调整（方向逻辑修正）
    new_top = original_top - top     # 正数上移/负数下移
    new_bottom = original_bottom + bottom  # 正数下移/负数上移
    new_left = original_left - left  # 正数左移/负数右移
    new_right = original_right + right  # 正数右移/负数左移

    # 严格边界约束（确保不越界）
    new_top = max(0.0, min(new_top, img_height - 1))
    new_bottom = max(new_top + 1.0, min(new_bottom, img_height))  # 最小高度1像素
    new_left = max(0.0, min(new_left, img_width - 1))
    new_right = max(new_left + 1.0, min(new_right, img_width))    # 最小宽度1像素

    # 计算新几何参数（保持浮点精度）
    new_width = new_right - new_left
    new_height = new_bottom - new_top
    new_x = (new_left + new_right) / 2.0
    new_y = (new_top + new_bottom) / 2.0

    # 转换回归一化坐标（四舍五入到6位小数）
    return [
        class_id,
        round(new_x / img_width, 6),
        round(new_y / img_height, 6),
        round(new_width / img_width, 6),
        round(new_height / img_height, 6)
    ]

def process_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 5:
            class_id = int(parts[0])
            bbox = [class_id] + [float(p) for p in parts[1:]]
            
            if class_id in TARGET_CLASSES:
                new_bbox = adjust_bbox(bbox, EXPAND_TOP, EXPAND_BOTTOM, EXPAND_LEFT, EXPAND_RIGHT, IMG_WIDTH, IMG_HEIGHT)
                new_line = f"{new_bbox[0]} {new_bbox[1]:.6f} {new_bbox[2]:.6f} {new_bbox[3]:.6f} {new_bbox[4]:.6f}\n"
            else:
                new_line = line
            new_lines.append(new_line)
        else:
            new_lines.append(line)
    
    with open(file_path, 'w') as f:
        f.writelines(new_lines)
    
    print(f"处理完成: {file_path}")
    return file_path

def process_folder(folder_path):
    processed_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                new_file = process_file(file_path)
                processed_files.append(new_file)
    return processed_files

def main():
    if len(sys.argv) < 2:
        print("请将TXT文件或包含TXT文件的文件夹拖到此脚本上。")
        input("按任意键退出...")
        return

    paths = sys.argv[1:]
    processed_files = []

    for path in paths:
        if os.path.isfile(path):
            if path.endswith('.txt'):
                new_file = process_file(path)
                processed_files.append(new_file)
            else:
                print(f"跳过非TXT文件: {path}")
        elif os.path.isdir(path):
            processed_files.extend(process_folder(path))

    if processed_files:
        print("\n处理完成的文件:")
        for file in processed_files:
            print(file)
    else:
        print("没有找到或处理任何TXT文件。")

    print(f"\n处理使用的设置:")
    print(f"上扩展: {EXPAND_TOP} 像素, 下扩展: {EXPAND_BOTTOM} 像素")
    print(f"左扩展: {EXPAND_LEFT} 像素, 右扩展: {EXPAND_RIGHT} 像素")
    print(f"图片宽度: {IMG_WIDTH}")
    print(f"图片高度: {IMG_HEIGHT}")
    print(f"调整类别: {TARGET_CLASSES}")

    input("\n按任意键继续...")

if __name__ == "__main__":
    main()