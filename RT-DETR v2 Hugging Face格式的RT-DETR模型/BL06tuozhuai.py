#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import torch
from PIL import Image, ImageDraw, ImageFont
from transformers import RTDetrV2ForObjectDetection, RTDetrImageProcessor
from tqdm import tqdm
import msvcrt

# ========== 可调参数区域 ==========
BATCH_SIZE = 4
IMG_WIDTH = 1024
IMG_HEIGHT = 1024

# 总开关：如果设置为 True，则检测到“DERTbiaoqianTXT”文件夹时跳过整个文件夹（表示已处理过）
SKIP_BIAOQIAN = False
GENERATE_MASK = True           # 是否生成掩膜图  
APPEND_EXISTING_LABELS = False  # 是否将标签追加到现有 TXT 文件中      
ENABLE_FILTER = True           # 若需要过滤，仅检测指定类别时，可设为 True
SAVE_INFERENCE_IMAGES = True   # 是否保存推理后带检测框的图片

FILTER_CLASSES = ['text_bubble', 'text_free']  # 只保留这些类别的检测结果，例如：'bubble', 'text_bubble', 'text_free'

# 各类别扩展量，格式：(上, 下, 左, 右)
EXPAND_VALUES = {
    0: (0, 0, 0, 0),   # bubble
    1: (0, 0, 0, 0),   # text_bubble
    2: (0, 0, 0, 0),   # text_free
    3: (0, 0, 0, 0),   # changfangtiao
    4: (0, 0, 0, 0)    # kuangwai
}

# 模型路径，请确保该路径下有正确的模型及配置文件
model_dir = r"D:\YOLO模型存放\RT-DETR v2 Hugging Face格式的RT-DETR模型\model"

# 置信度阈值（如需要可调低，例如 0.3）
CONFIDENCE_THRESHOLD = 0.5

# 给不同标签分配颜色（RGB元组）
LABEL_COLORS = {
    'bubble': (255, 0, 0),         # 红色
    'text_bubble': (0, 255, 0),    # 绿色
    'text_free': (0, 0, 255),      # 蓝色
    'changfangtiao': (255, 165, 0),# 橙色
    'kuangwai': (128, 0, 128),     # 紫色
}
DEFAULT_COLOR = (255, 0, 0)  # 默认红色

# 检查是否至少拖拽了一个文件夹
if len(sys.argv) < 2:
    print("请将文件夹拖拽到此脚本上执行！")
    input("按任意键继续...")
    sys.exit()

folder_list = [folder for folder in sys.argv[1:] if os.path.isdir(folder)]
if not folder_list:
    print("没有有效的文件夹，请检查拖拽的文件夹路径！")
    input("按任意键继续...")
    sys.exit()

print(f"检测到 {len(folder_list)} 个文件夹：")
for idx, folder in enumerate(folder_list, start=1):
    print(f"文件夹{idx}：{os.path.basename(folder)}")

print("\nLoading model...")
model = RTDetrV2ForObjectDetection.from_pretrained(model_dir)
image_processor = RTDetrImageProcessor.from_pretrained(model_dir)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)
model.to(device)

# 只有在需要保存图像时才创建 results 根目录
if SAVE_INFERENCE_IMAGES:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_result_dir = os.path.join(script_dir, "results")
    os.makedirs(base_result_dir, exist_ok=True)

# 尝试加载一个字体，若失败则使用默认字体
try:
    font = ImageFont.truetype("arial.ttf", 16)
except:
    font = ImageFont.load_default()

