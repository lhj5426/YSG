# -*- coding: utf-8 -*-
import os
import sys
import cv2
import math
import numpy as np
import io
import ctypes
import time
from datetime import timedelta

# ================= 用户可调设置 =================
IMG_EXTS = [".jpg", ".jpeg", ".png", ".bmp"]  # 支持的图片格式

# 旋转后的边界策略：
# - 'constant' -> 常量填充，给你“白边”（不拉伸，尺寸不变）
# - 'replicate' -> 边缘复制（无白边，但会有拉伸感）
# - 'expand' -> 扩大画布以完整容纳旋转图（无白边、不拉伸，尺寸变大）
BORDER_MODE = 'expand'

# 常量填充颜色（B,G,R），仅当 BORDER_MODE == 'constant' 时生效
BORDER_VALUE = (255, 255, 255)
# ===============================================


def _set_console_utf8():
    """
    将 Windows 控制台切换为 UTF-8，避免中文/日文路径与输出乱码。
    在非 Windows 上不做处理。
    """
    if os.name == "nt":
        try:
            # 切到 UTF-8 代码页
            os.system("")
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            # 确保标准流是 UTF-8
            if sys.stdout and (not sys.stdout.encoding or sys.stdout.encoding.lower() != "utf-8"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            if sys.stderr and (not sys.stderr.encoding or sys.stderr.encoding.lower() != "utf-8"):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass


def print_safe(*args, **kwargs):
    """
    避免因编码报错导致崩溃，输出时以 replace。
    """
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        if sys.stdout:
            enc = sys.stdout.encoding or "utf-8"
            sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + ("" if kwargs.get("end") else "\n"))
        else:
            pass


def imread_unicode(path):
    """
    兼容非 ASCII 路径的安全读图：
    使用 np.fromfile + cv2.imdecode 避开 Windows 路径编码问题。
    """
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def imwrite_unicode(path, img, ext=None, params=None):
    """
    兼容非 ASCII 路径的安全写图：
    使用 cv2.imencode + tofile。
    """
    if ext is None:
        _, ext = os.path.splitext(path)
    ext = ext.lower()
    # 缺省使用 .jpg 的质量设置
    if params is None and ext in [".jpg", ".jpeg"]:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), 95]
    try:
        success, buf = cv2.imencode(ext, img, params or [])
        if not success:
            return False
        buf.tofile(path)
        return True
    except Exception:
        return False


def rotate_points_affine(points_xy, M):
    pts = np.hstack([points_xy.astype(np.float32), np.ones((len(points_xy), 1), dtype=np.float32)])
    out = (M @ pts.T).T
    return out


def _get_rotation_matrix_expand(w, h, angle_deg):
    angle = math.radians(angle_deg)
    cos = abs(math.cos(angle))
    sin = abs(math.sin(angle))
    new_w = int(w * cos + h * sin + 0.5)
    new_h = int(h * cos + w * sin + 0.5)
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle_deg, 1.0)
    M[0, 2] += (new_w - w) / 2.0
    M[1, 2] += (new_h - h) / 2.0
    return M, (new_w, new_h)


def rotate_obb_labels(txt_path, save_path, rot_mat, img_size, out_size):
    """
    使用与图像相同的仿射矩阵 rot_mat 旋转 YOLO-OBB 标签。
    txt 格式：cls x1 y1 x2 y2 x3 y3 x4 y4（归一化）
    """
    W, H = img_size
    out_W, out_H = out_size

    if not os.path.exists(txt_path):
        return

    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        parts = line.strip().split()
        if len(parts) < 9:
            continue

        cls = parts[0]
        coords_norm = list(map(float, parts[1:9]))

        # 归一化 -> 像素
        pts_pix = []
        for i in range(0, 8, 2):
            x = coords_norm[i] * W
            y = coords_norm[i + 1] * H
            pts_pix.append([x, y])
        pts_pix = np.array(pts_pix, dtype=np.float32)

        # 旋转（与图像同矩阵）
        pts_rot_pix = rotate_points_affine(pts_pix, rot_mat)

        # 拟合最小外接矩形，稳定顶点
        rect = cv2.minAreaRect(pts_rot_pix.astype(np.float32))
        box_pix = cv2.boxPoints(rect)

        # 像素 -> 归一化（夹紧）
        new_coords_norm = []
        for x_p, y_p in box_pix:
            x_norm = float(np.clip(x_p / out_W, 0.0, 1.0))
            y_norm = float(np.clip(y_p / out_H, 0.0, 1.0))
            new_coords_norm.extend([x_norm, y_norm])

        new_line = f"{cls} " + " ".join(f"{v:.8f}" for v in new_coords_norm)
        new_lines.append(new_line)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


