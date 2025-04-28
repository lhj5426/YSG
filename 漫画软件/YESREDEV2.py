#!/usr/bin/env python3

import os
import base64
from io import BytesIO
from PIL import Image
from bottle import BaseRequest, route, run, request, static_file
import torch
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor
import logging

BaseRequest.MEMFILE_MAX = 1024 * 1024 * 10  # (or whatever you want)

# 设置日志记录
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# 每个类别的扩展值
EXPAND_VALUES = {
    0: (0, 0, 0, 0),   # balloon：bubble 上5，下20，左0，右0
    1: (0, 0, 0, 0),   # qipao：text_bubble 上0，下150，左0，右0
    2: (0, 0, 0, 0),   # fangkuai：text_free 上0，下0，左0，右0
    3: (0, 0, 0, 0),   # changfangtiao：上0，下0，左0，右0
    4: (0, 0, 0, 0)    # kuangwai：上0，下0，左0，右0
}

ENABLE_FILTER = True  # 控制是否启用过滤标签 开=True 关=False
FILTER_CLASSES = ['text_bubble','text_free']  # 只保留这些类别的检测结果('0 balloon', '1 qipao', '2 fangkuai', '3 changfangtiao', '4 kuangwai') 大佬的模型 ('0 bubble', '1 text_bubble', '2 text_free')
CONFIDENCE_THRESHOLD = 0.5  # 置信度阈值

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
    net_img = Image.open(BytesIO(bytes_decoded)).convert("RGB")

    # 处理图像
    inputs = image_processor(images=net_img, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    results = image_processor.post_process_object_detection(
        outputs,
        target_sizes=torch.tensor([net_img.size[::-1]]).to(device),
        threshold=CONFIDENCE_THRESHOLD
    )

    ret = {"results": []}
    low_confidence_results = []  # 用于存储低于阈值的结果

    for res in results:
        for score, label_id, box in zip(res["scores"], res["labels"], res["boxes"]):
            s, lab = score.item(), label_id.item()
            box = [round(x, 2) for x in box.tolist()]
            name = model.config.id2label[lab]

            # 计算中心点和宽高
            x_center = (box[0] + box[2]) / 2
            y_center = (box[1] + box[3]) / 2
            width = box[2] - box[0]
            height = box[3] - box[1]

            # 过滤类别
            if ENABLE_FILTER and name not in FILTER_CLASSES:
                continue

            # 调整边界框
            expand_values = EXPAND_VALUES.get(lab, (0, 0, 0, 0))
            x, y, w, h = adjust_bbox(x_center, y_center, width, height, expand_values)

            location = {
                "left": x,
                "top": y,
                "width": w,
                "height": h,
                "className": name
            }

            if s >= CONFIDENCE_THRESHOLD:
                ret["results"].append({"location": location, "confidence": s})
                logger.info(f"Class: {name}, 原始边界框: ({x_center:.3f}, {y_center:.3f}, {width:.3f}, {height:.3f}), 扩展后的边界框: ({x:.3f}, {y:.3f}, {w:.3f}, {h:.3f}), 置信度: {s:.3f}")
            else:
                low_confidence_results.append(f"Class: {name}, 原始边界框: ({x_center:.3f}, {y_center:.3f}, {width:.3f}, {height:.3f}), 扩展后的边界框: ({x:.3f}, {y:.3f}, {w:.3f}, {h:.3f}), 置信度: {s:.3f}")

    if low_confidence_results:
        logger.info("以下矩形由于置信度低于阈值未被传递:")
        for item in low_confidence_results:
            logger.info(item)

    return ret

@route('/<filepath:path>')  # 静态文件访问
def server_static(filepath):
    return static_file(filepath, root='www')

# 定义模型目录
model_dir = r"D:\Ddown\2504261024111\local_model"  # 请确保此路径正确

# 加载模型
model = RTDetrForObjectDetection.from_pretrained(model_dir)
image_processor = RTDetrImageProcessor.from_pretrained(model_dir)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

run(host='127.0.0.1', port=8085)
