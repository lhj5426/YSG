import os
import sys
import random
import shutil
from collections import defaultdict, Counter

supported_image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.avif')  # 可扩展格式
yolo_dir = 'YOLO'

def identify_folders(folder1, folder2):
    folder1_files = os.listdir(folder1)
    folder2_files = os.listdir(folder2)

    folder1_has_images = any(f.lower().endswith(supported_image_exts) for f in folder1_files)
    folder2_has_images = any(f.lower().endswith(supported_image_exts) for f in folder2_files)

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

def split_dataset(image_dir, label_dir, train_ratio=0.8):
    print(f"图片文件夹路径: {image_dir}")
    print(f"标签文件夹路径: {label_dir}")

    all_images = [f for f in os.listdir(image_dir) if f.lower().endswith(supported_image_exts)]
    if not all_images:
        print("图片文件夹中没有找到任何图片文件。")
        input("按任意键退出...")
        return

    random.shuffle(all_images)
    num_train = int(train_ratio * len(all_images))
    train_images = all_images[:num_train]
    val_images = all_images[num_train:]

    # 创建 YOLO 输出文件夹
    for subset in ['train', 'val']:
        os.makedirs(os.path.join(yolo_dir, 'images', subset), exist_ok=True)
        os.makedirs(os.path.join(yolo_dir, 'labels', subset), exist_ok=True)

    def copy_set(image_list, subset):
        for image in image_list:
            basename = os.path.splitext(image)[0]
            image_path = os.path.join(image_dir, image)
            label_path = os.path.join(label_dir, basename + '.txt')

            try:
                shutil.copy(image_path, os.path.join(yolo_dir, 'images', subset, image))
            except Exception as e:
                print(f"[{subset}] 复制图片失败: {image} 错误: {e}")

            if os.path.exists(label_path):
                try:
                    shutil.copy(label_path, os.path.join(yolo_dir, 'labels', subset, basename + '.txt'))
                except Exception as e:
                    print(f"[{subset}] 复制标签失败: {basename}.txt 错误: {e}")

    print(f"开始复制 {len(train_images)} 张训练图片和 {len(val_images)} 张验证图片...")
    copy_set(train_images, 'train')
    copy_set(val_images, 'val')

    # 统计信息
    train_img_map, train_img_total = count_files_by_extension(os.path.join(yolo_dir, 'images', 'train'), supported_image_exts)
    train_txt_map, train_txt_total = count_files_by_extension(os.path.join(yolo_dir, 'labels', 'train'), {'.txt'})

    val_img_map, val_img_total = count_files_by_extension(os.path.join(yolo_dir, 'images', 'val'), supported_image_exts)
    val_txt_map, val_txt_total = count_files_by_extension(os.path.join(yolo_dir, 'labels', 'val'), {'.txt'})

    total_img = train_img_total + val_img_total
    total_txt = train_txt_total + val_txt_total
    total_img_map = merge_maps(train_img_map, val_img_map)

    print("\n完成:")
    print(f"训练集：\n  图片：{train_img_total} 个（{format_ext_counts(train_img_map)}）\n  TXT：{train_txt_total} 个")
    print(f"验证集：\n  图片：{val_img_total} 个（{format_ext_counts(val_img_map)}）\n  TXT：{val_txt_total} 个")
    print(f"总计：\n  图片：{total_img} 个（{format_ext_counts(total_img_map)}）\n  TXT：{total_txt} 个")
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
