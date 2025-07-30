#!/usr/bin/env python3

import os
from PIL import Image, ImageDraw
from io import BytesIO
from bottle import BaseRequest, route, run, request, static_file
import base64
from ultralytics import YOLO
import logging

# --- 基础配置 ---
BaseRequest.MEMFILE_MAX = 10 * 1024 * 1024
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# ======================= 功能配置区 (已恢复完整注释) =======================

# --- 1. YOLO 模型及推理参数 --- D:\YOLO模型存放\A100 64G S150\150best.pt
YOLO_MODEL_PATH = r"D:\YOLO模型存放\A100 64G S150\150best.pt" # 你的YOLO模型文件 (.pt) 的完整路径。

# --- 分类型的初始置信度阈值 ---
# 在这里为需要特殊处理的类别设置专属的初始置信度，用于第一轮过滤。
PER_CLASS_CONF_CONFIG = {
    # '类别名': 初始置信度 (0.0-1.0)
    'balloon': 0.01,       # 对话气泡类，使用极低阈值，确保能捕获所有文字碎片用于合并。
    'changfangtiao': 0.2,  # 长条标题类，如果检测比较稳定，可以设置稍高阈值以减少噪点。
    'qipao': 0.6           # 旗袍类，根据实际情况设置。
}
# 为上面没有指定的类别设置一个全局的、默认的初始置信度。
DEFAULT_INITIAL_CONF = 0.01

# 全局IoU阈值：用于NMS（非极大值抑制）。此设置对所有类别生效。
IOU_THRESHOLD = 0.91

# 最终结果的置信度阈值：在所有处理（合并、扩展等）完成后，用于过滤最终结果。
FINAL_CONF_THRESHOLD = 0.5


# --- 2. 类别过滤 ---
ENABLE_FILTER = True           # 类别过滤功能的总开关。
FILTER_CLASSES = ['balloon', 'qipao', 'changfangtiao'] # 要保留的类别列表 (使用模型原始名)。


# --- 3. 智能合并功能 ---
# 为需要合并的类别指定方向: 'vertical' 或 'horizontal'。
MERGE_CONFIG = {
    'balloon': 'vertical',
    'changfangtiao': 'horizontal'
}

# --- 合并功能的对齐标准配置 (核心升级) ---
# 用于【垂直合并】的对齐阈值 (判断水平IoU)。
HORIZONTAL_IOU_FOR_VERTICAL_MERGE = 0.7
# 用于【垂直合并】的最大【垂直】间距 (单位: 像素)。
MAX_VERTICAL_GAP_FOR_VERTICAL_MERGE = 30

# 用于【水平合并】的对齐阈值 (判断垂直重叠率)。
VERTICAL_OVERLAP_FOR_HORIZONTAL_MERGE = 0.8
# 用于【水平合并】的最大【水平】间距 (单位: 像素)。
MAX_HORIZONTAL_GAP_FOR_HORIZONTAL_MERGE = 5


# --- 4. 统一尺寸功能 ---
# 统一宽度的总开关。  False   True
ENABLE_STANDARDIZED_WIDTH = False 
STANDARDIZED_WIDTHS = {
    # '类别名': 宽度值 (单位: 像素)
    'balloon': 35, 'qipao': 19, 'changfangtiao': 180
}

# 统一高度的总开关。  True  False
ENABLE_STANDARDIZED_HEIGHT = False
STANDARDIZED_HEIGHTS = {
    # '类别名': 高度值 (单位: 像素)
    'balloon': 40, 'qipao': 25, 'changfangtiao': 30
}


# --- 5. 扩展功能 ---
ENABLE_EXPANSION = False          # 边框扩展功能的总开关。 True  False
EXPAND_VALUES = {
    # '类别名': (上扩展, 下扩展, 左扩展, 右扩展)  (单位: 像素)
    'balloon': (0, 0, 5, 5),
    'qipao': (0, 0, 5, 5),
    'changfangtiao': (25, 25, 0, 0)
}


# --- 6. 类别名映射 ---
CLASS_NAME_MAP = {}               # 可选：将原始类别名映射为更友好的名字。{'原始名': '新名字'}


