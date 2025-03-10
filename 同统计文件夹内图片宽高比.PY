# -*- coding: utf-8 -*-
import sys
import os
from PIL import Image
from math import gcd
import shutil

def process_folder(folder_path):
    # 判断是否为有效的目录
    if not os.path.isdir(folder_path):
        print(f"错误：{folder_path} 并不是一个文件夹。")
        return
    
    # 准备统计用的数据结构
    total_count = 0          # 总图片数
    horizontal_count = 0     # 横向图数量
    vertical_count = 0       # 纵向图数量
    
    # 分别记录各种宽高比出现次数（横/纵分开）
    horizontal_ratios = {}   # { "16:9": 10, "4:3": 5, ... }
    vertical_ratios = {}
    
    # 用于记录每张图片的详细信息
    details = []
    
    # 递归扫描该文件夹及所有子文件夹
    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp')
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in valid_extensions:
                continue
            
            img_path = os.path.join(root, filename)
            try:
                with Image.open(img_path) as img:
                    w, h = img.size
                    # 避免宽高为 0 或异常情况
                    if w <= 0 or h <= 0:
                        continue
                    
                    total_count += 1
                    
                    # 判断横纵向
                    if w >= h:
                        horizontal_count += 1
                        orientation = "横向"
                    else:
                        vertical_count += 1
                        orientation = "纵向"
                    
                    # 计算最简分数形式的宽高比
                    g = gcd(w, h)
                    ratio_w = w // g
                    ratio_h = h // g
                    ratio_str = f"{ratio_w}:{ratio_h}"
                    
                    # 分别记录到横/纵向字典里
                    if orientation == "横向":
                        horizontal_ratios[ratio_str] = horizontal_ratios.get(ratio_str, 0) + 1
                    else:
                        vertical_ratios[ratio_str] = vertical_ratios.get(ratio_str, 0) + 1
                    
                    # 记录详细信息
                    details.append(f"{filename} => {w}x{h} => {orientation} => {ratio_str}")
            
            except Exception as e:
                # 图片读取异常时可跳过或打印日志
                pass
    
    # 根据横纵向图片的数量判断文件夹名字前缀
    prefix = "横向图多" if horizontal_count > vertical_count else "纵向图多"
    
    # 修改文件夹名字
    parent_dir = os.path.dirname(folder_path)  # 获取上一级目录
    new_folder_name = f"{prefix}_{os.path.basename(folder_path)}"
    new_folder_path = os.path.join(parent_dir, new_folder_name)
    
    # 重命名文件夹
    os.rename(folder_path, new_folder_path)
    folder_path = new_folder_path  # 更新为新的文件夹路径
    
    # 生成报告路径，确保报告文件名不重复前缀
    report_filename = f"{prefix}_{os.path.basename(folder_path)}_图像宽高比统计报告.txt"
    
    # 如果报告文件名中已经有重复前缀（例如：横向图多_横向图多_...），去掉多余的前缀
    if report_filename.startswith(f"{prefix}_{prefix}_"):
        report_filename = report_filename[len(prefix)+1:]  # 去掉重复的前缀部分
    report_path = os.path.join(parent_dir, report_filename)
    
    lines = []
    lines.append("====== 图像宽高比统计报告 ======")
    lines.append(f"目标文件夹：{folder_path}")
    lines.append("")
    
    # 先写统计汇总
    lines.append("====== 统计汇总 ======")
    lines.append(f"总图片数：{total_count}")
    lines.append(f"横向图片：{horizontal_count}")
    lines.append(f"纵向图片：{vertical_count}")
    lines.append("")
    
    lines.append("各宽高比分布：")
    lines.append("  [横向]")
    if horizontal_ratios:
        for ratio, cnt in sorted(horizontal_ratios.items(), key=lambda x: x[0]):
            lines.append(f"    {ratio} => {cnt} 张")
    else:
        lines.append("    （无）")
    
    lines.append("  [纵向]")
    if vertical_ratios:
        for ratio, cnt in sorted(vertical_ratios.items(), key=lambda x: x[0]):
            lines.append(f"    {ratio} => {cnt} 张")
    else:
        lines.append("    （无）")
    
    lines.append("")
    
    # 再写每张图片的详细信息
    lines.append("====== 详细列表 ======")
    if details:
        lines.extend(details)
    else:
        lines.append("（无可用图片）")
    
    # 写入 TXT 文件
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"统计完成！报告已生成：{report_path}")
    print(f"文件夹已重命名为：{new_folder_name}")

def main():
    if len(sys.argv) < 2:
        print("用法：将目标文件夹或多个文件夹拖拽到本脚本上即可。")
        sys.exit(1)
    
    # 获取传入的文件夹路径（支持多个文件夹）
    folder_paths = sys.argv[1:]
    
    for folder_path in folder_paths:
        process_folder(folder_path)

if __name__ == "__main__":
    main()
