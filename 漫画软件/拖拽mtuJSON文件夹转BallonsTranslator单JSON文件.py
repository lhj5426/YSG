#!/usr/bin/env python3
import argparse
import glob
import json
import os
import sys
import traceback
from copy import deepcopy
from typing import Any, Dict, List, Tuple

# ============== 描边宽度总开关与默认值配置 ==============
# 描边覆盖总开关：False 时使用源 JSON 的 stroke_width；True 时统一覆盖为下方值
ENABLE_OVERRIDE_STROKE_WIDTH = True
# 当 ENABLE_OVERRIDE_STROKE_WIDTH = True 时生效
OVERRIDE_STROKE_WIDTH_VALUE = 0.25


def _to_int_point(pt: List[float]) -> List[int]:
    return [int(round(float(pt[0]))), int(round(float(pt[1])))]


def _normalize_lines(lines: Any) -> List[List[List[int]]]:
    out: List[List[List[int]]] = []
    if not isinstance(lines, list):
        return out
    for poly in lines:
        if not isinstance(poly, list):
            continue
        pts: List[List[int]] = []
        for pt in poly:
            if isinstance(pt, list) and len(pt) >= 2:
                pts.append(_to_int_point(pt))
        if pts:
            out.append(pts)
    return out


def _bbox_from_lines(lines: List[List[List[int]]]) -> Tuple[int, int, int, int]:
    if not lines:
        return 0, 0, 0, 0
    xs: List[int] = []
    ys: List[int] = []
    for poly in lines:
        for x, y in poly:
            xs.append(x)
            ys.append(y)
    x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
    return x1, y1, x2, y2


def _bbox_from_white_frame(
    center: Any, white_frame_rect_local: Any, fallback: Tuple[int, int, int, int]
) -> Tuple[int, int, int, int]:
    """
    Convert manga-translator-ui's white_frame_rect_local into absolute bbox.
    white_frame_rect_local is relative to region center: [left, top, right, bottom].
    """
    if (
        not isinstance(center, list)
        or len(center) < 2
        or not isinstance(white_frame_rect_local, list)
        or len(white_frame_rect_local) < 4
    ):
        return fallback
    try:
        cx = float(center[0])
        cy = float(center[1])
        l = float(white_frame_rect_local[0])
        t = float(white_frame_rect_local[1])
        r = float(white_frame_rect_local[2])
        b = float(white_frame_rect_local[3])
        x1 = int(round(cx + l))
        y1 = int(round(cy + t))
        x2 = int(round(cx + r))
        y2 = int(round(cy + b))
        if x2 <= x1 or y2 <= y1:
            return fallback
        return x1, y1, x2, y2
    except Exception:
        return fallback


def _font_family_from_path(font_path: str) -> str:
    if not font_path:
        return "Microsoft YaHei"
    base = os.path.basename(font_path).strip()
    if not base:
        return "Microsoft YaHei"
    stem = os.path.splitext(base)[0]
    # Keep compatibility with BallonsTranslator project fonts.
    mapping = {
        "新兰圆-B": "XinLanYuan",
    }
    return mapping.get(stem, stem or "Microsoft YaHei")


def _alignment_to_int(alignment: str) -> int:
    # Keep a simple compatible mapping (Qt-like left/center/right).
    m = {"left": 0, "center": 1, "right": 2}
    return m.get((alignment or "").lower(), 0)


def _normalize_translation_breaks(text: str) -> str:
    # manga-translator-ui commonly uses [BR], while BallonsTranslator uses real newlines.
    s = text.replace("[BR]", "\n").replace("[br]", "\n")
    # Also handle HTML-style line breaks if they appear.
    s = s.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    return s


def _auto_stroke_color_from_text_rgb(frgb: List[int]) -> List[float]:
    # Perceived luminance (sRGB). Lower value means darker text.
    r, g, b = frgb
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Dark text -> white stroke; light text -> black stroke.
    if luminance < 128:
        return [255.0, 255.0, 255.0]
    return [0.0, 0.0, 0.0]


