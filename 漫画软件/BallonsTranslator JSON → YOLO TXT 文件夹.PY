import os
import sys
import json

def json_to_yolo_txt_folder(json_path, image_width, image_height):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = data.get("pages", {})
    output_folder = os.path.join(os.path.dirname(json_path), "biaoqianTXT")
    os.makedirs(output_folder, exist_ok=True)

    for img_name, regions in pages.items():
        name, _ = os.path.splitext(img_name)
        txt_path = os.path.join(output_folder, f"{name}.txt")
        lines = []

        for obj in regions:
            x1, y1, x2, y2 = obj["xyxy"]
            box_w = x2 - x1
            box_h = y2 - y1
            cx = x1 + box_w / 2
            cy = y1 + box_h / 2

            norm_cx = cx / image_width
            norm_cy = cy / image_height
            norm_w = box_w / image_width
            norm_h = box_h / image_height

            lines.append(f"0 {norm_cx:.6f} {norm_cy:.6f} {norm_w:.6f} {norm_h:.6f}")

        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    print("转换完成，生成文件夹：", output_folder)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("请将BallonsTranslator JSON文件拖拽到本脚本上")
        sys.exit(1)

    json_file = sys.argv[1]
    IMG_WIDTH = 2402
    IMG_HEIGHT = 1799

    json_to_yolo_txt_folder(json_file, IMG_WIDTH, IMG_HEIGHT)
