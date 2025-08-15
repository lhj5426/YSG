# -*- coding: utf-8 -*-
"""
将 YOLO 标注（txt）反向绘制为掩膜图（黑底白框/白块）。
用法（Windows）：
1) 把本脚本放到“图片所在目录”（与你的图片同一层）下。
2) 将装有 YOLO TXT 的文件夹（或单个 TXT 文件）拖拽到本脚本图标上。
3) 生成的 PNG 掩膜会保存在脚本所在目录下的 MAKS 文件夹中。

若想只画白色边框，把 DRAW_OUTLINE 改为 True；LINE_WIDTH 可调边框粗细。
"""

import sys
import os
from typing import Dict, List, Tuple

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("缺少 Pillow 库，请先安装：pip install pillow")
    sys.exit(1)

# 配置：是否只画白色边框；边框像素宽度
DRAW_OUTLINE = False   # False = 白色填充矩形（推荐用于掩膜）
LINE_WIDTH = 2

# 支持的图片扩展名（小写）
IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}

def build_image_index(image_dir: str) -> Dict[str, str]:
    """索引图片：stem -> 图片完整路径"""
    index = {}
    try:
        for name in os.listdir(image_dir):
            stem, ext = os.path.splitext(name)
            if ext.lower() in IMG_EXTS:
                index[stem] = os.path.join(image_dir, name)
    except FileNotFoundError:
        pass
    return index

def parse_yolo_line(line: str) -> Tuple[float, float, float, float]:
    """
    解析 YOLO 一行（class cx cy w h），返回 (cx, cy, w, h) 归一化浮点数。
    若非标准格式，抛出 ValueError。
    """
    parts = line.strip().split()
    if len(parts) < 5:
        raise ValueError("标注列数不足 5")
    # parts[0] 是 class id，这里不区分类别
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

    # 处理可能出现的 left>right / top>bottom
    if right < left:
        left, right = right, left
    if bottom < top:
        top, bottom = bottom, top

    return left, top, right, bottom

def load_txt_lines(txt_path: str) -> List[str]:
    """读取 txt 文件，忽略空行和注释。"""
    lines: List[str] = []
    # 尝试 utf-8-sig，可兼容 BOM；失败则退回到默认打开
    tried = False
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            with open(txt_path, "r", encoding=enc, errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s:
                        continue
                    if s.startswith("#"):
                        continue
                    lines.append(s)
            tried = True
            break
        except Exception:
            continue
    if not tried:
        with open(txt_path, "r") as f:
            for line in f:
                s = line.strip()
                if s and not s.startswith("#"):
                    lines.append(s)
    return lines

def process_single_txt(txt_path: str, image_index: Dict[str, str], out_dir: str) -> bool:
    """处理一个 txt，生成对应掩膜。返回是否成功。"""
    stem = os.path.splitext(os.path.basename(txt_path))[0]
    if stem not in image_index:
        print(f"[跳过] 找不到同名图片：{stem}.*")
        return False

    img_path = image_index[stem]
    try:
        with Image.open(img_path) as im:
            w, h = im.size
    except Exception as e:
        print(f"[跳过] 打开图片失败：{img_path} -> {e}")
        return False

    lines = load_txt_lines(txt_path)
    if not lines:
        # 亦可选择生成全黑 mask；这里选择跳过并提示
        print(f"[跳过] 标注为空：{os.path.basename(txt_path)}")
        return False

    # 创建黑底掩膜
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)

    any_box = False
    for ln in lines:
        try:
            cx, cy, bw, bh = parse_yolo_line(ln)
        except Exception:
            # 若为多边形分割格式（列数>5），这里不处理，直接跳过该行
            continue

        # 忽略无效/空框
        if bw <= 0 or bh <= 0:
            continue

        left, top, right, bottom = yolo_to_pixel_box(cx, cy, bw, bh, w, h)
        if DRAW_OUTLINE:
            draw.rectangle([left, top, right, bottom], outline=255, width=max(1, int(LINE_WIDTH)))
        else:
            draw.rectangle([left, top, right, bottom], fill=255, outline=255)
        any_box = True

    if not any_box:
        print(f"[跳过] 未绘制任何框：{os.path.basename(txt_path)}")
        return False

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, stem + ".png")
    try:
        mask.save(out_path, format="PNG")
        print(f"[完成] {os.path.basename(out_path)}")
        return True
    except Exception as e:
        print(f"[失败] 保存掩膜失败：{out_path} -> {e}")
        return False

def collect_txts(input_path: str) -> List[str]:
    """从拖拽的路径中收集 txt 列表。支持：拖拽文件夹（列举其下所有 .txt）或单个 .txt 文件。"""
    if os.path.isdir(input_path):
        files = []
        for name in os.listdir(input_path):
            p = os.path.join(input_path, name)
            if os.path.isfile(p) and name.lower().endswith(".txt"):
                files.append(p)
        files.sort()
        return files
    elif os.path.isfile(input_path) and input_path.lower().endswith(".txt"):
        return [input_path]
    else:
        return []

def main():
    if len(sys.argv) < 2:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print("用法：将“包含 YOLO TXT 的文件夹”或“单个 TXT 文件”拖拽到本脚本上。")
        print(f"提示：把脚本放在图片目录中。脚本当前所在目录：{script_dir}")
        return

    dropped_path = sys.argv[1]
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "MAKS")

    image_index = build_image_index(script_dir)
    if not image_index:
        print(f"[警告] 在脚本目录未找到任何图片（支持扩展名：{', '.join(sorted(IMG_EXTS))}）。")

    txt_list = collect_txts(dropped_path)
    if not txt_list:
        print(f"[错误] 未找到可处理的 TXT。请拖拽存放 YOLO TXT 的文件夹（或单个 TXT 文件）到脚本上。")
        return

    print(f"图片目录：{script_dir}")
    print(f"标注来源：{dropped_path}")
    print(f"输出目录：{out_dir}")
    print(f"绘制模式：{'白色边框' if DRAW_OUTLINE else '白色填充'}")
    print("-" * 50)

    ok, skip = 0, 0
    for txt in txt_list:
        if process_single_txt(txt, image_index, out_dir):
            ok += 1
        else:
            skip += 1

    print("-" * 50)
    print(f"处理完毕：成功 {ok}，跳过 {skip}。")

    # 额外统计并打印（与“统计：共发现图片 ...；生成掩膜 ...；缺少同名 txt 跳过 ...。”一致）
    total_images = len(image_index)
    txt_stems = {os.path.splitext(os.path.basename(p))[0] for p in txt_list}
    image_stems = set(image_index.keys())
    missing_txt_count = len(image_stems - txt_stems)
    print(f"统计：共发现图片 {total_images} 张；生成掩膜 {ok} 张；缺少同名 txt 跳过 {missing_txt_count} 张。")

    # Windows 下暂停，防止 CMD 窗口自动关闭，便于查看结果
    if os.name == "nt":
        try:
            input("按回车键退出...")
        except Exception:
            os.system("pause")

if __name__ == "__main__":
    main()