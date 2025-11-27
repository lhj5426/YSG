import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os

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


class RegexGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("区间正则生成器")
        self.root.geometry("600x500")
        self.root.resizable(True, True)
        
        self.create_widgets()
    
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 输入区域
        input_frame = ttk.LabelFrame(main_frame, text="输入参数", padding="10")
        input_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 前缀输入
        ttk.Label(input_frame, text="前缀:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.prefix_var = tk.StringVar()
        self.prefix_entry = ttk.Entry(input_frame, textvariable=self.prefix_var, width=30)
        self.prefix_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: HBSP").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        
        # 起始数字
        ttk.Label(input_frame, text="起始数字:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_var = tk.StringVar()
        self.start_entry = ttk.Entry(input_frame, textvariable=self.start_var, width=30)
        self.start_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: 33861").grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        
        # 结束数字
        ttk.Label(input_frame, text="结束数字:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_var = tk.StringVar()
        self.end_entry = ttk.Entry(input_frame, textvariable=self.end_var, width=30)
        self.end_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: 33906").grid(row=2, column=2, sticky=tk.W, padx=(10, 0))
        
        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.generate_btn = ttk.Button(btn_frame, text="生成正则", command=self.generate_regex)
        self.generate_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_btn = ttk.Button(btn_frame, text="保存到文件", command=self.save_to_file)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.copy_btn = ttk.Button(btn_frame, text="复制正则", command=self.copy_regex)
        self.copy_btn.pack(side=tk.LEFT)
        
        # 结果区域
        result_frame = ttk.LabelFrame(main_frame, text="生成结果", padding="10")
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        # 正则表达式显示
        ttk.Label(result_frame, text="正则表达式:").pack(anchor=tk.W)
        self.regex_text = tk.Text(result_frame, height=3, wrap=tk.WORD)
        self.regex_text.pack(fill=tk.X, pady=(5, 10))
        
        # 序列预览
        self.preview_label_var = tk.StringVar(value="序列预览:")
        ttk.Label(result_frame, textvariable=self.preview_label_var).pack(anchor=tk.W)
        
        preview_frame = ttk.Frame(result_frame)
        preview_frame.pack(fill=tk.BOTH, expand=True)
        
        self.preview_text = tk.Text(preview_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=scrollbar.set)
        
        self.preview_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(10, 0))
    
    def validate_input(self):
        """验证输入"""
        prefix = self.prefix_var.get().strip()
        start_str = self.start_var.get().strip()
        end_str = self.end_var.get().strip()
        
        if not prefix:
            messagebox.showerror("错误", "前缀不能为空！")
            return None
        
        if not start_str.isdigit() or not end_str.isdigit():
            messagebox.showerror("错误", "起始和结束必须是数字！")
            return None
        
        start = int(start_str)
        end = int(end_str)
        
        if start > end:
            messagebox.showerror("错误", "起始数字不能大于结束数字！")
            return None
        
        return prefix, start, end
    
    def generate_regex(self):
        """生成正则表达式"""
        result = self.validate_input()
        if not result:
            return
        
        prefix, start, end = result
        
        try:
            core_regex = range_to_regex(start, end)
            final_regex = rf"\b{prefix}(?:{core_regex})\b"
            
            # 显示正则
            self.regex_text.delete(1.0, tk.END)
            self.regex_text.insert(tk.END, final_regex)
            
            # 显示序列预览
            self.preview_text.delete(1.0, tk.END)
            count = end - start + 1
            for num in range(start, end + 1):
                self.preview_text.insert(tk.END, f"{prefix}{num}\n")
            
            self.preview_label_var.set(f"序列预览 (共 {count} 个):")
            self.status_var.set(f"已生成正则表达式，共 {count} 个序列")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def save_to_file(self):
        """保存到文件"""
        result = self.validate_input()
        if not result:
            return
        
        prefix, start, end = result
        regex_content = self.regex_text.get(1.0, tk.END).strip()
        
        if not regex_content:
            messagebox.showwarning("提示", "请先生成正则表达式！")
            return
        
        # 选择保存位置
        default_name = f"{prefix}_range_list.txt"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=default_name
        )
        
        if not filepath:
            return
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"正则：{regex_content}\n\n")
                for num in range(start, end + 1):
                    f.write(f"{prefix}{num}\n")
            
            count = end - start + 1
            self.status_var.set(f"已保存到: {os.path.basename(filepath)}")
            messagebox.showinfo("成功", f"文件已保存！\n路径: {filepath}\n共 {count} 个序列")
            
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
    
    def copy_regex(self):
        """复制正则到剪贴板"""
        regex_content = self.regex_text.get(1.0, tk.END).strip()
        if not regex_content:
            messagebox.showwarning("提示", "请先生成正则表达式！")
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append(regex_content)
        self.status_var.set("正则表达式已复制到剪贴板")


def main():
    root = tk.Tk()
    app = RegexGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
