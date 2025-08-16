import os
import sys
import json
import copy

# ==============================================================================
# ======================== 配置区: 在这里设置你的区域合并规则 ========================
# ==============================================================================

# 合并模式：
# - "VERTICAL" 仅按垂直方向规则合并（推荐你当前的需求）
# - "HORIZONTAL" 仅按水平方向规则合并
# - "VERTICAL_THEN_HORIZONTAL" 先垂直合并一轮，再水平合并一轮
# - "HORIZONTAL_THEN_VERTICAL" 先水平合并一轮，再垂直合并一轮
# - "NONE" 不进行任何合并
MERGE_MODE = "VERTICAL"

# 从不参与合并的标签（黑名单）：一旦任一框的标签命中此集合，直接不允许与其它框合并
LABELS_TO_EXCLUDE_FROM_MERGE = {"other"}

# 是否启用“特定标签组”合并机制：
# - True：只有在同一组内的标签才允许互相合并（例如 ["balloon", "balloon2"]）
# - False：不使用分组；此时是否要求相同标签由 REQUIRE_SAME_LABEL 决定
USE_SPECIFIC_MERGE_GROUPS = False

# 指定可互相合并的标签组，只有 USE_SPECIFIC_MERGE_GROUPS = True 时才生效
SPECIFIC_MERGE_GROUPS = [
    ["balloon", "balloon2"],
    # ["qipao", "qipao2"],
    # ["changfangtiao", "changfangtiao2"],
]

# 当未启用 SPECIFIC_MERGE_GROUPS 时，是否要求两个 shape 标签完全一致才允许合并
REQUIRE_SAME_LABEL = False

# 合并后如何确定新 shape 的标签：
# - "FIRST": 直接采用第一个框的标签
# - "COMBINE": 若两者不同，使用 "label1+label2"
# - "PREFER_NON_DEFAULT": 优先使用非默认/空标签
# - "PREFER_SHORTER": 两者不同取更短的标签字符串
LABEL_MERGE_STRATEGY = "PREFER_SHORTER"

# 垂直合并参数（当 MERGE_MODE 为纯垂直时主要参考此处）
VERTICAL_MERGE_PARAMS = {
    # 最大垂直间隙（像素）。两个框在垂直方向上的缝隙不能超过此值；
    # 若允许负间隙（allow_negative_gap=True），则重叠（gap<0）也可视作满足此条件。
    "max_vertical_gap": 3,
    # 最小水平重叠比例（百分比）。计算方式：水平重叠宽度 / 两框中较窄框的宽度 * 100%。
    # 为了应对浮点误差，实际比较时会加入 overlap_epsilon 容差。
    "min_width_overlap_ratio": 95,
    # 水平重叠比例计算的容差（像素）。避免 100% 重叠因浮点误差被判为 99.999%。
    "overlap_epsilon": 1e-6,
}

# 水平合并参数（结构保留；若 MERGE_MODE=VERTICAL 则不会使用）
HORIZONTAL_MERGE_PARAMS = {
    # 最大水平间隙（像素）
    "max_horizontal_gap": 10,
    # 最小垂直重叠比例（百分比）：垂直重叠高度 / 两框中较矮框的高度 * 100%
    "min_height_overlap_ratio": 10,
    # 垂直重叠比例计算的容差（像素）
    "overlap_epsilon": 1e-6,
}

# 是否合并包含关系（注：在纯垂直合并中，若重叠与间隙条件满足，包含关系自然可被合并）
MERGE_CONTAINED_BOXES = True  # 目前逻辑中未单独分支处理，留作语义说明

# 高级选项
ADVANCED_MERGE_OPTIONS = {
    # 注意：本脚本在纯垂直模式下仍严格按 vertical_can_merge 判定。
    # 这里的 merge_any_overlap 标志保留但不作为“任意重叠即合并”的捷径。
    "merge_any_overlap": True,
    # 是否允许负间隙（即原本就有重叠）
    "allow_negative_gap": True,
    # 调试输出开关：打印详细的重叠与间隙信息
    "debug_mode": False,
}
# --- 配置区结束 ---
# ==============================================================================


