# -*- coding: utf-8 -*-
import os
import sys
import cv2
import math
import numpy as np
import io
import ctypes
import time
import random
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

# 排除角度列表（顺时针角度标记）
EXCLUDED_ANGLES = {0,90, 180, 270}

# ============== 角度总开关与范围配置 ==============
# 角度总开关：False 时完全不做角度旋转（仅执行镜像/翻转增强）
ENABLE_ANGLE_ROTATION = True

# 是否启用“指定范围模式” True/False（仅当 ENABLE_ANGLE_ROTATION=True 时生效）
USE_ANGLE_RANGE = True
# 指定角度范围/列表（顺时针），示例："0, 30,45,60" 或 "300-358" 或 "10-20, 90, 120-125"
# 若需包含0度，请显式把 0 写进来，如 "0, 10-20"
ANGLE_RANGE_SPEC = "1-359"

# ============== 随机角度模式 ==============
# 是否启用"随机角度模式" True/False（仅当 ENABLE_ANGLE_ROTATION=True 时生效）
# True: 每张图片只随机生成指定数量的角度（从角度范围中随机选择）
# False: 每张图片生成所有角度（原有行为）
USE_RANDOM_ANGLE = True

# 随机角度数量：每张图片随机生成几个角度的增强图（仅当 USE_RANDOM_ANGLE=True 时生效）
# 例如：设置为 1 表示每张图生成1个随机角度，设置为 3 表示每张图生成3个不同的随机角度
# 注意：如果设置的数量大于可用角度总数，将自动调整为可用角度总数
RANDOM_ANGLE_COUNT = 1
# =====================================================

# ================= 镜像/翻转/上下颠倒增强控制 =================
ENABLE_MIRROR_FLIP = False

# 选择要生成的镜像/翻转类型（可多选并组合输出）
# 可选值：
#   'none'        -> 不做镜像/翻转
#   'hflip'       -> 水平镜像（左右反转）
#   'vflip'       -> 垂直镜像（上下反转）
#   'hvflip'      -> 水平+垂直（等价180°翻转，但与旋转组合时仍保留此路径）
#   'upsidedown'  -> 上下颠倒（等价180°旋转；这里实现为几何翻转路径，保持与标签一致）
# 你可以填多个，用逗号分隔，程序会为每种镜像/翻转分别生成（与角度列表笛卡尔积）。
MIRROR_FLIP_MODES = "hflip,vflip,hvflip"
# =====================================================


def _set_console_utf8():
    if os.name == "nt":
        try:
            os.system("")
            ctypes.windll.kernel32.SetConsoleCP(65001)
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            if sys.stdout and (not sys.stdout.encoding or sys.stdout.encoding.lower() != "utf-8"):
                sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
            if sys.stderr and (not sys.stderr.encoding or sys.stderr.encoding.lower() != "utf-8"):
                sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
        except Exception:
            pass


def print_safe(*args, **kwargs):
    text = " ".join(str(a) for a in args)
    try:
        print(text, **kwargs)
    except UnicodeEncodeError:
        if sys.stdout:
            enc = sys.stdout.encoding or "utf-8"
            sys.stdout.write(text.encode(enc, errors="replace").decode(enc, errors="replace") + ("" if kwargs.get("end") else "\n"))


def imread_unicode(path):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size == 0:
            return None
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def imwrite_unicode(path, img, ext=None, params=None):
    if ext is None:
        _, ext = os.path.splitext(path)
    ext = ext.lower()
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


def _parse_angle_spec(spec):
    if not isinstance(spec, str) or not spec.strip():
        return []
    angles = set()
    tokens = [t.strip() for t in spec.split(",") if t.strip()]
    for tk in tokens:
        if "-" in tk:
            try:
                a, b = tk.split("-", 1)
                a = int(float(a)) % 360
                b = int(float(b)) % 360
                if a <= b:
                    rng = range(a, b + 1)
                else:
                    rng = list(range(a, 360)) + list(range(0, b + 1))
                angles.update(rng)
            except Exception:
                continue
        else:
            try:
                angles.add(int(float(tk)) % 360)
            except Exception:
                continue
    out = sorted({int(a) % 360 for a in angles})
    return out


