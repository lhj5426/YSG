#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import torch
from PIL import Image, ImageDraw
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
from tqdm import tqdm

# ========== 可调参数区域 ==========
BATCH_SIZE = 4                    
IMG_WIDTH = 1024                  
IMG_HEIGHT = 1024                 

# 总开关：
# 当 SKIP_BIAOQIAN = True 时，False          
# 首先检查“本篇”文件夹内是否存在 DERTbiaoqianTXT 文件夹，
# 如果存在则表示之前已经处理过，直接跳过整个文件夹；
# 如果不存在，则在扫描图片时排除下列文件夹：DERTbiaoqianTXT 与 yolomask
SKIP_BIAOQIAN = False          

GENERATE_MASK = True           # 是否生成掩膜图  
APPEND_EXISTING_LABELS = True  # 是否将检测结果追加到现有 TXT 文件中      False          
ENABLE_FILTER = True           # 若需要过滤，仅检测指定类别时，可设为 True False          
SAVE_INFERENCE_IMAGES = True   # 是否保存推理后带检测框的图片

FILTER_CLASSES = ['bubble']  # 只保留这些类别的检测结果，例如：'bubble', 'text_bubble', 'text_free'

# 各类别扩展量，格式：(上, 下, 左, 右)
EXPAND_VALUES = {
    0: (10, 15, 20, 10),   # bubble：上10，下15，左20，右10
    1: (0, 50, 20, 10),    # text_bubble：上0，下50，左20，右10
    2: (30, 0, 0, 0),      # text_free：上30，下0，左0，右0
    3: (0, 0, 0, 0),       # changfangtiao：上0，下0，左0，右0
    4: (0, 0, 0, 0)        # kuangwai：上0，下0，左0，右0
}

# 模型路径，请确保该路径下有正确的模型及配置文件
model_dir = r"D:\Ddown\2504261024111\local_model"

# 置信度阈值（如需要可调低，例如 0.3）
CONFIDENCE_THRESHOLD = 0.5

# 检查是否至少拖拽了一个文件夹
if len(sys.argv) < 2:
    print("请将文件夹拖拽到此脚本上执行！")
    input("按任意键继续...")
    sys.exit()

# 整理所有拖拽进来的文件夹路径（只保留文件夹）
folder_list = [folder for folder in sys.argv[1:] if os.path.isdir(folder)]
if not folder_list:
    print("没有有效的文件夹，请检查拖拽的文件夹路径！")
    input("按任意键继续...")
    sys.exit()

# 打印所有拖拽进来的文件夹信息
num_folders = len(folder_list)
print(f"检测到 {num_folders} 个文件夹：")
for idx, folder in enumerate(folder_list, start=1):
    folder_name = os.path.basename(folder)
    print(f"文件夹{idx}：{folder_name}")

# 加载模型
print("\nLoading model...")
model = RTDetrForObjectDetection.from_pretrained(model_dir)
image_processor = RTDetrImageProcessor.from_pretrained(model_dir)

# 自动选择 GPU 或 CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)
model.to(device)

# 在脚本所在目录下建立保存推理后图片的 results 文件夹
script_dir = os.path.dirname(os.path.abspath(__file__))
base_result_dir = os.path.join(script_dir, "results")
os.makedirs(base_result_dir, exist_ok=True)