def get_bounding_box(shape):
    """
    根据 shape['points'] 计算外接矩形 [x_min, y_min, x_max, y_max]。
    假设 points 是一组二维坐标点，通常为矩形四点或多边形顶点。
    """
    points = shape['points']
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]
    return [min(x_coords), min(y_coords), max(x_coords), max(y_coords)]


def get_merge_group_for_label(label):
    """
    若启用 USE_SPECIFIC_MERGE_GROUPS，则返回 label 所属的合并组编号（下标）。
    - 未命中任何组则返回 -1
    - 当 USE_SPECIFIC_MERGE_GROUPS=False 时，始终返回 -1
    """
    if not USE_SPECIFIC_MERGE_GROUPS:
        return -1
    for idx, group in enumerate(SPECIFIC_MERGE_GROUPS):
        if label in group:
            return idx
    return -1


def can_labels_merge(label1, label2):
    """
    仅进行标签层面的规则检查（不包含几何关系）。
    规则顺序：
    1) 黑名单：任一标签命中黑名单 -> 不允许合并
    2) 若启用“特定标签组”：仅当两标签处于同一组 -> 允许合并
    3) 否则，若 REQUIRE_SAME_LABEL=True：要求两标签相同 -> 允许合并
    4) 否则：不要求相同标签 -> 允许合并
    """
    # 黑名单拦截
    if label1 in LABELS_TO_EXCLUDE_FROM_MERGE or label2 in LABELS_TO_EXCLUDE_FROM_MERGE:
        return False

    # 按“特定标签组”规则
    if USE_SPECIFIC_MERGE_GROUPS:
        g1 = get_merge_group_for_label(label1)
        g2 = get_merge_group_for_label(label2)
        return g1 != -1 and g1 == g2

    # 普通模式：是否要求相同标签
    if REQUIRE_SAME_LABEL:
        return label1 == label2
    return True


def merge_labels(label1, label2, strategy):
    """
    根据 LABEL_MERGE_STRATEGY 合并两个标签，返回新标签字符串。
    """
    if strategy == "FIRST":
        return label1
    elif strategy == "COMBINE":
        return label1 if label1 == label2 else f"{label1}+{label2}"
    elif strategy == "PREFER_NON_DEFAULT":
        # 若某一方为默认/空标签，则优先选择非默认的一方
        default_labels = {"label", ""}
        if label1 in default_labels and label2 not in default_labels:
            return label2
        if label2 in default_labels and label1 not in default_labels:
            return label1
        return label1
    elif strategy == "PREFER_SHORTER":
        # 若相同直接返回；否则取长度更短的标签
        if label1 == label2:
            return label1
        return label1 if len(label1) <= len(label2) else label2
    else:
        # 未知策略时回退到第一个标签
        return label1


def create_shape_from_box(box, shape1, shape2):
    """
    根据合并后的外接矩形 box 与两个参考 shape 生成一个新的 shape。
    - points：按 x_min,y_min -> x_max,y_min -> x_max,y_max -> x_min,y_max 顺序给出四角
    - label：根据 LABEL_MERGE_STRATEGY 合并 shape1/shape2 的 label
    - 其他元数据：沿用 shape1 的字段（通过 deepcopy 保留）
    """
    new_shape = copy.deepcopy(shape1)
    x_min, y_min, x_max, y_max = box
    new_shape['points'] = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
    new_shape['label'] = merge_labels(shape1.get('label', ''), shape2.get('label', ''), LABEL_MERGE_STRATEGY)
    return new_shape