for idx, folder_path in enumerate(folder_list, start=1):
    folder_name = os.path.basename(folder_path)
    print(f"\n==================== 正在处理文件夹 {idx}/{len(folder_list)}: {folder_name} ====================")

    txt_folder = os.path.join(folder_path, "DERTbiaoqianTXT")
    if SKIP_BIAOQIAN and os.path.exists(txt_folder):
        print(f"文件夹 {folder_name} 已存在 DERTbiaoqianTXT，已被跳过。")
        continue
    os.makedirs(txt_folder, exist_ok=True)

    if GENERATE_MASK:
        local_mask_base = os.path.join(folder_path, "yolomask")
        if os.path.exists(local_mask_base):
            shutil.rmtree(local_mask_base)
        os.makedirs(local_mask_base, exist_ok=True)

    image_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')) and not file.lower().startswith("cover."):
                image_files.append(os.path.join(root, file))

    print(f"检测到 {len(image_files)} 张图片，开始推理文件夹：{folder_name}")
    for img_path in tqdm(image_files, desc=f"推理 {folder_name[:30]}", unit="img"):
        img_name = os.path.basename(img_path)
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"无法打开 {img_path}，错误：{e}")
            continue

        if GENERATE_MASK:
            mask_img = Image.new('L', image.size, 0)
            draw_mask = ImageDraw.Draw(mask_img)

        inputs = image_processor(images=image, return_tensors="pt")
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model(**inputs)
        results = image_processor.post_process_object_detection(
            outputs,
            target_sizes=torch.tensor([image.size[::-1]]),
            threshold=CONFIDENCE_THRESHOLD
        )

        draw = ImageDraw.Draw(image)
        result_lines = []

        for res in results:
            for score, label_id, box in zip(res["scores"], res["labels"], res["boxes"]):
                score_val = score.item()
                lab = label_id.item()
                orig_box = [round(coord, 2) for coord in box.tolist()]
                top, bottom, left, right = EXPAND_VALUES.get(lab, (0, 0, 0, 0))
                x0, y0, x1, y1 = orig_box
                new_x0 = max(0, x0 - left)
                new_y0 = max(0, y0 - top)
                new_x1 = min(image.width, x1 + right)
                new_y1 = min(image.height, y1 + bottom)
                new_box = [new_x0, new_y0, new_x1, new_y1]

                name = model.config.id2label.get(lab, str(lab))
                if ENABLE_FILTER and name not in FILTER_CLASSES:
                    continue

                # 获取对应颜色，默认红色
                color = LABEL_COLORS.get(name, DEFAULT_COLOR)

                x_center = (new_x0 + new_x1) / 2 / image.width
                y_center = (new_y0 + new_y1) / 2 / image.height
                width_box = (new_x1 - new_x0) / image.width
                height_box = (new_y1 - new_y0) / image.height
                result_lines.append(f"{lab} {x_center:.6f} {y_center:.6f} {width_box:.6f} {height_box:.6f} {score_val:.2f}")

                # 画框，宽度3像素（Pillow支持width参数）
                draw.rectangle(new_box, outline=color, width=3)

                # 画标签文字和置信度，放在框上方，防止超出图片顶部
                text = f"{name} {score_val:.2f}"

                # 计算文字大小，兼容不同Pillow版本
                try:
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                except AttributeError:
                    text_width, text_height = font.getsize(text)

                text_bg_rect = [new_x0, max(new_y0 - text_height - 4, 0), new_x0 + text_width + 4, max(new_y0, text_height + 4)]
                # 画背景矩形（半透明黑色）
                draw.rectangle(text_bg_rect, fill=(0, 0, 0, 160))
                # 画文字
                draw.text((new_x0 + 2, max(new_y0 - text_height - 2, 0)), text, fill=color, font=font)

                if GENERATE_MASK:
                    draw_mask.rectangle(new_box, fill=255)

        if result_lines:
            txt_save_path = os.path.join(txt_folder, f"{os.path.splitext(img_name)[0]}.txt")
            mode = 'a' if APPEND_EXISTING_LABELS and os.path.exists(txt_save_path) else 'w'
            with open(txt_save_path, mode, encoding='utf-8') as f:
                f.write("\n".join(result_lines) + "\n")

        if SAVE_INFERENCE_IMAGES:
            relative_path = os.path.relpath(os.path.dirname(img_path), folder_path)
            result_image_folder = os.path.join(base_result_dir, folder_name, relative_path)
            os.makedirs(result_image_folder, exist_ok=True)
            image_out_path = os.path.join(result_image_folder, img_name)
            image.save(image_out_path)

        if GENERATE_MASK:
            mask_out_path = os.path.join(local_mask_base, img_name)
            mask_img.save(mask_out_path)

    print(f"✅ 文件夹 {folder_name} 处理完成！")

print("\n所有任务完成！")
print("按任意键退出...")
msvcrt.getch()
sys.exit(0)
