import os
import sys
import shutil
from ultralytics import RTDETR
import torch
import cv2
import numpy as np

# ========== 可调参数区域 ========== 
BATCH_SIZE = 1                      # 每次处理的图片数量
IMG_WIDTH = 1024                    # 图片宽度
IMG_HEIGHT = 1024                   # 图片高度

SKIP_BIAOQIAN = False               # True False 是否跳过已存在 biaoqianTXT 文件夹的图片
GENERATE_MASK = True               # True False 是否生成掩膜图
APPEND_EXISTING_LABELS = False      # True False 是否将标签追加到现有的 TXT 文件中
ENABLE_FILTER = True                # True False 是否仅保留指定类别（FILTER_CLASSES）进行推理结果保存
SAVE_INFERENCE_IMAGES = True        # True False 是否保存推理后的图片

# 过滤标签
FILTER_CLASSES = ['balloon']  # 只保留这些类别的检测结果('balloon', 'qipao', 'fangkuai', 'changfangtiao', 'kuangwai')

# 每个类别的边框扩展像素（top, bottom, left, right）
EXPAND_VALUES = {
    0: (10, 15, 20, 10),   # balloon：上10，下15，左20，右10
    1: (0, 0, 0, 0),       # qipao：上0，下0，左0，右0
    2: (0, 0, 0, 0),       # fangkuai：上0，下0，左0，右0
    3: (0, 0, 0, 0),       # changfangtiao：上0，下0，左0，右0
    4: (0, 0, 0, 0)        # kuangwai：上0，下0，左0，右0
}

# 模型路径
MODEL_PATH = r'J:\G\Desktop\reeeee\best.pt'  # 需要设置为实际的模型路径

# 置信度阈值
CONFIDENCE_THRESHOLD = 0.5  # 仅保存置信度大于此值的检测结果

# 非极大抑制
def non_max_suppression(boxes, scores, iou_threshold=0.4):
    """ 使用非极大抑制去重相同区域的检测框 """
    indices = torch.ops.torchvision.nms(boxes, scores, iou_threshold)
    return indices

# 修复的边框调整函数 - 直接在像素域中操作
def adjust_bbox_pixel(x1, y1, x2, y2, expand_values, img_width, img_height):
    """在像素级别上调整边框"""
    top, bottom, left, right = expand_values
    
    # 扩展边框
    new_x1 = max(0, x1 - left)
    new_y1 = max(0, y1 - top)
    new_x2 = min(img_width, x2 + right)
    new_y2 = min(img_height, y2 + bottom)
    
    return new_x1, new_y1, new_x2, new_y2

# 修复的调整边框函数 - 归一化坐标版
def adjust_bbox(bbox, expand_values, img_width, img_height):
    """
    调整归一化坐标格式的边框
    bbox: [class_id, x_center, y_center, width, height]
    """
    class_id, x_center, y_center, width, height = bbox
    top, bottom, left, right = expand_values
    
    # 转换为像素坐标进行扩展
    x1_pixel = int((x_center - width / 2) * img_width)
    y1_pixel = int((y_center - height / 2) * img_height)
    x2_pixel = int((x_center + width / 2) * img_width)
    y2_pixel = int((y_center + height / 2) * img_height)
    
    # 扩展像素坐标
    new_x1, new_y1, new_x2, new_y2 = adjust_bbox_pixel(
        x1_pixel, y1_pixel, x2_pixel, y2_pixel, 
        expand_values, img_width, img_height
    )
    
    # 转回归一化坐标
    new_width = (new_x2 - new_x1) / img_width
    new_height = (new_y2 - new_y1) / img_height
    new_x_center = (new_x1 + new_x2) / (2 * img_width)
    new_y_center = (new_y1 + new_y2) / (2 * img_height)
    
    return [class_id, new_x_center, new_y_center, new_width, new_height]

# 保存为 YOLO 格式的 txt 文件
def save_yolo_format(results, image_name, result_txt_dir, confidence_threshold=0.5):
    img_width, img_height = results.orig_img.shape[1], results.orig_img.shape[0]
    txt_file_path = os.path.join(result_txt_dir, f"{os.path.splitext(image_name)[0]}.txt")
    
    # 创建或打开文件
    mode = 'a' if APPEND_EXISTING_LABELS and os.path.exists(txt_file_path) else 'w'
    with open(txt_file_path, mode) as f:
        for result in results:
            boxes = result.boxes
            
            for idx in range(len(boxes)):
                cls = int(boxes.cls[idx])
                class_id = int(cls)
                class_name = result.names[class_id]
                confidence = float(boxes.conf[idx])
                
                # 置信度过滤
                if confidence < confidence_threshold:
                    continue  # 如果置信度低于阈值，则跳过该框
                
                # 类别过滤
                if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                    continue  # 如果启用过滤且该类别不在过滤列表中，则跳过
                
                # 获取边框原始坐标（xyxy格式）
                x1, y1, x2, y2 = boxes.xyxy[idx].tolist()
                
                # 应用边框扩展
                expand_values = EXPAND_VALUES.get(class_id, (0, 0, 0, 0))
                x1, y1, x2, y2 = adjust_bbox_pixel(x1, y1, x2, y2, expand_values, img_width, img_height)
                
                # 转换为YOLO格式
                width = (x2 - x1) / img_width
                height = (y2 - y1) / img_height
                x_center = (x1 + x2) / (2 * img_width)
                y_center = (y1 + y2) / (2 * img_height)
                
                # 将数据按 YOLO 格式写入文件
                f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f} {confidence:.6f}\n")