def vertical_can_merge(box1, box2, params):
    """
    仅按“垂直”规则判断两个外接矩形是否可合并。
    条件同时满足：
      1) 水平重叠比例 >= min_width_overlap_ratio（含容差 epsilon）
      2) 垂直间隙 <= max_vertical_gap
         - 若 allow_negative_gap=True，重叠（gap<0）同样允许
         - 若 allow_negative_gap=False，仅允许 0 <= gap <= max_vertical_gap

    说明：
    - 水平重叠比例计算：overlap_x / min(width1, width2) * 100%
      其中 overlap_x 使用 max(0, min(x_max1,x_max2) - max(x_min1,x_min2)) 再加 epsilon 做容差修正。
    - 垂直间隙计算：max(y_min1, y_min2) - min(y_max1, y_max2)
      若为负，表示两个框在垂直方向已有重叠。
    """
    eps = params.get("overlap_epsilon", 0.0)

    # 计算水平重叠宽度
    overlap_x = max(0.0, min(box1[2], box2[2]) - max(box1[0], box2[0]))
    # 加入容差，缓解边界浮点误差
    overlap_x_adj = max(0.0, overlap_x + eps)

    width1 = max(0.0, box1[2] - box1[0])
    width2 = max(0.0, box2[2] - box2[0])
    # 防止除零：最小宽度下限取一个极小正值
    min_width = max(1e-6, min(width1, width2))

    overlap_ratio_w = (overlap_x_adj / min_width) * 100.0

    # 垂直间隙：若为负值，表示两个框在竖直方向上有重叠
    vertical_gap = max(box1[1], box2[1]) - min(box1[3], box2[3])

    if ADVANCED_MERGE_OPTIONS["debug_mode"]:
        print(f"      垂直判定: overlap_w={overlap_ratio_w:.2f}%, gap={vertical_gap:.3f}")

    # 水平重叠比例不足则直接不合并
    if overlap_ratio_w < params["min_width_overlap_ratio"]:
        return False

    # 间隙判断
    if ADVANCED_MERGE_OPTIONS["allow_negative_gap"]:
        # 允许重叠或小缝隙
        return vertical_gap <= params["max_vertical_gap"]
    else:
        # 仅允许非负且不超过阈值的缝隙
        return 0 <= vertical_gap <= params["max_vertical_gap"]


def can_merge_shapes(shape1, shape2, mode, params):
    """
    综合判断两个 shape 是否可合并（先标签、后几何）。
    在“纯垂直合并”要求下：
      - 先通过标签合并规则 can_labels_merge
      - 再在 mode == 'VERTICAL' 时使用 vertical_can_merge 判定
      - 若 mode 为其他，提供水平合并的保留逻辑（当脚本被配置为相应模式时才会用到）
    """
    # 1) 标签规则先行
    if not can_labels_merge(shape1.get('label', ''), shape2.get('label', '')):
        if ADVANCED_MERGE_OPTIONS["debug_mode"]:
            print(f"    跳过: 标签规则不允许 -> {shape1.get('label','')} vs {shape2.get('label','')}")
        return False

    # 2) 几何规则
    box1, box2 = get_bounding_box(shape1), get_bounding_box(shape2)

    if mode == "VERTICAL":
        return vertical_can_merge(box1, box2, params)
    else:
        # 水平模式的判定（当 MERGE_MODE=HORIZONTAL 或组合模式时才会用到）
        eps = HORIZONTAL_MERGE_PARAMS.get("overlap_epsilon", 0.0)

        # 垂直重叠高度
        overlap_y = max(0.0, min(box1[3], box2[3]) - max(box1[1], box2[1]))
        overlap_y_adj = max(0.0, overlap_y + eps)

        height1 = max(0.0, box1[3] - box1[1])
        height2 = max(0.0, box2[3] - box2[1])
        min_height = max(1e-6, min(height1, height2))
        overlap_ratio_h = (overlap_y_adj / min_height) * 100.0

        # 水平间隙
        horizontal_gap = max(box1[0], box2[0]) - min(box1[2], box2[2])

        if overlap_ratio_h < HORIZONTAL_MERGE_PARAMS["min_height_overlap_ratio"]:
            return False

        if ADVANCED_MERGE_OPTIONS["allow_negative_gap"]:
            return horizontal_gap <= HORIZONTAL_MERGE_PARAMS["max_horizontal_gap"]
        else:
            return 0 <= horizontal_gap <= HORIZONTAL_MERGE_PARAMS["max_horizontal_gap"]


