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
from multiprocessing import Pool, cpu_count
import multiprocessing

# ================= 用户可调设置 =================
IMG_EXTS = [".jpg", ".jpeg", ".png", ".bmp"]  # 支持的图片格式

# ================= 多进程设置 =================
ENABLE_MULTIPROCESSING = True
# 是否启用多进程处理
# True: 使用多进程加速（推荐，速度提升2-4倍）
# False: 单进程处理（兼容性更好）

MAX_PROCESSES = 4
# 最大进程数（建议设置为CPU核心数）
# 0 = 自动检测CPU核心数
# 例如：4核CPU设置为4，8核CPU设置为8
# 设置过高可能导致内存不足
# =====================================================

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
ANGLE_RANGE_SPEC = "1-40,315-359,138-179,181-212"

# ============== 随机角度模式 ==============
# 是否启用"随机角度模式" True/False（仅当 ENABLE_ANGLE_ROTATION=True 时生效）
# True: 每张图片随机生成指定数量的角度（从角度范围中随机选择）
# False: 每张图片生成所有角度（全角度模式）
USE_RANDOM_ANGLE = True

# 随机角度数量（仅当 USE_RANDOM_ANGLE=True 时生效）
# 1 = 单角度模式（每张图1个随机角度）
# 3 = 多角度模式（每张图3个不同随机角度）
# N = 每张图N个不同随机角度
RANDOM_ANGLE_COUNT = 1
# =====================================================

# ================= 镜像/翻转/上下颠倒增强控制 =================
ENABLE_MIRROR_FLIP = True

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

# ================= 随机颜色变换增强控制 =================
ENABLE_COLOR_TRANSFORM = True
# 是否启用随机颜色变换增强（HSV色彩空间随机调整）
# True: 为每张图片生成随机颜色变换版本
# False: 不进行颜色变换

COLOR_TRANSFORM_PROB = 0.5
# 应用概率（0.0-1.0）
# 1.0 = 100%应用（所有图片都变换）
# 0.5 = 50%概率（默认）
# 0.3 = 30%概率
# 0.0 = 不应用

# 颜色模式选择
COLOR_CRAZY_MODE = True         # True=完全随机颜色（CSGO开箱风格，五彩斑斓）
                                # False=微调模式（模拟不同光照，使用下面的参数）

# 微调模式参数（仅当 COLOR_CRAZY_MODE=False 时生效）
COLOR_HUE_SHIFT = 35        # 色调偏移范围（0-180，推荐10-50）
COLOR_SAT_SCALE = 0.3       # 饱和度缩放范围（0.0-1.0，推荐0.2-0.5）
COLOR_VAL_SCALE = 0.3       # 明度缩放范围（0.0-1.0，推荐0.2-0.5）
# =====================================================

# ================= 噪点增强控制 =================
ENABLE_NOISE = True
# 是否启用噪点增强
# True: 为每张图片添加噪点
# False: 不添加噪点

NOISE_PROB = 0.5
# 应用概率（0.0-1.0），控制每种噪点类型的应用概率
# 1.0 = 100%应用
# 0.5 = 50%概率（默认）
# 0.0 = 不应用

# 噪点类型选择（可多选，用逗号分隔）
# 可选值：
#   'gaussian'    -> 高斯噪点（正态分布噪声，常见）
#   'salt_pepper' -> 椒盐噪点（随机黑白点）
#   'poisson'     -> 泊松噪点（光子计数噪声，低光照）
#   'speckle'     -> 斑点噪点（乘性噪声，雷达/超声）
NOISE_TYPES = "gaussian,salt_pepper,poisson,speckle"

# 高斯噪点参数（随机强度范围）
GAUSSIAN_MEAN = 0              # 高斯噪声均值
GAUSSIAN_SIGMA_MIN = 10        # 最小强度（轻微噪点）
GAUSSIAN_SIGMA_MAX = 40        # 最大强度（明显但不过分，超过50会很模糊）

# 椒盐噪点参数（随机密度范围）
SALT_PEPPER_AMOUNT_MIN = 0.005  # 最小密度（稀疏）
SALT_PEPPER_AMOUNT_MAX = 0.03   # 最大密度（密集但不过分）
SALT_RATIO = 0.5                # 盐噪点（白点）比例（0.0-1.0）

# 泊松噪点参数（随机缩放范围）
POISSON_SCALE_MIN = 0.5         # 最小缩放（噪点较弱）
POISSON_SCALE_MAX = 2.0         # 最大缩放（噪点较强）

# 斑点噪点参数（随机方差范围）
SPECKLE_VARIANCE_MIN = 0.05     # 最小方差
SPECKLE_VARIANCE_MAX = 0.2      # 最大方差
# =====================================================

# ================= 亮度/对比度增强控制 =================
ENABLE_BRIGHTNESS_CONTRAST = True
# 是否启用亮度/对比度随机调整
# True: 随机调整亮度和对比度
# False: 不调整

BRIGHTNESS_CONTRAST_PROB = 0.5
# 应用概率（0.0-1.0）
# 1.0 = 100%应用
# 0.5 = 50%概率（默认）
# 0.0 = 不应用

# 亮度调整范围（随机）
BRIGHTNESS_MIN = -30    # 最暗（负值变暗，避免全黑）
BRIGHTNESS_MAX = 30     # 最亮（正值变亮，避免过曝）

# 对比度调整范围（随机）
CONTRAST_MIN = 0.7     # 最低对比度（<1降低对比度）
CONTRAST_MAX = 1.3      # 最高对比度（>1增强对比度）
# =====================================================

# ================= 灰度化增强控制 =================
ENABLE_GRAYSCALE = True
# 是否启用灰度化增强（彩色转黑白）
# True: 随机将部分图片转为灰度图
# False: 不进行灰度化

GRAYSCALE_PROB = 0.4
# 应用概率（0.0-1.0）
# 1.0 = 100%应用（所有图片都变黑白）
# 0.5 = 50%概率（默认）
# 0.0 = 不应用

# 灰度化模式选择
# 'standard'  -> 标准灰度（加权平均，最常用）
# 'average'   -> 简单平均（R+G+B)/3
# 'luminosity'-> 亮度模式（更接近人眼感知）
GRAYSCALE_MODE = 'standard'

# 是否保持3通道输出（兼容性更好）
# True: 输出3通道灰度图（BGR格式，但三通道值相同）
# False: 输出单通道灰度图
GRAYSCALE_KEEP_3CH = True
# =====================================================

# ================= 类别ID替换功能（仅针对旋转标签OBB） =================
ENABLE_LABEL_ID_REPLACE = True
# 是否启用类别ID替换功能
# True: 在处理旋转标签（OBB）时替换类别ID
# False: 不替换类别ID

# 类别ID替换映射：原类别ID -> 新类别ID
# 例如：{0: 2, 1: 2, 3: 4} 表示将类别0和1都替换为2，类别3替换为4
LABEL_ID_REPLACE_MAP = {
    0: 2,
    1: 2,
    3: 4
}
# =====================================================

# ========================================================================
# 【核心参数】旋转与增强比例控制（仅对旋转矩形OBB有效）
# ========================================================================
ENABLE_ROTATION_RATIO = True
# 是否启用旋转比例控制（仅对旋转矩形OBB有效，水平矩形HBB不受影响）
# True: 随机选择 AUGMENTATION_RATIO 比例的图片 → 旋转+增强，其他不处理
# False: 100%图片都旋转 → 随机选择 AUGMENTATION_RATIO 比例的图片增强

