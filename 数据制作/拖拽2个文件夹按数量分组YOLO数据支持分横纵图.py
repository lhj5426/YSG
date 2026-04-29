import os
import re
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path
from PIL import Image


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff", ".avif", ".jxl"
}
DEFAULT_GROUP_SIZE = 1000
FILE_ACTION = "copy"  # 可改成 "move"
ENABLE_ORIENTATION_SPLIT = True  # True=按横竖分子文件夹，False=直接混放到分组文件夹里
ACTIVE_PROGRESS_TRACKER = None


def log(message=""):
    global ACTIVE_PROGRESS_TRACKER
    if ACTIVE_PROGRESS_TRACKER and not ACTIVE_PROGRESS_TRACKER.finished:
        ACTIVE_PROGRESS_TRACKER.clear_line()
        print(message, flush=True)
        ACTIVE_PROGRESS_TRACKER.render(force=True)
    else:
        print(message, flush=True)


def pause_and_exit(message="", code=0):
    if message:
        log(message)
    wait_for_exit()
    raise SystemExit(code)


def natural_key(text):
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def wait_for_exit():
    try:
        if sys.stdin.isatty():
            input("按回车键退出...")
    except EOFError:
        pass


class ProgressTracker:
    def __init__(self, total, prefix, width=30, min_interval=0.2):
        global ACTIVE_PROGRESS_TRACKER
        self.total = max(total, 1)
        self.prefix = prefix
        self.width = width
        self.min_interval = min_interval
        self.current = 0
        self.last_print_time = 0.0
        self.finished = False
        ACTIVE_PROGRESS_TRACKER = self
        self.render(force=True)

    def advance(self, step=1):
        self.current += step
        now = time.monotonic()
        if self.current >= self.total:
            self.current = self.total
            self.render(force=True)
            if not self.finished:
                self.clear_line()
                self.render(force=True)
                print(flush=True)
                self.finished = True
                self.deactivate()
            return
        if now - self.last_print_time >= self.min_interval:
            self.render()

    def render(self, force=False):
        if self.finished:
            return
        ratio = self.current / self.total
        filled = int(self.width * ratio)
        bar = "█" * filled + "░" * (self.width - filled)
        text = f"\r{self.prefix}: [{bar}] {ratio * 100:5.1f}% ({self.current}/{self.total})"
        print(text, end="", flush=True)
        if force:
            self.last_print_time = time.monotonic()

    def clear_line(self):
        print("\r" + " " * 140 + "\r", end="", flush=True)

    def deactivate(self):
        global ACTIVE_PROGRESS_TRACKER
        if ACTIVE_PROGRESS_TRACKER is self:
            ACTIVE_PROGRESS_TRACKER = None


def is_image_file(path):
    return path.suffix.lower() in IMAGE_EXTENSIONS


def is_txt_file(path):
    return path.suffix.lower() == ".txt"


def scan_folder(folder):
    log(f"正在统计扫描总量: {folder}")
    entries = list(folder.iterdir())
    tracker = ProgressTracker(len(entries), f"正在扫描: {folder.name}")
    image_files = []
    txt_files = []

    for item in entries:
        if item.is_file():
            if is_image_file(item):
                image_files.append(item)
            elif is_txt_file(item):
                txt_files.append(item)
        tracker.advance()

    log(f"扫描完成: {folder.name}  ->  图片 {len(image_files)} / TXT {len(txt_files)}")
    return {
        "folder": folder,
        "image_files": image_files,
        "txt_files": txt_files,
    }