def perform_merge(shapes, mode):
    """
    对输入的 shapes 执行一轮或多轮合并（根据给定的 mode）。
    过程：
      - 采用“贪心”扫描：从头开始，发现可合并对就合并为一个新 shape，
        替换原位置后重新从当前位置继续扫描；
      - 持续循环，直到本轮没有任何合并发生为止；
      - 返回合并完成后的 shapes 列表。

    注意：
      - 每次合并都将两个框的外接矩形包络为一个更大的矩形；
      - 标签按 LABEL_MERGE_STRATEGY 进行合并；
      - 合并顺序可能影响最终分组合并的数量（贪心特性）。
    """
    params = VERTICAL_MERGE_PARAMS if mode == "VERTICAL" else HORIZONTAL_MERGE_PARAMS

    merge_count = 0  # 记录本次调用内的合并次数
    while True:
        merged_in_pass = False  # 标记当前外层扫描是否发生了合并
        i = 0
        while i < len(shapes):
            j = i + 1
            while j < len(shapes):
                shape1, shape2 = shapes[i], shapes[j]

                # 判定是否可合并
                if can_merge_shapes(shape1, shape2, mode, params):
                    # 计算两个框的并集外接矩形（包络框）
                    b1, b2 = get_bounding_box(shape1), get_bounding_box(shape2)
                    merged_box = [
                        min(b1[0], b2[0]),  # x_min
                        min(b1[1], b2[1]),  # y_min
                        max(b1[2], b2[2]),  # x_max
                        max(b1[3], b2[3]),  # y_max
                    ]
                    # 生成新的合并 shape
                    new_shape = create_shape_from_box(merged_box, shape1, shape2)

                    # 用新 shape 替换原来的两个（先删 j 再删 i，避免索引前移混乱）
                    shapes.pop(j)
                    shapes.pop(i)
                    shapes.insert(i, new_shape)

                    merge_count += 1
                    merged_in_pass = True

                    if ADVANCED_MERGE_OPTIONS["debug_mode"]:
                        print(f"    合并: '{shape1.get('label','')}' + '{shape2.get('label','')}' -> '{new_shape.get('label','')}'")
                    break  # 跳出内层 j 循环，回到外层继续从 i 位置扫描
                else:
                    j += 1
            if merged_in_pass:
                # 本轮从位置 i 发生合并，继续从 i 继续扫描（因为此处已插入新 shape）
                break
            else:
                i += 1
        if not merged_in_pass:
            # 一整轮扫描未发生任何合并，结束
            break

    if merge_count > 0:
        print(f"    {mode} 合并: 执行了 {merge_count} 次合并操作")
    return shapes


def process_file(file_path):
    """
    处理单个 JSON 文件：
      1) 读取 JSON
      2) 根据 MERGE_MODE 执行合并
      3) 写回文件（覆盖原文件）
      4) 过程打印统计信息

    返回：
      - True 表示文件被成功处理并写回；
      - False 表示读取失败、写入失败或无需处理（如无 shapes）。
    """
    # 读取
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"  - 错误: 读取文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False

    # 基本校验
    if 'shapes' not in data or not data['shapes']:
        print(f"  - 跳过: {os.path.basename(file_path)} (无标注框)")
        return False

    initial_shapes = copy.deepcopy(data['shapes'])  # 深拷贝，避免直接修改原数据
    initial_count = len(initial_shapes)

    if MERGE_MODE == "NONE":
        print(f"  - 跳过: {os.path.basename(file_path)} (合并模式为NONE)")
        return False

    print(f"  - 处理: {os.path.basename(file_path)} (初始框数: {initial_count})")

    # 按模式执行合并
    if MERGE_MODE == "VERTICAL":
        final_shapes = perform_merge(initial_shapes, "VERTICAL")
    elif MERGE_MODE == "HORIZONTAL":
        final_shapes = perform_merge(initial_shapes, "HORIZONTAL")
    elif MERGE_MODE == "VERTICAL_THEN_HORIZONTAL":
        temp = perform_merge(initial_shapes, "VERTICAL")
        final_shapes = perform_merge(temp, "HORIZONTAL")
    elif MERGE_MODE == "HORIZONTAL_THEN_VERTICAL":
        temp = perform_merge(initial_shapes, "HORIZONTAL")
        final_shapes = perform_merge(temp, "VERTICAL")
    else:
        # 理论上不会到达此分支，兜底返回原始
        final_shapes = initial_shapes

    # 回写数据
    data['shapes'] = final_shapes
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"    完成: 框数 {initial_count} -> {len(final_shapes)} (减少了 {initial_count - len(final_shapes)} 个框)")
        return True
    except Exception as e:
        print(f"  - 错误: 写入文件 '{os.path.basename(file_path)}' 时失败: {e}")
        return False


