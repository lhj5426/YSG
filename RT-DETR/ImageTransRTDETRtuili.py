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

SKIP_BIAOQIAN = False               # 是否跳过已存在标签的文件夹
GENERATE_MASK = True                # 是否生成红色透明掩膜
APPEND_EXISTING_LABELS = False      # 是否追加标签到现有文件
ENABLE_FILTER = True                # 是否过滤指定类别
SAVE_INFERENCE_IMAGES = True        # 是否保存推理结果图

# 过滤类别配置
FILTER_CLASSES = ['balloon']  # 保留的类别名称

# 边框扩展配置（上,下,左,右）
EXPAND_VALUES = {
    0: (10, 15, 20, 10),   # balloon
    1: (0, 0, 0, 0),       # 其他类别...
}

# 模型路径配置
MODEL_PATH = r'J:\G\Desktop\reeeee\best.pt'  # 修改为你的模型路径

# 掩膜颜色配置 (BGR格式 + Alpha通道)
MASK_COLOR = (0, 0, 255, 255)  # 红色不透明

# 置信度阈值
CONFIDENCE_THRESHOLD = 0.5

# ========== 功能函数 ==========
def adjust_bbox_pixel(x1, y1, x2, y2, expand_values, img_w, img_h):
    """调整像素坐标的边框"""
    top, bottom, left, right = expand_values
    new_x1 = max(0, x1 - left)
    new_y1 = max(0, y1 - top)
    new_x2 = min(img_w, x2 + right)
    new_y2 = min(img_h, y2 + bottom)
    return new_x1, new_y1, new_x2, new_y2

def save_yolo_format(results, img_name, txt_dir, conf_threshold):
    """保存YOLO格式标签"""
    img = results.orig_img
    img_w, img_h = img.shape[1], img.shape[0]
    txt_path = os.path.join(txt_dir, f"{os.path.splitext(img_name)[0]}.txt")
    
    mode = 'a' if APPEND_EXISTING_LABELS and os.path.exists(txt_path) else 'w'
    with open(txt_path, mode) as f:
        for box in results.boxes:
            cls_id = int(box.cls)
            cls_name = results.names[cls_id]
            conf = float(box.conf)
            
            if conf < conf_threshold:
                continue
            if ENABLE_FILTER and cls_name not in FILTER_CLASSES:
                continue
            
            # 处理原始坐标
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            expand = EXPAND_VALUES.get(cls_id, (0,0,0,0))
            x1, y1, x2, y2 = adjust_bbox_pixel(x1, y1, x2, y2, expand, img_w, img_h)
            
            # 转换YOLO格式
            width = (x2 - x1) / img_w
            height = (y2 - y1) / img_h
            x_center = (x1 + x2) / (2 * img_w)
            y_center = (y1 + y2) / (2 * img_h)
            
            f.write(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f} {conf:.6f}\n")