def normalize_user_angle(user_input_angle):
    a = float(user_input_angle) % 360.0
    if 0 <= a <= 180:
        cw_angle = a
    else:
        cw_angle = -(360.0 - a)
    cv_angle = -cw_angle
    return cw_angle, cv_angle


def rotate_image_with_border(img, cv_angle):
    h, w = img.shape[:2]

    if BORDER_MODE == 'expand':
        M, (new_w, new_h) = _get_rotation_matrix_expand(w, h, cv_angle)
        rotated = cv2.warpAffine(
            img, M, (new_w, new_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=BORDER_VALUE
        )
        return rotated, (new_w, new_h), M

    center = (w / 2.0, h / 2.0)
    M = cv2.getRotationMatrix2D(center, cv_angle, 1.0)

    if BORDER_MODE == 'constant':
        rotated = cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=BORDER_VALUE
        )
    else:  # 'replicate'
        rotated = cv2.warpAffine(
            img, M, (w, h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE
        )

    return rotated, (w, h), M


# ============== 新增：进度条工具函数 ==============
def format_timedelta(seconds):
    if seconds is None or seconds != seconds or seconds == float('inf'):
        return "--:--"
    seconds = int(max(0, seconds))
    return str(timedelta(seconds=seconds))

def render_progress_bar(current, total, start_time, bar_len=30, prefix="进度"):
    current = min(current, total)
    ratio = 0 if total == 0 else current / total
    filled = int(bar_len * ratio)
    bar = "█" * filled + "░" * (bar_len - filled)
    elapsed = time.time() - start_time
    eta = None
    if current > 0:
        speed = current / elapsed
        remaining = (total - current) / max(1e-9, speed)
        eta = remaining
    percent = int(ratio * 100 + 0.5)
    return f"{prefix} [{bar}] {percent:3d}% {current}/{total} | 用时 {format_timedelta(elapsed)} | 预计剩余 {format_timedelta(eta)}"

def print_progress_line(line):
    # 单行动态刷新
    sys.stdout.write("\r" + line)
    sys.stdout.flush()

def end_progress_line():
    # 完成后换行
    sys.stdout.write("\n")
    sys.stdout.flush()
# =================================================


def process_folder(folder_path, user_input_angle):
    _set_console_utf8()

    # 规范化路径为 str（防止因 shell 传入的奇怪编码导致失败）
    folder_path = os.path.normpath(os.fsdecode(os.fsencode(folder_path)))

    cw_angle, cv_angle_to_use = normalize_user_angle(user_input_angle)

    print_safe(f"用户输入: {user_input_angle}°")
    print_safe(f"解释为顺时针角度: {cw_angle}°（正=顺时针，负=逆时针）")
    print_safe(f"用于 OpenCV 的角度: {cv_angle_to_use}°（逆时针为正）")
    print_safe(f"BORDER_MODE: {BORDER_MODE}")
    print_safe("")

    angle_str = str(user_input_angle).rstrip("0").rstrip(".") if "." in str(user_input_angle) else str(user_input_angle)
    out_dir = os.path.join(folder_path, f"{angle_str}du")
    os.makedirs(out_dir, exist_ok=True)

    try:
        files = os.listdir(folder_path)
    except Exception as e:
        print_safe(f"无法列出目录：{folder_path}，原因：{e}")
        return

    img_files = [f for f in files if os.path.splitext(f)[1].lower() in IMG_EXTS]
    img_files.sort()  # 固定顺序，体验更好

    total = len(img_files)
    if total == 0:
        print_safe("未找到图片文件。")
        return

    # 统计信息
    stats = {
        "ok": 0,
        "read_fail": 0,
        "rotate_fail": 0,
        "write_fail": 0,
        "label_processed": 0,
        "label_missing": 0
    }

    start_time = time.time()
    last_filename_shown = ""

    for idx, img_name in enumerate(img_files, start=1):
        img_path = os.path.join(folder_path, img_name)
        name_no_ext = os.path.splitext(img_name)[0]
        txt_path = os.path.join(folder_path, name_no_ext + ".txt")

        # 显示当前正在处理的文件名（尽量简短）
        display_name = img_name
        last_filename_shown = display_name

        # 进度条（先画一遍，显示当前文件名）
        progress_line = render_progress_bar(idx - 1, total, start_time)
        print_progress_line(progress_line + f" | 正在处理: {display_name}")

        # 读取图片
        img = imread_unicode(img_path)
        if img is None:
            stats["read_fail"] += 1
            # 更新进度到该项完成（即 idx）
            progress_line = render_progress_bar(idx, total, start_time)
            print_progress_line(progress_line + f" | 失败: 读图 -> {display_name}")
            continue

        # 旋转图像
        try:
            rotated_img, out_size, rot_mat = rotate_image_with_border(img, cv_angle_to_use)
            out_W, out_H = out_size
            if rotated_img is None or out_W == 0 or out_H == 0:
                stats["rotate_fail"] += 1
                progress_line = render_progress_bar(idx, total, start_time)
                print_progress_line(progress_line + f" | 失败: 旋转 -> {display_name}")
                continue
        except Exception:
            stats["rotate_fail"] += 1
            progress_line = render_progress_bar(idx, total, start_time)
            print_progress_line(progress_line + f" | 失败: 旋转异常 -> {display_name}")
            continue

        # 保存图片（保持原扩展名）
        save_img_path = os.path.join(out_dir, img_name)
        ok = imwrite_unicode(save_img_path, rotated_img, ext=os.path.splitext(img_name)[1])
        if not ok:
            stats["write_fail"] += 1
            progress_line = render_progress_bar(idx, total, start_time)
            print_progress_line(progress_line + f" | 失败: 写入 -> {display_name}")
            continue

        # 旋转标签
        if os.path.exists(txt_path):
            try:
                save_txt_path = os.path.join(out_dir, name_no_ext + ".txt")
                rotate_obb_labels(txt_path, save_txt_path, rot_mat, (img.shape[1], img.shape[0]), out_size)
                stats["label_processed"] += 1
            except Exception:
                # 标签失败不影响主进度
                pass
        else:
            stats["label_missing"] += 1

        stats["ok"] += 1

        # 完成当前项，刷新进度
        progress_line = render_progress_bar(idx, total, start_time)
        print_progress_line(progress_line + f" | 完成: {display_name}")

    # 收尾
    end_progress_line()

    # 汇总信息
    print_safe(f"处理完成，结果保存在：{out_dir}")
    print_safe(f"总计: {total} | 成功: {stats['ok']} | 读图失败: {stats['read_fail']} | 旋转失败: {stats['rotate_fail']} | 写入失败: {stats['write_fail']}")
    print_safe(f"标签: 已处理 {stats['label_processed']} | 缺失 {stats['label_missing']}")
    elapsed = time.time() - start_time
    print_safe(f"总用时: {format_timedelta(elapsed)}")


if __name__ == "__main__":
    _set_console_utf8()

    if len(sys.argv) < 2:
        print_safe("请将包含图片和TXT的文件夹拖拽到脚本上运行。")
        input("按回车退出...")
        sys.exit()

    # 拖拽路径可能包含引号，去除它，并使用规范化的 UTF-8 字符串
    raw_folder = sys.argv[1].strip('"').strip("'")
    folder = os.path.normpath(os.fsdecode(os.fsencode(raw_folder)))

    if not os.path.isdir(folder):
        print_safe(f"路径无效，请拖入文件夹：{folder}")
        input("按回车退出...")
        sys.exit()

    try:
        angle_str = input("请输入旋转角度（0到359之间，例如 10=顺时针10°, 350=逆时针10°）：").strip()
        angle = float(angle_str)
        if not (0 <= angle < 360):
            raise ValueError
    except ValueError:
        print_safe("输入无效，请输入0到359之间的数字。")
        input("按回车退出...")
        sys.exit()

    process_folder(folder, angle)
    input("\n处理完毕，按回车退出。")