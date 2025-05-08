import sys
import os
import json

def find_itp_file(directory):
    for file in os.listdir(directory):
        if file.endswith('.itp'):
            return os.path.join(directory, file)
    return None

def process_file(input_file, itp_file):
    with open(input_file, encoding='utf-8') as f1:
        data1 = json.load(f1)
    with open(itp_file, encoding='utf-8') as f2:
        data2 = json.load(f2)

    data2['dirPath'] = data1.get('directory', '')

    for page, boxes in data1.get('pages', {}).items():
        data2.setdefault('images', {})[page] = {'boxes': []}

        for box in boxes:
            bounding_rect = box.get('_bounding_rect')
            if not bounding_rect:
                print(f"Warning: '_bounding_rect' missing on page {page}, skip.")
                continue

            x, y, w, h = bounding_rect
            angle = box.get('angle', 0)

            raw_text = box.get('text', '')
            if isinstance(raw_text, list):
                full_text = ''.join(raw_text)
            else:
                full_text = str(raw_text)

            data2['images'][page]['boxes'].append({
                'degree': angle,
                'geometry': {'X': x, 'Y': y, 'width': w, 'height': h},
                'text': full_text,
                'target': box.get('translation', '')
            })

    output_file = os.path.splitext(input_file)[0] + '.itp'
    with open(output_file, 'w', encoding='utf-8') as f3:
        json.dump(data2, f3, indent=4, ensure_ascii=False)

    print(f'\n✅ 处理完成：{input_file}\n输出：{output_file}')

if __name__ == '__main__':
    try:
        if len(sys.argv) < 2:
            print('请将 JSON 文件拖拽到脚本上运行。')
            input("按任意键退出...")
            sys.exit(1)

        for input_file in sys.argv[1:]:
            itp_file = find_itp_file(os.path.dirname(input_file))
            if itp_file:
                process_file(input_file, itp_file)
            else:
                print(f'❌ 未找到 .itp，跳过：{input_file}')
    except Exception as e:
        print(f"\n❌ 处理失败：{e}")
        input("\n按任意键退出...")
