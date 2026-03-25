#!/usr/bin/env python3
import json
import os
import sys
from typing import Any, Dict, List, Tuple

# ============== 反向转换输出配置 ==============
# 输出文件名后缀（每页会输出: <stem><suffix>.json）
OUTPUT_SUFFIX = "_translations"
# 输出目录结构（在拖拽 JSON 的同级目录下）
OUTPUT_ROOT_DIRNAME = "manga_translator_work"
OUTPUT_JSON_DIRNAME = "json"
# 默认目标语言
DEFAULT_TARGET_LANG = "CHS"
# 默认源语言（当无法从 BallonsTranslator language 字段判断时）
DEFAULT_SOURCE_LANG = "ja"
# 自动描边颜色：深色文字->白描边，浅色文字->黑描边
ENABLE_AUTO_STROKE_COLOR = True
AUTO_STROKE_THRESHOLD = 128.0
# 描边宽度覆盖：False 使用原值；True 使用下方统一值
ENABLE_OVERRIDE_STROKE_WIDTH = False
OVERRIDE_STROKE_WIDTH_VALUE = 0.07


def _to_float_point(pt: List[Any]) -> List[float]:
    return [float(pt[0]), float(pt[1])]


def _bbox_to_center_and_white_frame(x1: float, y1: float, x2: float, y2: float) -> Tuple[List[float], List[float]]:
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    return [cx, cy], [x1 - cx, y1 - cy, x2 - cx, y2 - cy]


def _xyxy_from_region(region: Dict[str, Any]) -> Tuple[float, float, float, float]:
    xyxy = region.get("xyxy")
    if isinstance(xyxy, list) and len(xyxy) >= 4:
        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    br = region.get("_bounding_rect")
    if isinstance(br, list) and len(br) >= 4:
        x1, y1, w, h = float(br[0]), float(br[1]), float(br[2]), float(br[3])
        x2, y2 = x1 + max(0.0, w), y1 + max(0.0, h)
        if x2 > x1 and y2 > y1:
            return x1, y1, x2, y2
    return 0.0, 0.0, 0.0, 0.0


def _alignment_from_int(v: Any) -> str:
    try:
        iv = int(v)
    except Exception:
        iv = 0
    return {0: "left", 1: "center", 2: "right"}.get(iv, "left")


def _source_lang_from_region(region: Dict[str, Any]) -> str:
    lang = str(region.get("language", "")).strip()
    if not lang or lang == "unknown":
        return DEFAULT_SOURCE_LANG
    return lang


def _auto_stroke_color_from_text_rgb(frgb: List[int]) -> List[int]:
    r, g, b = frgb
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    if luminance < AUTO_STROKE_THRESHOLD:
        return [255, 255, 255]
    return [0, 0, 0]


