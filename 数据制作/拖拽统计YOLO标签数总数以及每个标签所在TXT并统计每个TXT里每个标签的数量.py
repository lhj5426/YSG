# -*- coding: utf-8 -*-
import sys
import os
from collections import defaultdict
import concurrent.futures
import shutil

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
    'all': '总计',
    'empty': '空TXT'
}
MAX_WORKERS = os.cpu_count() or 4
# ------------------------------------------

def get_display_width(text):
    """计算终端字符宽度，中文为2，英文为1"""
    width = 0
    for char in str(text):
        if '\u4e00' <= char <= '\u9fff' or '\uff01' <= char <= '\uff5e':
            width += 2
        else:
            width += 1
    return width

def process_file(file_path):
    """统计单个文件内每个类别的实例数"""
    local_counts = defaultdict(int)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    cid = int(parts[0])
                    if cid in CLASS_MAP:
                        local_counts[CLASS_MAP[cid]] += 1
                except:
                    pass
    except:
        pass
    return local_counts

def analyze_single_folder(folder_path):
    folder_name = os.path.basename(os.path.normpath(folder_path))
    if not os.path.isdir(folder_path):
        print(f"跳过: '{folder_name}' 不是一个有效文件夹。")
        return

    txt_files = [os.path.join(folder_path, f)
                 for f in os.listdir(folder_path)
                 if f.lower().endswith('.txt')]
    if not txt_files:
        print(f"文件夹 '{folder_name}' 中未找到 .txt 文件。")
        return

    # 1. 准备输出目录：<script_dir>/<folder_name>_analysis_results/
    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    output_dir = os.path.join(script_dir, f"{folder_name}_analysis_results")
    os.makedirs(output_dir, exist_ok=True)

    # 2. 在输出目录下创建详细标签数子文件夹
    detailed_dir = os.path.join(output_dir, "详细标签数")
    os.makedirs(detailed_dir, exist_ok=True)

    # 准备统计容器
    final_counts = defaultdict(int)
    class_to_files = defaultdict(list)
    empty_count = 0
    empty_files = []

    # 多线程处理
    with concurrent.futures.ThreadPoolExecutor(MAX_WORKERS) as executor:
        futures = { executor.submit(process_file, fp): fp for fp in txt_files }
        for future in tqdm(concurrent.futures.as_completed(futures),
                           total=len(txt_files),
                           desc=f"分析 {folder_name}",
                           unit="个文件"):
            fp = futures[future]
            basename = os.path.basename(fp)
            counts = future.result()

            # 分类统计
            if counts:
                for cls, num in counts.items():
                    final_counts[cls] += num
                    class_to_files[cls].append(basename)
            else:
                empty_count += 1
                empty_files.append(basename)

            # === 生成详细标签数文件 ===
            name_root = os.path.splitext(basename)[0]
            if counts:
                # 按 CLASS_MAP 顺序
                for cid in sorted(CLASS_MAP):
                    cname = CLASS_MAP[cid]
                    if cname in counts:
                        name_root += f"_{cname}={counts[cname]:02d}"
            else:
                name_root += "_空"
            target = os.path.join(detailed_dir, name_root + ".txt")
            shutil.copy(fp, target)

    # 构建汇总报告
    lines = []
    total_inst = sum(final_counts.values())
    header = (UI_TEXT['class'], UI_TEXT['images'], UI_TEXT['instances'])
    total_row = (UI_TEXT['all'], len(txt_files), total_inst)
    rows = [total_row]
    for cid in sorted(CLASS_MAP):
        cname = CLASS_MAP[cid]
        if cname in final_counts:
            rows.append((cname,
                         len(class_to_files[cname]),
                         final_counts[cname]))
    # 空TXT行
    rows.append((UI_TEXT['empty'], empty_count, 0))

    # 计算列宽
    w1 = max(get_display_width(r[0]) for r in [header] + rows)
    w2 = max(get_display_width(r[1]) for r in [header] + rows)
    w3 = max(get_display_width(r[2]) for r in [header] + rows)

    def fmt(a,b,c):
        return (
            str(a) + ' '*(w1-get_display_width(a)) + '    ' +
            ' '*(w2-get_display_width(b)) + str(b) + '    ' +
            ' '*(w3-get_display_width(c)) + str(c)
        )

    lines.append(fmt(*header))
    lines.append('-'*(w1+w2+w3+8))
    for r in rows:
        lines.append(fmt(*r))

    # 打印到命令行
    print(f"\n--- 文件夹 '{folder_name}' 分析报告 ---")
    for l in lines:
        print(l)

    # 写入报告文件
    report_path = os.path.join(output_dir, "00_summary_report.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"分析文件夹: {folder_path}\n\n")
        f.write('\n'.join(lines))

    # 各类别文件列表
    for cls, files in class_to_files.items():
        with open(os.path.join(output_dir, f"{cls}.txt"), 'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(files)))
    # 空文件列表
    if empty_files:
        with open(os.path.join(output_dir, f"{UI_TEXT['empty']}.txt"),
                  'w', encoding='utf-8') as f:
            f.write('\n'.join(sorted(empty_files)))

    print(f"\n[✓] 所有报告已保存至: {output_dir}")
    print(f"[✓] 详细标签数文件夹: {detailed_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用：将一个或多个包含 .txt 的文件夹拖入此脚本上。")
        sys.exit(1)

    for folder in sys.argv[1:]:
        print(f"\n========== 处理: {folder} ==========")
        analyze_single_folder(folder)
        print()
    print("所有任务结束。")
