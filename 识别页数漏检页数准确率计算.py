# page_accuracy.py
# 用于计算漫画检测的页数准确率（双击可用）

def calc_accuracy(total_pages, missed_pages):
    detected_pages = total_pages - missed_pages
    accuracy = detected_pages / total_pages
    print(f"\n总页数：{total_pages}")
    print(f"漏识别页数：{missed_pages}")
    print(f"识别成功页数：{detected_pages}")
    print(f"准确率：{accuracy:.2%}")

if __name__ == "__main__":
    try:
        total = int(input("请输入总页数："))
        missed = int(input("请输入漏识别的页数："))
        if missed > total or total <= 0:
            print("输入有误，请确保总页数大于0，且漏识别页数不超过总页数。")
        else:
            calc_accuracy(total, missed)
    except ValueError:
        print("输入错误，请输入整数。")

    input("\n按回车键退出...")