# ======================= 核心辅助函数 (已彻底重构) =======================

def are_boxes_aligned(b1, b2, direction):
    """全新的、更健壮的对齐判断函数，同时考虑对齐度和邻近度。"""
    if direction == 'horizontal':
        # 判断是否在同一行：1. 垂直重叠度足够高；2. 水平间隙足够小。
        if calculate_vertical_overlap_ratio(b1, b2) < VERTICAL_OVERLAP_FOR_HORIZONTAL_MERGE:
            return False
        horizontal_gap = max(b1['left'], b2['left']) - min(b1['left'] + b1['width'], b2['left'] + b2['width'])
        return horizontal_gap < MAX_HORIZONTAL_GAP_FOR_HORIZONTAL_MERGE
        
    elif direction == 'vertical':
        # 判断是否在同一列：1. 水平IoU足够高；2. 垂直间隙足够小。
        if calculate_horizontal_iou(b1, b2) < HORIZONTAL_IOU_FOR_VERTICAL_MERGE:
            return False
        vertical_gap = max(b1['top'], b2['top']) - min(b1['top'] + b1['height'], b2['top'] + b2['height'])
        return vertical_gap < MAX_VERTICAL_GAP_FOR_VERTICAL_MERGE
        
    return False

def calculate_horizontal_iou(b1, b2):
    x1_min, x1_max = b1['left'], b1['left'] + b1['width']
    x2_min, x2_max = b2['left'], b2['left'] + b2['width']
    i_w = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
    if i_w == 0: return 0.0
    u_w = (x1_max - x1_min) + (x2_max - x2_min) - i_w
    return i_w / u_w if u_w > 0 else 0.0

def calculate_vertical_overlap_ratio(b1, b2):
    y1_min, y1_max = b1['top'], b1['top'] + b1['height']
    y2_min, y2_max = b2['top'], b2['top'] + b2['height']
    intersection_height = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
    if intersection_height == 0: return 0.0
    min_height = min(b1['height'], b2['height'])
    if min_height == 0: return 0.0
    return intersection_height / min_height

def merge_cluster(cluster):
    if not cluster: return None
    locs = [b['location'] for b in cluster]
    min_left = min(l['left'] for l in locs)
    min_top = min(l['top'] for l in locs)
    max_right = max(l['left'] + l['width'] for l in locs)
    max_bottom = max(l['top'] + l['height'] for l in locs)
    return {
        "location": {
            "left": int(min_left), "top": int(min_top),
            "width": int(max_right - min_left), "height": int(max_bottom - min_top),
            "className": locs[0]['className']
        }, "confidence": round(max(b['confidence'] for b in cluster), 4)
    }

def cluster_and_merge(boxes, is_aligned_func):
    """通用的聚类和合并逻辑 (使用图算法，健壮且无bug)。"""
    if not boxes: return []
    num_boxes = len(boxes)
    parent = list(range(num_boxes))
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i]); return parent[i]
    def union(i, j):
        root_i, root_j = find(i), find(j)
        if root_i != root_j: parent[root_j] = root_i

    for i in range(num_boxes):
        for j in range(i + 1, num_boxes):
            if is_aligned_func(boxes[i]['location'], boxes[j]['location']):
                union(i, j)

    clusters = {}
    for i in range(num_boxes):
        root = find(i)
        if root not in clusters: clusters[root] = []
        clusters[root].append(boxes[i])
        
    return [merge_cluster(c) for c in clusters.values() if c]

# ======================= Web 服务逻辑区 (无需修改) =======================