AUGMENTATION_RATIO = 0.4
# 增强比例（0.0-1.0）
# 例如：0.5 = 50%的图片
# 
# 示例（100张旋转矩形图，AUGMENTATION_RATIO = 0.5）：
# - ENABLE_ROTATION_RATIO = True:  随机选50张 → 旋转+增强，其他50张不处理
# - ENABLE_ROTATION_RATIO = False: 100张都旋转 → 随机选50张增强，其他50张只旋转
# 
# 注意：水平矩形（HBB）标签会自动禁用旋转功能，只进行增强处理
# ========================================================================

# ========================================================================
# 【特殊模式】原图替换模式
# ========================================================================
ENABLE_REPLACE_ORIGINAL = False
# 是否启用原图替换模式
# True: 直接覆盖原文件（不生成新文件）
# False: 生成新文件到输出文件夹（默认模式）
#
# 原图替换模式说明：
# 1. 按照 AUGMENTATION_RATIO 随机选择图片
# 2. 直接覆盖原文件
# 3. ⚠️ 会永久覆盖原文件，使用前请备份！
#
# 旋转支持：
# - 如果 BORDER_MODE = 'expand'，旋转会被自动禁用（尺寸会变化）
# - 如果 BORDER_MODE = 'constant' 或 'replicate'，可以使用旋转（保持原尺寸）
# ========================================================================


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


# ============== 随机颜色变换函数 ==============
def apply_crazy_random_color(img):
    """
    完全随机颜色变换 - CSGO开箱风格
    每个像素随机偏移色调，产生五彩斑斓的效果
    避免全白和全黑
    """
    # 转换到 HSV 色彩空间
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
    
    # 完全随机色调偏移（0-180度，覆盖整个色谱）
    hue_shift = random.uniform(0, 180)
    hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
    
    # 随机饱和度（保持一定饱和度，避免灰色）
    sat_scale = random.uniform(0.8, 1.5)  # 增强饱和度
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 50, 255)  # 最低50避免灰色
    
    # 随机明度（避免全黑全白）
    val_scale = random.uniform(0.7, 1.3)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * val_scale, 30, 225)  # 30-225避免极端
    
    # 转换回 BGR
    hsv = hsv.astype(np.uint8)
    result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return result


def apply_random_color_transform(img):
    """
    智能随机颜色变换
    根据配置选择：完全随机模式 或 微调模式
    """
    if COLOR_CRAZY_MODE:
        # 完全随机模式（CSGO开箱风格）
        return apply_crazy_random_color(img)
    else:
        # 微调模式（模拟不同光照条件）
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV).astype(np.float32)
        
        # 随机调整色调（Hue）
        hue_shift = random.uniform(-COLOR_HUE_SHIFT, COLOR_HUE_SHIFT)
        hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
        
        # 随机调整饱和度（Saturation）
        sat_scale = random.uniform(1 - COLOR_SAT_SCALE, 1 + COLOR_SAT_SCALE)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_scale, 0, 255)
        
        # 随机调整明度（Value）
        val_scale = random.uniform(1 - COLOR_VAL_SCALE, 1 + COLOR_VAL_SCALE)
        hsv[:, :, 2] = np.clip(hsv[:, :, 2] * val_scale, 0, 255)
        
        # 转换回 BGR
        hsv = hsv.astype(np.uint8)
        result = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        return result


# ============== 噪点增强函数 ==============
def get_noise_type_list(spec: str):
    """
    解析噪点类型配置
    """
    if not ENABLE_NOISE:
        return []
    tokens = [t.strip().lower() for t in (spec or "").split(",") if t.strip()]
    valid = {"gaussian", "salt_pepper", "poisson", "speckle"}
    out = []
    for t in tokens:
        if t in valid:
            out.append(t)
    # 去重保持顺序
    seen = set()
    result = []
    for t in out:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def add_gaussian_noise(img, mean=0, sigma=25):
    """
    添加高斯噪点
    mean: 噪声均值
    sigma: 噪声标准差
    """
    noise = np.random.normal(mean, sigma, img.shape).astype(np.float32)
    noisy_img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return noisy_img


def add_salt_pepper_noise(img, amount=0.02, salt_ratio=0.5):
    """
    添加椒盐噪点
    amount: 噪点密度（0.0-1.0）
    salt_ratio: 盐噪点（白点）比例
    """
    noisy_img = img.copy()
    num_salt = int(amount * img.size * salt_ratio)
    num_pepper = int(amount * img.size * (1 - salt_ratio))
    
    # 添加盐噪点（白点）
    coords = [np.random.randint(0, i, num_salt) for i in img.shape[:2]]
    noisy_img[coords[0], coords[1], :] = 255
    
    # 添加椒噪点（黑点）
    coords = [np.random.randint(0, i, num_pepper) for i in img.shape[:2]]
    noisy_img[coords[0], coords[1], :] = 0
    
    return noisy_img


def add_poisson_noise(img, scale=1.0):
    """
    添加泊松噪点（Poisson Noise）
    模拟光子计数噪声，常见于低光照环境
    scale: 噪声缩放因子（>1增强噪点，<1减弱噪点）
    """
    vals = len(np.unique(img))
    vals = 2 ** np.ceil(np.log2(vals))
    # 应用缩放因子控制噪声强度
    noisy_img = np.random.poisson(img.astype(np.float32) * vals / scale) * scale / float(vals)
    noisy_img = np.clip(noisy_img, 0, 255).astype(np.uint8)
    return noisy_img


def add_speckle_noise(img, variance=0.1):
    """
    添加斑点噪点（Speckle Noise）
    乘性噪声，常见于雷达图像和超声图像
    variance: 噪声方差
    """
    noise = np.random.randn(*img.shape) * variance
    noisy_img = img.astype(np.float32) + img.astype(np.float32) * noise
    noisy_img = np.clip(noisy_img, 0, 255).astype(np.uint8)
    return noisy_img


def apply_noise(img, noise_type):
    """
    根据类型应用噪点（随机强度）
    """
    if noise_type == "gaussian":
        # 随机选择高斯噪点强度
        sigma = random.uniform(GAUSSIAN_SIGMA_MIN, GAUSSIAN_SIGMA_MAX)
        return add_gaussian_noise(img, GAUSSIAN_MEAN, sigma)
    elif noise_type == "salt_pepper":
        # 随机选择椒盐噪点密度
        amount = random.uniform(SALT_PEPPER_AMOUNT_MIN, SALT_PEPPER_AMOUNT_MAX)
        return add_salt_pepper_noise(img, amount, SALT_RATIO)
    elif noise_type == "poisson":
        # 随机选择泊松噪点缩放因子
        scale = random.uniform(POISSON_SCALE_MIN, POISSON_SCALE_MAX)
        return add_poisson_noise(img, scale)
    elif noise_type == "speckle":
        # 随机选择斑点噪点方差
        variance = random.uniform(SPECKLE_VARIANCE_MIN, SPECKLE_VARIANCE_MAX)
        return add_speckle_noise(img, variance)
    else:
        return img.copy()


# ============== 亮度/对比度调整函数 ==============
def adjust_brightness_contrast(img):
    """
    随机调整亮度和对比度
    避免全黑和过曝
    """
    # 随机亮度调整
    brightness = random.uniform(BRIGHTNESS_MIN, BRIGHTNESS_MAX)
    
    # 随机对比度调整
    contrast = random.uniform(CONTRAST_MIN, CONTRAST_MAX)
    
    # 应用调整
    # 公式：output = contrast * input + brightness
    adjusted = cv2.convertScaleAbs(img, alpha=contrast, beta=brightness)
    
    return adjusted


