import sys
import os

DEFAULT_CLASS_ID = 0
BEZIER_CURVE_STEPS = 15

def cubic_bezier(p0, p1, p2, p3, t):
    x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
    y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
    return (x, y)

def parse_ai_file(file_path):
    bbox_found = False
    llx, lly, urx, ury = 0, 0, 0, 0
    paths = []
    current_path = []

    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        lines = f.readlines()

    for line in lines:
        if line.startswith('%%HiResBoundingBox:') or line.startswith('%%BoundingBox:'):
            try:
                parts = line.split()
                llx, lly, urx, ury = map(float, parts[1:5])
                bbox_found = True
                break
            except:
                continue

    if not bbox_found:
        raise ValueError("未找到 BoundingBox")

    width = urx - llx
    height = ury - lly
    if width <= 0 or height <= 0:
        raise ValueError("边界框尺寸无效")

    target_width = width
    target_height = height

    in_path_block = False
    for line in lines:
        line = line.strip()
        if line == '*u':
            in_path_block = True
            continue
        if line == '*U':
            in_path_block = False
            if current_path:
                paths.append(current_path)
            current_path = []
            continue

        if in_path_block:
            parts = line.split()
            if not parts:
                continue
            command = parts[-1]
            try:
                if command == 'm':
                    if current_path:
                        paths.append(current_path)
                    current_path = [(float(parts[0]), float(parts[1]))]
                elif command == 'C':
                    if not current_path:
                        continue
                    p0 = current_path[-1]
                    p1 = (float(parts[0]), float(parts[1]))
                    p2 = (float(parts[2]), float(parts[3]))
                    p3 = (float(parts[4]), float(parts[5]))
                    for i in range(1, BEZIER_CURVE_STEPS + 1):
                        t = i / float(BEZIER_CURVE_STEPS)
                        current_path.append(cubic_bezier(p0, p1, p2, p3, t))
                elif command == 'L':
                    current_path.append((float(parts[0]), float(parts[1])))
                elif command == 'n':
                    if current_path:
                        paths.append(current_path)
                    current_path = []
            except:
                continue

    if current_path:
        paths.append(current_path)

    return paths, llx, lly, width, height, target_width, target_height

def convert_to_yolo_format(paths, llx, lly, width, height, target_width, target_height, class_id):
    yolo_lines = []
    for path in paths:
        if not path:
            continue
        normalized_points = []
        for x, y in path:
            x_pixel = (x - llx)
            y_pixel = (y - lly)
            x_norm = x_pixel / target_width
            y_norm = 1.0 - (y_pixel / target_height)
            x_norm = max(0.0, min(1.0, x_norm))
            y_norm = max(0.0, min(1.0, y_norm))
            normalized_points.append(f"{x_norm:.6f} {y_norm:.6f}")
        yolo_lines.append(f"{class_id} " + " ".join(normalized_points))
    return "\n".join(yolo_lines), len(yolo_lines)

def process_ai_file(file_path, output_dir):
    try:
        paths, llx, lly, width, height, target_width, target_height = parse_ai_file(file_path)
        yolo_data, label_count = convert_to_yolo_format(
            paths, llx, lly, width, height, target_width, target_height, DEFAULT_CLASS_ID
        )
        base_name = os.path.splitext(os.path.basename(file_path))[0] + ".txt"
        output_path = os.path.join(output_dir, base_name)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yolo_data)
        return label_count
    except Exception as e:
        print(f"❌ 跳过: {file_path} ({e})")
        return 0

def collect_ai_files(paths):
    ai_files = []
    for p in paths:
        if os.path.isfile(p) and p.lower().endswith('.ai'):
            ai_files.append(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    if f.lower().endswith('.ai'):
                        ai_files.append(os.path.join(root, f))
    return ai_files

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("请将 .ai 文件或文件夹拖放到此脚本上。")
        sys.exit()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "YOLO")
    os.makedirs(output_dir, exist_ok=True)

    ai_files = collect_ai_files(sys.argv[1:])
    print(f"共检测到 {len(ai_files)} 个 .ai 文件，开始转换...")

    total_labels = 0
    for file_path in ai_files:
        label_count = process_ai_file(file_path, output_dir)
        total_labels += label_count

    print(f"\n✅ 全部转换完成，共生成标签 {total_labels} 个，处理文件 {len(ai_files)} 个。")

    if os.name == 'nt':
        input("按 Enter 键退出...")
