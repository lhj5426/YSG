import cv2
import numpy as np
import os
import sys

# ========== 可配置项 ==========
# 填充颜色：支持 #RRGGBB 或 #RRGGBBAA（末尾 AA 为透明度，00 全透明，FF 不透明）
FILL_COLOR_HEX = "#ABE338"
# 若上面使用 #RRGGBB，则用此透明度；若为 #RRGGBBAA，则以 AA 为准并忽略此项
FILL_ALPHA = 255
# 空标注是否跳过不生成（True 跳过；False 生成全透明 PNG）
SKIP_EMPTY = True
# 输出目录名（例如与日志一致的 "ImageTrans_masks"）
OUTPUT_DIR_NAME = "ImageTrans_masks"
# ============================

def hex_to_rgba(hex_str, alpha_default=255):
    """
    将 #RRGGBB 或 #RRGGBBAA 转为 (R,G,B,A)
    """
    s = hex_str.strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 6:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        a = int(alpha_default)
        return (r, g, b, a)
    elif len(s) == 8:
        r = int(s[0:2], 16)
        g = int(s[2:4], 16)
        b = int(s[4:6], 16)
        a = int(s[6:8], 16)
        return (r, g, b, a)
    else:
        raise ValueError("颜色格式应为 #RRGGBB 或 #RRGGBBAA")

def rgba_to_bgra(rgba):
    """
    (R,G,B,A) -> (B,G,R,A) 供 OpenCV 使用
    """
    r, g, b, a = rgba
    return (b, g, r, a)

def win_long_path(path):
    """
    兼容 Windows 超长路径与中文路径写入：返回 \\?\\ 前缀的绝对路径
    """
    if os.name != "nt":
        return path
    path = os.path.abspath(path)
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        # UNC 网络路径
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path

def ensure_dir(p):
    """
    确保目录存在，兼容 Windows 长路径
    """
    try:
        os.makedirs(p, exist_ok=True)
    except Exception:
        if os.name == "nt":
            os.makedirs(win_long_path(p), exist_ok=True)
        else:
            raise

def imwrite_png_unicode(path, image):
    """
    解决 cv2.imwrite 在中文/长路径上的失败问题：
    先 imencode('.png')，然后用 Python 文件写入。
    """
    try:
        ok, buf = cv2.imencode(".png", image)
        if not ok:
            return False
        long_path = win_long_path(path)
        parent = os.path.dirname(long_path)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception:
                pass
        with open(long_path, "wb") as f:
            f.write(buf.tobytes())
        return True
    except Exception:
        return False