# ============== 灰度化函数 ==============
def apply_grayscale(img):
    """
    将彩色图像转换为灰度图
    支持多种灰度化模式
    """
    if GRAYSCALE_MODE == 'average':
        # 简单平均模式
        gray = np.mean(img, axis=2).astype(np.uint8)
    elif GRAYSCALE_MODE == 'luminosity':
        # 亮度模式（更接近人眼感知）
        # 公式：0.21*R + 0.72*G + 0.07*B
        gray = (0.07 * img[:, :, 0] + 0.72 * img[:, :, 1] + 0.21 * img[:, :, 2]).astype(np.uint8)
    else:
        # 标准模式（OpenCV默认，加权平均）
        # 公式：0.114*B + 0.587*G + 0.299*R
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    if GRAYSCALE_KEEP_3CH:
        # 保持3通道输出（兼容性更好）
        result = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    else:
        result = gray
    
    return result


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


def detect_label_format(txt_path):
    """
    检测标签格式：
    - 'obb': YOLO-OBB 格式（cls x1 y1 x2 y2 x3 y3 x4 y4）9个值
    - 'hbb': YOLO 水平框格式（cls x_center y_center width height）5个值
    - None: 无法识别或文件不存在
    """
    if not os.path.exists(txt_path):
        return None
    
    try:
        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 9:
                    return 'obb'
                elif len(parts) == 5:
                    return 'hbb'
        return None
    except Exception:
        return None


