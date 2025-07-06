#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import random
import shutil
from collections import defaultdict, Counter

# ================== 高级设置 ==================
ENABLE_TEST_SET = False  # 是否启用测试集

TRAIN_PERCENT = 80      # 训练集百分比
VAL_PERCENT = 20        # 验证集百分比
TEST_PERCENT = 15       # 测试集百分比，仅启用测试集时生效

# 支持的图片格式（注意全小写）
supported_image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.avif', '.bmp')

output_dir_name = 'YOLO'  # 输出文件夹名
clear_output_dir = True  # 是否先清空旧的输出目录
only_include_labeled = True  # 是否只包含有对应标签的图片
move_files_instead_of_copy = False  # True=移动文件，False=复制文件
# ===============================================

def split_dataset_mixed_folder(mixed_folder):
    print(f"混合文件夹路径: {mixed_folder}")

    all_files = os.listdir(mixed_folder)
    all_images = [f for f in all_files if f.lower().endswith(supported_image_exts)]

    if only_include_labeled:
        all_images = [
            f for f in all_images
            if os.path.exists(os.path.join(mixed_folder, os.path.splitext(f)[0] + '.txt'))
        ]

    print(f"找到 {len(all_images)} 张有效图片: {all_images[:10]}...")

    if not all_images:
        print("未找到符合条件的图片。")
        input("按任意键退出...")
        return

    total_percent = TRAIN_PERCENT + VAL_PERCENT + (TEST_PERCENT if ENABLE_TEST_SET else 0)
    if total_percent != 100:
        print(f"错误：训练/验证/测试集百分比之和为 {total_percent}%，必须为100%。请检查设置。")
        input("按任意键退出...")
        return

    train_ratio = TRAIN_PERCENT / 100
    val_ratio = VAL_PERCENT / 100
    test_ratio = TEST_PERCENT / 100 if ENABLE_TEST_SET else 0

    yolo_dir = os.path.join(os.path.dirname(__file__), output_dir_name)

    if clear_output_dir and os.path.exists(yolo_dir):
        shutil.rmtree(yolo_dir)

    subsets = ['train', 'val']
    if ENABLE_TEST_SET:
        subsets.append('test')

    for subset in subsets:
        os.makedirs(os.path.join(yolo_dir, 'images', subset), exist_ok=True)
        os.makedirs(os.path.join(yolo_dir, 'labels', subset), exist_ok=True)

    random.shuffle(all_images)

    num_total = len(all_images)
    num_train = round(train_ratio * num_total)
    num_val = round(val_ratio * num_total)
    num_test = num_total - num_train - num_val

    if not ENABLE_TEST_SET:
        num_val += num_test
        num_test = 0

    train_images = all_images[:num_train]
    val_images = all_images[num_train:num_train + num_val]
    test_images = all_images[num_train + num_val:] if ENABLE_TEST_SET else []

    print(f"开始处理数据集划分：训练集={len(train_images)}，验证集={len(val_images)}，测试集={len(test_images)}")

    file_op = shutil.move if move_files_instead_of_copy else shutil.copy

    def process_files(image_list, subset):
        for image in image_list:
            basename = os.path.splitext(image)[0]
            image_path = os.path.join(mixed_folder, image)
            label_path = os.path.join(mixed_folder, basename + '.txt')

            dst_img = os.path.join(yolo_dir, 'images', subset, image)
            dst_lbl = os.path.join(yolo_dir, 'labels', subset, basename + '.txt')

            try:
                file_op(image_path, dst_img)
            except Exception as e:
                print(f"[{subset}] 图片失败: {image} 错误: {e}")

            if os.path.exists(label_path):
                try:
                    file_op(label_path, dst_lbl)
                except Exception as e:
                    print(f"[{subset}] 标签失败: {basename}.txt 错误: {e}")

    process_files(train_images, 'train')
    process_files(val_images, 'val')
    if ENABLE_TEST_SET:
        process_files(test_images, 'test')

    # 统计部分
    def count_files_by_extension(folder, exts=None):
        count_map = defaultdict(int)
        total = 0
        if not os.path.exists(folder):
            return count_map, 0
        for f in os.listdir(folder):
            ext = os.path.splitext(f)[1].lower()
            if (not exts) or (ext in exts):
                count_map[ext] += 1
                total += 1
        return count_map, total

    def format_ext_counts(count_map):
        return ', '.join(f'{ext}: {count}' for ext, count in sorted(count_map.items()))

    def merge_maps(*maps):
        result = Counter()
        for m in maps:
            result.update(m)
        return dict(result)

    # 各子集统计
    train_img_map, train_img_total = count_files_by_extension(os.path.join(yolo_dir, 'images', 'train'), supported_image_exts)
    train_txt_map, train_txt_total = count_files_by_extension(os.path.join(yolo_dir, 'labels', 'train'), {'.txt'})

    val_img_map, val_img_total = count_files_by_extension(os.path.join(yolo_dir, 'images', 'val'), supported_image_exts)
    val_txt_map, val_txt_total = count_files_by_extension(os.path.join(yolo_dir, 'labels', 'val'), {'.txt'})

    test_img_map, test_img_total = count_files_by_extension(os.path.join(yolo_dir, 'images', 'test'), supported_image_exts) if ENABLE_TEST_SET else ({}, 0)
    test_txt_map, test_txt_total = count_files_by_extension(os.path.join(yolo_dir, 'labels', 'test'), {'.txt'}) if ENABLE_TEST_SET else ({}, 0)

    # 总计
    total_img = train_img_total + val_img_total + test_img_total
    total_txt = train_txt_total + val_txt_total + test_txt_total
    total_img_map = merge_maps(train_img_map, val_img_map, test_img_map)

    # 打印输出
    print("\n完成:")
    print(f"训练集：\n  图片：{train_img_total} 个（{format_ext_counts(train_img_map)}）\n  TXT：{train_txt_total} 个")
    print(f"验证集：\n  图片：{val_img_total} 个（{format_ext_counts(val_img_map)}）\n  TXT：{val_txt_total} 个")
    print(f"测试集：\n  图片：{test_img_total} 个（{format_ext_counts(test_img_map)}）\n  TXT：{test_txt_total} 个")
    print(f"总计：\n  图片：{total_img} 个（{format_ext_counts(total_img_map)}）\n  TXT：{total_txt} 个")

    input("按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        mixed_folder = sys.argv[1]
        split_dataset_mixed_folder(mixed_folder)
    else:
        print("请拖拽包含图片和TXT标签的混合文件夹到该脚本上。")
        input("按任意键退出...")
