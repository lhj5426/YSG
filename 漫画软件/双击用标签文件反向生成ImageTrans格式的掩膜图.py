# -*- coding: utf-8 -*-
"""
从与图片同目录的 YOLO 检测标注（txt，格式：class cx cy w h）生成彩色掩膜 PNG：
- 背景完全透明
- 标注矩形区域用指定颜色实心填充（默认 #ABE338）
- 空标注或无有效框：跳过不生成
- 仅对“有同名 .txt”的图片生成

用法：
- 将本脚本放在图片与 txt 的同一目录，双击运行。
- 输出到当前目录的 MAKS 文件夹。

依赖：
- Python 3.7+，Pillow：pip install pillow
"""

import os
import sys
from typing import Dict, List, Tuple

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("缺少 Pillow 库，请先安装：pip install pillow")
    if os.name == "nt":
        input("按回车键退出...")
    sys.exit(1)

# ========== 配置 ==========
OUT_DIR_NAME = "MAKS"          # 输出文件夹名（按你的命名）
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

COLOR_HEX = "#ABE338"          # 填充颜色（#RRGGBB 或 #RRGGBBAA）
FILL_ALPHA = 255               # 透明度 0-255（当 COLOR_HEX 为 #RRGGBB 时生效；#RRGGBBAA 将优先生效）
# =========================

def parse_hex_color(s: str, alpha_default: int = 255) -> Tuple[int, int, int, int]:
    """
    解析 #RRGGBB 或 #RRGGBBAA 为 (R,G,B,A)。
    若为 #RRGGBB，则使用 alpha_default 作为透明度。
    """
    s = s.strip()
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

def build_image_index(image_dir: str) -> Dict[str, str]:
    """索引当前目录中的图片：stem -> 图片完整路径"""
    index: Dict[str, str] = {}
    for name in os.listdir(image_dir):
        stem, ext = os.path.splitext(name)
        if ext.lower() in IMG_EXTS:
            index.setdefault(stem, os.path.join(image_dir, name))
    return index

def load_txt_lines(txt_path: str) -> List[str]:
    """读取 txt 文件，忽略空行和以 # 开头的注释行。"""
    lines: List[str] = []
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with open(txt_path, "r", encoding=enc, errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    lines.append(s)
            return lines
        except Exception:
            continue
    try:
        with open(txt_path, "r") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    lines.append(s)
    except Exception:
        pass
    return lines

def parse_yolo_line(line: str) -> Tuple[float, float, float, float]:
    """
    解析 YOLO 检测标注一行（class cx cy w h），返回 (cx, cy, w, h) 归一化浮点数。
    若列数<5则抛出异常；列数>5 会忽略多余列（不支持分割多边形）。
    """
    parts = line.strip().split()
    if len(parts) < 5:
        raise ValueError("标注列数不足 5")
    cx = float(parts[1])
    cy = float(parts[2])
    bw = float(parts[3])
    bh = float(parts[4])
    return cx, cy, bw, bh

def yolo_to_pixel_box(cx: float, cy: float, bw: float, bh: float, w: int, h: int) -> Tuple[int, int, int, int]:
    """将归一化 YOLO 框转为像素坐标 (left, top, right, bottom)，并做边界裁剪。"""
    x_center = cx * w
    y_center = cy * h
    box_w = bw * w
    box_h = bh * h

    left = int(round(x_center - box_w / 2))
    top = int(round(y_center - box_h / 2))
    right = int(round(x_center + box_w / 2))
    bottom = int(round(y_center + box_h / 2))

    # 边界裁剪
    left = max(0, min(left, w - 1))
    right = max(0, min(right, w - 1))
    top = max(0, min(top, h - 1))
    bottom = max(0, min(bottom, h - 1))

    if right < left:
        left, right = right, left
    if bottom < top:
        top, bottom = bottom, top

    return left, top, right, bottom

def draw_mask(img_path: str, txt_path: str, out_path: str, fill_rgba: Tuple[int, int, int, int]) -> str:
    """
    根据图片尺寸与 txt 标注生成彩色掩膜 PNG（透明背景 + 指定颜色实心矩形）。
    返回状态：'ok' 正常生成；'empty' 空标注/无有效框；'error' 错误。
    """
    try:
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception as e:
        print(f"[跳过] 打开图片失败：{os.path.basename(img_path)} -> {e}")
        return "error"

    lines = load_txt_lines(txt_path)

    # 透明背景（RGBA，A=0）
    mask = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)

    any_box = False
    for ln in lines:
        try:
            cx, cy, bw, bh = parse_yolo_line(ln)
        except Exception:
            continue
        if bw <= 0 or bh <= 0:
            continue

        left, top, right, bottom = yolo_to_pixel_box(cx, cy, bw, bh, w, h)
        draw.rectangle([left, top, right, bottom], fill=fill_rgba)
        any_box = True

    if not any_box:
        print(f"[跳过] {os.path.basename(txt_path)} 空标注/无有效框，不生成")
        return "empty"

    try:
        mask.save(out_path, format="PNG")
        print(f"[完成] {os.path.basename(out_path)}")
        return "ok"
    except Exception as e:
        print(f"[失败] 保存掩膜失败：{os.path.basename(out_path)} -> {e}")
        return "error"

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, OUT_DIR_NAME)
    os.makedirs(out_dir, exist_ok=True)

    try:
        fill_rgba = parse_hex_color(COLOR_HEX, FILL_ALPHA)
    except Exception as e:
        print(f"[错误] 颜色解析失败：{COLOR_HEX} -> {e}")
        if os.name == "nt":
            input("按回车键退出...")
        sys.exit(1)

    image_index = build_image_index(script_dir)
    if not image_index:
        print("[警告] 当前目录未发现图片文件。支持扩展名：", ", ".join(sorted(IMG_EXTS)))

    total = 0
    generated = 0
    skipped_no_txt = 0
    skipped_empty = 0
    failed = 0

    print("图片目录：", script_dir)
    print("输出目录：", out_dir)
    print(f"填充颜色：{COLOR_HEX}，透明度：{fill_rgba[3]}")
    print("-" * 50)

    for stem, img_path in sorted(image_index.items()):
        total += 1
        txt_path = os.path.join(script_dir, stem + ".txt")
        if not os.path.exists(txt_path):
            skipped_no_txt += 1
            continue

        out_path = os.path.join(out_dir, stem + ".png")
        status = draw_mask(img_path, txt_path, out_path, fill_rgba)
        if status == "ok":
            generated += 1
        elif status == "empty":
            skipped_empty += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"统计：发现图片 {total} 张；生成 {generated} 张；缺少同名 txt 跳过 {skipped_no_txt} 张；空标注跳过 {skipped_empty} 张；失败 {failed} 张。")

if __name__ == "__main__":
    main()
    if os.name == "nt":
        try:
            input("按回车键退出...")
        except Exception:
            pass