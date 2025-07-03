#!/usr/bin/env python3

import os
from PIL import Image
from io import BytesIO
from bottle import BaseRequest, route, run, request, static_file
import base64
from ultralytics import YOLO
import logging

BaseRequest.MEMFILE_MAX = 1024 * 1024 * 10

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# ======================= 功能配置区 (已优化结构) =======================

# --- 1. 统一宽度配置 ---
# 开关: 开=True 关=False 控制是否启用“统一宽度”模式 (先统一，后扩展)
ENABLE_STANDARDIZED_WIDTH = True
# 配置: (仅在开关为True时生效)
STANDARDIZED_WIDTHS = {
    0: 35,   # balloon
    1: 35,   # qipao
    2: 20,   # fangkuai
    3: 25,   # changfangtiao
    4: 10,   # kuangwai
}

# --- 2. 扩展功能配置 ---
# 开关: 开=True 关=False 控制是否启用“扩展”功能
ENABLE_EXPANSION = False
# 配置: (仅在开关为True时生效)
# 格式: (上扩展, 下扩展, 左扩展, 右扩展)
EXPAND_VALUES = {
    #               (上,  下,  左,  右)
    0: (0,  0,  5,  5),     # balloon
    1: (0,  0,  5,  5),     # qipao
    2: (0,  0,  0,  0),     # fangkuai
    3: (0,  0,  0,  0),     # changfangtiao
    4: (0,  0,  0,  0)      # kuangwai
}

# --- 3. 类别过滤配置 ---
# 开关: 开=True 关=False 控制是否启用过滤功能
ENABLE_FILTER = True
# 配置:  (仅在开关为True时生效)
FILTER_CLASSES = ['balloon', 'qipao', 'fangkuai', 'changfangtiao', 'kuangwai']

# --- 4. 置信度阈值 ---
CONFIDENCE_THRESHOLD = 0.5


# ======================= 服务逻辑区 =======================

@route('/detect', method='POST')
def detect():
    logger.info("开始检测")
    json_data = request.json
    image = json_data["image"]
    bytes_decoded = base64.b64decode(image)
    net_img = Image.open(BytesIO(bytes_decoded))

    prediction = model.predict(source=net_img, conf=CONFIDENCE_THRESHOLD, imgsz=(640), agnostic_nms=True)[0]

    ret = {}
    results = []

    if prediction.boxes is not None:
        for box in prediction.boxes:
            cls = int(box.cls)
            class_name = model.names[cls]
            if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                continue

            confidence = box.conf[0].item()
            
            x_center, y_center, original_w, original_h = box.xywh[0].tolist()
            
            # --- 确定基础宽度 ---
            base_w = 0
            log_mode = ""
            if ENABLE_STANDARDIZED_WIDTH and cls in STANDARDIZED_WIDTHS:
                base_w = STANDARDIZED_WIDTHS.get(cls, original_w) # 使用.get()更安全
                log_mode = "[统一]"
            else:
                base_w = original_w
                log_mode = "[原始]"

            # --- 获取扩展值 ---
            expand_values = (0, 0, 0, 0) # 默认为不扩展
            if ENABLE_EXPANSION:
                expand_values = EXPAND_VALUES.get(cls, (0, 0, 0, 0))
                log_mode += "[扩展:开]"
            else:
                log_mode += "[扩展:关]"
                
            top_expand, bottom_expand, left_expand, right_expand = expand_values
            
            # --- 计算最终尺寸 ---
            final_w = base_w + left_expand + right_expand
            final_h = original_h + top_expand + bottom_expand

            # --- 计算最终坐标 ---
            final_x = x_center - (final_w / 2)
            final_y = y_center - (final_h / 2)

            location = {
                "left": final_x,
                "top": final_y,
                "width": final_w,
                "height": final_h,
                "className": class_name
            }
            results.append({"location": location, "confidence": confidence})
            
            logger.info(
                f"Class: {class_name}, "
                f"最终宽度: {final_w:.1f} (基础:{base_w:.1f} +左:{left_expand} +右:{right_expand}), "
                f"最终高度: {final_h:.1f} (原始:{original_h:.1f} +上:{top_expand} +下:{bottom_expand}), "
                f"置信度: {confidence:.3f} {log_mode}"
            )

    ret["results"] = results
    return ret

@route('/<filepath:path>')
def server_static(filepath):
    return static_file(filepath, root='www')

# ======================= 模型加载区 =======================
model = YOLO(r"J:\G\Desktop\2.0气泡拆分YOLO11N重新训练\runs\detect\train43\weights\best.pt")
logger.info(f"模型加载成功，类别: {model.names}")

run(server="paste", host='127.0.0.1', port=8085)