import os
import sys
import json
from collections import defaultdict

# ==============================================================================
# ========================== 配置区：类别映射与扩展值 ===========================
# ==============================================================================

# 1) 每个类别的预设像素调整值（上、下、左、右）
#    - 值可为整数或浮点数
#    - 正数 = 向外扩展；负数 = 向内收缩
EXPAND_VALUES = {
    0: (-40, -50, -50, -30),  # 示例：balloon（按需修改）
    1: (0, 0, 0, 1.5),        # qipao
    2: (0, 0, 0, 0),          # fangkuai
    3: (0, 0, 0, 0),          # changfangtiao
    4: (0, 0, 0, 0),          # kuangwai
    5: (0, 0, 0, 0),          # other
    6: (0, 0, 0, 0),          # balloon2
    7: (0, 0, 0, 0),          # qipao2
    8: (0, 0, 0, 0),          # changfangtiao2
}

# 2) 可选：标签名 → 类别索引映射
LABEL_TO_CLASS = {
    "balloon": 0,
    "qipao": 1,
    "fangkuai": 2,
    "changfangtiao": 3,
    "kuangwai": 4,
    "other": 5,
    "balloon2": 6,
    "qipao2": 7,
    "changfangtiao2": 8,
}

# 3) 默认类别（既无 class_id 也无法通过 label 映射时使用）
DEFAULT_CLASS_ID = 0

# 4) 边界限制与调试选项
BOUNDARY_OPTIONS = {
    "keep_within_image": False,  # 是否限制调整后不能超过图像边界
    "min_width": 5,              # 最小宽度
    "min_height": 5,             # 最小高度
    "debug_mode": False,         # 是否打印更详细的调试信息
}

# --- 配置区结束 ---
# ==============================================================================


def get_image_dimensions_and_shapes(data):
    """
    兼容两种文件结构，返回 (img_w, img_h, shapes, structure_type, root_ref)
    - structure_type: 'dict' 或 'list'
    - root_ref: 用于写回时的引用（dict 或 list）
    """
    if isinstance(data, dict):
        img_w = data.get('imageWidth', None)
        img_h = data.get('imageHeight', None)
        shapes = data.get('shapes', [])
        if not isinstance(shapes, list):
            shapes = []
        return img_w, img_h, shapes, 'dict', data
    elif isinstance(data, list):
        return None, None, data, 'list', data
    else:
        return None, None, None, 'unknown', data


