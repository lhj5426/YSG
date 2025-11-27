import re

def split_range(start, end):
    """将任意正整数范围拆成多个子段，生成对应的正则片段"""
    parts = []
    while start <= end:
        next_end = min(end, (start // 10) * 10 + 9)
        parts.append((start, next_end))
        start = next_end + 1
    return parts

def range_to_regex(start, end):
    """将区间 [start, end] 转换为正则表达式片段"""
    segments = split_range(start, end)
    regex_parts = []

    for s, e in segments:
        s_str = str(s)
        e_str = str(e)

        if len(s_str) != len(e_str):
            raise ValueError("起始与结束数字位数必须一致")

        prefix = ""
        i = 0
        while i < len(s_str) and s_str[i] == e_str[i]:
            prefix += s_str[i]
            i += 1

        s_remain = s_str[i:]
        e_remain = e_str[i:]

        if len(s_remain) == 1:
            regex_parts.append(prefix + f"[{s_remain}-{e_remain}]")
            continue

        inner = []
        for j in range(len(s_remain)):
            if j == 0:
                if s_remain[j] == e_remain[j]:
                    inner.append(s_remain[j])
                else:
                    inner.append(f"[{s_remain[j]}-{e_remain[j]}]")
            else:
                inner.append(r"\d")

        regex_parts.append(prefix + "".join(inner))

    return "|".join(regex_parts)


def main():
    print("====== 区间正则生成器 + 序列TXT生成（含正则写入） ======\n")

    prefix = input("请输入前缀 (例如 HBSP 或 ABC_ ): ").strip()
    if prefix == "":
        print("前缀不能为空！")
        return

    start = input("请输入起始数字 (例如 33861): ").strip()
    end = input("请输入结束数字 (例如 33906): ").strip()

    if not start.isdigit() or not end.isdigit():
        print("错误：起始和结束必须是数字！")
        return

    start = int(start)
    end = int(end)

    if start > end:
        print("起始数字不能大于结束数字！")
        return

    try:
        core_regex = range_to_regex(start, end)
    except Exception as e:
        print("错误：", e)
        return

    final_regex = rf"\b{prefix}(?:{core_regex})\b"

    print("\n===== 生成的正则表达式 =====")
    print(final_regex)

    # ------------ 生成 TXT 文件 --------------
    filename = f"{prefix}_range_list.txt"
    with open(filename, "w", encoding="utf-8") as f:
        # 第一行写正则表达式
        f.write(f"正则：{final_regex}\n\n")

        # 后续写所有序列
        for num in range(start, end + 1):
            f.write(f"{prefix}{num}\n")

    print(f"\nTXT 已生成：{filename}")
    print(f"第一行已写入正则表达式")
    print(f"后续 {end - start + 1} 行为完整序列")

    input("\n按回车退出...")


if __name__ == "__main__":
    main()
