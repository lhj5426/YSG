import os
import sys
import random
import shutil

# ================== Adjustable Parameters ==================
train_ratio = 0.8  # 训练集比例
supported_image_exts = ('.png', '.jpg', '.jpeg')  # 支持的图片格式
output_dir_name = 'YOLO'  # 输出文件夹名
clear_output_dir = True  # 如果存在旧的输出目录，是否先清空
only_include_labeled = True  # 是否只包含有对应标签的图片
move_files_instead_of_copy = True  # False = 移动文件；False = 拷贝文件
# ===========================================================

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

    yolo_dir = os.path.join(os.path.dirname(__file__), output_dir_name)

    if clear_output_dir and os.path.exists(yolo_dir):
        shutil.rmtree(yolo_dir)

    for subset in ['train', 'val']:
        os.makedirs(os.path.join(yolo_dir, 'images', subset), exist_ok=True)
        os.makedirs(os.path.join(yolo_dir, 'labels', subset), exist_ok=True)

    random.shuffle(all_images)
    num_train = int(train_ratio * len(all_images))
    train_images = all_images[:num_train]
    val_images = all_images[num_train:]

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
                print(f"[{subset}] {'移动' if move_files_instead_of_copy else '复制'}图片: {image}")
            except Exception as e:
                print(f"[{subset}] 图片失败: {image} 错误: {e}")

            if os.path.exists(label_path):
                try:
                    file_op(label_path, dst_lbl)
                    print(f"[{subset}] {'移动' if move_files_instead_of_copy else '复制'}标签: {basename}.txt")
                except Exception as e:
                    print(f"[{subset}] 标签失败: {basename}.txt 错误: {e}")
            else:
                if not only_include_labeled:
                    print(f"[{subset}] 缺失标签: {basename}.txt")

    print("开始处理训练集和验证集...")
    process_files(train_images, 'train')
    process_files(val_images, 'val')

    print(f"完成: 训练集 {len(train_images)} 张，验证集 {len(val_images)} 张")
    input("按任意键退出...")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        mixed_folder = sys.argv[1]
        split_dataset_mixed_folder(mixed_folder)
    else:
        print("请拖拽包含图片和TXT标签的混合文件夹到该脚本上。")
        input("按任意键退出...")
