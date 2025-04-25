import os
import sys

# 每个类别的预设值（上、下、左、右分别设置）
EXPAND_VALUES = {
    0: (3, 5, 0, 0),   # balloon：上0，下3，左1，右2
    1: (0, 3, 1, 2),   # qipao：上0，下3，左1，右2
    2: (0, 0, 0, 0),   # fangkuai：上0，下0，左1，右1
    3: (0, 0, 0, 0),   # changfangtiao：上1，下2，左0，右3
    4: (0, 0, 0, 0)    # kuangwai：上0，下1，左0，右1
}
IMG_WIDTH = 640     # 模型输入尺寸
IMG_HEIGHT = 640    # 模型输入尺寸

def adjust_bbox(bbox, expand_values, img_w, img_h):
    class_id, x_center_norm, y_center_norm, width_norm, height_norm = bbox
    delta_top, delta_bottom, delta_left, delta_right = expand_values
    
    # 转换为像素坐标系（精确浮点计算）
    x_center = x_center_norm * img_w
    y_center = y_center_norm * img_h
    half_width = width_norm * img_w / 2
    half_height = height_norm * img_h / 2

    # 原始边界坐标（精确到亚像素）
    original_top = y_center - half_height
    original_bottom = y_center + half_height
    original_left = x_center - half_width
    original_right = x_center + half_width

    # 应用像素级调整（方向逻辑修正）
    new_top = original_top - delta_top    # 正数上移/负数下移
    new_bottom = original_bottom + delta_bottom  # 正数下移/负数上移
    new_left = original_left - delta_left  # 正数左移/负数右移
    new_right = original_right + delta_right  # 正数右移/负数左移

    # 严格边界约束（确保不越界）
    new_top = max(0.0, min(new_top, img_h - 1))
    new_bottom = max(new_top + 1.0, min(new_bottom, img_h))  # 最小高度1像素
    new_left = max(0.0, min(new_left, img_w - 1))
    new_right = max(new_left + 1.0, min(new_right, img_w))    # 最小宽度1像素

    # 计算新几何参数（保持浮点精度）
    new_width = new_right - new_left
    new_height = new_bottom - new_top
    new_x = (new_left + new_right) / 2.0
    new_y = (new_top + new_bottom) / 2.0

    # 转换回归一化坐标（四舍五入到6位小数）
    return [
        class_id,
        round(new_x / img_w, 6),
        round(new_y / img_h, 6),
        round(new_width / img_w, 6),
        round(new_height / img_h, 6)
    ]

# 以下代码保持不变 ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼
def process_file(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 5:
            class_id = int(parts[0])
            bbox = [class_id] + [float(p) for p in parts[1:]]
            
            if class_id in EXPAND_VALUES:
                expand_values = EXPAND_VALUES[class_id]
                new_bbox = adjust_bbox(bbox, expand_values, IMG_WIDTH, IMG_HEIGHT)
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
    for class_id, values in EXPAND_VALUES.items():
        print(f"类别 {class_id} - 上: {values[0]}px, 下: {values[1]}px, 左: {values[2]}px, 右: {values[3]}px")
    print(f"图片尺寸: {IMG_WIDTH}x{IMG_HEIGHT}")

    input("\n按任意键继续...")

if __name__ == "__main__":
    main()