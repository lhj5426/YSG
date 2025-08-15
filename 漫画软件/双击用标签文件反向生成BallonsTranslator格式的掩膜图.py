# -*- coding: utf-8 -*-
"""
将与图片同目录的 YOLO 标注（txt）反向绘制为掩膜图（黑底+白色实心矩形）。
- 把本脚本放在图片和 yolo txt 同一目录（例如 ...\labels\ 下），直接双击运行。
- 只有当同名 .txt 中存在至少一个有效框时，才会生成掩膜 PNG。
- 若 .txt 不存在：跳过；若 .txt 为空或无有效框：跳过不生成。

需要：Python 3.7+，Pillow：pip install pillow
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

# 输出目录名（按你的命名要求）
OUT_DIR_NAME = "MAKS"
# 支持的图片扩展名
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

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
    若列数<5则抛出异常；列数>5 会忽略多余列（不支持多边形涂抹）。
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

def draw_mask(img_path: str, txt_path: str, out_path: str) -> str:
    """
    根据图片尺寸与 txt 标注生成掩膜 PNG（白色实心矩形）。
    返回状态：'ok' 正常生成；'empty' 空标注/无有效框；'error' 错误。
    """
    try:
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception as e:
        print(f"[跳过] 打开图片失败：{os.path.basename(img_path)} -> {e}")
        return "error"

    lines = load_txt_lines(txt_path)

    # 创建黑底掩膜
    mask = Image.new("L", (w, h), 0)
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
        # 白色实心矩形
        draw.rectangle([left, top, right, bottom], fill=255)
        any_box = True

    if not any_box:
        print(f"[跳过] {os.path.basename(txt_path)} 空标注/无有效框，不生成掩膜")
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
    print("绘制模式：白色填充（实心）")
    print("-" * 50)

    for stem, img_path in sorted(image_index.items()):
        total += 1
        txt_path = os.path.join(script_dir, stem + ".txt")
        if not os.path.exists(txt_path):
            skipped_no_txt += 1
            continue

        out_path = os.path.join(out_dir, stem + ".png")
        status = draw_mask(img_path, txt_path, out_path)
        if status == "ok":
            generated += 1
        elif status == "empty":
            skipped_empty += 1
        else:
            failed += 1

    print("-" * 50)
    print(f"统计：发现图片 {total} 张；生成掩膜 {generated} 张；缺少同名 txt 跳过 {skipped_no_txt} 张；空标注跳过 {skipped_empty} 张；失败 {failed} 张。")

if __name__ == "__main__":
    main()
    if os.name == "nt":
        try:
            input("按回车键退出...")
        except Exception:
            pass