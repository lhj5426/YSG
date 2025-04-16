import sys
import os
import json
import re

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    return (0, 0, 0)

def extract_color_from_rich_text(rich_text):
    match = re.search(r'color\s*:\s*#([0-9a-fA-F]{6})', rich_text)
    if match:
        return hex_to_rgb(match.group(1))
    return None

def find_itp_file(directory):
    for file in os.listdir(directory):
        if file.endswith('.itp'):
            return os.path.join(directory, file)
    return None

def process_file(input_file, itp_file):
    # 读取输入的 JSON 文件
    with open(input_file, encoding='utf-8') as f1:
        data1 = json.load(f1)

    # 读取模板 .itp 文件
    with open(itp_file, encoding='utf-8') as f2:
        data2 = json.load(f2)

    # 把 directory 写入 dirPath
    data2['dirPath'] = data1.get('directory', '')

    # 遍历每一页
    for page, boxes in data1.get('pages', {}).items():
        data2.setdefault('images', {})[page] = {'boxes': []}

        for box in boxes:
            bounding_rect = box.get('_bounding_rect')
            if not bounding_rect:
                print(f"Warning: '_bounding_rect' is missing for a box on page {page}. Skipping.")
                continue

            x, y, w, h = bounding_rect
            angle = box.get('angle', 0)
            fg_colors = box.get('fg_colors')

            # 尝试从 rich_text 提取颜色
            rich_text = box.get('rich_text', '')
            extracted_rgb = extract_color_from_rich_text(rich_text)

            if extracted_rgb:
                textColor = ','.join(map(str, extracted_rgb))
            elif fg_colors:
                textColor = ','.join(map(str, map(int, fg_colors)))
            else:
                textColor = '0,0,0'

            # 拼接完整文本：如果 box['text'] 是列表，就 join；如果已经是字符串，也不会出错
            raw_text = box.get('text', '')
            if isinstance(raw_text, list):
                full_text = ''.join(raw_text)
            else:
                full_text = str(raw_text)

            data2['images'][page]['boxes'].append({
                'degree': angle,
                'geometry': {
                    'X': x,
                    'Y': y,
                    'width': w,
                    'height': h
                },
                'text': full_text,
                'textColor': textColor,
                'target': box.get('translation', '')
            })

    # 输出到新的 .itp 文件（与输入 JSON 同名）
    output_file = os.path.splitext(input_file)[0] + '.itp'
    with open(output_file, 'w', encoding='utf-8') as f3:
        json.dump(data2, f3, indent=4, ensure_ascii=False)

    print(f'\n✅ 处理完成：{input_file}\n输出文件：{output_file}')

if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print('请将 JSON 文件拖拽到脚本上运行。')
            input("按任意键退出...")
            sys.exit(1)

        input_files = sys.argv[1:]
        for input_file in input_files:
            directory = os.path.dirname(input_file)
            itp_file = find_itp_file(directory)

            if itp_file:
                process_file(input_file, itp_file)
            else:
                print(f'❌ 未找到 .itp 文件，跳过：{input_file}')
        
    except Exception as e:
        print(f"\n❌ 处理失败：{e}")
        input("\n按任意键退出...")
