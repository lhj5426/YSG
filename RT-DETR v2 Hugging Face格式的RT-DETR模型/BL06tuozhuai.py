#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import shutil
import torch
from PIL import Image, ImageDraw
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
from tqdm import tqdm

# ========== 可调参数区域 ==========
BATCH_SIZE = 4                    
IMG_WIDTH = 1024                  
IMG_HEIGHT = 1024                 

# 总开关：如果设置为 True，则检测到“DERTbiaoqianTXT”文件夹时跳过整个文件夹（表示已处理过）
SKIP_BIAOQIAN = False
GENERATE_MASK = True           # 是否生成掩膜图  
APPEND_EXISTING_LABELS = True  # 是否将标签追加到现有 TXT 文件中      
ENABLE_FILTER = True           # 若需要过滤，仅检测指定类别时，可设为 True
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

# 打印检测到的文件夹信息，逐行列出
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

# 在脚本所在目录下，创建保存推理后图片的 results 文件夹
script_dir = os.path.dirname(os.path.abspath(__file__))
base_result_dir = os.path.join(script_dir, "results")
os.makedirs(base_result_dir, exist_ok=True)

# 遍历每个拖入的文件夹
for idx, folder_path in enumerate(folder_list, start=1):
    folder_name = os.path.basename(folder_path)
    print(f"\n==================== 正在处理文件夹 {idx}/{num_folders}: {folder_name} ====================")
    
    # 获取当前文件夹下名为 "本篇" 的子文件夹
    bens_folder = os.path.join(folder_path, "本篇")
    if not os.path.isdir(bens_folder):
        print(f"文件夹 {folder_name} 内未找到名为 '本篇' 的子文件夹，跳过此文件夹。")
        continue

    # 定位“本篇”内的 DERTbiaoqianTXT 文件夹（用于存放 TXT 标签文件）
    txt_folder = os.path.join(bens_folder, "DERTbiaoqianTXT")
    if SKIP_BIAOQIAN and os.path.exists(txt_folder):
        print(f"文件夹 {folder_name} 已存在 DERTbiaoqianTXT，已被跳过。")
        continue

    # 确保 TXT 文件夹存在
    os.makedirs(txt_folder, exist_ok=True)

    # 如果生成掩膜，则在“本篇”内创建存放掩膜图的文件夹，与 DERTbiaoqianTXT 同级，
    # 若已存在则删除，保证用户每次跑推理用最新结果
    if GENERATE_MASK:
        local_mask_base = os.path.join(bens_folder, "yolomask")
        if os.path.exists(local_mask_base):
            shutil.rmtree(local_mask_base)
        os.makedirs(local_mask_base, exist_ok=True)

    # 遍历“本篇”及其子目录中的图片文件
    image_files = []
    for root, dirs, files in os.walk(bens_folder):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_files.append(os.path.join(root, file))
    
    total_images = len(image_files)
    print(f"检测到 {total_images} 张图片，开始推理文件夹：{folder_name}")

    # 针对该文件夹中的每张图片进行处理
    for img_path in tqdm(image_files, desc=f"推理 {folder_name[:30]}", total=total_images, unit="img"):
        img_name = os.path.basename(img_path)
        try:
            image = Image.open(img_path).convert("RGB")
        except Exception as e:
            print(f"无法打开 {img_path}，错误：{e}")
            continue

        # 如果生成掩膜，初始化全黑掩膜图（模式 L：0为黑色）
        if GENERATE_MASK:
            mask_img = Image.new('L', image.size, 0)
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
        result_lines = []  # 用于存放 TXT 文件中每行的检测结果

        # 遍历检测结果，对检测框进行扩展处理
        for res in results:
            for score, label_id, box in zip(res["scores"], res["labels"], res["boxes"]):
                score_val = score.item()
                lab = label_id.item()
                # 获取原始检测框坐标（四舍五入，便于调试）
                orig_box = [round(coord, 2) for coord in box.tolist()]

                # 获取扩展量，默认为 (0, 0, 0, 0)
                expand = EXPAND_VALUES.get(lab, (0, 0, 0, 0))
                top_expand, bottom_expand, left_expand, right_expand = expand

                # 计算扩展后的坐标，确保不超出图片范围
                x0, y0, x1, y1 = orig_box
                new_x0 = max(0, x0 - left_expand)
                new_y0 = max(0, y0 - top_expand)
                new_x1 = min(image.width, x1 + right_expand)
                new_y1 = min(image.height, y1 + bottom_expand)
                new_box = [new_x0, new_y0, new_x1, new_y1]

                # 获取类别名称，若无则直接使用 lab 数值
                name = model.config.id2label.get(lab, str(lab))
                if ENABLE_FILTER and name not in FILTER_CLASSES:
                    continue

                # 转换为 YOLO 格式：中心坐标、宽、高（归一化到0~1）
                x_center = (new_x0 + new_x1) / 2 / image.width
                y_center = (new_y0 + new_y1) / 2 / image.height
                width_box = (new_x1 - new_x0) / image.width
                height_box = (new_y1 - new_y0) / image.height
                result_lines.append(f"{lab} {x_center:.6f} {y_center:.6f} {width_box:.6f} {height_box:.6f} {score_val:.2f}")

                # 在图像上绘制扩展后的检测框和类别标签
                draw.rectangle(new_box, outline="red", width=2)
                draw.text((new_x0, max(new_y0 - 10, 0)), f"{name} {score_val:.2f}", fill="red")

                # 如果生成掩膜，填充检测区域（白色：255）
                if GENERATE_MASK:
                    draw_mask.rectangle(new_box, fill=255)

        # 保存 TXT 文件（仅在有检测结果时）
        if result_lines:
            txt_save_path = os.path.join(txt_folder, f"{os.path.splitext(img_name)[0]}.txt")
            mode = 'a' if APPEND_EXISTING_LABELS and os.path.exists(txt_save_path) else 'w'
            with open(txt_save_path, mode, encoding='utf-8') as f:
                f.write("\n".join(result_lines) + "\n")

        # 保存推理后带检测框的图片至脚本目录下的 results 文件夹
        relative_path = os.path.relpath(os.path.dirname(img_path), bens_folder)
        # 如果相对路径中包含 "yolomask", 则剔除该部分，避免在 results 中嵌套 yolomask 文件夹
        relative_path = relative_path.replace("yolomask", "").strip(os.sep)
        result_image_folder = os.path.join(base_result_dir, folder_name, relative_path)
        os.makedirs(result_image_folder, exist_ok=True)
        image_out_path = os.path.join(result_image_folder, img_name)
        image.save(image_out_path)

        # 保存生成的掩膜图到“本篇”内的 yolomask 文件夹中（始终保存在 local_mask_base 根目录下）
        if GENERATE_MASK:
            mask_out_path = os.path.join(local_mask_base, img_name)
            mask_img.save(mask_out_path)

    print(f"✅ 文件夹 {folder_name} 处理完成！")

import sys
import msvcrt

print("\n所有任务完成！")
print("按任意键退出...")

# 捕获单个按键，不需要回车
msvcrt.getch()

sys.exit(0)