def detect_folders(folder1, folder2):
    log("正在扫描你拖进来的两个文件夹，请稍等...")
    folder1_info = scan_folder(folder1)
    folder2_info = scan_folder(folder2)
    folder1_images = folder1_info["image_files"]
    folder1_txts = folder1_info["txt_files"]
    folder2_images = folder2_info["image_files"]
    folder2_txts = folder2_info["txt_files"]

    log(f"检测到文件夹 1: {folder1}")
    log(f"  图片数量: {len(folder1_images)}")
    log(f"  TXT 数量: {len(folder1_txts)}")
    log(f"检测到文件夹 2: {folder2}")
    log(f"  图片数量: {len(folder2_images)}")
    log(f"  TXT 数量: {len(folder2_txts)}")

    folder1_more_like_images = len(folder1_images) > 0 and len(folder1_images) >= len(folder1_txts)
    folder2_more_like_images = len(folder2_images) > 0 and len(folder2_images) >= len(folder2_txts)
    folder1_more_like_txt = len(folder1_txts) > 0 and len(folder1_txts) >= len(folder1_images)
    folder2_more_like_txt = len(folder2_txts) > 0 and len(folder2_txts) >= len(folder2_images)

    if folder1_more_like_images and folder2_more_like_txt and not folder2_more_like_images:
        return folder1_info, folder2_info

    if folder2_more_like_images and folder1_more_like_txt and not folder1_more_like_images:
        return folder2_info, folder1_info

    if len(folder1_images) > 0 and len(folder2_txts) > 0 and len(folder2_images) == 0:
        return folder1_info, folder2_info

    if len(folder2_images) > 0 and len(folder1_txts) > 0 and len(folder1_images) == 0:
        return folder2_info, folder1_info

    pause_and_exit(
        "无法可靠判断哪个是图片文件夹、哪个是 TXT 文件夹。\n"
        "请确保你拖进来的是 1 个图片文件夹 + 1 个标签 TXT 文件夹。"
    )


def build_file_map(files):
    file_map = {}
    duplicates = []

    for file_path in sorted(files, key=lambda item: natural_key(item.name)):
        stem = file_path.stem
        if stem in file_map:
            duplicates.append(stem)
            continue
        file_map[stem] = file_path

    return file_map, duplicates


def ask_group_size():
    if len(sys.argv) >= 4:
        raw_value = sys.argv[3].strip()
        if raw_value.isdigit() and int(raw_value) > 0:
            return int(raw_value)
        log(f"第三个参数不是有效数字，将改为手动输入。收到: {raw_value}")

    while True:
        user_input = input(
            f"请输入每个文件夹放多少组图片+TXT（直接回车默认 {DEFAULT_GROUP_SIZE}）: "
        ).strip()
        if not user_input:
            return DEFAULT_GROUP_SIZE
        if user_input.isdigit() and int(user_input) > 0:
            return int(user_input)
        log("输入无效，请输入大于 0 的整数。")


def get_output_base_dir(folder1, folder2):
    common_path = Path(folder1).resolve()
    try:
        common_path = Path(os.path.commonpath([str(folder1), str(folder2)]))
    except ValueError:
        common_path = folder1.parent

    if common_path.is_file():
        common_path = common_path.parent

    return common_path


def create_output_root(base_dir):
    output_root = base_dir / "分组检查"
    if output_root.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_root = base_dir / f"分组检查_{timestamp}"
    output_root.mkdir(parents=True, exist_ok=True)
    return output_root


def transfer_file(source_path, target_path):
    if FILE_ACTION.lower() == "move":
        shutil.move(str(source_path), str(target_path))
    else:
        shutil.copy2(str(source_path), str(target_path))


def get_orientation_name(image_path):
    with Image.open(image_path) as image:
        width, height = image.size
    return "横图" if width >= height else "竖图"


def prepare_orientation_layout(chunk_names, image_map):
    orientation_groups = {
        "横图": [],
        "竖图": [],
    }

    for name in chunk_names:
        orientation = get_orientation_name(image_map[name])
        orientation_groups[orientation].append(name)

    orientation_dirs = {}
    for orientation, names in orientation_groups.items():
        if not names:
            continue
        orientation_dirs[orientation] = f"[{len(names)}]{orientation}"

    return orientation_groups, orientation_dirs


