import os
import sys
import re
import shutil
from PIL import Image

# ========= 可调节参数区域 =========
# 是否生成每个文件夹的图像统计报告
ENABLE_REPORT = True

# TXT模板路径
SOURCE_TXT = r"J:\G\Desktop\biaoqian.txt"

# 支持的图片扩展名
VALID_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
# =================================

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
    if not os.path.exists(dst):
        try:
            shutil.copy(src, dst)
            print(f"【Step1】已复制第一张图片：\n  {src}\n到\n  {dst}")
        except Exception as e:
            print(f"【Step1】复制 cover 失败：{e}")
    else:
        print(f"【Step1】cover 文件已存在：{dst}")

def move_images_to_benpian(folder_path):
    benpian = os.path.join(folder_path, "本篇")
    if not os.path.exists(benpian):
        os.makedirs(benpian)
        print(f"【Step2】创建子文件夹：{benpian}")
    files = sorted([f for f in os.listdir(folder_path)
                    if os.path.isfile(os.path.join(folder_path, f)) and
                    f.lower().endswith(VALID_EXTS) and
                    not f.lower().startswith("cover")])
    for f in files:
        src = os.path.join(folder_path, f)
        dst = os.path.join(benpian, f)
        try:
            shutil.move(src, dst)
        except Exception as e:
            print(f"【Step2】移动文件 {src} 失败：{e}")
    print(f"【Step2】已将根目录中的图片移动到：{benpian}")
    benpian_files = sorted([f for f in os.listdir(benpian)
                             if os.path.isfile(os.path.join(benpian, f)) and
                             f.lower().endswith(VALID_EXTS)])
    for idx, f in enumerate(benpian_files, start=1):
        ext = os.path.splitext(f)[1]
        new_name = f"{idx:04d}{ext}"
        src = os.path.join(benpian, f)
        dst = os.path.join(benpian, new_name)
        try:
            os.rename(src, dst)
        except Exception as e:
            print(f"【Step2】重命名 {src} -> {dst} 失败：{e}")
    print(f"【Step2】'本篇' 中图片已按自然顺序重新编号。")

def copy_txt_to_benpian(folder_path):
    benpian = os.path.join(folder_path, "本篇")
    if not os.path.isdir(benpian):
        print(f"【Step3】警告：未找到 '本篇' 文件夹：{folder_path}")
        return
    dst = os.path.join(benpian, os.path.basename(SOURCE_TXT))
    try:
        shutil.copy(SOURCE_TXT, dst)
        print(f"【Step3】已将 TXT 文件复制到：{dst}")
    except Exception as e:
        print(f"【Step3】复制 TXT 失败：{e}")

def generate_report_and_update_orientation(folder_path):
    total = 0
    horz = 0
    vert = 0
    details = []
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            if f.lower().endswith(VALID_EXTS):
                total += 1
                img_path = os.path.join(root, f)
                try:
                    with Image.open(img_path) as img:
                        w, h = img.size
                        orientation = "横向" if w >= h else "纵向"
                        if orientation == "横向":
                            horz += 1
                        else:
                            vert += 1
                        details.append(f"{f} => {w}x{h} => {orientation}")
                except Exception:
                    print(f"【Step4】无法读取图片 {img_path}，跳过。")
    base_name = os.path.basename(folder_path)
    base_name_no_num = re.sub(r'^\[\d+\]', '', base_name).strip()
    base_name_no_orient = re.sub(r'^(横向图多_|纵向图多_)', '', base_name_no_num)
    orient_prefix = "横向图多_" if horz >= vert else "纵向图多_"
    new_name = f"{orient_prefix}{base_name_no_orient}"
    parent = os.path.dirname(folder_path)
    new_folder_path = os.path.join(parent, new_name)
    if new_folder_path != folder_path:
        try:
            os.rename(folder_path, new_folder_path)
            print(f"【Step4】更新方向前缀成功：\n  原名称：{base_name}\n  新名称：{new_name}")
            folder_path = new_folder_path
        except Exception as e:
            print(f"【Step4】更新方向前缀失败：{e}")
    else:
        print("【Step4】文件夹已包含正确的方向前缀。")

    if ENABLE_REPORT:
        report_lines = []
        report_lines.append("====== 图像统计报告 ======")
        report_lines.append(f"目标文件夹：{folder_path}")
        report_lines.append("")
        report_lines.append(f"总图片数：{total}")
        report_lines.append(f"横向图片：{horz}")
        report_lines.append(f"纵向图片：{vert}")
        report_lines.append("")
        report_lines.append("====== 详细列表 ======")
        if details:
            report_lines.extend(details)
        else:
            report_lines.append("（无可用图片）")
        report_filename = f"{os.path.basename(folder_path)}.txt"
        report_path = os.path.join(folder_path, report_filename)
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_lines))
            print(f"【Step4】统计报告生成：{report_path}")
        except Exception as e:
            print(f"【Step4】生成报告失败：{e}")
    return folder_path

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

def process_folder(folder_path):
    print(f"\n开始处理文件夹：{folder_path}")
    copy_first_image_as_cover(folder_path)
    move_images_to_benpian(folder_path)
    copy_txt_to_benpian(folder_path)
    folder_path = generate_report_and_update_orientation(folder_path)
    folder_path = update_folder_with_numeric_prefix(folder_path)
    print(f"处理完成，最终文件夹名称：{folder_path}")

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
