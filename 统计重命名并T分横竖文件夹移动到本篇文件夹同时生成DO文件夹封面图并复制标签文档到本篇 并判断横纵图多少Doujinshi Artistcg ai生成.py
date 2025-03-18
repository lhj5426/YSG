import os
import sys
import re
import shutil
from PIL import Image

# 固定TXT文件路径
SOURCE_TXT = r"J:\G\Desktop\biaoqian.txt"

# 定义支持的图片扩展名（小写）
VALID_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')

#############################################
# Step 1: 复制文件夹中第一张图片并改名为 cover.<ext>
#############################################
def copy_first_image_as_cover(folder_path):
    files = sorted([f for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f)) and
                    f.lower().endswith(VALID_EXTS) and not f.lower().startswith("cover")])
    if not files:
        print(f"【Step1】文件夹 {folder_path} 中没有找到可用图片。")
        return
    first_img = files[0]
    src = os.path.join(folder_path, first_img)
    ext = os.path.splitext(first_img)[1]
    dst = os.path.join(folder_path, f"cover{ext}")
    try:
        shutil.copy(src, dst)
        print(f"【Step1】已复制第一张图片：\n  {src}\n并重命名为：\n  {dst}")
    except Exception as e:
        print(f"【Step1】复制 cover 失败：{e}")

#############################################
# Step 2: 统计除 cover 图片外的所有图片的宽高比，并生成TXT统计报告
#############################################
def generate_report(folder_path):
    report_lines = []
    report_lines.append("====== 图像统计报告 ======")
    total = 0
    horz = 0
    vert = 0
    orientation_dict = {}  # 存储文件名对应的方向 ('横' 或 '竖')
    # 仅扫描根目录中图片（排除 cover 开头的文件）
    for f in sorted(os.listdir(folder_path)):
        if os.path.isfile(os.path.join(folder_path, f)) and f.lower().endswith(VALID_EXTS) and not f.lower().startswith("cover"):
            img_path = os.path.join(folder_path, f)
            try:
                with Image.open(img_path) as img:
                    w, h = img.size
                    orientation = "横" if w >= h else "竖"
                    orientation_dict[f] = orientation
                    total += 1
                    if orientation == "横":
                        horz += 1
                    else:
                        vert += 1
                    report_lines.append(f"{f} => {w}x{h} => {orientation}")
            except Exception as e:
                print(f"【Step2】无法读取图片 {img_path}，跳过。")
    report_lines.insert(1, f"总图片数：{total}，横图：{horz}，竖图：{vert}")
    report_filename = "统计报告.txt"
    report_path = os.path.join(folder_path, report_filename)
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))
        print(f"【Step2】统计报告已生成：{report_path}")
    except Exception as e:
        print(f"【Step2】生成统计报告失败：{e}")
    return orientation_dict

#############################################
# Step 3: 在文件夹内创建名为本篇的文件夹，并在其内创建横和竖子文件夹
#############################################
def create_main_folders(folder_path):
    benpian = os.path.join(folder_path, "本篇")
    try:
        os.makedirs(benpian, exist_ok=True)
        print(f"【Step3】已创建文件夹：{benpian}")
    except Exception as e:
        print(f"【Step3】创建 '本篇' 文件夹失败：{e}")
        return None
    folder_heng = os.path.join(benpian, "横")
    folder_shu = os.path.join(benpian, "竖")
    try:
        os.makedirs(folder_heng, exist_ok=True)
        os.makedirs(folder_shu, exist_ok=True)
        print(f"【Step3】已在 '本篇' 内创建子文件夹：\n  横: {folder_heng}\n  竖: {folder_shu}")
    except Exception as e:
        print(f"【Step3】创建 '横' 或 '竖' 文件夹失败：{e}")
    return benpian

#############################################
# 更新子文件夹（横/竖）的前缀，添加图片数量
#############################################
def update_orientation_folder_prefix(benpian):
    for subfolder in ["横", "竖"]:
        folder_path = os.path.join(benpian, subfolder)
        if os.path.isdir(folder_path):
            count = 0
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith(VALID_EXTS):
                        count += 1
            # 去除原有的 [数字] 前缀
            base = os.path.basename(folder_path)
            base_new = re.sub(r'^\[\d+\]', '', base).strip()
            new_name = f"[{count}]{base_new}"
            parent = os.path.dirname(folder_path)
            new_folder_path = os.path.join(parent, new_name)
            if new_folder_path != folder_path:
                try:
                    os.rename(folder_path, new_folder_path)
                    print(f"【Step4】更新子文件夹前缀成功：\n  原名称：{base}\n  新名称：{new_name}")
                except Exception as e:
                    print(f"【Step4】更新子文件夹前缀失败：{folder_path} -> {new_folder_path}，错误：{e}")
        else:
            print(f"【Step4】子文件夹不存在：{folder_path}")

