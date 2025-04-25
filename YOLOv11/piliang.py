import torch
from ultralytics import YOLO
import os
import sys
import cv2
import numpy as np

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
model = YOLO(r'J:\G\Desktop\yolo模型存放\X11\best.pt', task='detect')  # 请修改为你的模型路径

# 设置可调参数
BATCH_SIZE = 10                         # 批次大小
IMG_WIDTH = 1024                         # 默认图片宽度
IMG_HEIGHT = 1024                        # 默认图片高度
SKIP_BIAOQIAN = False                   # 控制是否跳过已有 biaoqianTXT 文件夹 开=True 关=False
GENERATE_MASK = False                    # 控制是否生成掩膜图 开=True 关=False
APPEND_EXISTING_LABELS = False           # 控制是否保留现有标签 开=True 关=False
ENABLE_FILTER = False                   # 控制是否启用过滤标签 开=True 关=False

# 过滤标签
FILTER_CLASSES = ['changfangtiao']  # 只保留这些类别的检测结果('balloon', 'qipao', 'fangkuai', 'changfangtiao', 'kuangwai')


# 标签边界调整参数
ADJUST_PARAMS = {
    0: (0, 0, 0, 1),   # balloon：上5，下20，左0，右0
    1: (0, 1, 1, 2),  # qipao：上0，下0，左30，右20
    2: (0, 0, 0, 0),    # fangkuai：上0，下0，左0，右0
    3: (0, 0, 2, 3),    # changfangtiao：上0，下0，左0，右0
    4: (0, 0, 0, 0)     # kuangwai：上0，下0，左0，右0
}



# 调整边界框
def adjust_bbox(bbox, top, bottom, left, right, img_width, img_height):
    class_id, x_center, y_center, width, height = bbox
    expand_top = top / img_height
    expand_bottom = bottom / img_height
    expand_left = left / img_width
    expand_right = right / img_width
    new_width = min(1.0, max(0, width + expand_left + expand_right))
    new_height = min(1.0, max(0, height + expand_top + expand_bottom))
    x_center = max(new_width / 2, min(1 - new_width / 2, x_center + (expand_right - expand_left) / 2))
    y_center = max(new_height / 2, min(1 - new_height / 2, y_center + (expand_bottom - expand_top) / 2))
    return [class_id, x_center, y_center, new_width, new_height]

# 处理单个图片文件夹
def process_image_folder(folder_path, current_index, total_folders):
    try:
        biaoqian_dir = os.path.join(folder_path, 'biaoqianTXT')
        if SKIP_BIAOQIAN and os.path.exists(biaoqian_dir):
            print(f"跳过文件夹 {folder_path}: 已存在 'biaoqianTXT' 文件夹")
            return

        image_paths = []
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                    image_paths.append(os.path.join(root, file))

        if not image_paths:
            print(f"跳过文件夹 {folder_path}: 未找到图片")
            return

        total_images = len(image_paths)
        print(f"\n开始处理文件夹: {folder_path}，共找到 {total_images} 张图片。")
        os.makedirs(biaoqian_dir, exist_ok=True)
        mask_folder_path = os.path.join(folder_path, 'yolomask')
        os.makedirs(mask_folder_path, exist_ok=True)
        custom_color = (255, 255, 255)

        for batch_start in range(0, total_images, BATCH_SIZE):
            batch_paths = image_paths[batch_start:batch_start + BATCH_SIZE]
            if use_gpu:
                torch.cuda.empty_cache()
            results = model.predict(source=batch_paths, save=True, show=False, device=device, verbose=False, conf=0.5, iou=0.5)

            for result, image_path in zip(results, batch_paths):
                image_name = os.path.splitext(os.path.basename(image_path))[0]
                detections = {}
                for box in result.boxes:
                    cls = int(box.cls)
                    cls_name = result.names[cls]
                    detections[cls_name] = detections.get(cls_name, 0) + 1
                detection_str = ", ".join([f"{count} {name}{'s' if count > 1 else ''}" for name, count in detections.items()])
                if not detection_str:
                    detection_str = "no objects"
                print(f"{image_name}: {result.orig_shape[1]}x{result.orig_shape[0]} {detection_str}")

                txt_path = os.path.join(biaoqian_dir, f"{image_name}.txt")
                write_mode = 'a' if APPEND_EXISTING_LABELS else 'w'
                with open(txt_path, write_mode) as f:
                    for box in result.boxes:
                        cls = int(box.cls)
                        class_name = result.names[cls]  # 获取类别名称
                        if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                            continue  # 跳过不在过滤列表中的类别

                        bbox = [cls] + box.xywhn[0].tolist()
                        if cls in ADJUST_PARAMS:
                            top, bottom, left, right = ADJUST_PARAMS[cls]
                            adjusted_bbox = adjust_bbox(bbox, top, bottom, left, right, IMG_WIDTH, IMG_HEIGHT)
                            f.write(f"{adjusted_bbox[0]} {adjusted_bbox[1]:.6f} {adjusted_bbox[2]:.6f} {adjusted_bbox[3]:.6f} {adjusted_bbox[4]:.6f}\n")
                        else:
                            f.write(f"{cls} {bbox[1]:.6f} {bbox[2]:.6f} {bbox[3]:.6f} {bbox[4]:.6f}\n")

                # 生成掩膜图
                if GENERATE_MASK:
                    img = result.orig_img
                    mask_color_map = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
                    for box in result.boxes:  # 迭代每个检测框
                        cls = int(box.cls[0])
                        class_name = result.names[cls]  # 获取类别名称
                        if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                            continue  # 跳过不在过滤列表中的类别

                        if cls in ADJUST_PARAMS:  # 只处理指定类别
                            top, bottom, left, right = ADJUST_PARAMS[cls]
                            bbox = [cls] + box.xywhn[0].tolist()
                            adjusted_bbox = adjust_bbox(bbox, top, bottom, left, right, IMG_WIDTH, IMG_HEIGHT)
                            x_center, y_center, width, height = adjusted_bbox[1:]
                            x1 = int((x_center - width / 2) * img.shape[1])
                            y1 = int((y_center - height / 2) * img.shape[0])
                            x2 = int((x_center + width / 2) * img.shape[1])
                            y2 = int((y_center + height / 2) * img.shape[0])
                            cv2.rectangle(mask_color_map, (x1, y1), (x2, y2), custom_color, -1)  # -1表示填充
                        else:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                            cv2.rectangle(mask_color_map, (x1, y1), (x2, y2), custom_color, -1)

                    mask_filepath = os.path.join(mask_folder_path, f"{image_name}.png")
                    cv2.imwrite(mask_filepath, mask_color_map)

            # 修改处理进度显示
            print(f"文件夹队列的进度 {current_index}/{total_folders}: 处理当前文件夹的进度: {min(batch_start + BATCH_SIZE, total_images)}/{total_images}")

        print(f"文件夹处理完成：{folder_path}")
    except Exception as e:
        print(f"处理文件夹时出错 {folder_path}: {str(e)}")

# 主入口
if __name__ == "__main__":
    if len(sys.argv) > 1:
        paths = sys.argv[1:]
        total_folders = len(paths)
        print(f"共找到 {total_folders} 个文件夹：")
        for index, folder_path in enumerate(paths, start=1):
            print(f"{index}: {folder_path}")

        for current_index, folder_path in enumerate(paths, start=1):
            print(f"\n开始处理第 {current_index} 个文件夹，剩余 {total_folders - current_index} 个文件夹。")
            process_image_folder(folder_path, current_index, total_folders)
    else:
        print("请将图片文件夹拖放到此脚本上运行。")