def _build_angle_list():
    # 若总开关关闭，直接返回空列表和说明
    if not ENABLE_ANGLE_ROTATION:
        return [], "角度总开关已关闭（不进行任何角度旋转）"

    excluded = {int(a) % 360 for a in EXCLUDED_ANGLES}
    if USE_ANGLE_RANGE:
        base = _parse_angle_spec(ANGLE_RANGE_SPEC)
        angles = [a for a in base if a not in excluded]
        mode_note = "开启指定范围模式"
    else:
        angles = [a for a in range(0, 360) if a not in excluded]  # 允许0度
        mode_note = "使用默认角度模式（0..359，应用排除列表）"
    angles = sorted(set(int(a) % 360 for a in angles))
    return angles, mode_note


def normalize_user_angle(user_input_angle):
    a = float(user_input_angle) % 360.0
    if 0 <= a <= 180:
        cw_angle = a
    else:
        cw_angle = -(360.0 - a)
    cv_angle = -cw_angle  # OpenCV 逆时针为正
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


# ============== 镜像/翻转 仿射矩阵与应用 ==============
def get_flip_mode_list(spec: str):
    if not ENABLE_MIRROR_FLIP:
        return ["none"]
    tokens = [t.strip().lower() for t in (spec or "").split(",") if t.strip()]
    valid = {"none", "hflip", "vflip", "hvflip", "upsidedown"}
    out = []
    for t in tokens:
        if t in valid:
            out.append(t)
    if not out:
        out = ["none"]
    # 去重保持顺序
    seen = set()
    result = []
    for t in out:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def get_flip_affine_matrix(mode, w, h):
    if mode == "none":
        M = np.array([[1, 0, 0],
                      [0, 1, 0]], dtype=np.float32)
    elif mode == "hflip":
        M = np.array([[-1, 0, w - 1],
                      [ 0, 1, 0     ]], dtype=np.float32)
    elif mode == "vflip":
        M = np.array([[1,  0, 0     ],
                      [0, -1, h - 1 ]], dtype=np.float32)
    elif mode == "hvflip" or mode == "upsidedown":
        M = np.array([[-1, 0, w - 1],
                      [ 0,-1, h - 1]], dtype=np.float32)
    else:
        M = np.array([[1, 0, 0],
                      [0, 1, 0]], dtype=np.float32)
    return M


def apply_flip_image(img, mode):
    if mode == "none":
        return img.copy(), (img.shape[1], img.shape[0]), np.array([[1,0,0],[0,1,0]], dtype=np.float32)
    if mode == "hflip":
        flipped = cv2.flip(img, 1)
    elif mode == "vflip":
        flipped = cv2.flip(img, 0)
    elif mode == "hvflip" or mode == "upsidedown":
        flipped = cv2.flip(img, -1)
    else:
        flipped = img.copy()
    h, w = flipped.shape[:2]
    M = get_flip_affine_matrix(mode, w, h)
    return flipped, (w, h), M


# ============== 进度条工具函数 ==============
def format_timedelta(seconds):
    if seconds is None or seconds != seconds or seconds == float('inf'):
        return "--:--"
    seconds = int(max(0, seconds))
    return str(timedelta(seconds=seconds))

def render_progress_bar(current, total, start_time, bar_len=30, prefix="进度"):
    current = min(current, total)
    ratio = 0 if total == 0 else (current / total if total > 0 else 0)
    filled = int(bar_len * ratio)
    bar = "█" * filled + "░" * (bar_len - filled)
    elapsed = time.time() - start_time
    eta = None
    if current > 0:
        speed = current / max(1e-9, elapsed)
        remaining = (total - current) / max(1e-9, speed)
        eta = remaining
    percent = int(ratio * 100 + 0.5)
    return f"{prefix} [{bar}] {percent:3d}% {current}/{total} | 用时 {format_timedelta(elapsed)} | 预计剩余 {format_timedelta(eta)}"

def print_progress_line(line):
    sys.stdout.write("\r" + line)
    sys.stdout.flush()

def end_progress_line():
    sys.stdout.write("\n")
    sys.stdout.flush()
# ===========================================


def rotate_obb_labels(txt_path, save_path, M_total, in_size, out_size):
    """
    使用组合仿射矩阵 M_total（先镜像/翻转，再旋转，若有）变换 YOLO-OBB 标签。
    txt 格式：cls x1 y1 x2 y2 x3 y3 x4 y4（归一化）
    in_size: (W,H) 输入图像尺寸
    out_size: (W,H) 输出图像尺寸
    """
    W, H = in_size
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

        pts_pix = []
        for i in range(0, 8, 2):
            x = coords_norm[i] * W
            y = coords_norm[i + 1] * H
            pts_pix.append([x, y])
        pts_pix = np.array(pts_pix, dtype=np.float32)

        pts_trans_pix = rotate_points_affine(pts_pix, M_total)

        rect = cv2.minAreaRect(pts_trans_pix.astype(np.float32))
        box_pix = cv2.boxPoints(rect)

        new_coords_norm = []
        for x_p, y_p in box_pix:
            x_norm = float(np.clip(x_p / out_W, 0.0, 1.0))
            y_norm = float(np.clip(y_p / out_H, 0.0, 1.0))
            new_coords_norm.extend([x_norm, y_norm])

        new_line = f"{cls} " + " ".join(f"{v:.8f}" for v in new_coords_norm)
        new_lines.append(new_line)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