#############################################
# Step 4: 根据统计报告，将图片（除 cover 外）移动到对应的横或竖文件夹，
#         并在移动后更新横、竖文件夹名称前添加图片数量的前缀
#############################################
def move_images_to_orientation_subfolders(folder_path, orientation_dict):
    benpian = os.path.join(folder_path, "本篇")
    if not os.path.isdir(benpian):
        print(f"【Step4】未找到 '本篇' 文件夹：{folder_path}")
        return
    for f, orientation in orientation_dict.items():
        src = os.path.join(folder_path, f)
        if orientation == "横":
            dst = os.path.join(benpian, "横", f)
        else:
            dst = os.path.join(benpian, "竖", f)
        if os.path.exists(src):
            try:
                shutil.move(src, dst)
                print(f"【Step4】移动 {f} 到 {orientation} 文件夹")
            except Exception as e:
                print(f"【Step4】移动文件 {src} 失败：{e}")
        else:
            print(f"【Step4】文件 {src} 不存在，可能已被移动。")
    # 移动完成后，更新 "横" 和 "竖" 子文件夹的名称前缀
    update_orientation_folder_prefix(benpian)

#############################################
# Step 5: 统计 '本篇' 内所有子文件夹中的图片总数量，并更新主文件夹的计数前缀
#############################################
def update_folder_with_numeric_prefix(folder_path):
    benpian = os.path.join(folder_path, "本篇")
    count = 0
    if os.path.isdir(benpian):
        for root, dirs, files in os.walk(benpian):
            for f in files:
                if f.lower().endswith(VALID_EXTS):
                    count += 1
    else:
        print(f"【Step5】警告：未找到 '本篇' 文件夹于 {folder_path}，计数为0")
    base = os.path.basename(folder_path)
    base_new = re.sub(r'^\[\d+\]', '', base).strip()
    new_name = f"[{count}]{base_new}"
    parent = os.path.dirname(folder_path)
    new_folder_path = os.path.join(parent, new_name)
    if new_folder_path != folder_path:
        try:
            os.rename(folder_path, new_folder_path)
            print(f"【Step5】更新计数前缀成功：\n  原名称：{base}\n  新名称：{new_name}")
            folder_path = new_folder_path
        except Exception as e:
            print(f"【Step5】更新计数前缀失败：{e}")
    else:
        print("【Step5】文件夹名称计数前缀未变化。")
    return folder_path

#############################################
# Step 6: 复制固定 TXT 文件到 "本篇"
#############################################
def copy_txt_to_benpian(folder_path):
    benpian = os.path.join(folder_path, "本篇")
    if not os.path.isdir(benpian):
        print(f"【Step6】警告：未找到 '本篇' 文件夹于 {folder_path}")
        return
    dst = os.path.join(benpian, os.path.basename(SOURCE_TXT))
    try:
        shutil.copy(SOURCE_TXT, dst)
        print(f"【Step6】已将固定 TXT 文件复制到：{dst}")
    except Exception as e:
        print(f"【Step6】复制固定 TXT 文件失败：{e}")

#############################################
# 总流程：按步骤执行各任务
#############################################
def process_folder(folder_path):
    print(f"\n开始处理文件夹：{folder_path}")
    # Step 1: 复制第一张图片并改名为 cover
    copy_first_image_as_cover(folder_path)
    # Step 2: 统计图片宽高比，并生成统计报告
    orientation_dict = generate_report(folder_path)
    # Step 3: 创建 '本篇' 及其内的 '横' 和 '竖' 文件夹
    create_main_folders(folder_path)
    # Step 4: 根据统计报告移动图片到对应的子文件夹，并更新子文件夹名称前缀
    move_images_to_orientation_subfolders(folder_path, orientation_dict)
    # Step 5: 统计 '本篇' 内图片总数量，并更新主文件夹计数前缀
    new_folder_path = update_folder_with_numeric_prefix(folder_path)
    # Step 6: 复制固定 TXT 文件到 "本篇"
    copy_txt_to_benpian(new_folder_path)
    print(f"处理完成，最终文件夹名称：{new_folder_path}")

#############################################
# 主函数：支持批量拖拽文件夹处理
#############################################
def main():
    folder_paths = sys.argv[1:]
    if not folder_paths:
        print("请将文件夹拖拽到本脚本上运行！")
        input("按任意键退出...")
        return
    print("待处理文件夹：")
    for idx, fp in enumerate(folder_paths, start=1):
        print(f"{idx}. {fp}")
    print("-" * 40)
    for fp in folder_paths:
        if os.path.isdir(fp):
            process_folder(fp)
        else:
            print(f"错误：{fp} 不是有效的文件夹路径")
    input("\n全部处理完成！按任意键退出...")

if __name__ == "__main__":
    main()
