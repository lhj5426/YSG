import sys
import os

# --- 配置 ---
# 目标物体的类别ID
DEFAULT_CLASS_ID = 0

# 贝塞尔曲线的平滑度 (数值越大，曲线越平滑)
BEZIER_CURVE_STEPS = 15

# 目标图像尺寸
IMAGE_WIDTH = 2400  # 图像宽度（像素）
IMAGE_HEIGHT = 1800  # 图像高度（像素）
# --- 配置结束 ---

def cubic_bezier(p0, p1, p2, p3, t):
    """计算三次贝塞尔曲线上在t位置的点坐标。"""
    x = (1-t)**3*p0[0] + 3*(1-t)**2*t*p1[0] + 3*(1-t)*t**2*p2[0] + t**3*p3[0]
    y = (1-t)**3*p0[1] + 3*(1-t)**2*t*p1[1] + 3*(1-t)*t**2*p2[1] + t**3*p3[1]
    return (x, y)

def parse_ai_file(file_path):
    """
    解析.ai文件，提取边界框和路径坐标。
    """
    bbox_found = False
    llx, lly, urx, ury = 0, 0, 0, 0
    paths = []
    current_path = []
    
    with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
        lines = f.readlines()

    # 1. 查找边界框 (优先使用HiResBoundingBox)
    for line in lines:
        if line.startswith('%%HiResBoundingBox:'):
            try:
                parts = line.split()
                llx, lly, urx, ury = map(float, parts[1:5])
                bbox_found = True
                print(f"找到高精度边界框: llx={llx}, lly={lly}, urx={urx}, ury={ury}")
                break
            except (ValueError, IndexError):
                continue
    
    if not bbox_found:
        for line in lines:
            if line.startswith('%%BoundingBox:'):
                try:
                    parts = line.split()
                    llx, lly, urx, ury = map(float, parts[1:5])
                    bbox_found = True
                    print(f"找到标准边界框: llx={llx}, lly={lly}, urx={urx}, ury={ury}")
                    break
                except (ValueError, IndexError):
                    continue

    if not bbox_found:
        raise ValueError("错误：在文件中未找到 %%BoundingBox 或 %%HiResBoundingBox。")

    # 2. 计算边界框尺寸
    width = urx - llx
    height = ury - lly
    if width <= 0 or height <= 0:
        raise ValueError(f"错误: 边界框尺寸无效 (width={width}, height={height})。")

    # 3. 确认目标图像尺寸
    target_width = IMAGE_WIDTH
    target_height = IMAGE_HEIGHT
    print(f"使用目标图像尺寸: width={target_width}, height={target_height}")

    # 4. 提取路径坐标
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
                if command == 'm':  # moveto
                    if current_path:
                        paths.append(current_path)
                    current_path = [(float(parts[0]), float(parts[1]))]
                elif command == 'C':  # curveto
                    if not current_path:
                        continue
                    p0 = current_path[-1]
                    p1 = (float(parts[0]), float(parts[1]))
                    p2 = (float(parts[2]), float(parts[3]))
                    p3 = (float(parts[4]), float(parts[5]))
                    for i in range(1, BEZIER_CURVE_STEPS + 1):
                        t = i / float(BEZIER_CURVE_STEPS)
                        current_path.append(cubic_bezier(p0, p1, p2, p3, t))
                elif command == 'L':  # lineto
                    current_path.append((float(parts[0]), float(parts[1])))
                elif command == 'n':  # newpath
                    if current_path:
                        paths.append(current_path)
                    current_path = []
            except (ValueError, IndexError):
                continue

    if current_path:
        paths.append(current_path)
    
    if not paths:
        raise ValueError("错误：在文件中未找到有效路径数据。")
    
    return paths, llx, lly, width, height, target_width, target_height

def convert_to_yolo_format(paths, llx, lly, width, height, target_width, target_height, class_id):
    """
    将路径坐标转换为YOLO分割格式，适配目标图像尺寸。
    """
    yolo_lines = []
    for path_idx, path in enumerate(paths):
        if not path:
            continue
        
        normalized_points = []
        for x, y in path:
            # 将 .ai 坐标转换为像素坐标（相对于目标图像）
            x_pixel = (x - llx) * (target_width / width)
            y_pixel = (y - lly) * (target_height / height)
            
            # 归一化到 [0, 1]（YOLO 格式）
            x_norm = x_pixel / target_width
            y_norm = y_pixel / target_height
            
            # 翻转 Y 轴（从 .ai 左下角原点到 YOLO 左上角原点）
            y_norm = 1.0 - y_norm
            
            # 限制坐标在 [0, 1] 范围内
            x_norm = max(0.0, min(1.0, x_norm))
            y_norm = max(0.0, min(1.0, y_norm))
            
            # 调试输出：打印原始和归一化坐标
            print(f"路径 {path_idx+1}, 原始坐标: ({x:.6f}, {y:.6f}), 归一化坐标: ({x_norm:.6f}, {y_norm:.6f})")
            
            normalized_points.append(f"{x_norm:.6f} {y_norm:.6f}")
        
        yolo_line = f"{class_id} " + " ".join(normalized_points)
        yolo_lines.append(yolo_line)
        
    return "\n".join(yolo_lines)

def process_file(file_path):
    """处理单个文件的主函数。"""
    print("-" * 50)
    print(f"正在处理文件: {file_path}")

    if not os.path.exists(file_path) or not file_path.lower().endswith('.ai'):
        print("错误: 文件不存在或不是一个 .ai 文件。")
        return

    try:
        # 获取脚本目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        yolo_dir = os.path.join(script_dir, "YOLO")
        os.makedirs(yolo_dir, exist_ok=True)
        print(f"输出目录: {yolo_dir}")

        # 解析 . shape 文件
        paths, llx, lly, width, height, target_width, target_height = parse_ai_file(file_path)
        
        if not paths:
            print("警告: 未在文件中找到任何可识别的路径数据。")
            return

        print(f"成功解析 {len(paths)} 条路径，生成 {sum(len(p) for p in paths)} 个坐标点。")

        # 转换为 YOLO 格式
        yolo_data = convert_to_yolo_format(paths, llx, lly, width, height, target_width, target_height, DEFAULT_CLASS_ID)
        
        # 保存输出
        base_name = os.path.basename(file_path)
        txt_filename = os.path.splitext(base_name)[0] + ".txt"
        output_path = os.path.join(yolo_dir, txt_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(yolo_data)
            
        print(f"\n成功! YOLO 分割文件已保存到:\n{output_path}")

    except Exception as e:
        print(f"\n处理文件时发生错误: {e}")
    finally:
        print("-" * 50)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for file_path in sys.argv[1:]:
            process_file(file_path)
    else:
        print("请将一个或多个 .ai 文件拖拽到此脚本上以进行转换。")

    if os.name == 'nt':
        input("\n按 Enter 键退出...")