# ============== 命名前缀策略 ==============
def flip_prefix(mode: str) -> str:
    """
    为不同翻转模式提供不同前缀，避免文件名覆盖：
    - hflip -> JXH（镜像-水平）
    - vflip -> JXV（镜像-垂直）
    - hvflip -> JXHV（镜像-水平+垂直）
    - upsidedown -> DZ（颠倒）
    - none -> ""
    """
    if mode == "upsidedown":
        return "DZ"
    elif mode == "hflip":
        return "JXH"
    elif mode == "vflip":
        return "JXV"
    elif mode == "hvflip":
        return "JXHV"
    else:
        return ""


def angle_prefix(angle: int, include_zero=True) -> str:
    """
    角度命名为 {angle}du；当 angle==0 且 include_zero 为 False 时返回空。
    """
    angle = int(angle) % 360
    if angle == 0 and not include_zero:
        return ""
    return f"{angle}du"


def build_save_prefix(mode: str, angle: int, angle_enabled: bool) -> str:
    """
    当 angle_enabled=False 时，不附加角度前缀，仅返回镜像/颠倒前缀。
    """
    parts = []
    fp = flip_prefix(mode)
    if fp:
        parts.append(fp)

    if angle_enabled:
        # 角度0是否输出 du 前缀由 include_zero 控制，当前为了可见性设为 False（保持你原有逻辑）
        ap = angle_prefix(angle, include_zero=False)
        if ap:
            parts.append(ap)

    return "_".join(parts) + ("_" if parts else "")


