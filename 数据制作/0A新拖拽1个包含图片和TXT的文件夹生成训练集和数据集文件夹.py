#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import random
import shutil
from collections import defaultdict, Counter

try:
    from tqdm import tqdm
except ImportError:
    print("正在安装 tqdm 进度条库...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'tqdm', '-q'])
    from tqdm import tqdm

# ================== 高级设置 ==================
ENABLE_TEST_SET = False  # 是否启用测试集

TRAIN_PERCENT = 80      # 训练集百分比
VAL_PERCENT = 20        # 验证集百分比
TEST_PERCENT = 15       # 测试集百分比，仅启用测试集时生效

# 支持的图片格式（注意全小写）
supported_image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.avif', '.bmp')

output_dir_name = '1YOLO1'  # 输出文件夹名
clear_output_dir = True  # 是否先清空旧的输出目录
only_include_labeled = True  # 是否只包含有对应标签的图片
move_files_instead_of_copy = False  # True=移动文件，False=复制文件
# ===============================================

def split_dataset_mixed_folder(mixed_folder, queue_current=1, queue_total=1):
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

    # 用拖拽的文件夹名+YOLO来命名输出文件夹
    folder_basename = os.path.basename(mixed_folder)
    actual_output_name = f"{folder_basename}_YOLO"
    yolo_dir = os.path.join(os.path.dirname(__file__), actual_output_name)

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
    if queue_total > 1:
        print(f"当前队列: {queue_current}/{queue_total}")

    file_op = shutil.move if move_files_instead_of_copy else shutil.copy

    def process_files(image_list, subset):
        if not image_list:
            return
        desc = f"处理{subset}集"
        for image in tqdm(image_list, desc=desc, unit="张", ncols=80, leave=True):
            basename = os.path.splitext(image)[0]
            image_path = os.path.join(mixed_folder, image)
            label_path = os.path.join(mixed_folder, basename + '.txt')

            dst_img = os.path.join(yolo_dir, 'images', subset, image)
            dst_lbl = os.path.join(yolo_dir, 'labels', subset, basename + '.txt')

            try:
                file_op(image_path, dst_img)
            except Exception as e:
                tqdm.write(f"[{subset}] 图片失败: {image} 错误: {e}")

            if os.path.exists(label_path):
                try:
                    file_op(label_path, dst_lbl)
                except Exception as e:
                    tqdm.write(f"[{subset}] 标签失败: {basename}.txt 错误: {e}")

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
    print(f"输出目录: {yolo_dir}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        # 获取所有拖入的文件夹
        folders = []
        for arg in sys.argv[1:]:
            path = os.path.normpath(arg.strip('"').strip("'"))
            if os.path.isdir(path):
                folders.append(path)
            else:
                print(f"跳过无效路径: {path}")
        
        if not folders:
            print("没有有效的文件夹。")
            input("按任意键退出...")
            sys.exit()
        
        # 显示队列
        total_folders = len(folders)
        if total_folders > 1:
            print("")
            print("=" * 60)
            print(f"检测到 {total_folders} 个文件夹待处理：")
            print("-" * 60)
            for i, f in enumerate(folders, 1):
                print(f"  [{i}] {os.path.basename(f)}")
            print("=" * 60)
            print("")
        
        # 依次处理每个文件夹
        for idx, folder in enumerate(folders, 1):
            if total_folders > 1:
                print("")
                print("=" * 60)
                print(f"【队列 {idx}/{total_folders}】正在处理: {os.path.basename(folder)}")
                print("=" * 60)
            split_dataset_mixed_folder(folder, queue_current=idx, queue_total=total_folders)
        
        if total_folders > 1:
            print("")
            print("=" * 60)
            print(f"全部完成！共处理 {total_folders} 个文件夹")
            print("=" * 60)
        input("\n按任意键退出...")
    else:
        print("请拖拽包含图片和TXT标签的混合文件夹到该脚本上。")
        print("支持同时拖拽多个文件夹进行批量处理。")
        input("按任意键退出...")
