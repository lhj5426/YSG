#!/usr/bin/env python3

import os
import base64
from io import BytesIO
from PIL import Image
from bottle import BaseRequest, route, run, request, static_file
import torch
from transformers import RTDetrV2ForObjectDetection, RTDetrImageProcessor  # ✅ 使用v2模型类
import logging

BaseRequest.MEMFILE_MAX = 1024 * 1024 * 10  # 设置上传文件的最大内存限制

# 设置日志记录
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger()

# 每个类别的扩展值
EXPAND_VALUES = {
    0: (0, 0, 0, 0),   # balloon：bubble
    1: (0, 0, 0, 0),   # qipao：text_bubble
    2: (0, 0, 0, 0),   # fangkuai：text_free
    3: (0, 0, 0, 0),   # changfangtiao
    4: (0, 0, 0, 0)    # kuangwai
}

ENABLE_FILTER = True  # 是否启用类别过滤
FILTER_CLASSES = ['bubble']  # 只保留这些类别的检测结果
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

    # 统一尺寸推理
    inputs = image_processor(images=net_img, return_tensors="pt", size={"height": 640, "width": 640})
    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)

    results = image_processor.post_process_object_detection(
        outputs,
        target_sizes=torch.tensor([net_img.size[::-1]]).to(device),
        threshold=CONFIDENCE_THRESHOLD
    )

    ret = {"results": []}
    low_confidence_results = []

    for res in results:
        for score, label_id, box in zip(res["scores"], res["labels"], res["boxes"]):
            s, lab = score.item(), label_id.item()
            box = [round(x, 2) for x in box.tolist()]
            name = model.config.id2label[lab]

            x_center = (box[0] + box[2]) / 2
            y_center = (box[1] + box[3]) / 2
            width = box[2] - box[0]
            height = box[3] - box[1]

            if ENABLE_FILTER and name not in FILTER_CLASSES:
                continue

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

@route('/<filepath:path>')  # 用于服务静态文件（如 HTML 网页等）
def server_static(filepath):
    return static_file(filepath, root='www')

# 模型路径（确认这个文件夹中包含 config.json、pytorch_model.bin 等 HuggingFace 格式文件）
model_dir = r"D:\YOLO模型存放\RT-DETR v2 Hugging Face格式的RT-DETR模型\model"

# ✅ 正确加载 v2 模型
model = RTDetrV2ForObjectDetection.from_pretrained(model_dir)
image_processor = RTDetrImageProcessor.from_pretrained(model_dir)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# 启动 Bottle 服务
run(host='127.0.0.1', port=8085)
