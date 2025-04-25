#!/usr/bin/env python3

import os
from PIL import Image
from io import BytesIO
from bottle import BaseRequest, route, run, request, static_file
import base64
from ultralytics import YOLO
import logging

BaseRequest.MEMFILE_MAX = 1024 * 1024 * 10  # (or whatever you want)

# 设置日志记录
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# 每个类别的扩展值
EXPAND_VALUES = {
    0: (0, 0, 0, 0),   # balloon：上5，下20，左0，右0
    1: (0, 0, 0, 0),   # qipao：上0，下150，左0，右0
    2: (0, 0, 0, 0),   # fangkuai：上0，下0，左0，右0
    3: (0, 0, 0, 0),   # changfangtiao：上0，下0，左0，右0
    4: (0, 0, 0, 0)    # kuangwai：上0，下0，左0，右0
}

ENABLE_FILTER = False  # 控制是否启用过滤标签 开=True 关=False
FILTER_CLASSES = ['balloon', 'qipao']  # 只保留这些类别的检测结果
CONFIDENCE_THRESHOLD = 0.5  # 过滤掉置信度低于 0.3 的框

def adjust_bbox(x_center, y_center, w, h, expand_values):
    top, bottom, left, right = expand_values
    new_w = w + left + right
    new_h = h + top + bottom
    new_x = x_center - 0.5 * w - left
    new_y = y_center - 0.5 * h - top
    return new_x, new_y, new_w, new_h

@route('/detect', method='POST')
def detect():
    logger.info("开始检测")
    json_data = request.json
    image = json_data["image"]
    bytes_decoded = base64.b64decode(image)
    net_img = Image.open(BytesIO(bytes_decoded))

    # 使用模型进行推理
    prediction = model.predict(source=net_img, conf=CONFIDENCE_THRESHOLD, imgsz=(1280), agnostic_nms=True)[0]

    ret = {}
    results = []

    if prediction.boxes is not None:
        for box in prediction.boxes:
            cls = int(box.cls)
            class_name = model.names[cls]
            if ENABLE_FILTER and class_name not in FILTER_CLASSES:
                continue  # 跳过不在过滤列表中的类别

            confidence = box.conf[0].item()
            if confidence >= CONFIDENCE_THRESHOLD:  # 只传输高于置信度阈值的框
                x_center, y_center, w, h = box.xywh[0].tolist()
                expand_values = EXPAND_VALUES.get(cls, (0, 0, 0, 0))
                x, y, w, h = adjust_bbox(x_center, y_center, w, h, expand_values)
                location = {
                    "left": x,
                    "top": y,
                    "width": w,
                    "height": h,
                    "className": class_name
                }
                results.append({"location": location, "confidence": confidence})
                logger.info(f"Class: {class_name}, 原始边界框: ({x_center:.3f}, {y_center:.3f}, {w:.3f}, {h:.3f}), 扩展后的边界框: ({x:.3f}, {y:.3f}, {w:.3f}, {h:.3f}), 置信度: {confidence:.3f}")

    ret["results"] = results
    return ret

@route('/<filepath:path>')  # 静态文件访问
def server_static(filepath):
    return static_file(filepath, root='www')

# 加载YOLO模型
model = YOLO(r"D:\YOLO模型存放\A100 64G N110\110best.pt")

logger.info(model.names)

run(server="paste", host='127.0.0.1', port=8085)