# 遍历每个拖拽的文件夹进行处理
for idx, folder_path in enumerate(folder_list, start=1):
    folder_name = os.path.basename(folder_path)
    print(f"\n==================== 正在处理文件夹 {idx}/{num_folders}: {folder_name} ====================")
    
    # 获取当前文件夹下名为 "本篇" 的子文件夹
    bens_folder = os.path.join(folder_path, "本篇")
    if not os.path.isdir(bens_folder):
        print(f"文件夹 {folder_name} 内未找到名为 '本篇' 的子文件夹，跳过此文件夹。")
        continue

    # 如果开启 SKIP_BIAOQIAN，则先判断 “本篇” 下是否已经存在 DERTbiaoqianTXT 文件夹
    txt_folder = os.path.join(bens_folder, "DERTbiaoqianTXT")
    if SKIP_BIAOQIAN and os.path.exists(txt_folder):
        print(f"文件夹 {folder_name} 内已存在 DERTbiaoqianTXT，直接跳过该文件夹。")
        continue

    # 当未跳过时，在扫描图片时排除掉已有的“DERTbiaoqianTXT”与“yolomask”文件夹（如果存在）
    image_files = []
    for root, dirs, files in os.walk(bens_folder):
        # 过滤目录，排除 "DERTbiaoqianTXT" 与 "yolomask"
        dirs[:] = [d for d in dirs if d not in ("DERTbiaoqianTXT", "yolomask")]
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    
    total_images = len(image_files)
    print(f"检测到 {total_images} 张图片，开始推理文件夹：{folder_name}")

    # 当处理过程中需要保存 TXT 与 yolomask 时，若文件夹不存在，则创建
    os.makedirs(txt_folder, exist_ok=True)
    if GENERATE_MASK:
        local_mask_base = os.path.join(bens_folder, "yolomask")
        os.makedirs(local_mask_base, exist_ok=True)

    # 针对该文件夹中的每张图片进行推理
    for img_path in tqdm(image_files, desc=f"推理 {folder_name[:30]}", total=total_images, unit="img"):
        img_name = os.path.basename(img_path)
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"无法打开 {img_path}，错误：{e}")
            continue

        # 如果生成掩膜，则创建一个透明背景的图片（RGBA），用来绘制红色矩形区域
        if GENERATE_MASK:
            mask_img = Image.new('RGBA', image.size, (0, 0, 0, 0))
            draw_mask = ImageDraw.Draw(mask_img)

        # 模型推理
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
        result_lines = []  # 存放 TXT 文件中每行的检测结果

        # 遍历检测结果，对检测框进行扩展处理并绘制到图片和掩膜上
        for res in results:
            for score, label_id, box in zip(res["scores"], res["labels"], res["boxes"]):
                score_val = score.item()
                lab = label_id.item()
                # 获取原始检测框坐标（四舍五入，方便调试）
                orig_box = [round(coord, 2) for coord in box.tolist()]

                # 获取扩展量，默认为 (0,0,0,0)
                expand = EXPAND_VALUES.get(lab, (0, 0, 0, 0))
                top_expand, bottom_expand, left_expand, right_expand = expand

                # 计算扩展后的坐标，确保不超出图片范围
                x0, y0, x1, y1 = orig_box
                new_x0 = max(0, x0 - left_expand)
                new_y0 = max(0, y0 - top_expand)
                new_x1 = min(image.width, x1 + right_expand)
                new_y1 = min(image.height, y1 + bottom_expand)
                new_box = [new_x0, new_y0, new_x1, new_y1]

                # 获取类别名称，若无则使用 lab 数值
                name = model.config.id2label.get(lab, str(lab))
                # 如果启用了过滤，只保留设定类别
                if ENABLE_FILTER and name not in FILTER_CLASSES:
                    continue

                # 转换为 YOLO 格式：中心坐标、宽、高（归一化到0~1）
                x_center = (new_x0 + new_x1) / 2 / image.width
                y_center = (new_y0 + new_y1) / 2 / image.height
                width_box = (new_x1 - new_x0) / image.width
                height_box = (new_y1 - new_y0) / image.height
                result_lines.append(f"{lab} {x_center:.6f} {y_center:.6f} {width_box:.6f} {height_box:.6f} {score_val:.2f}")

                # 在原图上绘制检测框和类别标签
                draw.rectangle(new_box, outline="red", width=2)
                draw.text((new_x0, max(new_y0 - 10, 0)), f"{name} {score_val:.2f}", fill="red")
                
                # 如果生成掩膜，绘制红色填充的矩形区域到透明背景掩膜图上
                if GENERATE_MASK:
                    draw_mask.rectangle(new_box, fill=(255, 0, 0, 255))

        # 仅在检测到物体（即 result_lines 非空）时保存 TXT 文件
        if result_lines:
            txt_save_path = os.path.join(txt_folder, f"{os.path.splitext(img_name)[0]}.txt")
            mode = 'a' if APPEND_EXISTING_LABELS and os.path.exists(txt_save_path) else 'w'
            with open(txt_save_path, mode, encoding='utf-8') as f:
                f.write("\n".join(result_lines) + "\n")

        # 保存推理后带检测框的图片至脚本目录下的 results 文件夹
        relative_path = os.path.relpath(os.path.dirname(img_path), bens_folder)
        result_image_folder = os.path.join(base_result_dir, folder_name, relative_path)
        os.makedirs(result_image_folder, exist_ok=True)
        image_out_path = os.path.join(result_image_folder, img_name)
        image.save(image_out_path)

        # 保存生成的掩膜图到“本篇”内与 DERTbiaoqianTXT 同级的 yolomask 文件夹中（保存为 PNG 格式）
        if GENERATE_MASK:
            mask_image_folder = os.path.join(local_mask_base, relative_path)
            os.makedirs(mask_image_folder, exist_ok=True)
            mask_out_path = os.path.join(mask_image_folder, os.path.splitext(img_name)[0] + ".png")
            mask_img.save(mask_out_path)

    print(f"✅ 文件夹 {folder_name} 处理完成！")

import msvcrt
print("\n所有任务完成！")
print("按任意键退出...")
msvcrt.getch()
sys.exit(0)