def process_folder_all(folder_path):
    _set_console_utf8()

    folder_path = os.path.normpath(os.fsdecode(os.fsencode(folder_path)))

    # 角度列表
    angles, mode_note = _build_angle_list()
    flip_modes = get_flip_mode_list(MIRROR_FLIP_MODES)

    print_safe("模式：旋转 + 镜像/颠倒 批量角度增强（OBB 同步）")
    print_safe(mode_note)
    print_safe(f"已排除角度: {sorted({int(a)%360 for a in EXCLUDED_ANGLES})}")
    print_safe(f"BORDER_MODE: {BORDER_MODE}")
    print_safe(f"镜像/翻转模式: {flip_modes}")
    print_safe(f"角度总开关: {'开启' if ENABLE_ANGLE_ROTATION else '关闭'}")
    if ENABLE_ANGLE_ROTATION and USE_RANDOM_ANGLE:
        print_safe(f"随机角度模式: 开启（每张图生成 {RANDOM_ANGLE_COUNT} 个随机角度）")
    else:
        print_safe(f"随机角度模式: 关闭（生成所有角度）")
    print_safe("")

    # 当角度总开关关闭时，angles 应为空列表；我们改为逻辑上生成一个“虚拟角度循环”仅用于流程，但不进行旋转
    angle_iter = angles if ENABLE_ANGLE_ROTATION else [None]

    out_dir = os.path.join(folder_path, "旋转_镜像_颠倒_数据增强")
    os.makedirs(out_dir, exist_ok=True)

    # 新增：专门放置标签的子目录
    out_txt_dir = os.path.join(out_dir, "TXT")
    os.makedirs(out_txt_dir, exist_ok=True)

    try:
        files = os.listdir(folder_path)
    except Exception as e:
        print_safe(f"无法列出目录：{folder_path}，原因：{e}")
        return

    img_files = [f for f in files if os.path.splitext(f)[1].lower() in IMG_EXTS]
    img_files.sort()

    total_imgs = len(img_files)
    if total_imgs == 0:
        print_safe("未找到图片文件。")
        return

    # 计算总任务数：如果启用随机角度模式，每张图生成指定数量的随机角度
    if ENABLE_ANGLE_ROTATION and USE_RANDOM_ANGLE:
        # 确保随机角度数量不超过可用角度总数
        actual_random_count = min(RANDOM_ANGLE_COUNT, len(angles)) if len(angles) > 0 else 1
        total_tasks = total_imgs * max(1, len(flip_modes)) * actual_random_count
    else:
        total_tasks = total_imgs * max(1, len(flip_modes)) * (len(angles) if ENABLE_ANGLE_ROTATION else 1)

    stats = {
        "ok": 0,
        "read_fail": 0,
        "rotate_fail": 0,
        "write_fail": 0,
        "label_processed": 0,
        "label_missing": 0
    }

    start_time = time.time()
    completed = 0

    if ENABLE_ANGLE_ROTATION:
        if USE_RANDOM_ANGLE:
            actual_random_count = min(RANDOM_ANGLE_COUNT, len(angles)) if len(angles) > 0 else 1
            print_safe(f"随机角度范围: {angles[0]}-{angles[-1]}度（共{len(angles)}个可选角度）")
            print_safe(f"每张图片将从该范围随机选择 {actual_random_count} 个角度")
            if RANDOM_ANGLE_COUNT > len(angles):
                print_safe(f"⚠️ 注意：设置的随机数量({RANDOM_ANGLE_COUNT})大于可用角度数({len(angles)})，已自动调整为{actual_random_count}")
        else:
            print_safe(f"将处理角度: {angles}")
    else:
        print_safe("角度已关闭：仅进行镜像/颠倒增强，不进行任何旋转。")
    print_safe(f"预计生成图片数量: {total_tasks} 张（不含原图）")
    print_safe("")

    for img_name in img_files:
        img_path = os.path.join(folder_path, img_name)
        name_no_ext = os.path.splitext(img_name)[0]
        txt_path = os.path.join(folder_path, name_no_ext + ".txt")

        img = imread_unicode(img_path)
        if img is None:
            if ENABLE_ANGLE_ROTATION and USE_RANDOM_ANGLE:
                actual_random_count = min(RANDOM_ANGLE_COUNT, len(angles)) if len(angles) > 0 else 1
                fail = max(1, len(flip_modes)) * actual_random_count
            else:
                fail = max(1, len(flip_modes)) * (len(angles) if ENABLE_ANGLE_ROTATION else 1)
            stats["read_fail"] += fail
            completed += fail
            progress_line = render_progress_bar(completed, total_tasks, start_time)
            print_progress_line(progress_line + f" | 失败: 读图 -> {img_name}")
            continue

        H0, W0 = img.shape[:2]

        for flip_mode in flip_modes:
            # 1) 先做镜像/翻转（若为 none 则为单位矩阵）
            try:
                img_flip, (Wf, Hf), M_flip = apply_flip_image(img, flip_mode)
            except Exception:
                if ENABLE_ANGLE_ROTATION and USE_RANDOM_ANGLE:
                    actual_random_count = min(RANDOM_ANGLE_COUNT, len(angles)) if len(angles) > 0 else 1
                    skip = actual_random_count
                else:
                    skip = (len(angles) if ENABLE_ANGLE_ROTATION else 1)
                stats["rotate_fail"] += skip
                completed += skip
                progress_line = render_progress_bar(completed, total_tasks, start_time)
                print_progress_line(progress_line + f" | 失败: 镜像/翻转 -> {flip_mode}_{img_name}")
                continue

            # 随机角度模式：为每张图随机选择指定数量的角度
            if ENABLE_ANGLE_ROTATION and USE_RANDOM_ANGLE:
                actual_random_count = min(RANDOM_ANGLE_COUNT, len(angles)) if len(angles) > 0 else 1
                # 使用 random.sample 确保不重复选择
                if actual_random_count >= len(angles):
                    current_angle_list = angles.copy()  # 如果要求的数量>=总数，就用全部
                else:
                    current_angle_list = random.sample(angles, actual_random_count)
            else:
                current_angle_list = angle_iter

            for angle in current_angle_list:
                # angle_enabled 决定是否真的旋转
                angle_enabled = ENABLE_ANGLE_ROTATION
                if angle_enabled:
                    cw_angle, cv_angle_to_use = normalize_user_angle(angle)
                else:
                    cw_angle, cv_angle_to_use = 0, 0.0  # 不旋转

                progress_line = render_progress_bar(completed, total_tasks, start_time)
                prefix = build_save_prefix(flip_mode, (angle if angle is not None else 0), angle_enabled)
                # 显示名称：将前缀放在文件名后面
                if prefix:
                    base_name, ext = os.path.splitext(img_name)
                    display_name = f"{base_name}_{prefix.rstrip('_')}{ext}"
                else:
                    display_name = img_name
                print_progress_line(progress_line + f" | 正在处理: {display_name}")

                # 2) 旋转（如果关闭角度则不旋转）
                try:
                    if angle_enabled:
                        rotated_img, out_size, M_rot = rotate_image_with_border(img_flip, cv_angle_to_use)
                    else:
                        rotated_img = img_flip  # 不做旋转
                        out_size = (Wf, Hf)
                        # 单位仿射矩阵
                        M_rot = np.array([[1, 0, 0],
                                          [0, 1, 0]], dtype=np.float32)

                    out_W, out_H = out_size
                    if rotated_img is None or out_W == 0 or out_H == 0:
                        stats["rotate_fail"] += 1
                        completed += 1
                        progress_line = render_progress_bar(completed, total_tasks, start_time)
                        print_progress_line(progress_line + f" | 失败: 旋转 -> {display_name}")
                        continue
                except Exception:
                    stats["rotate_fail"] += 1
                    completed += 1
                    progress_line = render_progress_bar(completed, total_tasks, start_time)
                    print_progress_line(progress_line + f" | 失败: 旋转异常 -> {display_name}")
                    continue

                # 组合仿射矩阵：M_total = M_rot @ M_flip（先 flip 再 rot；若无旋转则 M_rot 为单位矩阵）
                M_flip_3x3 = np.vstack([M_flip, [0, 0, 1]]).astype(np.float32)
                M_rot_3x3  = np.vstack([M_rot,  [0, 0, 1]]).astype(np.float32)
                M_total_3x3 = M_rot_3x3 @ M_flip_3x3
                M_total = M_total_3x3[:2, :]

                # 保存图片（保存在 out_dir）- 将前缀放在文件名后面
                if prefix:
                    # 分离文件名和扩展名，将前缀插入中间
                    base_name, ext = os.path.splitext(img_name)
                    save_img_name = f"{base_name}_{prefix.rstrip('_')}{ext}"
                else:
                    save_img_name = img_name
                save_img_path = os.path.join(out_dir, save_img_name)
                ok = imwrite_unicode(save_img_path, rotated_img, ext=os.path.splitext(img_name)[1])
                if not ok:
                    stats["write_fail"] += 1
                    completed += 1
                    progress_line = render_progress_bar(completed, total_tasks, start_time)
                    print_progress_line(progress_line + f" | 失败: 写入 -> {save_img_name}")
                    continue

                # 同步并保存标签（保存在 out_txt_dir）- 将前缀放在文件名后面
                if os.path.exists(txt_path):
                    try:
                        if prefix:
                            save_txt_name = f"{name_no_ext}_{prefix.rstrip('_')}.txt"
                        else:
                            save_txt_name = name_no_ext + ".txt"
                        save_txt_path = os.path.join(out_txt_dir, save_txt_name)  # 修改：写入到 TXT 子目录
                        rotate_obb_labels(txt_path, save_txt_path, M_total, (W0, H0), out_size)
                        stats["label_processed"] += 1
                    except Exception:
                        pass
                else:
                    stats["label_missing"] += 1

                stats["ok"] += 1
                completed += 1

                progress_line = render_progress_bar(completed, total_tasks, start_time)
                print_progress_line(progress_line + f" | 完成: {save_img_name}")

    end_progress_line()

    print_safe(f"处理完成，结果保存在：{out_dir}")
    print_safe(f"其中 TXT 标签统一保存在：{out_txt_dir}")
    print_safe(f"总任务: {total_tasks} | 成功: {stats['ok']} | 读图失败任务: {stats['read_fail']} | 旋转失败: {stats['rotate_fail']} | 写入失败: {stats['write_fail']}")
    print_safe(f"标签: 已处理 {stats['label_processed']} | 缺失或未参与 {stats['label_missing']}")
    elapsed = time.time() - start_time
    print_safe(f"总用时: {format_timedelta(elapsed)}")


if __name__ == "__main__":
    _set_console_utf8()

    if len(sys.argv) < 2:
        print_safe("请将包含图片和TXT的文件夹拖拽到脚本上运行。")
        input("按回车退出...")
        sys.exit()

    raw_folder = sys.argv[1].strip('"').strip("'")
    folder = os.path.normpath(os.fsdecode(os.fsencode(raw_folder)))

    if not os.path.isdir(folder):
        print_safe(f"路径无效，请拖入文件夹：{folder}")
        input("按回车退出...")
        sys.exit()

    process_folder_all(folder)
    input("\n处理完毕，按回车退出。")