def transform_hbb_labels(txt_path, save_path, M_total, in_size, out_size):
    """
    使用仿射矩阵变换 YOLO 水平框标签（仅镜像/翻转，不支持旋转）
    txt 格式：cls x_center y_center width height（归一化）
    注意：水平框在旋转后会变成旋转框，这里仅处理镜像/翻转情况
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
        if len(parts) < 5:
            continue

        cls = parts[0]
        x_center_norm, y_center_norm, w_norm, h_norm = map(float, parts[1:5])

        # 转换为像素坐标
        x_center = x_center_norm * W
        y_center = y_center_norm * H
        w = w_norm * W
        h = h_norm * H

        # 计算四个角点
        x1, y1 = x_center - w/2, y_center - h/2
        x2, y2 = x_center + w/2, y_center - h/2
        x3, y3 = x_center + w/2, y_center + h/2
        x4, y4 = x_center - w/2, y_center + h/2

        pts_pix = np.array([[x1, y1], [x2, y2], [x3, y3], [x4, y4]], dtype=np.float32)

        # 应用仿射变换
        pts_trans_pix = rotate_points_affine(pts_pix, M_total)

        # 计算新的边界框
        x_min = np.min(pts_trans_pix[:, 0])
        x_max = np.max(pts_trans_pix[:, 0])
        y_min = np.min(pts_trans_pix[:, 1])
        y_max = np.max(pts_trans_pix[:, 1])

        # 转换回归一化坐标
        new_x_center = (x_min + x_max) / 2 / out_W
        new_y_center = (y_min + y_max) / 2 / out_H
        new_w = (x_max - x_min) / out_W
        new_h = (y_max - y_min) / out_H

        # 裁剪到 [0, 1] 范围
        new_x_center = float(np.clip(new_x_center, 0.0, 1.0))
        new_y_center = float(np.clip(new_y_center, 0.0, 1.0))
        new_w = float(np.clip(new_w, 0.0, 1.0))
        new_h = float(np.clip(new_h, 0.0, 1.0))

        new_line = f"{cls} {new_x_center:.8f} {new_y_center:.8f} {new_w:.8f} {new_h:.8f}"
        new_lines.append(new_line)

    with open(save_path, "w", encoding="utf-8") as f:
        f.write("\n".join(new_lines))


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
        
        # 类别ID替换（仅针对OBB标签）
        if ENABLE_LABEL_ID_REPLACE:
            try:
                cls_id = int(cls)
                if cls_id in LABEL_ID_REPLACE_MAP:
                    cls = str(LABEL_ID_REPLACE_MAP[cls_id])
            except ValueError:
                pass  # 如果类别不是数字，保持原样
        
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


def transform_labels_auto(txt_path, save_path, M_total, in_size, out_size, angle_enabled):
    """
    自动检测标签格式并应用相应的变换
    angle_enabled: 是否启用了角度旋转
    """
    label_format = detect_label_format(txt_path)
    
    if label_format == 'obb':
        # OBB 格式支持旋转和镜像
        rotate_obb_labels(txt_path, save_path, M_total, in_size, out_size)
    elif label_format == 'hbb':
        if angle_enabled:
            # 水平框不支持旋转，跳过
            return False
        else:
            # 水平框支持镜像/翻转
            transform_hbb_labels(txt_path, save_path, M_total, in_size, out_size)
    
    return True


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


def color_transform_prefix() -> str:
    """随机颜色变换前缀"""
    return "SC"  # 随机色彩


def noise_prefix(noise_type: str) -> str:
    """
    噪点前缀：
    - gaussian -> ZDG（噪点-高斯）
    - salt_pepper -> ZDJ（噪点-椒盐）
    """
    if noise_type == "gaussian":
        return "ZDG"
    elif noise_type == "salt_pepper":
        return "ZDJ"
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


def build_save_prefix(mode: str, angle: int, angle_enabled: bool, 
                      has_color_transform: bool = False, noise_type: str = None) -> str:
    """
    构建保存文件的前缀
    mode: 镜像/翻转模式
    angle: 旋转角度
    angle_enabled: 是否启用角度旋转
    has_color_transform: 是否进行随机颜色变换
    noise_type: 噪点类型（None表示无噪点）
    """
    parts = []
    
    # 镜像/翻转前缀
    fp = flip_prefix(mode)
    if fp:
        parts.append(fp)

    # 角度前缀
    if angle_enabled:
        ap = angle_prefix(angle, include_zero=False)
        if ap:
            parts.append(ap)
    
    # 随机颜色变换前缀
    if has_color_transform:
        parts.append(color_transform_prefix())
    
    # 噪点前缀
    if noise_type:
        np_prefix = noise_prefix(noise_type)
        if np_prefix:
            parts.append(np_prefix)

    return "_".join(parts) + ("_" if parts else "")


# 全局变量（用于多进程）
_global_config = {}

def _init_worker(config):
    """初始化工作进程"""
    global _global_config
    _global_config = config

def _process_single_image_worker(img_name):
    """
    多进程工作函数：处理单张图片
    """
    try:
        config = _global_config
        folder_path = config['folder_path']
        out_dir = config['out_dir']
        out_txt_dir = config['out_txt_dir']
        angles = config['angles']
        angle_rotation_enabled = config['angle_rotation_enabled']
        use_random_angle = config['use_random_angle']
        random_angle_count = config['random_angle_count']
        augmentation_img_set = config['augmentation_img_set']
        flip_modes = config['flip_modes']
        noise_types = config['noise_types']
        
        img_path = os.path.join(folder_path, img_name)
        name_no_ext = os.path.splitext(img_name)[0]
        ext = os.path.splitext(img_name)[1]
        txt_path = os.path.join(folder_path, name_no_ext + ".txt")
        
        # 读取图片
        img = imread_unicode(img_path)
        if img is None:
            return {'success': False, 'img_name': img_name, 'error': 'read_fail'}
        
        H0, W0 = img.shape[:2]
        
        # 确定角度列表
        if angle_rotation_enabled and len(angles) > 0:
            if use_random_angle:
                angle_list = random.sample(angles, min(random_angle_count, len(angles)))
            else:
                angle_list = angles.copy()
        else:
            angle_list = [None]
        
        results = []
        for rotation_angle in angle_list:
            should_apply_augmentation = img_name in augmentation_img_set
            
            # 决定增强
            apply_rotation = rotation_angle is not None
            apply_mirror = False
            mirror_mode = None
            
            if not apply_rotation and ENABLE_MIRROR_FLIP and len(flip_modes) > 0 and should_apply_augmentation:
                if random.choice([True, False]):
                    mirror_mode = random.choice([m for m in flip_modes if m != 'none'])
                    if mirror_mode:
                        apply_mirror = True
            
            apply_color = should_apply_augmentation and ENABLE_COLOR_TRANSFORM and (random.random() < COLOR_TRANSFORM_PROB)
            apply_brightness_contrast = should_apply_augmentation and ENABLE_BRIGHTNESS_CONTRAST and (random.random() < BRIGHTNESS_CONTRAST_PROB)
            apply_grayscale_aug = should_apply_augmentation and ENABLE_GRAYSCALE and (random.random() < GRAYSCALE_PROB)
            apply_gaussian = should_apply_augmentation and ENABLE_NOISE and 'gaussian' in noise_types and (random.random() < NOISE_PROB)
            apply_salt_pepper = should_apply_augmentation and ENABLE_NOISE and 'salt_pepper' in noise_types and (random.random() < NOISE_PROB)
            apply_poisson = should_apply_augmentation and ENABLE_NOISE and 'poisson' in noise_types and (random.random() < NOISE_PROB)
            apply_speckle = should_apply_augmentation and ENABLE_NOISE and 'speckle' in noise_types and (random.random() < NOISE_PROB)
            
            # 应用增强
            final_img = img.copy()
            M_transform = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
            out_size = (W0, H0)
            
            if apply_rotation:
                cw_angle, cv_angle = normalize_user_angle(rotation_angle)
                final_img, out_size, M_transform = rotate_image_with_border(final_img, cv_angle)
            elif apply_mirror:
                final_img, out_size, M_transform = apply_flip_image(final_img, mirror_mode)
            
            if apply_color:
                final_img = apply_random_color_transform(final_img)
            if apply_brightness_contrast:
                final_img = adjust_brightness_contrast(final_img)
            if apply_grayscale_aug:
                final_img = apply_grayscale(final_img)
            if apply_gaussian:
                final_img = apply_noise(final_img, 'gaussian')
            if apply_salt_pepper:
                final_img = apply_noise(final_img, 'salt_pepper')
            if apply_poisson:
                final_img = apply_noise(final_img, 'poisson')
            if apply_speckle:
                final_img = apply_noise(final_img, 'speckle')
            
            # 构建文件名
            if ENABLE_REPLACE_ORIGINAL:
                save_img_path = img_path
                save_txt_path = txt_path
                save_img_name = img_name
            else:
                if apply_rotation:
                    save_img_name = f"{name_no_ext}_{rotation_angle}du{ext}"
                    save_txt_name = f"{name_no_ext}_{rotation_angle}du.txt"
                else:
                    save_img_name = f"{name_no_ext}_ZQ{ext}"
                    save_txt_name = f"{name_no_ext}_ZQ.txt"
                save_img_path = os.path.join(out_dir, save_img_name)
                save_txt_path = os.path.join(out_txt_dir, save_txt_name)
            
            # 保存图片
            ok = imwrite_unicode(save_img_path, final_img, ext=ext)
            if not ok:
                results.append({'success': False, 'error': 'write_fail'})
                continue
            
            # 保存标签
            label_ok = False
            if os.path.exists(txt_path):
                try:
                    label_format = detect_label_format(txt_path)
                    if label_format == 'obb':
                        rotate_obb_labels(txt_path, save_txt_path, M_transform, (W0, H0), out_size)
                        label_ok = True
                    elif label_format == 'hbb' and not apply_rotation:
                        transform_hbb_labels(txt_path, save_txt_path, M_transform, (W0, H0), out_size)
                        label_ok = True
                except Exception:
                    pass
            
            # 收集增强信息用于日志
            aug_info = []
            if apply_rotation:
                aug_info.append(f"旋转{rotation_angle}度")
            if apply_mirror:
                aug_info.append(f"镜像:{mirror_mode}")
            if apply_color:
                aug_info.append("颜色")
            if apply_brightness_contrast:
                aug_info.append("亮度对比度")
            if apply_grayscale_aug:
                aug_info.append("灰度化")
            if apply_gaussian:
                aug_info.append("高斯噪点")
            if apply_salt_pepper:
                aug_info.append("椒盐噪点")
            if apply_poisson:
                aug_info.append("泊松噪点")
            if apply_speckle:
                aug_info.append("斑点噪点")
            
            results.append({
                'success': True,
                'img_name': save_img_name,
                'label_ok': label_ok,
                'angle': rotation_angle if apply_rotation else None,
                'enhancements': aug_info
            })
        
        return {'success': True, 'img_name': img_name, 'results': results}
        
    except Exception as e:
        return {'success': False, 'img_name': img_name, 'error': str(e)}


def process_folder_all(folder_path, queue_current=1, queue_total=1):
    _set_console_utf8()

    folder_path = os.path.normpath(os.fsdecode(os.fsencode(folder_path)))

    # 先获取文件列表用于检测标签格式
    try:
        files_for_detection = os.listdir(folder_path)
    except Exception as e:
        print_safe(f"无法列出目录：{folder_path}，原因：{e}")
        return

    # ============== 自动检测标签格式 ==============
    print_safe("正在检测标签格式...")
    txt_files = [f for f in files_for_detection if f.lower().endswith('.txt')]
    
    label_format_stats = {'obb': 0, 'hbb': 0, 'unknown': 0}
    sample_size = min(10, len(txt_files))  # 采样检测前10个标签文件
    
    for txt_file in txt_files[:sample_size]:
        txt_path = os.path.join(folder_path, txt_file)
        fmt = detect_label_format(txt_path)
        if fmt == 'obb':
            label_format_stats['obb'] += 1
        elif fmt == 'hbb':
            label_format_stats['hbb'] += 1
        else:
            label_format_stats['unknown'] += 1
    
    # 判断主要标签格式
    detected_format = None
    if label_format_stats['obb'] > 0 and label_format_stats['hbb'] == 0:
        detected_format = 'obb'
    elif label_format_stats['hbb'] > 0 and label_format_stats['obb'] == 0:
        detected_format = 'hbb'
    elif label_format_stats['obb'] > 0 and label_format_stats['hbb'] > 0:
        detected_format = 'mixed'
    
    # 根据检测结果决定是否启用旋转
    angle_rotation_enabled = ENABLE_ANGLE_ROTATION
    auto_disabled_rotation = False
    
    if detected_format == 'hbb':
        if ENABLE_ANGLE_ROTATION:
            angle_rotation_enabled = False
            auto_disabled_rotation = True
            print_safe("✓ 检测到 YOLO 水平框标签格式")
            print_safe("⚠️  自动禁用旋转功能（水平框不支持旋转）")
        else:
            print_safe("✓ 检测到 YOLO 水平框标签格式")
    elif detected_format == 'obb':
        print_safe("✓ 检测到 YOLO-OBB 旋转框标签格式")
        if ENABLE_ANGLE_ROTATION:
            print_safe("✓ 旋转功能已启用")
    elif detected_format == 'mixed':
        print_safe("⚠️  检测到混合标签格式（OBB + 水平框）")
        print_safe("   将根据每个文件的标签格式分别处理")
    else:
        print_safe("⚠️  未检测到标签文件或格式未知")
    
    print_safe("")
    # ============================================

    # 角度列表（使用检测后的开关）
    if angle_rotation_enabled:
        angles, mode_note = _build_angle_list()
    else:
        angles = []
        if auto_disabled_rotation:
            mode_note = "旋转已自动禁用（检测到水平框标签）"
        else:
            mode_note = "旋转总开关已关闭"
    
    flip_modes = get_flip_mode_list(MIRROR_FLIP_MODES)
    noise_types = get_noise_type_list(NOISE_TYPES)

    print_safe("模式：旋转 + 镜像/颠倒 + 随机颜色 + 噪点 批量增强（支持OBB和水平标签）")
    print_safe(mode_note)
    print_safe(f"已排除角度: {sorted({int(a)%360 for a in EXCLUDED_ANGLES})}")
    print_safe(f"BORDER_MODE: {BORDER_MODE}")
    print_safe(f"镜像/翻转模式: {flip_modes}")
    print_safe(f"随机颜色变换: {'开启' if ENABLE_COLOR_TRANSFORM else '关闭'}")
    print_safe(f"灰度化增强: {'开启' if ENABLE_GRAYSCALE else '关闭'}")
    print_safe(f"噪点增强: {'开启' if ENABLE_NOISE else '关闭'}")
    if ENABLE_NOISE:
        print_safe(f"噪点类型: {noise_types}")
    if angle_rotation_enabled:
        print_safe(f"随机角度模式: 每张图随机选择1个角度")
    print_safe("")

    # 当角度总开关关闭时，angles 应为空列表；我们改为逻辑上生成一个“虚拟角度循环”仅用于流程，但不进行旋转
    angle_iter = angles if angle_rotation_enabled else [None]

    # 根据检测到的标签格式和启用的功能动态命名输出文件夹
    # 原图替换模式不需要创建新文件夹
    if not ENABLE_REPLACE_ORIGINAL:
        folder_name_parts = []
        if angle_rotation_enabled:
            folder_name_parts.append("旋转")
        if detected_format == 'hbb':
            folder_name_parts.append("水平框")
        elif detected_format == 'obb':
            folder_name_parts.append("旋转框")
        if ENABLE_MIRROR_FLIP:
            folder_name_parts.append("镜像")
        if ENABLE_COLOR_TRANSFORM:
            folder_name_parts.append("颜色")
        if ENABLE_NOISE:
            folder_name_parts.append("噪点")
        
        if not folder_name_parts:
            folder_name_parts.append("数据增强")
        
        folder_name = "_".join(folder_name_parts) + "_增强"
        out_dir = os.path.join(folder_path, folder_name)
        os.makedirs(out_dir, exist_ok=True)

        # 创建TXT子文件夹存放标签
        out_txt_dir = os.path.join(out_dir, "TXT")
        os.makedirs(out_txt_dir, exist_ok=True)
    else:
        # 原图替换模式：不创建新文件夹
        out_dir = folder_path
        out_txt_dir = folder_path

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

    # 检查原图替换模式，确定实际使用的角度模式参数
    use_random_angle = USE_RANDOM_ANGLE
    random_angle_count = RANDOM_ANGLE_COUNT
    
    if ENABLE_REPLACE_ORIGINAL:
        print_safe("✓ 原图替换模式已启用")
        print_safe("⚠️  警告：将直接覆盖原文件！")
        
        # 检查旋转配置
        if angle_rotation_enabled:
            # 检查边界模式
            if BORDER_MODE == 'expand':
                print_safe("⚠️  原图替换模式 + expand边界模式会改变图像尺寸")
                print_safe("   建议使用 BORDER_MODE = 'constant' 或 'replicate'")
                print_safe("   继续使用 expand 模式（尺寸会变化，但标签位置正确）")
            
            # 检查角度模式
            if use_random_angle and random_angle_count > 1:
                print_safe("⚠️  原图替换模式只支持单角度模式（RANDOM_ANGLE_COUNT = 1）")
                print_safe(f"   当前配置: RANDOM_ANGLE_COUNT = {random_angle_count}")
                print_safe("   已自动调整为单角度模式")
                random_angle_count = 1
            elif not use_random_angle:
                print_safe("⚠️  原图替换模式不支持全角度模式（USE_RANDOM_ANGLE = False）")
                print_safe("   已自动切换为单角度模式")
                use_random_angle = True
                random_angle_count = 1
            
            print_safe(f"✓ 旋转功能已启用（单角度模式，边界模式: {BORDER_MODE}）")
    
    # 确定要处理的图片列表（简化逻辑）
    num_selected = max(1, int(total_imgs * AUGMENTATION_RATIO))
    if num_selected >= total_imgs:
        selected_img_files = img_files.copy()
    else:
        selected_img_files = random.sample(img_files, num_selected)
    
    if not angle_rotation_enabled:
        # 水平矩形（无旋转）：直接按 AUGMENTATION_RATIO 选择图片进行增强
        rotation_img_files = []
        augmentation_img_files = selected_img_files.copy()
    elif ENABLE_ROTATION_RATIO:
        # 旋转矩形 + 开启比例控制：选中的图片旋转+增强，其他不处理
        rotation_img_files = selected_img_files.copy()
        augmentation_img_files = selected_img_files.copy()
    else:
        # 旋转矩形 + 关闭比例控制：所有图片都旋转，选中的图片增强
        rotation_img_files = img_files.copy()
        augmentation_img_files = selected_img_files.copy()
        selected_img_files = img_files.copy()
    
    # 转换为集合以加速查找（O(1) 而不是 O(n)）
    augmentation_img_set = set(augmentation_img_files)
    
    # 计算总任务数
    if angle_rotation_enabled:
        if use_random_angle:
            # 单角度或多角度模式
            total_tasks = len(selected_img_files) * random_angle_count
        else:
            # 全角度模式
            total_tasks = len(selected_img_files) * len(angles)
    else:
        # 无旋转模式
        total_tasks = len(selected_img_files)
    
    print_safe(f"总图片数: {total_imgs}")
    print_safe(f"增强比例: {AUGMENTATION_RATIO * 100:.1f}%")
    
    if not angle_rotation_enabled:
        # 水平矩形模式
        print_safe(f"水平矩形模式: 只增强不旋转")
        print_safe(f"  → {len(augmentation_img_files)} 张：应用增强")
        print_safe(f"  → {total_imgs - len(augmentation_img_files)} 张：不处理")
    elif ENABLE_ROTATION_RATIO:
        # 旋转矩形 + 开启比例控制
        print_safe(f"旋转比例控制: 开启")
        print_safe(f"  → {len(selected_img_files)} 张：旋转+增强")
        print_safe(f"  → {total_imgs - len(selected_img_files)} 张：不处理")
    else:
        # 旋转矩形 + 关闭比例控制
        print_safe(f"旋转比例控制: 关闭")
        print_safe(f"  → {len(rotation_img_files)} 张：全部旋转")
        print_safe(f"  → {len(augmentation_img_files)} 张：应用增强")
        print_safe(f"  → {len(rotation_img_files) - len(augmentation_img_files)} 张：只旋转")
    
    if angle_rotation_enabled:
        print_safe(f"旋转角度范围: {angles[0]}-{angles[-1]}度（共{len(angles)}个可选角度）")
        if use_random_angle:
            print_safe(f"角度模式: 随机角度模式（每张图{random_angle_count}个角度）")
        else:
            print_safe(f"角度模式: 全角度模式（每张图{len(angles)}个角度）")
    
    if ENABLE_MIRROR_FLIP and not angle_rotation_enabled:
        print_safe(f"镜像模式: {flip_modes}")
    if ENABLE_COLOR_TRANSFORM:
        print_safe(f"随机颜色: 开启（{'完全随机' if COLOR_CRAZY_MODE else '微调模式'}）")
    if ENABLE_BRIGHTNESS_CONTRAST:
        print_safe(f"亮度对比度: 开启")
    if ENABLE_NOISE:
        print_safe(f"随机噪点: {noise_types}")
    if ENABLE_LABEL_ID_REPLACE:
        print_safe(f"类别ID替换: 开启（仅OBB标签）")
        print_safe(f"  映射: {LABEL_ID_REPLACE_MAP}")
    
    print_safe(f"预计生成: {total_tasks} 张增强图")
    if queue_total > 1:
        print_safe(f"当前队列: {queue_current}/{queue_total}")
    print_safe("")

    stats = {
        "ok": 0,
        "read_fail": 0,
        "process_fail": 0,
        "write_fail": 0,
        "label_processed": 0,
        "label_missing": 0,
        "label_skipped": 0  # 未参与的标签（未被选中的图片）
    }

    start_time = time.time()
    completed = 0
    
    # 创建日志列表
    augmentation_log = []
    
    # 多进程处理
    if ENABLE_MULTIPROCESSING and len(selected_img_files) > 1:
        num_processes = MAX_PROCESSES if MAX_PROCESSES > 0 else cpu_count()
        print_safe(f"多进程模式: 开启（{num_processes}个进程）")
        print_safe("")
        
        # 准备配置
        worker_config = {
            'folder_path': folder_path,
            'out_dir': out_dir,
            'out_txt_dir': out_txt_dir,
            'angles': angles,
            'angle_rotation_enabled': angle_rotation_enabled,
            'use_random_angle': use_random_angle,
            'random_angle_count': random_angle_count,
            'augmentation_img_set': augmentation_img_set,
            'flip_modes': flip_modes,
            'noise_types': noise_types
        }
        
        # 使用多进程池
        with Pool(processes=num_processes, initializer=_init_worker, initargs=(worker_config,)) as pool:
            for result in pool.imap_unordered(_process_single_image_worker, selected_img_files):
                if result['success']:
                    if 'results' in result:
                        for r in result['results']:
                            if r['success']:
                                stats['ok'] += 1
                                if r['label_ok']:
                                    stats['label_processed'] += 1
                                else:
                                    stats['label_missing'] += 1
                                
                                # 收集日志信息
                                log_entry = {
                                    'original': result['img_name'],
                                    'output': r['img_name'],
                                    'angle': r.get('angle'),
                                    'enhancements': r.get('enhancements', [])
                                }
                                augmentation_log.append(log_entry)
                            else:
                                stats['write_fail'] += 1
                else:
                    if result.get('error') == 'read_fail':
                        stats['read_fail'] += 1
                    else:
                        stats['process_fail'] += 1
                
                completed += 1
                progress_line = render_progress_bar(completed, len(selected_img_files), start_time)
                print_progress_line(progress_line + f" | 完成: {result['img_name']}")
        
        end_progress_line()
    else:
        # 单进程处理
        if not ENABLE_MULTIPROCESSING:
            print_safe("多进程模式: 关闭（单进程处理）")
        else:
            print_safe("单进程模式: 图片数量太少")
        print_safe("")
        
        for idx, img_name in enumerate(selected_img_files, 1):
            img_path = os.path.join(folder_path, img_name)
            name_no_ext = os.path.splitext(img_name)[0]
            ext = os.path.splitext(img_name)[1]
            txt_path = os.path.join(folder_path, name_no_ext + ".txt")
            
            # 读取图片（只读一次）
            img = imread_unicode(img_path)
            if img is None:
                stats["read_fail"] += 1
                # 根据角度模式跳过相应数量的任务
                if angle_rotation_enabled:
                    skip_count = random_angle_count if use_random_angle else len(angles)
                else:
                    skip_count = 1
                completed += skip_count
                progress_line = render_progress_bar(completed, total_tasks, start_time)
                print_progress_line(progress_line + f" | 失败: 读图 -> {img_name}")
                continue
            
            H0, W0 = img.shape[:2]
            
            # 确定要生成的角度列表
            if angle_rotation_enabled and len(angles) > 0:
                if use_random_angle:
                    # 随机角度模式：随机选择N个不同角度
                    angle_list = random.sample(angles, min(random_angle_count, len(angles)))
                else:
                    # 全角度模式：使用所有角度
                    angle_list = angles.copy()
            else:
                # 无旋转模式：使用None表示不旋转
                angle_list = [None]
            
            # 对每个角度生成一张增强图
            for rotation_angle in angle_list:
                progress_line = render_progress_bar(completed, total_tasks, start_time)
                print_progress_line(progress_line + f" | 正在处理: {img_name}")
                
                try:
                    # ============ 步骤1：判断是否应用增强 ============
                    
                    # 判断当前图片是否在增强列表中（使用集合查找，O(1)时间复杂度）
                    should_apply_augmentation = img_name in augmentation_img_set
                    
                    # ============ 步骤2：随机决定应用哪些增强 ============
                    
                    # 2.1 几何变换（旋转 或 镜像，二选一）
                    apply_rotation = False
                    apply_mirror = False
                    mirror_mode = None
                    M_transform = np.array([[1, 0, 0], [0, 1, 0]], dtype=np.float32)
                    out_size = (W0, H0)
                    
                    if rotation_angle is not None:
                        # 旋转模式：使用指定角度
                        apply_rotation = True
                    elif ENABLE_MIRROR_FLIP and len(flip_modes) > 0 and should_apply_augmentation:
                        # 镜像模式：随机决定是否镜像（仅当允许增强时）
                        if random.choice([True, False]):
                            mirror_mode = random.choice([m for m in flip_modes if m != 'none'])
                            if mirror_mode:
                                apply_mirror = True
                    
                    # 2.2 颜色变换（按概率应用，仅当允许增强时）
                    apply_color = should_apply_augmentation and ENABLE_COLOR_TRANSFORM and (random.random() < COLOR_TRANSFORM_PROB)
                    
                    # 2.3 亮度/对比度（按概率应用，仅当允许增强时）
                    apply_brightness_contrast = should_apply_augmentation and ENABLE_BRIGHTNESS_CONTRAST and (random.random() < BRIGHTNESS_CONTRAST_PROB)
                    
                    # 2.4 灰度化（按概率应用，仅当允许增强时）
                    apply_grayscale_aug = should_apply_augmentation and ENABLE_GRAYSCALE and (random.random() < GRAYSCALE_PROB)
                    
                    # 2.5 噪点（按概率应用，仅当允许增强时）
                    apply_gaussian = should_apply_augmentation and ENABLE_NOISE and 'gaussian' in noise_types and (random.random() < NOISE_PROB)
                    apply_salt_pepper = should_apply_augmentation and ENABLE_NOISE and 'salt_pepper' in noise_types and (random.random() < NOISE_PROB)
                    apply_poisson = should_apply_augmentation and ENABLE_NOISE and 'poisson' in noise_types and (random.random() < NOISE_PROB)
                    apply_speckle = should_apply_augmentation and ENABLE_NOISE and 'speckle' in noise_types and (random.random() < NOISE_PROB)
                    
                    # 2.6 确保至少应用一种变换（旋转或增强）
                    # 如果允许增强，确保至少应用一种增强
                    if should_apply_augmentation:
                        has_any_enhancement = (apply_rotation or apply_mirror or apply_color or 
                                              apply_brightness_contrast or apply_grayscale_aug or apply_gaussian or 
                                              apply_salt_pepper or apply_poisson or apply_speckle)
                        
                        if not has_any_enhancement:
                            # 如果没有任何增强，强制应用一种
                            available_enhancements = []
                            if ENABLE_COLOR_TRANSFORM:
                                available_enhancements.append('color')
                            if ENABLE_BRIGHTNESS_CONTRAST:
                                available_enhancements.append('brightness')
                            if ENABLE_GRAYSCALE:
                                available_enhancements.append('grayscale')
                            if ENABLE_NOISE and noise_types:
                                available_enhancements.extend(noise_types)
                            if ENABLE_MIRROR_FLIP and len(flip_modes) > 0:
                                available_enhancements.append('mirror')
                            
                            if available_enhancements:
                                forced_enhancement = random.choice(available_enhancements)
                                if forced_enhancement == 'color':
                                    apply_color = True
                                elif forced_enhancement == 'brightness':
                                    apply_brightness_contrast = True
                                elif forced_enhancement == 'grayscale':
                                    apply_grayscale_aug = True
                                elif forced_enhancement == 'mirror':
                                    mirror_mode = random.choice([m for m in flip_modes if m != 'none'])
                                    if mirror_mode:
                                        apply_mirror = True
                                elif forced_enhancement == 'gaussian':
                                    apply_gaussian = True
                                elif forced_enhancement == 'salt_pepper':
                                    apply_salt_pepper = True
                                elif forced_enhancement == 'poisson':
                                    apply_poisson = True
                                elif forced_enhancement == 'speckle':
                                    apply_speckle = True
                    
                    # ============ 步骤2：应用增强 ============
                    
                    final_img = img.copy()
                    
                    # 2.1 应用几何变换
                    if apply_rotation:
                        # 旋转
                        cw_angle, cv_angle = normalize_user_angle(rotation_angle)
                        final_img, out_size, M_rot = rotate_image_with_border(final_img, cv_angle)
                        M_transform = M_rot
                    elif apply_mirror:
                        # 镜像
                        final_img, out_size, M_flip = apply_flip_image(final_img, mirror_mode)
                        M_transform = M_flip
                    
                    # 2.2 应用颜色变换
                    if apply_color:
                        final_img = apply_random_color_transform(final_img)
                    
                    # 2.3 应用亮度/对比度
                    if apply_brightness_contrast:
                        final_img = adjust_brightness_contrast(final_img)
                    
                    # 2.4 应用灰度化
                    if apply_grayscale_aug:
                        final_img = apply_grayscale(final_img)
                    
                    # 2.5 应用噪点
                    if apply_gaussian:
                        final_img = apply_noise(final_img, 'gaussian')
                    if apply_salt_pepper:
                        final_img = apply_noise(final_img, 'salt_pepper')
                    if apply_poisson:
                        final_img = apply_noise(final_img, 'poisson')
                    if apply_speckle:
                        final_img = apply_noise(final_img, 'speckle')
                    
                    # ============ 步骤3：构建文件名 ============
                    
                    if ENABLE_REPLACE_ORIGINAL:
                        # 原图替换模式：保持原文件名
                        save_img_name = img_name
                        save_img_path = img_path
                        save_txt_name = name_no_ext + ".txt"
                        save_txt_path = txt_path
                    else:
                        # 生成新文件模式
                        if apply_rotation:
                            # 有旋转：文件名_角度.ext（不管是否增强，统一命名）
                            save_img_name = f"{name_no_ext}_{rotation_angle}du{ext}"
                            save_txt_name = f"{name_no_ext}_{rotation_angle}du.txt"
                        else:
                            # 无旋转：文件名_ZQ.ext
                            save_img_name = f"{name_no_ext}_ZQ{ext}"
                            save_txt_name = f"{name_no_ext}_ZQ.txt"
                        
                        save_img_path = os.path.join(out_dir, save_img_name)
                        save_txt_path = os.path.join(out_txt_dir, save_txt_name)
                    
                    # ============ 步骤4：保存图片 ============
                    
                    ok = imwrite_unicode(save_img_path, final_img, ext=ext)
                    if not ok:
                        stats["write_fail"] += 1
                        completed += 1
                        print_progress_line(progress_line + f" | 失败: 写入 -> {save_img_name}")
                        continue
                    
                    # ============ 步骤5：保存标签 ============
                    
                    if os.path.exists(txt_path):
                        try:
                            # 检测标签格式
                            label_format = detect_label_format(txt_path)
                            
                            if label_format == 'obb':
                                # OBB格式
                                rotate_obb_labels(txt_path, save_txt_path, M_transform, (W0, H0), out_size)
                                stats["label_processed"] += 1
                            elif label_format == 'hbb':
                                # 水平框格式
                                if not apply_rotation:
                                    transform_hbb_labels(txt_path, save_txt_path, M_transform, (W0, H0), out_size)
                                    stats["label_processed"] += 1
                                else:
                                    stats["label_missing"] += 1
                            else:
                                stats["label_missing"] += 1
                        except Exception as e:
                            stats["label_missing"] += 1
                    else:
                        stats["label_missing"] += 1
                    
                    stats["ok"] += 1
                    completed += 1
                    
                    # 显示应用的增强
                    aug_info = []
                    if apply_rotation:
                        aug_info.append(f"旋转{rotation_angle}度")
                    if apply_mirror:
                        aug_info.append(f"镜像:{mirror_mode}")
                    if apply_color:
                        aug_info.append("颜色")
                    if apply_brightness_contrast:
                        aug_info.append("亮度对比度")
                    if apply_grayscale_aug:
                        aug_info.append("灰度化")
                    if apply_gaussian:
                        aug_info.append("高斯噪点")
                    if apply_salt_pepper:
                        aug_info.append("椒盐噪点")
                    if apply_poisson:
                        aug_info.append("泊松噪点")
                    if apply_speckle:
                        aug_info.append("斑点噪点")
                    
                    # 显示信息
                    if apply_rotation and not should_apply_augmentation:
                        display_info = f" [只旋转{rotation_angle}度]"
                    elif aug_info:
                        display_info = f" [{'+'.join(aug_info)}]"
                    else:
                        display_info = " [无变换]"
                    
                    progress_line = render_progress_bar(completed, total_tasks, start_time)
                    print_progress_line(progress_line + f" | 完成: {save_img_name}{display_info}")
                    
                    # 记录到日志
                    log_entry = {
                        'original': img_name,
                        'output': save_img_name,
                        'angle': rotation_angle if apply_rotation else None,
                        'enhancements': aug_info
                    }
                    augmentation_log.append(log_entry)
                    
                except Exception as e:
                    stats["process_fail"] += 1
                    completed += 1
                    print_progress_line(progress_line + f" | 失败: 处理异常 -> {img_name}: {e}")
                    continue
        
        end_progress_line()

    # 输出统计
    print_safe("")
    print_safe("=" * 60)
    if ENABLE_REPLACE_ORIGINAL:
        print_safe(f"原图替换完成！")
        print_safe(f"已覆盖 {stats['ok']} 张原图")
    else:
        print_safe(f"处理完成，结果保存在：{out_dir}")
        print_safe(f"其中 TXT 标签统一保存在：{out_txt_dir}")
    
    print_safe("")
    print_safe("【图片统计】")
    print_safe(f"  总图片数: {total_imgs}")
    print_safe(f"  已增强: {stats['ok']}")
    print_safe(f"  未处理: {total_imgs - total_tasks}")
    if stats['read_fail'] > 0:
        print_safe(f"  读取失败: {stats['read_fail']}")
    if stats['process_fail'] > 0:
        print_safe(f"  处理失败: {stats['process_fail']}")
    if stats['write_fail'] > 0:
        print_safe(f"  写入失败: {stats['write_fail']}")
    
    print_safe("")
    print_safe("【标签统计】")
    print_safe(f"  已处理: {stats['label_processed']}")
    print_safe(f"  缺失: {stats['label_missing']}")
    print_safe(f"  未参与: {total_imgs - total_tasks}")
    
    elapsed = time.time() - start_time
    print_safe("")
    print_safe(f"总用时: {format_timedelta(elapsed)}")
    print_safe("=" * 60)
    
    # 保存增强日志（保存到脚本所在目录）
    if augmentation_log:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        folder_name = os.path.basename(folder_path)
        log_filename = f"增强日志_{folder_name}_{time.strftime('%Y%m%d_%H%M%S')}.log"
        log_path = os.path.join(script_dir, log_filename)
        
        try:
            with open(log_path, "w", encoding="utf-8") as log_file:
                log_file.write("=" * 80 + "\n")
                if ENABLE_REPLACE_ORIGINAL:
                    log_file.write("数据增强日志 - 原图替换模式\n")
                else:
                    log_file.write("数据增强日志\n")
                log_file.write("=" * 80 + "\n")
                log_file.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"模式: {'原图替换模式' if ENABLE_REPLACE_ORIGINAL else '生成新文件模式'}\n")
                log_file.write(f"总图片数: {total_imgs}\n")
                log_file.write(f"选中图片: {len(selected_img_files)} 张\n")
                if ENABLE_REPLACE_ORIGINAL:
                    log_file.write(f"已替换原图: {stats['ok']} 张\n")
                    log_file.write(f"未替换原图: {total_imgs - len(selected_img_files)} 张\n")
                else:
                    log_file.write(f"生成增强图: {stats['ok']} 张\n")
                    log_file.write(f"未处理原图: {total_imgs - len(selected_img_files)} 张\n")
                log_file.write(f"增强比例: {AUGMENTATION_RATIO * 100:.1f}%\n")
                log_file.write("=" * 80 + "\n\n")
                
                # 按原图分组
                if ENABLE_REPLACE_ORIGINAL:
                    log_file.write("已替换的原图列表：\n")
                else:
                    log_file.write("详细增强记录：\n")
                log_file.write("-" * 80 + "\n")
                
                current_original = None
                for entry in augmentation_log:
                    if entry['original'] != current_original:
                        if current_original is not None:
                            log_file.write("\n")
                        current_original = entry['original']
                        if ENABLE_REPLACE_ORIGINAL:
                            log_file.write(f"\n✓ 已替换: {entry['original']}\n")
                        else:
                            log_file.write(f"\n原图: {entry['original']}\n")
                    
                    enhancements_str = " + ".join(entry['enhancements']) if entry['enhancements'] else "无增强"
                    
                    if ENABLE_REPLACE_ORIGINAL:
                        if entry['angle'] is not None:
                            log_file.write(f"   旋转角度: {entry['angle']}度\n")
                        log_file.write(f"   应用增强: {enhancements_str}\n")
                    else:
                        log_file.write(f"  → {entry['output']}\n")
                        if entry['angle'] is not None:
                            log_file.write(f"     旋转角度: {entry['angle']}度\n")
                        log_file.write(f"     增强: {enhancements_str}\n")
                
                # 未处理的原图列表
                if not ENABLE_REPLACE_ORIGINAL:
                    unprocessed_imgs = [f for f in img_files if f not in selected_img_files]
                    if unprocessed_imgs:
                        log_file.write("\n\n" + "=" * 80 + "\n")
                        log_file.write(f"未处理的原图列表（共 {len(unprocessed_imgs)} 张）：\n")
                        log_file.write("-" * 80 + "\n")
                        for img in sorted(unprocessed_imgs):
                            log_file.write(f"  • {img}\n")
                else:
                    unprocessed_imgs = [f for f in img_files if f not in selected_img_files]
                    if unprocessed_imgs:
                        log_file.write("\n\n" + "=" * 80 + "\n")
                        log_file.write(f"未替换的原图列表（共 {len(unprocessed_imgs)} 张）：\n")
                        log_file.write("-" * 80 + "\n")
                        for img in sorted(unprocessed_imgs):
                            log_file.write(f"  • {img}\n")
                
                log_file.write("\n" + "=" * 80 + "\n")
                log_file.write("增强类型统计：\n")
                log_file.write("-" * 80 + "\n")
                
                # 统计各种增强的使用次数（排除旋转角度）
                enhancement_stats = {}
                for entry in augmentation_log:
                    for enh in entry['enhancements']:
                        # 跳过旋转角度（因为会在下面单独统计）
                        if not enh.startswith('旋转') or not enh.endswith('度'):
                            enhancement_stats[enh] = enhancement_stats.get(enh, 0) + 1
                
                for enh, count in sorted(enhancement_stats.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / len(augmentation_log)) * 100
                    log_file.write(f"  {enh}: {count} 次 ({percentage:.1f}%)\n")
                
                # 统计旋转角度的使用次数
                angle_stats = {}
                for entry in augmentation_log:
                    if entry['angle'] is not None:
                        angle = entry['angle']
                        angle_stats[angle] = angle_stats.get(angle, 0) + 1
                
                if angle_stats:
                    log_file.write("\n" + "-" * 80 + "\n")
                    log_file.write("旋转角度统计：\n")
                    log_file.write("-" * 80 + "\n")
                    
                    total_rotations = sum(angle_stats.values())
                    for angle, count in sorted(angle_stats.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / total_rotations) * 100
                        log_file.write(f"  {angle}度: {count} 次 ({percentage:.1f}%)\n")
                    
                    log_file.write(f"\n  总旋转次数: {total_rotations}\n")
                    log_file.write(f"  使用的不同角度数: {len(angle_stats)}\n")
                
                log_file.write("\n" + "=" * 80 + "\n")
            
            print_safe(f"\n✓ 增强日志已保存: {log_path}")
        except Exception as e:
            print_safe(f"\n⚠️  保存日志失败: {e}")


if __name__ == "__main__":
    _set_console_utf8()

    if len(sys.argv) < 2:
        print_safe("请将包含图片和TXT的文件夹拖拽到脚本上运行。")
        print_safe("支持同时拖拽多个文件夹进行批量处理。")
        input("按回车退出...")
        sys.exit()

    # 获取所有拖入的文件夹
    folders = []
    for arg in sys.argv[1:]:
        raw_folder = arg.strip('"').strip("'")
        folder = os.path.normpath(os.fsdecode(os.fsencode(raw_folder)))
        if os.path.isdir(folder):
            folders.append(folder)
        else:
            print_safe(f"跳过无效路径: {folder}")
    
    if not folders:
        print_safe("没有有效的文件夹，请拖入文件夹。")
        input("按回车退出...")
        sys.exit()
    
    # 显示队列
    print_safe("")
    print_safe("=" * 60)
    print_safe(f"检测到 {len(folders)} 个文件夹待处理：")
    print_safe("-" * 60)
    for i, f in enumerate(folders, 1):
        print_safe(f"  [{i}] {os.path.basename(f)}")
    print_safe("=" * 60)
    print_safe("")

    # 根据模式选择处理方式
    if ENABLE_REPLACE_ORIGINAL:
        # 原图替换模式
        print_safe("⚠️  警告：原图替换模式将直接覆盖原文件！")
        print_safe("⚠️  建议先备份数据！")
        print_safe("")
        confirm = input("确认继续？(输入 yes 继续): ").strip().lower()
        if confirm != "yes":
            print_safe("已取消操作。")
            input("按回车退出...")
            sys.exit()
    
    # 依次处理每个文件夹
    total_folders = len(folders)
    for idx, folder in enumerate(folders, 1):
        print_safe("")
        print_safe("=" * 60)
        print_safe(f"【队列 {idx}/{total_folders}】正在处理: {os.path.basename(folder)}")
        print_safe("=" * 60)
        process_folder_all(folder, queue_current=idx, queue_total=total_folders)
        print_safe("")
    
    print_safe("")
    print_safe("=" * 60)
    print_safe(f"全部完成！共处理 {total_folders} 个文件夹")
    print_safe("=" * 60)
    input("\n按回车退出。")