def draw_inference_image(result, img_path, output_path, model):
    """绘制推理结果图"""
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    
    for box in result.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        cls_id = int(box.cls)
        cls_name = model.names[cls_id]
        conf = float(box.conf)
        
        if conf < CONFIDENCE_THRESHOLD:
            continue
        if ENABLE_FILTER and cls_name not in FILTER_CLASSES:
            continue
        
        # 设置颜色
        colors = [(0,255,0), (255,0,0), (0,0,255)]
        color = colors[cls_id % len(colors)]
        
        # 绘制原始框（虚线）
        cv2.rectangle(img, (x1,y1), (x2,y2), color, 1, lineType=cv2.LINE_AA)
        
        # 绘制扩展框（实线）
        expand = EXPAND_VALUES.get(cls_id, (0,0,0,0))
        nx1, ny1, nx2, ny2 = adjust_bbox_pixel(x1,y1,x2,y2, expand, w, h)
        cv2.rectangle(img, (nx1,ny1), (nx2,ny2), color, 2)
        
        # 添加标签
        label = f"{cls_name}:{conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
        cv2.rectangle(img, (nx1, ny1-th-10), (nx1+tw, ny1), color, -1)
        cv2.putText(img, label, (nx1, ny1-5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1)
    
    cv2.imwrite(output_path, img)

def process_folder(folder_path, index, total):
    """处理单个文件夹"""
    try:
        # 创建输出目录
        folder_name = os.path.basename(folder_path)
        runs_dir = os.path.join(os.path.dirname(__file__), 'runs', folder_name)
        txt_dir = os.path.join(folder_path, 'biaoqianTXT')
        
        if SKIP_BIAOQIAN and os.path.exists(txt_dir):
            print(f"[{index}/{total}] 跳过 {folder_path}（标签已存在）")
            return
        
        # 收集图片路径
        img_paths = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.png','.jpg','.jpeg','.bmp')):
                    img_paths.append(os.path.join(root, file))
        
        if not img_paths:
            print(f"[{index}/{total}] 跳过 {folder_path}（无图片）")
            return
        
        print(f"\n[{index}/{total}] 处理 {folder_path}（共 {len(img_paths)} 张图片）")
        
        # 创建目录
        os.makedirs(txt_dir, exist_ok=True)
        if SAVE_INFERENCE_IMAGES:
            os.makedirs(runs_dir, exist_ok=True)
        if GENERATE_MASK:
            mask_dir = os.path.join(folder_path, 'yolomask')
            os.makedirs(mask_dir, exist_ok=True)
        
        # 加载模型
        model = RTDETR(MODEL_PATH)
        
        # 处理每张图片
        for i, img_path in enumerate(img_paths, 1):
            print(f"处理进度: {i}/{len(img_paths)}")
            results = model(img_path)
            
            # 保存结果
            base_name = os.path.basename(img_path)
            for result in (results if isinstance(results, list) else [results]):
                # 保存标签
                save_yolo_format(result, base_name, txt_dir, CONFIDENCE_THRESHOLD)
                
                # 保存推理图
                if SAVE_INFERENCE_IMAGES:
                    output_path = os.path.join(runs_dir, base_name)
                    draw_inference_image(result, img_path, output_path, model)
                
                # 生成掩膜
                if GENERATE_MASK:
                    h, w = result.orig_img.shape[:2]
                    mask = np.zeros((h, w, 4), dtype=np.uint8)  # BGRA格式
                    
                    for box in result.boxes:
                        cls_id = int(box.cls)
                        cls_name = model.names[cls_id]
                        conf = float(box.conf)
                        
                        if conf < CONFIDENCE_THRESHOLD:
                            continue
                        if ENABLE_FILTER and cls_name not in FILTER_CLASSES:
                            continue
                        
                        # 处理坐标
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        expand = EXPAND_VALUES.get(cls_id, (0,0,0,0))
                        nx1, ny1, nx2, ny2 = adjust_bbox_pixel(x1,y1,x2,y2, expand, w, h)
                        
                        # 绘制红色掩膜
                        cv2.rectangle(mask, (nx1,ny1), (nx2,ny2), MASK_COLOR, -1)
                    
                    # 保存透明掩膜
                    mask_path = os.path.join(mask_dir, f"{os.path.splitext(base_name)[0]}.png")
                    cv2.imwrite(mask_path, mask)
        
        print(f"[{index}/{total}] 完成处理：{folder_path}")

    except Exception as e:
        print(f"处理失败：{folder_path}")
        print(f"错误信息：{str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        folders = sys.argv[1:]
        total = len(folders)
        print(f"发现 {total} 个待处理文件夹")
        
        # 创建输出根目录
        if SAVE_INFERENCE_IMAGES:
            runs_root = os.path.join(os.path.dirname(__file__), 'runs')
            os.makedirs(runs_root, exist_ok=True)
            print(f"推理结果将保存至：{runs_root}")
        
        # 处理每个文件夹
        for idx, folder in enumerate(folders, 1):
            process_folder(folder, idx, total)
    else:
        print("请将图片文件夹拖拽到本脚本上运行")
        input("按任意键退出...")