def get_box_from_points(points):
    """
    从点集计算边界框 [x_min, y_min, x_max, y_max]。
    支持两点或四点的矩形表示。
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]


def box_to_points(box):
    """
    将边界框转换为矩形四顶点（左上、右上、右下、左下）。
    """
    x_min, y_min, x_max, y_max = box
    return [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]


def box_size(box):
    """
    计算边界框的宽度与高度。
    """
    x_min, y_min, x_max, y_max = box
    return x_max - x_min, y_max - y_min


def get_class_id_for_shape(shape):
    """
    解析类别索引（优先 class_id/category_id，再用 label 映射，否则默认）。
    """
    for key in ('class_id', 'category_id'):
        if key in shape:
            try:
                return int(shape[key])
            except Exception:
                pass
    label = str(shape.get('label', '')).strip()
    if label:
        key = label.lower()
        if key in LABEL_TO_CLASS:
            return LABEL_TO_CLASS[key]
    return DEFAULT_CLASS_ID


def class_margins(class_id):
    """
    将 EXPAND_VALUES 的元组转换为字典。
    """
    t, b, l, r = EXPAND_VALUES.get(class_id, EXPAND_VALUES.get(DEFAULT_CLASS_ID, (0, 0, 0, 0)))
    return {"top": float(t), "bottom": float(b), "left": float(l), "right": float(r)}


def margins_str(m):
    return f"上{m['top']} 下{m['bottom']} 左{m['left']} 右{m['right']}"


def box_str(box):
    w, h = box_size(box)
    return f"[{box[0]:.2f}, {box[1]:.2f}, {box[2]:.2f}, {box[3]:.2f}] (宽{w:.2f}×高{h:.2f})"


def adjust_box(box, margins, image_w=None, image_h=None):
    """
    应用边距调整并执行边界/最小尺寸限制。
    返回：new_box, constrained(bool), notes(list)
    """
    x_min, y_min, x_max, y_max = box
    notes = []
    constrained = False

    # 1) 应用扩展值（正数向外扩）
    nx_min = x_min - margins["left"]
    ny_min = y_min - margins["top"]
    nx_max = x_max + margins["right"]
    ny_max = y_max + margins["bottom"]

    # 2) 限制在图像内（可选；若无图像尺寸则不启用裁剪）
    if BOUNDARY_OPTIONS["keep_within_image"] and image_w is not None and image_h is not None:
        if nx_min < 0:
            nx_min = 0
            constrained = True
            notes.append("x_min 裁剪至 0")
        if ny_min < 0:
            ny_min = 0
            constrained = True
            notes.append("y_min 裁剪至 0")
        if nx_max > image_w:
            nx_max = image_w
            constrained = True
            notes.append(f"x_max 裁剪至 {image_w}")
        if ny_max > image_h:
            ny_max = image_h
            constrained = True
            notes.append(f"y_max 裁剪至 {image_h}")

    # 3) 最小尺寸限制
    min_w = BOUNDARY_OPTIONS["min_width"]
    min_h = BOUNDARY_OPTIONS["min_height"]
    cur_w = nx_max - nx_min
    cur_h = ny_max - ny_min

    if cur_w < min_w:
        cx = (nx_min + nx_max) / 2
        nx_min = cx - min_w / 2
        nx_max = cx + min_w / 2
        constrained = True
        notes.append(f"宽度不足(min={min_w})，围绕中心扩展")

    if cur_h < min_h:
        cy = (ny_min + ny_max) / 2
        ny_min = cy - min_h / 2
        ny_max = cy + min_h / 2
        constrained = True
        notes.append(f"高度不足(min={min_h})，围绕中心扩展")

    return [nx_min, ny_min, nx_max, ny_max], constrained, notes


def process_file(file_path, global_stats):
    """
    处理单个 JSON 文件：
    - 读取文件并兼容 dict/list 结构
    - 对 rectangle 类型的 shape 应用扩展值
    - 打印每个框的简要信息
    - 回写 JSON
    - 更新全局统计（仅计数，不打印）
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  - 错误: 读取文件 '{os.path.basename(file_path)}' 失败: {e}")
        return False

    img_w, img_h, shapes, structure_type, root_ref = get_image_dimensions_and_shapes(data)

    if structure_type == 'unknown' or shapes is None:
        print(f"  - 跳过: {os.path.basename(file_path)} (不支持的 JSON 结构：{type(data).__name__})")
        return False

    img_size_str = f"{img_w}x{img_h}" if (img_w is not None and img_h is not None) else "未知"
    print(f"  - 处理: {os.path.basename(file_path)} (结构: {structure_type}, 图像尺寸: {img_size_str}, 框数: {len(shapes)})")

    modified = 0
    skipped_not_rect = 0
    skipped_no_change = 0

    # 统计容器（不打印，只用于全局计数）
    per_label = defaultdict(lambda: {"count": 0, "sum_top": 0.0, "sum_bottom": 0.0, "sum_left": 0.0, "sum_right": 0.0})
    per_class = defaultdict(lambda: {"count": 0, "sum_top": 0.0, "sum_bottom": 0.0, "sum_left": 0.0, "sum_right": 0.0})

    for idx, shape in enumerate(shapes, start=1):
        if not isinstance(shape, dict):
            skipped_not_rect += 1
            if BOUNDARY_OPTIONS["debug_mode"]:
                print(f"    跳过: 索引{idx} - 非 dict 结构的 shape")
            continue

        label = str(shape.get('label', '')).strip()
        shape_type = str(shape.get('shape_type', '')).strip().lower()
        points = shape.get('points', None)

        if not shape_type and isinstance(points, list) and len(points) in (2, 4):
            shape_type = 'rectangle'

        if shape_type != 'rectangle' or not points:
            skipped_not_rect += 1
            if BOUNDARY_OPTIONS["debug_mode"]:
                print(f"    跳过: 框{idx} ({label}) - 非 rectangle 或缺少 points")
            continue

        class_id = get_class_id_for_shape(shape)
        margins = class_margins(class_id)

        # 若四边均为 0，则跳过
        if margins["top"] == 0 and margins["bottom"] == 0 and margins["left"] == 0 and margins["right"] == 0:
            skipped_no_change += 1
            if BOUNDARY_OPTIONS["debug_mode"]:
                print(f"    跳过: 框{idx} ({label}|class={class_id}) - 扩展值为 0")
            continue

        original_box = get_box_from_points(points)
        new_box, constrained, notes = adjust_box(original_box, margins, img_w, img_h)

        # 写回新点
        shape['points'] = box_to_points(new_box)
        modified += 1

        # 统计（不打印）
        per_label[label]["count"] += 1
        per_label[label]["sum_top"] += margins["top"]
        per_label[label]["sum_bottom"] += margins["bottom"]
        per_label[label]["sum_left"] += margins["left"]
        per_label[label]["sum_right"] += margins["right"]

        per_class[class_id]["count"] += 1
        per_class[class_id]["sum_top"] += margins["top"]
        per_class[class_id]["sum_bottom"] += margins["bottom"]
        per_class[class_id]["sum_left"] += margins["left"]
        per_class[class_id]["sum_right"] += margins["right"]

        # 逐框输出（保留）
        print(f"    处理标签 {label if label else '(无标签)'} (class={class_id})")
        print(f"    原始: {box_str(original_box)}")
        print(f"    扩展: {box_str(new_box)}")
        print(f"    扩展值: {margins_str(margins)}")

        # 附加详细（可选）
        if constrained or BOUNDARY_OPTIONS["debug_mode"]:
            dx_left = original_box[0] - new_box[0]
            dy_top = original_box[1] - new_box[1]
            dx_right = new_box[2] - original_box[2]
            dy_bottom = new_box[3] - original_box[3]
            print(f"      触发限制: {'是' if constrained else '否'}")
            print(f"      变化量: 左{dx_left:.2f} 上{dy_top:.2f} 右{dx_right:.2f} 下{dy_bottom:.2f}")
            if notes:
                print(f"      限制详情: " + "；".join(notes))
            if BOUNDARY_OPTIONS["keep_within_image"] and (img_w is None or img_h is None):
                print("      提示: 缺少图像尺寸，已跳过边界裁剪")

    # 写回 JSON：保持原结构
    try:
        if structure_type == 'dict':
            root_ref['shapes'] = shapes
        elif structure_type == 'list':
            pass
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(root_ref, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  - 错误: 写入文件 '{os.path.basename(file_path)}' 失败: {e}")
        return False

    # 不打印“完成: 成功调整了 X …”这句，保持安静
    # 更新全局计数（仅用于最终总计行）
    global_stats["processed_files"] += 1

    return True


def main():
    """
    主入口：
    - 支持拖拽模式与双击模式。
    - 显示当前配置与选项。
    - 对每个 JSON 执行处理并输出逐框明细。
    """
    print("="*70)
    print("标注框边距扩展脚本（按类别 EXPAND_VALUES 配置）")
    print("="*70)

    # 打印配置
    print("类别扩展值 EXPAND_VALUES：")
    for cid in sorted(EXPAND_VALUES.keys()):
        t, b, l, r = EXPAND_VALUES[cid]
        print(f"  类别 {cid}: 上{t:+}, 下{b:+}, 左{l:+}, 右{r:+}")
    print("标签到类别映射 LABEL_TO_CLASS：")
    if LABEL_TO_CLASS:
        for k, v in LABEL_TO_CLASS.items():
            print(f"  标签 '{k}' -> 类别 {v}")
    else:
        print("  （未配置映射，若 shape 无 class_id 将使用 DEFAULT_CLASS_ID）")

    print(f"默认类别: {DEFAULT_CLASS_ID}")
    print(f"边界限制: {'开启' if BOUNDARY_OPTIONS['keep_within_image'] else '关闭'}")
    print(f"最小尺寸: {BOUNDARY_OPTIONS['min_width']} x {BOUNDARY_OPTIONS['min_height']}")
    print(f"调试模式: {'开启' if BOUNDARY_OPTIONS['debug_mode'] else '关闭'}")
    print("="*70 + "\n")

    # 收集待处理 JSON
    targets = []
    if len(sys.argv) > 1:
        print("进入 [拖拽模式] - 仅处理传入的文件/文件夹...")
        uniq = set()
        for p in sys.argv[1:]:
            p = p.strip('"')
            if os.path.isfile(p) and p.lower().endswith('.json'):
                uniq.add(os.path.abspath(p))
                print(f"  添加文件: {os.path.basename(p)}")
            elif os.path.isdir(p):
                print(f"  扫描文件夹: {p}")
                for root, _, files in os.walk(p):
                    for fn in files:
                        if fn.lower().endswith('.json'):
                            full = os.path.join(root, fn)
                            uniq.add(os.path.abspath(full))
                            print(f"    发现文件: {fn}")
        targets = sorted(list(uniq))
    else:
        print("进入 [双击模式] - 扫描脚本所在目录...")
        try:
            work_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            work_dir = os.getcwd()
        print(f"扫描目录: {work_dir}")
        try:
            for fn in os.listdir(work_dir):
                if fn.lower().endswith('.json'):
                    full = os.path.join(work_dir, fn)
                    targets.append(full)
                    print(f"  发现文件: {fn}")
        except Exception as e:
            print(f"错误: 无法访问目录 {work_dir}: {e}")
            input("按 Enter 键退出...")
            return

    if not targets:
        print("\n未找到任何 .json 文件。")
        input("按 Enter 键退出...")
        return

    print(f"\n总计找到 {len(targets)} 个 JSON 文件，开始处理...\n")

    # 全局统计（仅计数）
    global_stats = {
        "processed_files": 0
    }

    for path in targets:
        if path.endswith('.py'):
            continue
        process_file(path, global_stats)

    # 结尾仅保留三行 + “按 Enter 键退出...”
    print("\n" + "="*50)
    print(f"处理完成！总共成功修改了 {global_stats['processed_files']} 个 JSON 文件。")
    print("="*50)
    input("按 Enter 键退出...")


if __name__ == "__main__":
    main()