@route('/detect', method='POST')
def detect():
    logger.info("开始处理检测请求...")
    try:
        json_data = request.json; image_b64 = json_data.get("image")
        if not image_b64: return {"error": "请求中未找到图像数据"}

        net_img = Image.open(BytesIO(base64.b64decode(image_b64))).convert("RGB")
        prediction = model.predict(source=net_img, conf=0.01, iou=IOU_THRESHOLD, imgsz=1280, agnostic_nms=True)[0]

        initial_filtered_boxes = []
        if prediction.boxes is not None:
            for box in prediction.boxes:
                class_name = model.names[int(box.cls)]
                confidence = float(box.conf[0].item())
                class_specific_conf = PER_CLASS_CONF_CONFIG.get(class_name, DEFAULT_INITIAL_CONF)
                if confidence >= class_specific_conf:
                    if not ENABLE_FILTER or (ENABLE_FILTER and class_name in FILTER_CLASSES):
                        initial_filtered_boxes.append(box)

        raw_results_by_class = {}
        for box in initial_filtered_boxes:
            class_name = model.names[int(box.cls)]
            x_c, y_c, w, h = box.xywh[0].tolist()
            if class_name not in raw_results_by_class: raw_results_by_class[class_name] = []
            raw_results_by_class[class_name].append({
                "location": {"left": x_c - w/2, "top": y_c - h/2, "width": w, "height": h, "className": class_name},
                "confidence": float(box.conf[0].item())
            })
        
        processed_results = []
        for class_name, bboxes in raw_results_by_class.items():
            direction = MERGE_CONFIG.get(class_name)
            if direction == 'vertical':
                merged = cluster_and_merge(bboxes, lambda b1, b2: are_boxes_aligned(b1, b2, 'vertical'))
                processed_results.extend(merged)
            elif direction == 'horizontal':
                merged = cluster_and_merge(bboxes, lambda b1, b2: are_boxes_aligned(b1, b2, 'horizontal'))
                processed_results.extend(merged)
            else:
                processed_results.extend(bboxes)

        confident_results = [res for res in processed_results if res['confidence'] >= FINAL_CONF_THRESHOLD]

        final_results = []
        for res in confident_results:
            original_loc = res['location']
            c_name = original_loc['className']
            x_c, y_c = original_loc['left'] + original_loc['width']/2, original_loc['top'] + original_loc['height']/2
            base_w = STANDARDIZED_WIDTHS.get(c_name, original_loc['width']) if ENABLE_STANDARDIZED_WIDTH else original_loc['width']
            base_h = STANDARDIZED_HEIGHTS.get(c_name, original_loc['height']) if ENABLE_STANDARDIZED_HEIGHT else original_loc['height']
            t_e, b_e, l_e, r_e = EXPAND_VALUES.get(c_name, (0,0,0,0)) if ENABLE_EXPANSION else (0,0,0,0)
            f_w = base_w + l_e + r_e
            f_h = base_h + t_e + b_e
            final_x_c = x_c + (r_e - l_e) / 2
            final_y_c = y_c + (b_e - t_e) / 2
            final_loc = {"left": final_x_c - f_w/2, "top": final_y_c - f_h/2, "width": f_w, "height": f_h}
            
            original_xywh_log = f"({x_c:.3f}, {y_c:.3f}, {original_loc['width']:.3f}, {original_loc['height']:.3f})"
            expanded_ltwh_log = f"({final_loc['left']:.3f}, {final_loc['top']:.3f}, {final_loc['width']:.3f}, {final_loc['height']:.3f})"
            
            logger.info(
                f"Class: {c_name}, 原始边界框: {original_xywh_log}, 扩展后的边界框: {expanded_ltwh_log}, 置信度: {res['confidence']:.3f}"
            )
            
            final_results.append({
                "location": final_loc, "className": CLASS_NAME_MAP.get(c_name, c_name),
                "confidence": res['confidence']
            })
        return {"results": final_results}

    except Exception as e:
        logger.error(f"检测过程中发生错误: {e}", exc_info=True)
        return {"error": f"服务器内部错误: {e}"}

@route('/<filepath:path>')
def server_static(filepath): return static_file(filepath, root='www')

# ======================= 模型加载与启动 =======================
if __name__ == '__main__':
    try:
        model = YOLO(YOLO_MODEL_PATH)
        logger.info(f"YOLO模型加载成功: {YOLO_MODEL_PATH} | 类别: {model.names}")
    except Exception as e:
        logger.error(f"模型加载失败，请检查路径: '{YOLO_MODEL_PATH}'. 错误: {e}", exc_info=True); exit(1)
    logger.info("启动Web服务器，监听地址: http://127.0.0.1:8085")
    run(server="paste", host='127.0.0.1', port=8085)