def _to_mtu_region(region: Dict[str, Any]) -> Dict[str, Any]:
    x1, y1, x2, y2 = _xyxy_from_region(region)
    ff = region.get("fontformat", {}) if isinstance(region.get("fontformat"), dict) else {}
    lines = region.get("lines")
    if not isinstance(lines, list) or not lines:
        lines = [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]
    norm_lines: List[List[List[float]]] = []
    for poly in lines:
        if not isinstance(poly, list):
            continue
        pts: List[List[float]] = []
        for pt in poly:
            if isinstance(pt, list) and len(pt) >= 2:
                pts.append(_to_float_point(pt))
        if pts:
            norm_lines.append(pts)
    if not norm_lines:
        norm_lines = [[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]]

    center, wf = _bbox_to_center_and_white_frame(x1, y1, x2, y2)
    text_list = region.get("text")
    if isinstance(text_list, list) and text_list:
        texts = [str(t) for t in text_list]
    else:
        t = str(region.get("text", ""))
        texts = [t] if t else []

    translation = str(region.get("translation", ""))
    translation = translation.replace("\r\n", "[BR]").replace("\n", "[BR]").replace("\r", "[BR]")

    frgb = ff.get("frgb", [0, 0, 0])
    srgb = ff.get("srgb", [255, 255, 255])
    if not isinstance(frgb, list):
        frgb = [0, 0, 0]
    if not isinstance(srgb, list):
        srgb = [255, 255, 255]
    frgb = [int(round(float(c))) for c in (frgb + [0, 0, 0])[:3]]
    srgb = [int(round(float(c))) for c in (srgb + [255, 255, 255])[:3]]
    if ENABLE_AUTO_STROKE_COLOR:
        srgb = _auto_stroke_color_from_text_rgb(frgb)

    stroke_width = float(ff.get("stroke_width", 0.07))
    if ENABLE_OVERRIDE_STROKE_WIDTH:
        stroke_width = float(OVERRIDE_STROKE_WIDTH_VALUE)

    font_family = str(ff.get("font_family", "XinLanYuan")).strip() or "XinLanYuan"
    font_path = region.get("font_path")
    if not font_path:
        if font_family == "XinLanYuan":
            font_path = "fonts/新兰圆-B.ttf"
        else:
            font_path = f"fonts/{font_family}.ttf"
    font_path = str(font_path).replace("\\", "/")

    return {
        "lines": norm_lines,
        "center": center,
        "texts": texts,
        "text": "".join(texts),
        "translation": translation,
        "angle": float(region.get("angle", 0)),
        "font_size": int(round(float(ff.get("font_size", 36)))),
        "fg_colors": frgb,
        "bg_colors": srgb,
        "direction": "v" if bool(ff.get("vertical", region.get("src_is_vertical", True))) else "h",
        "alignment": _alignment_from_int(ff.get("alignment", 0)),
        "target_lang": DEFAULT_TARGET_LANG,
        "source_lang": _source_lang_from_region(region),
        "line_spacing": float(ff.get("line_spacing", 1.0)),
        "letter_spacing": float(ff.get("letter_spacing", 1.0)),
        "stroke_width": stroke_width,
        "prob": 1.0,
        "font_path": font_path,
        "white_frame_rect_local": wf,
        "has_custom_white_frame": True,
    }


def convert(input_file: str, output_dir: str) -> None:
    with open(input_file, "r", encoding="utf-8", errors="replace") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Input must be a BallonsTranslator project JSON object.")

    pages = data.get("pages", {})
    if not isinstance(pages, dict) or not pages:
        raise ValueError("Input JSON has no pages.")

    image_info = data.get("image_info", {})
    if not isinstance(image_info, dict):
        image_info = {}
    directory = str(data.get("directory", "")).replace("/", "\\")

    os.makedirs(output_dir, exist_ok=True)
    count = 0
    for page_name, regions in pages.items():
        if not isinstance(regions, list):
            regions = []
        page_regions = [_to_mtu_region(r) for r in regions if isinstance(r, dict)]

        stem, _ = os.path.splitext(page_name)
        abs_img = os.path.join(directory, page_name) if directory else page_name
        info = image_info.get(page_name, {}) if isinstance(image_info.get(page_name), dict) else {}
        out_obj = {
            abs_img: {
                "regions": page_regions,
                "textlines": [],
                "original_width": int(info.get("width", 0) or 0),
                "original_height": int(info.get("height", 0) or 0),
                "skip_font_scaling": False,
            }
        }
        out_path = os.path.join(output_dir, f"{stem}{OUTPUT_SUFFIX}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, ensure_ascii=False, indent=2)
        print(f"已写入: {out_path}（{len(page_regions)} 个文本区域）")
        count += 1

    print(f"完成，共拆分 {count} 页，已生成 MTU JSON 文件。")


def main() -> None:
    # Drag-and-drop mode only:
    # Drop one BallonsTranslator JSON file onto this script.
    if len(sys.argv) < 2:
        print("用法：把一个 BallonsTranslator 的 JSON 文件拖到本脚本上。")
        return

    input_file = os.path.abspath(sys.argv[1])
    output_dir = os.path.join(
        os.path.dirname(input_file),
        OUTPUT_ROOT_DIRNAME,
        OUTPUT_JSON_DIRNAME,
    )
    convert(input_file, output_dir)


if __name__ == "__main__":
    try:
        main()
    finally:
        if os.name == "nt":
            try:
                input("\n处理完成，按回车退出...")
            except EOFError:
                pass