def export_unmatched_files(output_root, image_map, label_map, missing_labels, missing_images):
    image_only_dir = output_root / "只有图片没有TXT"
    txt_only_dir = output_root / "只有TXT没有图片"

    if missing_labels:
        image_only_dir.mkdir(parents=True, exist_ok=True)
        tracker = ProgressTracker(len(missing_labels), "正在处理未配对数据: 只有图片没有TXT")
        for name in missing_labels:
            transfer_file(image_map[name], image_only_dir / image_map[name].name)
            tracker.advance()
        log(f"已生成补漏文件夹: {image_only_dir.name}  ->  {len(missing_labels)} 个文件")

    if missing_images:
        txt_only_dir.mkdir(parents=True, exist_ok=True)
        tracker = ProgressTracker(len(missing_images), "正在处理未配对数据: 只有TXT没有图片")
        for name in missing_images:
            transfer_file(label_map[name], txt_only_dir / label_map[name].name)
            tracker.advance()
        log(f"已生成补漏文件夹: {txt_only_dir.name}  ->  {len(missing_images)} 个文件")


def write_missing_report(
    output_root,
    image_dir,
    label_dir,
    group_size,
    matched_names,
    missing_labels,
    missing_images,
    duplicate_images,
    duplicate_labels,
):
    report_path = output_root / "补漏清单.txt"
    lines = [
        "YOLO 分组补漏清单",
        "",
        f"图片文件夹: {image_dir}",
        f"TXT 文件夹: {label_dir}",
        f"每组数量: {group_size}",
        f"成功配对数量: {len(matched_names)}",
        f"只有图片没有TXT: {len(missing_labels)}",
        f"只有TXT没有图片: {len(missing_images)}",
        f"重复图片文件名数量: {len(duplicate_images)}",
        f"重复TXT文件名数量: {len(duplicate_labels)}",
        "",
        "=== 只有图片没有TXT ===",
    ]

    if missing_labels:
        for name in missing_labels:
            lines.append(name)
    else:
        lines.append("无")

    lines.extend(["", "=== 只有TXT没有图片 ==="])
    if missing_images:
        for name in missing_images:
            lines.append(name)
    else:
        lines.append("无")

    lines.extend(["", "=== 重复图片文件名（不含后缀） ==="])
    if duplicate_images:
        for name in duplicate_images:
            lines.append(name)
    else:
        lines.append("无")

    lines.extend(["", "=== 重复TXT文件名（不含后缀） ==="])
    if duplicate_labels:
        for name in duplicate_labels:
            lines.append(name)
    else:
        lines.append("无")

    report_path.write_text("\n".join(lines), encoding="utf-8-sig")
    log(f"已生成补漏清单: {report_path.name}")


