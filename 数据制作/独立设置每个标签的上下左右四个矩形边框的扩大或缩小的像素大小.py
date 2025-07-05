import os
import sys

# 每个类别的预设像素调整值（上、下、左、右）
EXPAND_VALUES = {
    0: (0, 0, 1, 1),   # balloon
    1: (0, 0, 0, 1.5),   # qipao
    2: (0, 0, 0, 0),   # fangkuai
    3: (0, 0, 0, 0),   # changfangtiao
    4: (0, 0, 0, 0),   # kuangwai
    5: (0, 0, 0, 0),     # other
    6: (0, 0, 0, 0),     # balloon2
    7: (0, 0, 0, 0) ,    # qipao2
    8: (0, 0, 0, 0) ,   # changfangtiao2
}

IMG_WIDTH = 1024
IMG_HEIGHT = 1024

def adjust_bbox(bbox, expand_values, img_w, img_h):
    class_id, x_center_norm, y_center_norm, width_norm, height_norm = bbox
    delta_top, delta_bottom, delta_left, delta_right = expand_values

    x_center = x_center_norm * img_w
    y_center = y_center_norm * img_h
    half_width = width_norm * img_w / 2
    half_height = height_norm * img_h / 2

    orig_top = y_center - half_height
    orig_bottom = y_center + half_height
    orig_left = x_center - half_width
    orig_right = x_center + half_width

    new_top = orig_top - delta_top
    new_bottom = orig_bottom + delta_bottom
    new_left = orig_left - delta_left
    new_right = orig_right + delta_right

    new_top = max(0.0, min(new_top, img_h - 1))
    new_bottom = max(new_top + 1.0, min(new_bottom, img_h))
    new_left = max(0.0, min(new_left, img_w - 1))
    new_right = max(new_left + 1.0, min(new_right, img_w))

    new_width = new_right - new_left
    new_height = new_bottom - new_top
    new_x = (new_left + new_right) / 2.0
    new_y = (new_top + new_bottom) / 2.0

    return [
        class_id,
        round(new_x / img_w, 6),
        round(new_y / img_h, 6),
        round(new_width / img_w, 6),
        round(new_height / img_h, 6)
    ]

def process_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) == 5:
            try:
                class_id = int(parts[0])
                bbox = [class_id] + [float(x) for x in parts[1:]]
                if class_id in EXPAND_VALUES:
                    expand_values = EXPAND_VALUES[class_id]
                    new_bbox = adjust_bbox(bbox, expand_values, IMG_WIDTH, IMG_HEIGHT)
                    line_out = f"{new_bbox[0]} {new_bbox[1]:.6f} {new_bbox[2]:.6f} {new_bbox[3]:.6f} {new_bbox[4]:.6f}\n"
                else:
                    line_out = line
                new_lines.append(line_out)
            except Exception as e:
                print(f"解析出错（跳过此行）: {line.strip()} 错误: {e}")
        else:
            new_lines.append(line)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)

    print(f"处理完成: {file_path}")
    return file_path

def process_folder(folder_path):
    processed_files = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                processed_files.append(process_file(file_path))
    return processed_files

def main():
    if len(sys.argv) < 2:
        print("请将TXT文件或包含TXT文件的文件夹拖到此脚本上。")
        input("按任意键退出...")
        return

    paths = sys.argv[1:]
    processed = []

    for path in paths:
        if os.path.isfile(path) and path.endswith('.txt'):
            processed.append(process_file(path))
        elif os.path.isdir(path):
            processed.extend(process_folder(path))
        else:
            print(f"跳过无效路径: {path}")

    if processed:
        print("\n以下文件已处理：")
        for f in processed:
            print(f)
    else:
        print("未找到可处理的TXT文件。")

    print("\n使用设置：")
    print(f"图片尺寸：{IMG_WIDTH}x{IMG_HEIGHT}")
    for cid, (t, b, l, r) in EXPAND_VALUES.items():
        print(f"类别 {cid}：上 {t}px，下 {b}px，左 {l}px，右 {r}px")

    input("\n按任意键退出...")

if __name__ == '__main__':
    main()
