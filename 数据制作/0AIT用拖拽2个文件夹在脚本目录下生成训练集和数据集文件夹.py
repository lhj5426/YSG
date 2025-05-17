import os
import sys
import random
import shutil

# ========== 高级设置 ==========
ENABLE_TEST_SET = True  # 是否启用测试集

TRAIN_PERCENT = 70      # 训练集百分比
VAL_PERCENT = 15        # 验证集百分比
TEST_PERCENT = 15       # 测试集百分比，仅在 ENABLE_TEST_SET=True 时有效
# =============================

def identify_folders(folder1, folder2):
    folder1_files = os.listdir(folder1)
    folder2_files = os.listdir(folder2)

    folder1_has_images = any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in folder1_files)
    folder2_has_images = any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in folder2_files)

    if folder1_has_images:
        image_dir = folder1
        label_dir = folder2
    elif folder2_has_images:
        image_dir = folder2
        label_dir = folder1
    else:
        print("未能找到包含图片的文件夹，请检查文件夹内容。")
        input("按任意键退出...")
        sys.exit()

    return image_dir, label_dir

def split_dataset(image_dir, label_dir):
    print(f"图片文件夹路径: {image_dir}")
    print(f"标签文件夹路径: {label_dir}")

    all_images = [f for f in os.listdir(image_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    print(f"找到 {len(all_images)} 张图片文件: {all_images[:10]}...")

    if not all_images:
        print("图片文件夹中没有找到任何图片文件。")
        input("按任意键退出...")
        return

    # 校验百分比设置
    total_percent = TRAIN_PERCENT + VAL_PERCENT + (TEST_PERCENT if ENABLE_TEST_SET else 0)
    if total_percent != 100:
        print(f"错误：训练/验证/测试集百分比之和为 {total_percent}%，必须为100%。请检查设置。")
        input("按任意键退出...")
        return

    # 转为小数
    train_ratio = TRAIN_PERCENT / 100
    val_ratio = VAL_PERCENT / 100
    test_ratio = TEST_PERCENT / 100 if ENABLE_TEST_SET else 0

    yolo_dir = 'YOLO'
    os.makedirs(yolo_dir, exist_ok=True)

    subsets = ['train', 'val']
    if ENABLE_TEST_SET:
        subsets.append('test')

    for subset in subsets:
        os.makedirs(os.path.join(yolo_dir, 'images', subset), exist_ok=True)
        os.makedirs(os.path.join(yolo_dir, 'labels', subset), exist_ok=True)

    random.shuffle(all_images)

    num_total = len(all_images)
    num_train = int(train_ratio * num_total)
    num_val = int(val_ratio * num_total)
    num_test = num_total - num_train - num_val if ENABLE_TEST_SET else 0

    train_images = all_images[:num_train]
    val_images = all_images[num_train:num_train + num_val]
    test_images = all_images[num_train + num_val:] if ENABLE_TEST_SET else []

    print(f"开始复制数据：训练集={len(train_images)}，验证集={len(val_images)}，测试集={len(test_images)}")

    def copy_files(images, subset):
        for image in images:
            basename = os.path.splitext(image)[0]
            image_path = os.path.join(image_dir, image)
            label_path = os.path.join(label_dir, basename + '.txt')

            try:
                shutil.copy(image_path, os.path.join(yolo_dir, 'images', subset, image))
                print(f"[{subset}] 复制图片: {image}")
            except Exception as e:
                print(f"[{subset}] 图片复制失败 {image}: {e}")

            if os.path.exists(label_path):
                try:
                    shutil.copy(label_path, os.path.join(yolo_dir, 'labels', subset, basename + '.txt'))
                    print(f"[{subset}] 复制标签: {basename}.txt")
                except Exception as e:
                    print(f"[{subset}] 标签复制失败 {basename}.txt: {e}")
            else:
                print(f"[{subset}] 标签缺失: {basename}.txt")

    copy_files(train_images, 'train')
    copy_files(val_images, 'val')
    if ENABLE_TEST_SET:
        copy_files(test_images, 'test')

    print("\n=== 数据集划分完成 ===")
    print(f"训练集: {len(train_images)} 张 ({TRAIN_PERCENT}%)")
    print(f"验证集: {len(val_images)} 张 ({VAL_PERCENT}%)")
    if ENABLE_TEST_SET:
        print(f"测试集: {len(test_images)} 张 ({TEST_PERCENT}%)")
    input("按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) > 2:
        folder1 = sys.argv[1]
        folder2 = sys.argv[2]
        image_directory, label_directory = identify_folders(folder1, folder2)
        split_dataset(image_directory, label_directory)
    else:
        print("请拖拽包含图片的文件夹和标签的文件夹到该脚本上。")
        input("按任意键退出...")