def split_pairs(image_dir, label_dir, image_files, txt_files, group_size, output_base_dir):
    log("正在建立图片索引...")
    image_map, duplicate_images = build_file_map(image_files)
    log("正在建立 TXT 索引...")
    label_map, duplicate_labels = build_file_map(txt_files)

    matched_names = sorted(set(image_map) & set(label_map), key=natural_key)
    missing_labels = sorted(set(image_map) - set(label_map), key=natural_key)
    missing_images = sorted(set(label_map) - set(image_map), key=natural_key)

    log(f"\n成功匹配到 {len(matched_names)} 组图片 + TXT。")
    log(f"只有图片没有 TXT 的数量: {len(missing_labels)}")
    log(f"只有 TXT 没有图片的数量: {len(missing_images)}")

    if duplicate_images:
        log(f"警告: 发现重复图片文件名（不含后缀）{len(duplicate_images)} 个，已跳过重复项。")
    if duplicate_labels:
        log(f"警告: 发现重复 TXT 文件名（不含后缀）{len(duplicate_labels)} 个，已跳过重复项。")

    output_root = create_output_root(output_base_dir)
    log(f"\n输出目录: {output_root}")
    log(f"文件处理方式: {FILE_ACTION}")

    export_unmatched_files(output_root, image_map, label_map, missing_labels, missing_images)
    if missing_labels or missing_images or duplicate_images or duplicate_labels:
        write_missing_report(
            output_root,
            image_dir,
            label_dir,
            group_size,
            matched_names,
            missing_labels,
            missing_images,
            duplicate_images,
            duplicate_labels,
        )

    if not matched_names:
        log("\n没有找到同名的图片和 TXT，本次只生成了补漏文件夹。")
        return

    log("\n开始处理正常配对的数据...")
    overall_tracker = ProgressTracker(len(matched_names), "正在处理正常配对数据")

    for start_index in range(0, len(matched_names), group_size):
        chunk_names = matched_names[start_index:start_index + group_size]
        end_number = start_index + len(chunk_names)
        chunk_dir = output_root / str(end_number)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        if ENABLE_ORIENTATION_SPLIT:
            orientation_groups, orientation_dirs = prepare_orientation_layout(chunk_names, image_map)

            for folder_name in orientation_dirs.values():
                (chunk_dir / folder_name).mkdir(parents=True, exist_ok=True)

            for orientation in ("横图", "竖图"):
                names = orientation_groups[orientation]
                if not names:
                    continue
                target_dir = chunk_dir / orientation_dirs[orientation]
                for name in names:
                    transfer_file(image_map[name], target_dir / image_map[name].name)
                    transfer_file(label_map[name], target_dir / label_map[name].name)
                    overall_tracker.advance()

            horizontal_count = len(orientation_groups["横图"])
            vertical_count = len(orientation_groups["竖图"])
            log(
                f"已完成文件夹: {chunk_dir.name}  ->  {len(chunk_names)} 组"
                f"（横图 {horizontal_count} / 竖图 {vertical_count}）"
            )
        else:
            for name in chunk_names:
                transfer_file(image_map[name], chunk_dir / image_map[name].name)
                transfer_file(label_map[name], chunk_dir / label_map[name].name)
                overall_tracker.advance()

            log(f"已完成文件夹: {chunk_dir.name}  ->  {len(chunk_names)} 组")

    log("\n处理完成。")
    log("说明:")
    log("1. 每 1 组 = 1 张图片 + 1 个同名 TXT。")
    if ENABLE_ORIENTATION_SPLIT:
        log("2. 当前已开启横竖分组：每个分组号文件夹里，会再按横竖分成两个子文件夹。")
        log("3. 横竖规则和你给的脚本一致：宽 >= 高算横图，宽 < 高算竖图。")
        log("4. 横竖子文件夹名称会带数量，例如 [300]横图、[700]竖图。")
        log("5. 文件夹名称 1000 / 2000 / 3000... 表示当前累计分到第多少组。")
        log("6. 最后一个文件夹如果不足设定数量，也会单独创建。")
        missing_label_line = 7
        missing_image_line = 8
        missing_summary_line = 9
    else:
        log("2. 当前未开启横竖分组：每个分组号文件夹里直接混放图片和对应 TXT。")
        log("3. 文件夹名称 1000 / 2000 / 3000... 表示当前累计分到第多少组。")
        log("4. 最后一个文件夹如果不足设定数量，也会单独创建。")
        missing_label_line = 5
        missing_image_line = 6
        missing_summary_line = 7
    if missing_labels:
        log(f"{missing_label_line}. 有 {len(missing_labels)} 张图片没找到同名 TXT，未参与分组。")
    if missing_images:
        log(f"{missing_image_line}. 有 {len(missing_images)} 个 TXT 没找到同名图片，未参与分组。")
    if missing_labels or missing_images:
        log(f"{missing_summary_line}. 缺失配对的数据已经单独放进补漏文件夹。")


def main():
    if len(sys.argv) < 3:
        pause_and_exit("请把 2 个文件夹一起拖到这个脚本上运行。")

    folder1 = Path(sys.argv[1]).resolve()
    folder2 = Path(sys.argv[2]).resolve()

    if not folder1.is_dir() or not folder2.is_dir():
        pause_and_exit("拖入的参数里有不是文件夹的内容，请重新拖拽 2 个文件夹。")

    image_info, label_info = detect_folders(folder1, folder2)
    image_dir = image_info["folder"]
    label_dir = label_info["folder"]
    image_files = image_info["image_files"]
    txt_files = label_info["txt_files"]

    log(f"\n识别结果:")
    log(f"图片文件夹: {image_dir}")
    log(f"TXT 文件夹: {label_dir}")

    group_size = ask_group_size()
    log(f"每个文件夹分组数量: {group_size}")

    output_base_dir = get_output_base_dir(folder1, folder2)
    split_pairs(image_dir, label_dir, image_files, txt_files, group_size, output_base_dir)
    log()
    wait_for_exit()


if __name__ == "__main__":
    main()