def _region_to_balloon(
    region: Dict[str, Any],
    default_region: Dict[str, Any] = None,
    override_stroke_width: bool = False,
    stroke_width_value: float = 0.07,
) -> Dict[str, Any]:
    lines = _normalize_lines(region.get("lines"))
    line_bbox = _bbox_from_lines(lines)
    x1, y1, x2, y2 = _bbox_from_white_frame(
        region.get("center"), region.get("white_frame_rect_local"), line_bbox
    )
    w, h = max(0, x2 - x1), max(0, y2 - y1)

    texts = region.get("texts")
    if isinstance(texts, list) and texts:
        text_list = [str(x) for x in texts]
    else:
        text_list = [str(region.get("text", ""))]

    translation = _normalize_translation_breaks(str(region.get("translation", "")))
    direction = str(region.get("direction", "")).lower()
    fg = region.get("fg_colors") if isinstance(region.get("fg_colors"), list) else [0, 0, 0]
    fg = [int(round(float(c))) for c in (fg + [0, 0, 0])[:3]]

    if default_region is None:
        default_region = {}

    out = deepcopy(default_region)
    out.setdefault("fontformat", {})
    ff = deepcopy(out.get("fontformat", {}))

    font_size = float(region.get("font_size", ff.get("font_size", 36)))
    stroke_width = float(region.get("stroke_width", ff.get("stroke_width", 0.0)))
    if override_stroke_width:
        stroke_width = float(stroke_width_value)
    line_spacing = float(region.get("line_spacing", ff.get("line_spacing", 1.0)))
    letter_spacing = float(region.get("letter_spacing", ff.get("letter_spacing", 1.0)))

    src_font_path = str(region.get("font_path", "")).strip()
    if src_font_path:
        src_font_path = src_font_path.replace("\\", "/")
    if src_font_path:
        font_family = _font_family_from_path(src_font_path)
    else:
        font_family = ff.get("font_family", "Microsoft YaHei")

    out.update(
        {
            "xyxy": [x1, y1, x2, y2],
            "lines": lines,
            "language": str(region.get("source_lang", out.get("language", "unknown"))),
            "distance": out.get("distance", [0.0]),
            "angle": float(region.get("angle", out.get("angle", 0.0))),
            "vec": [0.0, float(h)],
            "norm": float(h),
            "merged": False,
            "text": text_list,
            "translation": translation,
            # Important: do NOT inherit template rich_text content per-region.
            "rich_text": "",
            "font_path": src_font_path or out.get("font_path", ""),
            "_bounding_rect": [x1, y1, w, h],
            "src_is_vertical": direction == "v",
            "_detected_font_size": int(round(font_size)),
        }
    )

    ff.update(
        {
            "font_family": font_family,
            "font_size": font_size,
            "stroke_width": stroke_width,
            "frgb": fg,
            # Auto stroke color by text brightness:
            # dark text -> white stroke, light text -> black stroke.
            "srgb": _auto_stroke_color_from_text_rgb(fg),
            "alignment": _alignment_to_int(str(region.get("alignment", "left"))),
            "vertical": direction == "v",
            "line_spacing": line_spacing,
            "letter_spacing": letter_spacing,
        }
    )
    out["fontformat"] = ff
    return out


def convert(
    input_glob: str,
    output_path: str,
    template_path: str = "",
    override_stroke_width: bool = False,
    stroke_width_value: float = 0.07,
) -> None:
    files = sorted(glob.glob(input_glob))
    if not files:
        raise FileNotFoundError(f"No files matched: {input_glob}")

    pages: Dict[str, List[Dict[str, Any]]] = {}
    image_info: Dict[str, Dict[str, int]] = {}
    directory = ""

    default_region: Dict[str, Any] = {}
    tpl = None
    if template_path:
        with open(template_path, "r", encoding="utf-8", errors="replace") as f:
            tpl = json.load(f)
        if isinstance(tpl, dict):
            tpl_pages = tpl.get("pages", {})
            if isinstance(tpl_pages, dict):
                for _k, _regions in tpl_pages.items():
                    if isinstance(_regions, list) and _regions:
                        if isinstance(_regions[0], dict):
                            default_region = deepcopy(_regions[0])
                            break

    for fp in files:
        with open(fp, "r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data:
            continue

        img_abs = next(iter(data.keys()))
        img_name = os.path.basename(img_abs)
        payload = data[img_abs]
        if not isinstance(payload, dict):
            continue

        if not directory:
            directory = os.path.dirname(img_abs).replace("\\", "/")

        regions = payload.get("regions", [])
        page_regions: List[Dict[str, Any]] = []
        if isinstance(regions, list):
            for region in regions:
                if isinstance(region, dict):
                    page_regions.append(
                        _region_to_balloon(
                            region,
                            default_region,
                            override_stroke_width=override_stroke_width,
                            stroke_width_value=stroke_width_value,
                        )
                    )
        pages[img_name] = page_regions

        image_info[img_name] = {
            "finish_code": 11,
            "width": int(payload.get("original_width", 0) or 0),
            "height": int(payload.get("original_height", 0) or 0),
        }

    page_names = sorted(pages.keys())
    if template_path and isinstance(tpl, dict):
        out = {
            "directory": tpl.get("directory", directory),
            "pages": {k: pages[k] for k in page_names},
            "current_img": tpl.get("current_img", page_names[0] if page_names else ""),
            "image_info": {},
        }
        tpl_info = tpl.get("image_info", {})
        for k in page_names:
            if isinstance(tpl_info, dict) and k in tpl_info and isinstance(tpl_info[k], dict):
                merged = dict(tpl_info[k])
                merged["width"] = image_info[k]["width"]
                merged["height"] = image_info[k]["height"]
                out["image_info"][k] = merged
            else:
                out["image_info"][k] = image_info[k]
    else:
        out = {
            "directory": directory,
            "pages": {k: pages[k] for k in page_names},
            "current_img": page_names[0] if page_names else "",
            "image_info": {k: image_info[k] for k in page_names},
        }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"Converted {len(files)} files -> {output_path}")
    for k in page_names:
        print(f"  {k}: {len(pages[k])} regions")