# 绘制并保存推理结果图像
def draw_inference_image(result, image_path, output_path, model):
    img = cv2.imread(image_path)
    img_width, img_height = img.shape[1], img.shape[0]
    
    for r in result:
        boxes = r.boxes
        for idx in range(len(boxes)):
            x1, y1, x2, y2 = boxes.xyxy[idx].tolist()
            class_id = int(boxes.cls[idx])
            class_name = model.names[class_id]
            confidence = float(boxes.conf[idx])
            
            # 只处理高于阈值的检测结果
            if confidence < CONFIDENCE_THRESHOLD:
                continue
                
            # 过滤类别
            if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                continue
                
            # 根据类别设置不同的颜色 (BGR格式)
            colors = [(0, 255, 0), (255, 0, 0), (0, 0, 255), (255, 255, 0), (0, 255, 255)]
            color = colors[class_id % len(colors)]
            
            # 原始框 - 细实线
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color, 1)
            
            # 扩展框 - 粗实线
            expand_values = EXPAND_VALUES.get(class_id, (0, 0, 0, 0))
            new_x1, new_y1, new_x2, new_y2 = adjust_bbox_pixel(x1, y1, x2, y2, expand_values, img_width, img_height)
            cv2.rectangle(img, (int(new_x1), int(new_y1)), (int(new_x2), int(new_y2)), color, 2)
            
            # 添加类别标签和置信度
            label = f'{class_name}: {confidence:.2f}'
            (label_w, label_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(img, (int(new_x1), int(new_y1) - label_h - 10), (int(new_x1) + label_w, int(new_y1)), color, -1)
            cv2.putText(img, label, (int(new_x1), int(new_y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 保存图像
    cv2.imwrite(output_path, img)
    return img

# 处理文件夹
def process_image_folder(folder_path, current_folder_index, total_folders, confidence_threshold):
    try:
        # 获取文件夹名称用于保存推理图像
        folder_name = os.path.basename(folder_path)
        
        # 创建输出目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        runs_dir = os.path.join(script_dir, 'runs')
        inference_out_dir = os.path.join(runs_dir, folder_name)
        
        if SAVE_INFERENCE_IMAGES:
            os.makedirs(inference_out_dir, exist_ok=True)
            print(f"推理图像将保存到: {inference_out_dir}")
        
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
        
        if GENERATE_MASK:
            mask_folder_path = os.path.join(folder_path, 'yolomask')
            os.makedirs(mask_folder_path, exist_ok=True)
            custom_color = (255, 255, 255)  # 白色填充

        model = RTDETR(MODEL_PATH)

        for i, image_path in enumerate(image_paths):
            print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 处理当前文件夹进度: {i+1}/{total_images}")
            results = model(image_path)
            
            if not isinstance(results, list):
                results = [results]  # 如果不是列表，转为列表处理

            for result in results:
                image_name = os.path.basename(image_path)
                base_name = os.path.splitext(image_name)[0]
                
                # 保存检测结果为 YOLO 格式
                save_yolo_format(result, base_name, biaoqian_dir, confidence_threshold)
                
                # 保存推理图像
                if SAVE_INFERENCE_IMAGES:
                    inference_image_path = os.path.join(inference_out_dir, image_name)
                    draw_inference_image(result, image_path, inference_image_path, model)
                
                if GENERATE_MASK:
                    img = result.orig_img
                    img_width, img_height = img.shape[1], img.shape[0]
                    mask_color_map = np.zeros((img_height, img_width, 3), dtype=np.uint8)
                    
                    for idx in range(len(result.boxes)):
                        box = result.boxes.xyxy[idx]
                        x1, y1, x2, y2 = box.tolist()
                        score = result.boxes.conf[idx]
                        cls = int(result.boxes.cls[idx])
                        class_name = model.names[cls]
                        
                        if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                            continue
                            
                        if score < confidence_threshold:
                            continue
                        
                        # 扩展边框
                        expand_values = EXPAND_VALUES.get(cls, (0, 0, 0, 0))
                        new_x1, new_y1, new_x2, new_y2 = adjust_bbox_pixel(
                            x1, y1, x2, y2, expand_values, img_width, img_height
                        )
                        
                        # 仅绘制纯色矩形掩膜（已移除置信度显示）
                        cv2.rectangle(mask_color_map, 
                                    (int(new_x1), int(new_y1)), 
                                    (int(new_x2), int(new_y2)), 
                                    custom_color, -1)

                    mask_filepath = os.path.join(mask_folder_path, f"{base_name}.png")
                    cv2.imwrite(mask_filepath, mask_color_map)

        print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 文件夹处理完成：{folder_path}")
        if SAVE_INFERENCE_IMAGES:
            print(f"推理图像已保存到：{inference_out_dir}")

    except Exception as e:
        print(f"文件夹队列进度: {current_folder_index}/{total_folders}: 处理文件夹时出错 {folder_path}: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
        total_folders = len(paths)
        print(f"共找到 {total_folders} 个文件夹：")
        for index, folder_path in enumerate(paths, start=1):
            print(f"{index}: {folder_path}")

        if SAVE_INFERENCE_IMAGES:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            runs_dir = os.path.join(script_dir, 'runs')
            os.makedirs(runs_dir, exist_ok=True)
            print(f"推理图像将保存到 {runs_dir} 目录下的对应文件夹中")

        for current_index, folder_path in enumerate(paths, start=1):
            process_image_folder(folder_path, current_index, total_folders, CONFIDENCE_THRESHOLD)
    else:
        print("请将图片文件夹拖放到此脚本上运行。")