def main():
    """
    脚本入口：
      - 支持“拖拽模式”：将文件/文件夹拖拽到脚本上运行（命令行参数存在）
      - 支持“双击模式”：无命令行参数时，将扫描脚本所在目录下的所有 .json 文件
      - 对符合条件的 JSON 文件逐一执行处理
    """
    # 打印配置概览
    print("="*60)
    print("区域合并脚本（纯垂直/纯横向 版）")
    print(f"合并模式: {MERGE_MODE}")
    print(f"精细化合并控制: {'启用' if USE_SPECIFIC_MERGE_GROUPS else '禁用'}")
    if USE_SPECIFIC_MERGE_GROUPS:
        for i, g in enumerate(SPECIFIC_MERGE_GROUPS):
            print(f"  组{i}: {g}")
    else:
        print(f"要求相同标签: {'是' if REQUIRE_SAME_LABEL else '否'}")
    print(f"合并包含关系矩形: {'是' if MERGE_CONTAINED_BOXES else '否'}")
    print(f"标签合并策略: {LABEL_MERGE_STRATEGY}")
    print(f"排除合并的标签: {list(LABELS_TO_EXCLUDE_FROM_MERGE) if LABELS_TO_EXCLUDE_FROM_MERGE else '无'}")
    print(f"调试模式: {'开启' if ADVANCED_MERGE_OPTIONS['debug_mode'] else '关闭'}")
    print("="*60 + "\n")

    # 收集目标文件路径
    files_to_process = []
    if len(sys.argv) > 1:
        # 拖拽模式：命令行参数中包含文件或文件夹
        print("进入 [拖拽模式]...")
        unique_json_paths = set()
        for path in sys.argv[1:]:
            if os.path.isfile(path) and path.lower().endswith('.json'):
                unique_json_paths.add(os.path.abspath(path))
            elif os.path.isdir(path):
                # 递归扫描文件夹
                for root, _, filenames in os.walk(path):
                    for filename in filenames:
                        if filename.lower().endswith('.json'):
                            unique_json_paths.add(os.path.join(root, filename))
        files_to_process = sorted(list(unique_json_paths))
    else:
        # 双击模式：扫描脚本当前目录
        print("进入 [双击模式]...")
        try:
            # 在某些环境（如交互解释器）下 __file__ 可能不可用，因此做兜底
            work_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            work_dir = os.getcwd()
        print(f"扫描目录: {work_dir}")
        files_to_process = [os.path.join(work_dir, f) for f in os.listdir(work_dir) if f.lower().endswith('.json')]

    if not files_to_process:
        print("\n未找到任何 .json 文件进行处理。")
        # 暂停等待用户查看信息（适合双击运行的窗口）
        input("按 Enter 键退出...")
        return

    print(f"\n找到 {len(files_to_process)} 个目标JSON文件，开始处理...\n")
    processed_count = 0
    for file_path in files_to_process:
        # 避免把脚本自身当作输入（通常不是 .json，但此处保底）
        if file_path == os.path.abspath(__file__):
            continue
        if process_file(file_path):
            processed_count += 1

    print(f"\n处理完成！总共修改了 {processed_count} 个 JSON 文件。")
    input("按 Enter 键退出...")


if __name__ == "__main__":
    main()