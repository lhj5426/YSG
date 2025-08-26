#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO标签 + CTD模型生成精确文字轮廓掩膜
功能: 使用BallonsTranslator的CTD模型生成精确的文字轮廓掩膜
用法: 将labels文件夹拖拽到此脚本上
"""

import cv2
import numpy as np
import os
import sys
import torch
from pathlib import Path

# 添加BallonsTranslator路径到系统路径
ballons_path = r"D:\BallonsTranslator\BallonsTranslator"
if ballons_path not in sys.path:
    sys.path.insert(0, ballons_path)

try:
    from modules.textdetector.ctd import CTDModel
    from modules.textdetector.ctd.inference import preprocess_img, postprocess_mask
except ImportError as e:
    print(f"无法导入BallonsTranslator模块: {e}")
    print("请确保BallonsTranslator路径正确")
    sys.exit(1)

# 支持的图片格式
IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']

# CTD模型路径
CTD_MODEL_PATH = r"D:\BallonsTranslator\BallonsTranslator\data\models\comictextdetector.pt"

def read_yolo_labels(label_path):
    """读取YOLO标签文件"""
    boxes = []
    if os.path.exists(label_path):
        with open(label_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split()
                    if len(parts) >= 5:
                        # class_id, x_center, y_center, width, height
                        _, x_center, y_center, width, height = map(float, parts[:5])
                        boxes.append((x_center, y_center, width, height))
    return boxes

def yolo_to_pixel_coords(boxes, img_width, img_height):
    """将YOLO归一化坐标转换为像素坐标"""
    pixel_boxes = []
    for x_center, y_center, width, height in boxes:
        # 转换为像素坐标
        x_center_px = x_center * img_width
        y_center_px = y_center * img_height
        width_px = width * img_width
        height_px = height * img_height
        
        # 计算左上角和右下角坐标
        x1 = int(x_center_px - width_px / 2)
        y1 = int(y_center_px - height_px / 2)
        x2 = int(x_center_px + width_px / 2)
        y2 = int(y_center_px + height_px / 2)
        
        # 确保坐标在图像范围内
        x1 = max(0, min(x1, img_width))
        y1 = max(0, min(y1, img_height))
        x2 = max(0, min(x2, img_width))
        y2 = max(0, min(y2, img_height))
        
        pixel_boxes.append((x1, y1, x2, y2))
    
    return pixel_boxes

def load_ctd_model():
    """加载CTD模型"""
    try:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"使用设备: {device}")
        
        if not os.path.exists(CTD_MODEL_PATH):
            print(f"CTD模型文件不存在: {CTD_MODEL_PATH}")
            return None
            
        model = CTDModel(CTD_MODEL_PATH, detect_size=1024, device=device)
        print("CTD模型加载成功!")
        return model
    except Exception as e:
        print(f"CTD模型加载失败: {e}")
        return None

def filter_mask_with_yolo_boxes(mask, yolo_boxes):
    """使用YOLO检测框过滤CTD生成的掩膜"""
    if not yolo_boxes:
        return mask
    
    # 创建YOLO区域掩膜
    yolo_mask = np.zeros_like(mask)
    for x1, y1, x2, y2 in yolo_boxes:
        yolo_mask[y1:y2, x1:x2] = 255
    
    # 只保留YOLO检测框内的文字掩膜
    filtered_mask = cv2.bitwise_and(mask, yolo_mask)
    
    return filtered_mask

def generate_mask_ctd(image_path, label_path, output_path, ctd_model):
    """使用CTD模型生成精确掩膜"""
    try:
        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            print(f"无法读取图片: {image_path}")
            return False
        
        img_height, img_width = image.shape[:2]
        
        # 读取YOLO标签
        boxes = read_yolo_labels(label_path)
        yolo_boxes = yolo_to_pixel_coords(boxes, img_width, img_height) if boxes else []
        
        # 使用CTD模型生成掩膜
        print(f"🔄 使用CTD模型处理: {os.path.basename(image_path)}")
        
        # CTD推理
        mask, mask_refined, blk_list = ctd_model(image, refine_mode=0, keep_undetected_mask=False)
        
        # 如果有YOLO标签，使用YOLO框过滤掩膜
        if yolo_boxes:
            print(f"   📍 使用{len(yolo_boxes)}个YOLO检测框过滤掩膜")
            final_mask = filter_mask_with_yolo_boxes(mask_refined, yolo_boxes)
        else:
            print("   ⚠️ 无YOLO标签，使用完整CTD掩膜")
            final_mask = mask_refined
        
        # 保存掩膜文件
        cv2.imwrite(output_path, final_mask)
        return True
        
    except Exception as e:
        print(f"处理 {image_path} 时发生错误: {str(e)}")
        return False

def find_image_file(script_dir, base_name):
    """在脚本目录下查找同名图片文件"""
    for ext in IMAGE_EXTENSIONS:
        image_path = script_dir / (base_name + ext)
        if image_path.exists():
            return str(image_path)
    return None

def process_labels_folder_ctd(labels_folder_path):
    """使用CTD模型批量处理labels文件夹"""
    labels_folder = Path(labels_folder_path)
    script_dir = Path(__file__).parent  # 脚本所在目录
    
    # 创建MASK输出文件夹
    mask_folder = script_dir / "MASK"
    mask_folder.mkdir(exist_ok=True)
    
    # 加载CTD模型
    print("🚀 初始化CTD模型...")
    ctd_model = load_ctd_model()
    if ctd_model is None:
        print("❌ CTD模型加载失败，退出处理")
        return
    
    # 获取所有txt文件
    label_files = list(labels_folder.glob("*.txt"))
    
    if not label_files:
        print(f"在 {labels_folder} 中没有找到txt标签文件")
        return
    
    print(f"找到 {len(label_files)} 个标签文件")
    print(f"输出目录: {mask_folder}")
    print("-" * 50)
    
    processed_count = 0
    success_count = 0
    
    for label_file in label_files:
        # 获取文件基本名称 (不含扩展名)
        base_name = label_file.stem
        
        # 查找对应的图片文件
        image_path = find_image_file(script_dir, base_name)
        
        if image_path is None:
            print(f"❌ {base_name}: 未找到对应的图片文件")
            continue
        
        # 生成输出掩膜路径
        output_path = mask_folder / (base_name + ".png")
        
        # 使用CTD生成掩膜
        success = generate_mask_ctd(image_path, str(label_file), str(output_path), ctd_model)
        
        processed_count += 1
        if success:
            success_count += 1
            print(f"✅ {base_name}: CTD掩膜生成成功")
        else:
            print(f"❌ {base_name}: CTD掩膜生成失败")
        
    print("-" * 50)
    print(f"处理完成! 成功: {success_count}/{processed_count}")
    print(f"精确掩膜文件保存在: {mask_folder}")

def main():
    """主函数"""
    print("YOLO标签 + CTD模型 → 精确文字轮廓掩膜生成器 v1.0")
    print("=" * 60)
    
    print("🔍 调试信息:")
    print(f"   Python路径: {sys.executable}")
    print(f"   工作目录: {os.getcwd()}")
    print(f"   命令行参数: {sys.argv}")
    
    # 检查命令行参数 (支持拖拽)
    if len(sys.argv) > 1:
        labels_folder_path = sys.argv[1]
        print(f"   接收到参数: {labels_folder_path}")
    else:
        # 交互式输入
        labels_folder_path = input("请输入labels文件夹路径 (或直接拖拽): ").strip().strip('"')
    
    print(f"🎯 处理标签文件夹: {labels_folder_path}")
    
    # 检查路径是否存在
    if not os.path.exists(labels_folder_path):
        print(f"❌ 错误: 路径不存在 - {labels_folder_path}")
        input("按回车键退出...")
        return
    
    if not os.path.isdir(labels_folder_path):
        print(f"❌ 错误: 不是一个文件夹 - {labels_folder_path}")
        input("按回车键退出...")
        return
    
    print(f"✅ 路径验证通过")
    
    # 测试导入
    try:
        print("🔄 测试导入BallonsTranslator模块...")
        from modules.textdetector.ctd import CTDModel
        from modules.textdetector.ctd.inference import preprocess_img, postprocess_mask
        print("✅ BallonsTranslator模块导入成功")
    except ImportError as e:
        print(f"❌ 无法导入BallonsTranslator模块: {e}")
        print("   请确保在BallonsTranslator目录下运行或正确设置路径")
        input("按回车键退出...")
        return
    except Exception as e:
        print(f"❌ 其他导入错误: {e}")
        input("按回车键退出...")
        return
    
    # 开始处理
    try:
        print("🚀 开始处理...")
        process_labels_folder_ctd(labels_folder_path)
    except Exception as e:
        print(f"❌ 处理过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n按回车键退出...")

if __name__ == "__main__":
    main()