def main() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(
        description="Convert manga-translator-ui JSON files into BallonsTranslator project JSON format."
    )
    parser.add_argument(
        "input_folder",
        nargs="?",
        default="",
        help="(Drag-drop mode) Folder containing *_translations.json files.",
    )
    parser.add_argument(
        "--input-glob",
        default=os.path.join("json", "*_translations.json"),
        help="Input glob for manga-translator-ui files.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Output BallonsTranslator JSON path.",
    )
    parser.add_argument(
        "--template",
        default="",
        help="Optional BallonsTranslator JSON template to copy top-level metadata from.",
    )
    parser.add_argument(
        "--override-stroke-width",
        dest="override_stroke_width",
        action="store_true",
        help="Enable custom stroke width override for all regions.",
    )
    parser.add_argument(
        "--no-override-stroke-width",
        dest="override_stroke_width",
        action="store_false",
        help="Disable custom stroke width override for all regions.",
    )
    parser.add_argument(
        "--stroke-width-value",
        type=float,
        default=OVERRIDE_STROKE_WIDTH_VALUE,
        help="Custom stroke width value used when override is enabled.",
    )
    parser.set_defaults(override_stroke_width=ENABLE_OVERRIDE_STROKE_WIDTH)
    args = parser.parse_args()

    input_glob = args.input_glob
    output_path = args.output
    template_path = args.template

    # Drag a folder onto the script:
    # - Read *_translations.json from that folder (or its json subfolder).
    # - Write output to the folder's parent directory.
    if args.input_folder:
        drag_folder = os.path.abspath(args.input_folder)
        direct_glob = os.path.join(drag_folder, "*_translations.json")
        json_sub_glob = os.path.join(drag_folder, "json", "*_translations.json")
        if glob.glob(direct_glob):
            input_glob = direct_glob
        else:
            input_glob = json_sub_glob

        if not output_path:
            output_path = os.path.join(
                os.path.dirname(drag_folder), "imgtrans_from_mtu.json"
            )
        elif not os.path.isabs(output_path):
            output_path = os.path.join(os.path.dirname(drag_folder), output_path)

        if not template_path:
            candidates = [
                p
                for p in glob.glob(os.path.join(os.path.dirname(drag_folder), "imgtrans_*.json"))
                if os.path.basename(p) != os.path.basename(output_path)
            ]
            if candidates:
                template_path = candidates[0]
    else:
        if not output_path:
            output_path = os.path.join(script_dir, "imgtrans_from_mtu.json")
        elif not os.path.isabs(output_path):
            output_path = os.path.join(script_dir, output_path)

        if not template_path:
            candidates = [
                p
                for p in glob.glob(os.path.join(script_dir, "imgtrans_*.json"))
                if os.path.basename(p) != os.path.basename(output_path)
            ]
            if candidates:
                template_path = candidates[0]

    convert(
        input_glob,
        output_path,
        template_path,
        override_stroke_width=args.override_stroke_width,
        stroke_width_value=args.stroke_width_value,
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        # Keep console open for drag/drop or double-click usage on Windows.
        if os.name == "nt":
            try:
                input("\n[Error] Press Enter to exit...")
            except EOFError:
                pass
        raise
    else:
        # Keep console open for drag/drop or double-click usage on Windows.
        if os.name == "nt" and not sys.stdin.isatty():
            try:
                input("\nDone. Press Enter to exit...")
            except EOFError:
                pass
