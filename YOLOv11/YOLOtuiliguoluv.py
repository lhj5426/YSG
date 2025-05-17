import torch
from ultralytics import YOLO
import os
import sys
import cv2
import numpy as np
from tqdm import tqdm

# 检查GPU可用性
def check_gpu():
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        gpu_name = torch.cuda.get_device_name(0)
        total_memory = torch.cuda.get_device_properties(0).total_memory / 1024 / 1024  # 转换为MB
        print(f"找到 {gpu_count} 个GPU设备")
        print(f"使用GPU: {gpu_name}")
        print(f"GPU总显存: {total_memory:.1f}MB")
        return True
    else:
        print("未找到GPU，将使用CPU进行处理")
        return False

# 加载模型
use_gpu = check_gpu()
device = "cuda" if use_gpu else "cpu"
model = YOLO(r'D:\YOLO模型存放\A100 64G S150\150best.pt', task='detect')  # 请修改为你的模型路径

# 设置可调参数
BATCH_SIZE = 1                        # 批次大小（每次处理的图片数）
IMG_WIDTH = 1024                     # 默认图片宽度
IMG_HEIGHT = 1024                    # 默认图片高度
SKIP_BIAOQIAN = False                # 控制是否跳过已有 biaoqianTXT 文件夹 开=True 关=False
GENERATE_MASK = False                # 控制是否生成掩膜图 开=True 关=False
APPEND_EXISTING_LABELS = False       # 控制是否保留现有标签 开=True 关=False
ENABLE_FILTER = False                # 控制是否启用过滤标签 开=True 关=False

# 过滤标签
FILTER_CLASSES = ['changfangtiao']  # 只保留这些类别的检测结果

# 每个类别的扩展值（上、下、左、右像素）
EXPAND_VALUES = {
    0: (0, 0, 0, 0),   # balloon
    1: (0, 0, 2, 3),   # qipao
    2: (0, 0, 0, 0),   # fangkuai
    3: (0, 0, 0, 0),   # changfangtiao
    4: (0, 0, 0, 0),   # kuangwai
    5: (0, 0, 0, 0)    # other
}

# 调整边界框坐标
def adjust_bbox(bbox, expand_values, img_width, img_height):
    class_id, x_center, y_center, width, height = bbox
    top, bottom, left, right = expand_values
    expand_top = top / img_height
    expand_bottom = bottom / img_height
    expand_left = left / img_width
    expand_right = right / img_width
    new_width = min(1.0, max(0, width + expand_left + expand_right))
    new_height = min(1.0, max(0, height + expand_top + expand_bottom))
    x_center = max(new_width / 2, min(1 - new_width / 2, x_center + (expand_right - expand_left) / 2))
    y_center = max(new_height / 2, min(1 - new_height / 2, y_center + (expand_bottom - expand_top) / 2))
    return [class_id, x_center, y_center, new_width, new_height]

# 保存推理结果（图像、标签、可选掩膜）
def save_results(image_path, result, biaoqian_dir, output_image_dir, mask_folder_path, custom_color):
    image_name = os.path.splitext(os.path.basename(image_path))[0]
    txt_path = os.path.join(biaoqian_dir, f"{image_name}.txt")
    write_mode = 'a' if APPEND_EXISTING_LABELS else 'w'
    with open(txt_path, write_mode) as f:
        for box in result.boxes:
            cls = int(box.cls)
            class_name = model.names[cls]
            if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                continue
            bbox = [cls] + box.xywhn[0].tolist()
            expand_values = EXPAND_VALUES.get(cls, (0, 0, 0, 0))
            adjusted_bbox = adjust_bbox(bbox, expand_values, IMG_WIDTH, IMG_HEIGHT)
            f.write(f"{adjusted_bbox[0]} {adjusted_bbox[1]:.6f} {adjusted_bbox[2]:.6f} {adjusted_bbox[3]:.6f} {adjusted_bbox[4]:.6f}\n")

    # 保存带框图像
    img_with_boxes = result.plot()
    output_path = os.path.join(output_image_dir, os.path.basename(image_path))
    cv2.imwrite(output_path, img_with_boxes)

    # 可选保存掩膜图像
    if GENERATE_MASK:
        img = result.orig_img
        mask_color_map = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
        for box in result.boxes:
            cls = int(box.cls[0])
            class_name = model.names[cls]
            if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                continue
            bbox = [cls] + box.xywhn[0].tolist()
            adjusted_bbox = adjust_bbox(bbox, EXPAND_VALUES.get(cls, (0, 0, 0, 0)), IMG_WIDTH, IMG_HEIGHT)
            x_center, y_center, width, height = adjusted_bbox[1:]
            x1 = int((x_center - width / 2) * img.shape[1])
            y1 = int((y_center - height / 2) * img.shape[0])
            x2 = int((x_center + width / 2) * img.shape[1])
            y2 = int((y_center + height / 2) * img.shape[0])
            cv2.rectangle(mask_color_map, (x1, y1), (x2, y2), custom_color, -1)
        mask_filepath = os.path.join(mask_folder_path, f"{image_name}.png")
        cv2.imwrite(mask_filepath, mask_color_map)

# 处理单个文件夹
def process_image_folder(folder_path, current_folder_index, total_folders):
    try:
        folder_name = os.path.basename(os.path.normpath(folder_path))
        output_image_dir = os.path.join("runs", folder_name)
        os.makedirs(output_image_dir, exist_ok=True)

        biaoqian_dir = os.path.join(folder_path, 'biaoqianTXT')
        if SKIP_BIAOQIAN and os.path.exists(biaoqian_dir):
            print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 跳过文件夹 {folder_path}: 已存在 'biaoqianTXT' 文件夹")
            return

        image_paths = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    image_paths.append(os.path.join(root, file))

        if not image_paths:
            print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 跳过文件夹 {folder_path}: 未找到图片")
            return

        total_images = len(image_paths)
        print(f"\n文件夹队列进度: {current_folder_index}/{total_folders}: 开始处理文件夹: {folder_path}，共找到 {total_images} 张图片。")
        os.makedirs(biaoqian_dir, exist_ok=True)
        mask_folder_path = os.path.join(folder_path, 'yolomask')
        if GENERATE_MASK:
            os.makedirs(mask_folder_path, exist_ok=True)
        custom_color = (255, 255, 255)

        # 创建 tqdm 进度条（按图片数）
        progress_bar = tqdm(total=total_images, desc="推理图片", unit="img")

        for i in range(0, total_images, BATCH_SIZE):
            batch_paths = image_paths[i:i + BATCH_SIZE]
            if use_gpu:
                torch.cuda.empty_cache()
            results = model.predict(source=batch_paths, save=False, show=False, device=device, verbose=False, conf=0.5, iou=0.5)
            for img_path, result in zip(batch_paths, results):
                save_results(img_path, result, biaoqian_dir, output_image_dir, mask_folder_path, custom_color)
                progress_bar.update(1)

        progress_bar.close()
        print(f"文件夹处理完成：{folder_path}")

    except Exception as e:
        print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 处理文件夹时出错 {folder_path}: {str(e)}")

# 主入口
if __name__ == "__main__":
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
        total_folders = len(paths)
        print(f"共找到 {total_folders} 个文件夹：")
        for index, folder_path in enumerate(paths, start=1):
            print(f"{index}: {folder_path}")
        for current_index, folder_path in enumerate(paths, start=1):
            process_image_folder(folder_path, current_index, total_folders)
    else:
        print("请将图片文件夹拖放到此脚本上运行。")