def read_image_unicode(path):
    """
    以支持中文/长路径的方式读取图片：np.fromfile + cv2.imdecode
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None

def load_txt_lines(txt_path):
    """
    读取标签文件，返回去除空行/注释行的列表。多编码容错。
    """
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with open(txt_path, "r", encoding=enc, errors="ignore") as f:
                lines = []
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    lines.append(s)
                return lines
        except Exception:
            continue
    # 兜底
    try:
        with open(txt_path, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    except Exception:
        return []

def create_colored_transparent_masks_from_yolo(label_folder_path):
    """
    通过 YOLO 标签文件和图片，生成“透明背景 + 指定颜色填充矩形”的 PNG 掩膜。
    Args:
        label_folder_path (str): 拖拽进来的YOLO标签TXT文件所在的文件夹路径 (例如 '筛选TXT')。
    """

    # 检查拖拽的路径是否存在且是文件夹
    if not os.path.isdir(label_folder_path):
        print(f"错误: 拖拽的路径不是一个有效的文件夹: {label_folder_path}")
        return

    # 提示文件夹名（保持原脚本提示逻辑）
    if os.path.basename(label_folder_path).lower() != '筛选txt':
        print(f"警告: 拖拽的文件夹名称不是 '筛选TXT' (或 '筛选txt')。")
        print(f"脚本将尝试从 '{label_folder_path}' 读取标签。")
        print(f"请确保您的图片在 '{os.path.dirname(label_folder_path)}'。")

    label_dir = label_folder_path
    # 图片文件夹是标签文件夹的上一级目录
    image_dir = os.path.dirname(label_dir)

    # 确定输出掩膜的目录
    output_mask_dir = os.path.join(image_dir, OUTPUT_DIR_NAME)
    ensure_dir(output_mask_dir)
    print(f"输出目录: {output_mask_dir}")

    # 解析颜色
    try:
        fill_rgba = hex_to_rgba(FILL_COLOR_HEX, FILL_ALPHA)
    except Exception as e:
        print(f"错误: 无法解析颜色 {FILL_COLOR_HEX} -> {e}")
        return
    fill_bgra = rgba_to_bgra(fill_rgba)
    print(f"矩形填充颜色: {FILL_COLOR_HEX} (RGBA={fill_rgba})；背景: 透明")

    processed_count = 0
    skipped_count = 0
    total_txt = 0

    # 遍历标签目录中的所有TXT文件
    for label_filename in os.listdir(label_dir):
        if not label_filename.lower().endswith('.txt'):
            continue  # 只处理txt文件

        total_txt += 1
        base_name = os.path.splitext(label_filename)[0]  # 文件名（不含扩展名）
        label_path = os.path.join(label_dir, label_filename)
        output_mask_path = os.path.join(output_mask_dir, base_name + '.png')  # 输出 PNG（含透明通道）

        # 尝试查找对应的图片文件，支持多种常见图片格式
        image_path = None
        img = None
        for ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
            temp_image_path = os.path.join(image_dir, base_name + ext)
            if os.path.exists(temp_image_path):
                img = read_image_unicode(temp_image_path)
                if img is not None:
                    image_path = temp_image_path
                    break  # 找到并成功读取图片，跳出循环

        if image_path is None or img is None:
            print(f"警告: 未找到 {base_name} 对应的图片 (尝试了.jpg, .jpeg, .png, .bmp, .tiff) 或无法读取/解码，跳过 {label_filename}。")
            skipped_count += 1
            continue

        height, width, _ = img.shape

        # 创建透明（全 0）RGBA 掩膜图像
        mask = np.zeros((height, width, 4), dtype=np.uint8)  # 背景透明

        drew_any = False  # 是否绘制过至少一个有效矩形

        # 读取标签文件并绘制矩形
        try:
            lines = load_txt_lines(label_path)
            for line in lines:
                parts = line.strip().split()
                if len(parts) != 5:
                    if line.strip():
                        print(f"警告: 标签文件 {label_filename} 中的行格式不正确: '{line.strip()}'，跳过。")
                    continue
                try:
                    _, center_x, center_y, bbox_width, bbox_height = map(float, parts)
                except ValueError:
                    print(f"警告: 标签文件 {label_filename} 中的数值解析错误: '{line.strip()}'，跳过。")
                    continue

                # 忽略无效框
                if bbox_width <= 0 or bbox_height <= 0:
                    continue

                # 归一化 -> 像素
                x_center_abs = center_x * width
                y_center_abs = center_y * height
                bbox_width_abs = bbox_width * width
                bbox_height_abs = bbox_height * height

                x1 = int(round(x_center_abs - bbox_width_abs / 2))
                y1 = int(round(y_center_abs - bbox_height_abs / 2))
                x2 = int(round(x_center_abs + bbox_width_abs / 2))
                y2 = int(round(y_center_abs + bbox_height_abs / 2))

                # 边界裁剪
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(width - 1, x2)
                y2 = min(height - 1, y2)

                # 无面积则跳过
                if x2 <= x1 or y2 <= y1:
                    continue

                # 绘制“实心矩形”，颜色为 BGRA（带透明度）
                cv2.rectangle(mask, (x1, y1), (x2, y2), fill_bgra, thickness=-1)
                drew_any = True
        except Exception as e:
            print(f"错误: 读取标签文件 {label_path} 时发生异常: {e}")
            skipped_count += 1
            continue

        # 空标注处理
        if SKIP_EMPTY and not drew_any:
            print(f"跳过: {label_filename} 为空标注/无有效框（未生成文件）")
            skipped_count += 1
            continue

        # 保存 PNG（包含透明通道），使用 imencode 规避 imwrite 的路径问题
        success = imwrite_png_unicode(output_mask_path, mask)
        if success:
            if drew_any:
                print(f"已生成彩色透明掩膜: {output_mask_path}")
            else:
                print(f"已生成全透明掩膜（空标注）: {output_mask_path}")
            processed_count += 1
        else:
            print(f"!!! 严重警告: 无法保存掩膜文件: {output_mask_path} (imencode+写文件 失败)")
            skipped_count += 1

    print("\n--- 掩膜生成完成 ---")
    print(f"统计：共发现标签TXT {total_txt} 个；成功生成 {processed_count} 个；跳过 {skipped_count} 个。")
    print(f"输出目录：{output_mask_dir}")

    # 输出目录内容预览
    if os.path.exists(output_mask_dir):
        generated_files = os.listdir(output_mask_dir)
        if generated_files:
            print(f"\n在 '{output_mask_dir}' 中找到以下文件：")
            for f in generated_files[:10]:  # 只打印前10个
                print(f"- {f}")
            if len(generated_files) > 10:
                print(f"... (共 {len(generated_files)} 个文件)")
        else:
            print(f"\n警告: 脚本运行结束后，目录 '{output_mask_dir}' 仍然是空的！")

def main():
    if len(sys.argv) < 2:
        print("--- 透明彩色掩膜生成脚本 ---")
        print("使用方法: 请将包含YOLO标签TXT文件的文件夹 ('筛选TXT') 拖拽到此脚本上运行。")
        print("\n例如：")
        print("你的图片在: D:\\Ddown\\...\\labels")
        print("你的标签在: D:\\Ddown\\...\\labels\\筛选TXT")
        print("把 '筛选TXT' 文件夹拖拽到本脚本上。")
        # 不直接 return，交给 finally 去等待回车后退出
        sys.exit(1)

    dragged_folder_path = sys.argv[1]
    print(f"检测到拖拽路径: {dragged_folder_path}")
    create_colored_transparent_masks_from_yolo(dragged_folder_path)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 捕获未预期异常，打印出来，方便调试
        print(f"\n[未捕获异常] {e}")
    finally:
        # Windows 下双击运行时，窗口不自动关闭
        if os.name == "nt":
            try:
                input("按回车键退出...")
            except Exception:
                pass