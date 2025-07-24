# -*- coding: utf-8 -*-
import sys
import os
from collections import defaultdict
import concurrent.futures

try:
    from tqdm import tqdm
except ImportError:
    print("错误: 缺少 'tqdm' 模块。")
    print("请打开命令行(CMD)并运行: pip install tqdm")
    input("按 Enter 键退出...")
    sys.exit()

# ----------------- 配置区 -----------------
CLASS_MAP = {
    0: 'balloon',
    1: 'qipao',
    2: 'fangkuai',
    3: 'changfangtiao',
    4: 'kuangwai',
    5: 'other'
}
UI_TEXT = {
    'class': '类别',
    'images': '图片数',
    'instances': '实例数',
    'all': '总计'
}
MAX_WORKERS = os.cpu_count() or 4
# ------------------------------------------

def get_display_width(text):
    """计算字符串在终端中的实际显示宽度 (中文=2, 英文=1)。"""
    width = 0
    for char in str(text):
        if '\u4e00' <= char <= '\u9fff' or '\uff01' <= char <= '\uff5e':
            width += 2
        else:
            width += 1
    return width

def process_file(file_path):
    """工作线程函数：处理单个文件，返回该文件中各类别的实例数。"""
    local_instance_counts = defaultdict(int)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if not parts: continue
                try:
                    class_id = int(parts[0])
                    if class_id in CLASS_MAP:
                        class_name = CLASS_MAP[class_id]
                        local_instance_counts[class_name] += 1
                except (ValueError, IndexError): pass
    except Exception: pass
    return local_instance_counts

def analyze_single_folder(folder_path):
    """使用多线程分析单个文件夹，并将所有报告统一保存到一个专属文件夹中。"""
    folder_name = os.path.basename(os.path.normpath(folder_path))
    if not os.path.isdir(folder_path):
        print(f"跳过: '{folder_name}' 不是一个有效的文件夹。")
        return

    txt_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.txt')]
    if not txt_files:
        print(f"文件夹 '{folder_name}' 中未找到任何 .txt 标签文件。")
        return

    final_instance_counts = defaultdict(int)
    class_to_filenames = defaultdict(list)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(process_file, fp): fp for fp in txt_files}
        progress_bar = tqdm(concurrent.futures.as_completed(future_to_file), total=len(txt_files), desc=f"分析 {folder_name}", unit="个文件")

        for future in progress_bar:
            file_path = future_to_file[future]
            try:
                local_counts = future.result()
                if not local_counts: continue
                file_basename = os.path.basename(file_path)
                for class_name, count in local_counts.items():
                    final_instance_counts[class_name] += count
                    class_to_filenames[class_name].append(file_basename)
            except Exception as e: print(f"\n处理文件 {os.path.basename(file_path)} 时出错: {e}")

    # --- 准备报告内容 ---
    summary_output_lines = []
    # (此部分逻辑不变)
    total_instances_all_classes = sum(final_instance_counts.values())
    header_data = (UI_TEXT['class'], UI_TEXT['images'], UI_TEXT['instances'])
    total_data = (UI_TEXT['all'], len(txt_files), total_instances_all_classes)
    row_data_list = [total_data]
    for class_id in sorted(CLASS_MAP.keys()):
        class_name = CLASS_MAP[class_id]
        if class_name in final_instance_counts:
            row_data_list.append((class_name, len(class_to_filenames[class_name]), final_instance_counts[class_name]))
    col1_w = max(get_display_width(row[0]) for row in [header_data] + row_data_list)
    col2_w = max(get_display_width(row[1]) for row in [header_data] + row_data_list)
    col3_w = max(get_display_width(row[2]) for row in [header_data] + row_data_list)
    def format_row(c1, c2, c3):
        col1 = str(c1) + ' ' * (col1_w - get_display_width(c1))
        col2 = ' ' * (col2_w - get_display_width(c2)) + str(c2)
        col3 = ' ' * (col3_w - get_display_width(c3)) + str(c3)
        return f"{col1}    {col2}    {col3}"
    summary_output_lines.append(format_row(*header_data))
    summary_output_lines.append("-" * (col1_w + col2_w + col3_w + 8))
    for row_data in row_data_list:
        summary_output_lines.append(format_row(*row_data))

    # --- 打印CMD汇总报告 ---
    print(f"\n--- 文件夹 '{folder_name}' 分析报告 ---")
    for line in summary_output_lines:
        print(line)

    # --- 核心改动：将所有报告保存到同一个文件夹 ---
    try:
        script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        # 1. 创建总的输出文件夹
        output_dir_name = f"{folder_name}_analysis_results"
        output_dir_path = os.path.join(script_dir, output_dir_name)
        os.makedirs(output_dir_path, exist_ok=True)

        # 2. 保存汇总报告到该文件夹
        summary_report_filename = "00_summary_report.txt"
        summary_report_filepath = os.path.join(output_dir_path, summary_report_filename)
        with open(summary_report_filepath, 'w', encoding='utf-8') as f:
            f.write(f"分析文件夹: {folder_path}\n\n")
            f.write("\n".join(summary_output_lines))

        # 3. 保存详细清单到该文件夹
        for class_name, filenames in class_to_filenames.items():
            # 文件名简化，因为父文件夹已说明一切
            detail_filename = f"{class_name}.txt"
            with open(os.path.join(output_dir_path, detail_filename), 'w', encoding='utf-8') as f:
                f.write("\n".join(sorted(filenames)))
        
        print(f"\n[✓] 所有报告已统一保存至文件夹: {output_dir_path}")
    except Exception as e:
        print(f"\n[✗] 错误：保存报告时出错。原因: {e}")


if __name__ == "__main__":
    folders_to_process = sys.argv[1:]
    
    if not folders_to_process:
        print("使用方法：请将一个或多个包含 .txt 标签文件的文件夹拖到此脚本上。")
    else:
        total_folders = len(folders_to_process)
        print(f"已接收 {total_folders} 个项目进行分析，使用最多 {MAX_WORKERS} 个线程。\n")
        
        for i, folder_path in enumerate(folders_to_process):
            folder_name = os.path.basename(os.path.normpath(folder_path))
            print(f"========== 开始处理第 {i+1}/{total_folders} 个项目: {folder_name} ==========")
            analyze_single_folder(folder_path)
            print("=" * (50 + len(str(i+1)) + len(str(total_folders)) + len(folder_name)))
            print()

        print("所有任务已完成。")

    if os.name == 'nt':
        input("\n按 Enter 键退出...")