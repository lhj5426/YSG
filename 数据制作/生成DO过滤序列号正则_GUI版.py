import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os


def range_to_regex_padded(start, end, width):
    """
    生成固定宽度（带前导零）的数字范围正则表达式
    使用递归分治策略生成最优正则
    """
    start_str = str(start).zfill(width)
    end_str = str(end).zfill(width)
    
    patterns = generate_range_patterns(start_str, end_str)
    return "|".join(patterns)


def generate_range_patterns(start_str, end_str):
    """递归生成范围正则模式"""
    if start_str == end_str:
        return [start_str]
    
    n = len(start_str)
    patterns = []
    
    start_int = int(start_str)
    end_int = int(end_str)
    
    # 找到起始数字能到达的最近的 "整十/整百/..." 边界
    # 例如: 00023 -> 00029, 00030 -> 00099, 00100 -> 00999
    
    current = start_int
    
    while current <= end_int:
        # 找到当前数字的"上界"
        s = str(current).zfill(n)
        
        # 计算能覆盖到的最大范围
        upper = find_upper_bound(current, end_int, n)
        u = str(upper).zfill(n)
        
        # 生成这个子范围的模式
        pattern = make_pattern(s, u, n)
        patterns.append(pattern)
        
        current = upper + 1
    
    return patterns


def find_upper_bound(start, max_end, width):
    """找到从start开始能用一个简单模式覆盖的最大值"""
    s = str(start).zfill(width)
    
    # 从最后一位开始，尝试扩展到9
    for i in range(width - 1, -1, -1):
        # 尝试把第i位之后都变成9
        candidate = s[:i] + s[i] + "9" * (width - i - 1)
        candidate_int = int(candidate)
        
        if candidate_int <= max_end:
            # 检查是否可以进一步扩展第i位
            if s[i] != '9':
                for d in range(int(s[i]) + 1, 10):
                    bigger = s[:i] + str(d) + "9" * (width - i - 1)
                    if int(bigger) <= max_end:
                        candidate = bigger
                        candidate_int = int(candidate)
                    else:
                        break
            return candidate_int
    
    return start


def make_pattern(start_str, end_str, width):
    """为一个可以简单表示的范围生成正则模式"""
    if start_str == end_str:
        return start_str
    
    result = []
    for i in range(width):
        s_char = start_str[i]
        e_char = end_str[i]
        
        if s_char == e_char:
            result.append(s_char)
        elif s_char == '0' and e_char == '9':
            result.append(r"\d")
        elif s_char == e_char:
            result.append(s_char)
        else:
            result.append(f"[{s_char}-{e_char}]")
    
    return "".join(result)


class RegexGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("区间正则生成器")
        self.root.geometry("700x850")
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
        self.prefix_var.trace('w', lambda *args: self.auto_remove_numbers(self.prefix_var))
        self.prefix_entry = ttk.Entry(input_frame, textvariable=self.prefix_var, width=30)
        self.prefix_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: HBSP").grid(row=0, column=2, sticky=tk.W, padx=(10, 0))
        
        # 起始数字
        ttk.Label(input_frame, text="起始数字:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.start_var = tk.StringVar()
        self.start_var.trace('w', lambda *args: self.auto_extract_number(self.start_var))
        self.start_entry = ttk.Entry(input_frame, textvariable=self.start_var, width=30)
        self.start_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: 33861").grid(row=1, column=2, sticky=tk.W, padx=(10, 0))
        
        # 结束数字或数量选择
        ttk.Label(input_frame, text="结束数字:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.end_var = tk.StringVar()
        self.end_var.trace('w', lambda *args: self.auto_extract_number(self.end_var))
        self.end_entry = ttk.Entry(input_frame, textvariable=self.end_var, width=30)
        self.end_entry.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        ttk.Label(input_frame, text="例如: 33906").grid(row=2, column=2, sticky=tk.W, padx=(10, 0))
        
        # 或者按数量计算
        ttk.Label(input_frame, text="或输入数量:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.count_var = tk.StringVar()
        self.count_entry = ttk.Entry(input_frame, textvariable=self.count_var, width=30)
        self.count_entry.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(10, 0))
        
        calc_end_btn = ttk.Button(input_frame, text="计算结束数字", command=self.calc_end_from_count)
        calc_end_btn.grid(row=3, column=2, sticky=tk.W, padx=(10, 0))
        
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
        result_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 正则表达式显示
        ttk.Label(result_frame, text="正则表达式:").pack(anchor=tk.W)
        self.regex_text = tk.Text(result_frame, height=3, wrap=tk.WORD)
        self.regex_text.pack(fill=tk.X, pady=(5, 10))
        
        # 序列预览
        self.preview_label_var = tk.StringVar(value="序列预览:")
        ttk.Label(result_frame, textvariable=self.preview_label_var).pack(anchor=tk.W)
        
        preview_frame = ttk.Frame(result_frame)
        preview_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.preview_text = tk.Text(preview_frame, height=6, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL, command=self.preview_text.yview)
        self.preview_text.configure(yscrollcommand=scrollbar.set)
        
        self.preview_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 缺失序列号计算区域
        missing_frame = ttk.LabelFrame(main_frame, text="缺失序列号计算", padding="10")
        missing_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # 已存在序列输入
        self.existing_label_var = tk.StringVar(value="粘贴已存在的序列号 (每行一个):")
        ttk.Label(missing_frame, textvariable=self.existing_label_var).pack(anchor=tk.W)
        
        existing_input_frame = ttk.Frame(missing_frame)
        existing_input_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))
        
        self.existing_text = tk.Text(existing_input_frame, height=5, wrap=tk.WORD)
        existing_scrollbar = ttk.Scrollbar(existing_input_frame, orient=tk.VERTICAL, command=self.existing_text.yview)
        self.existing_text.configure(yscrollcommand=existing_scrollbar.set)
        self.existing_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        existing_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 监听文本变化
        self.existing_text.bind('<KeyRelease>', self.on_existing_text_change)
        self.existing_text.bind('<<Paste>>', self.on_existing_text_paste)
        
        # 计算按钮
        calc_btn_frame = ttk.Frame(missing_frame)
        calc_btn_frame.pack(fill=tk.X, pady=5)
        
        self.calc_missing_btn = ttk.Button(calc_btn_frame, text="计算缺失序列", command=self.calc_missing)
        self.calc_missing_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.copy_missing_btn = ttk.Button(calc_btn_frame, text="复制缺失序列", command=self.copy_missing)
        self.copy_missing_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.save_missing_btn = ttk.Button(calc_btn_frame, text="导出缺失序列", command=self.save_missing_to_file)
        self.save_missing_btn.pack(side=tk.LEFT)
        
        # 缺失序列结果
        self.missing_label_var = tk.StringVar(value="缺失序列:")
        ttk.Label(missing_frame, textvariable=self.missing_label_var).pack(anchor=tk.W)
        
        missing_result_frame = ttk.Frame(missing_frame)
        missing_result_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        self.missing_text = tk.Text(missing_result_frame, height=5, wrap=tk.WORD)
        missing_scrollbar = ttk.Scrollbar(missing_result_frame, orient=tk.VERTICAL, command=self.missing_text.yview)
        self.missing_text.configure(yscrollcommand=missing_scrollbar.set)
        self.missing_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        missing_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(fill=tk.X, pady=(10, 0))
        
        # 标记，防止递归调用
        self.is_updating = False
    
    def auto_remove_numbers(self, var):
        """自动移除数字部分，只保留非数字字符"""
        if self.is_updating:
            return
        
        value = var.get()
        if not value:
            return
        
        # 移除所有数字
        import re
        cleaned = re.sub(r'\d+', '', value)
        
        # 如果清理后的值和原值不同，更新
        if cleaned != value:
            self.is_updating = True
            var.set(cleaned)
            self.is_updating = False
    
    def auto_extract_number(self, var):
        """自动提取数字部分"""
        if self.is_updating:
            return
        
        value = var.get()
        if not value:
            return
        
        # 提取所有数字
        import re
        numbers = re.findall(r'\d+', value)
        
        if numbers:
            # 取最后一个连续的数字串（通常是序列号）
            extracted = numbers[-1]
            
            # 如果提取的数字和原值不同，更新
            if extracted != value:
                self.is_updating = True
                var.set(extracted)
                self.is_updating = False
    
    def calc_end_from_count(self):
        """根据起始数字和数量计算结束数字"""
        start_str = self.start_var.get().strip()
        count_str = self.count_var.get().strip()
        
        if not start_str:
            messagebox.showwarning("提示", "请先输入起始数字！")
            return
        
        if not count_str:
            messagebox.showwarning("提示", "请输入数量！")
            return
        
        if not start_str.isdigit() or not count_str.isdigit():
            messagebox.showerror("错误", "起始数字和数量必须是数字！")
            return
        
        start = int(start_str)
        count = int(count_str)
        
        if count <= 0:
            messagebox.showerror("错误", "数量必须大于0！")
            return
        
        # 计算结束数字 = 起始数字 + 数量 - 1
        end = start + count - 1
        
        # 保持和起始数字相同的位数（补零）
        num_width = len(start_str)
        end_str = str(end).zfill(num_width)
        
        self.end_var.set(end_str)
        self.status_var.set(f"已计算: 从 {start_str} 开始，共 {count} 个，结束于 {end_str}")
    
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
        
        # 保留原始输入的位数（用于补零）
        num_width = len(start_str)
        
        return prefix, start, end, num_width
    
    def generate_regex(self):
        """生成正则表达式"""
        result = self.validate_input()
        if not result:
            return
        
        prefix, start, end, num_width = result
        
        try:
            # 生成带补零的正则
            core_regex = range_to_regex_padded(start, end, num_width)
            final_regex = rf"\b{prefix}(?:{core_regex})\b"
            
            # 显示正则
            self.regex_text.delete(1.0, tk.END)
            self.regex_text.insert(tk.END, final_regex)
            
            # 显示序列预览（带补零）
            self.preview_text.delete(1.0, tk.END)
            count = end - start + 1
            for num in range(start, end + 1):
                self.preview_text.insert(tk.END, f"{prefix}{str(num).zfill(num_width)}\n")
            
            self.preview_label_var.set(f"序列预览 (共 {count} 个):")
            self.status_var.set(f"已生成正则表达式，共 {count} 个序列")
            
        except Exception as e:
            messagebox.showerror("错误", str(e))
    
    def save_to_file(self):
        """保存到文件"""
        result = self.validate_input()
        if not result:
            return
        
        prefix, start, end, num_width = result
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
                    f.write(f"{prefix}{str(num).zfill(num_width)}\n")
            
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
    
    def update_existing_count(self):
        """更新已存在序列的数量显示"""
        content = self.existing_text.get(1.0, tk.END).strip()
        if content:
            lines = [line.strip() for line in content.split('\n') if line.strip()]
            count = len(lines)
            self.existing_label_var.set(f"粘贴已存在的序列号 (已输入 {count} 个):")
        else:
            self.existing_label_var.set("粘贴已存在的序列号 (每行一个):")
    
    def on_existing_text_change(self, event=None):
        """文本变化时更新计数"""
        self.update_existing_count()
    
    def on_existing_text_paste(self, event=None):
        """粘贴后更新计数"""
        self.root.after(10, self.update_existing_count)
    
    def calc_missing(self):
        """计算缺失的序列号"""
        # 获取生成的完整序列
        full_sequences = self.preview_text.get(1.0, tk.END).strip().split('\n')
        full_sequences = [s.strip() for s in full_sequences if s.strip()]
        
        if not full_sequences:
            messagebox.showwarning("提示", "请先生成序列！")
            return
        
        # 获取已存在的序列
        existing_text = self.existing_text.get(1.0, tk.END).strip()
        if not existing_text:
            messagebox.showwarning("提示", "请粘贴已存在的序列号！")
            return
        
        # 解析已存在的序列（支持多种格式）
        existing_sequences = set()
        for line in existing_text.split('\n'):
            line = line.strip()
            if line:
                # 提取序列号（支持带路径或其他前缀的格式）
                # 尝试匹配前缀+数字的模式
                prefix = self.prefix_var.get().strip()
                if prefix:
                    import re
                    pattern = rf'{re.escape(prefix)}\d+'
                    matches = re.findall(pattern, line)
                    for m in matches:
                        existing_sequences.add(m)
                else:
                    existing_sequences.add(line)
        
        # 计算缺失的序列
        full_set = set(full_sequences)
        missing = full_set - existing_sequences
        missing_sorted = sorted(missing)
        
        # 显示结果
        self.missing_text.delete(1.0, tk.END)
        for seq in missing_sorted:
            self.missing_text.insert(tk.END, f"{seq}\n")
        
        self.missing_label_var.set(f"缺失序列 (共 {len(missing_sorted)} 个):")
        self.status_var.set(f"计算完成: 总共 {len(full_sequences)} 个, 已存在 {len(existing_sequences)} 个, 缺失 {len(missing_sorted)} 个")
    
    def copy_missing(self):
        """复制缺失序列到剪贴板"""
        missing_content = self.missing_text.get(1.0, tk.END).strip()
        if not missing_content:
            messagebox.showwarning("提示", "没有缺失序列可复制！")
            return
        
        self.root.clipboard_clear()
        self.root.clipboard_append(missing_content)
        self.status_var.set("缺失序列已复制到剪贴板")
    
    def save_missing_to_file(self):
        """导出缺失序列到文件"""
        missing_content = self.missing_text.get(1.0, tk.END).strip()
        if not missing_content:
            messagebox.showwarning("提示", "没有缺失序列可导出！请先计算缺失序列。")
            return
        
        prefix = self.prefix_var.get().strip() or "missing"
        default_name = f"{prefix}_缺失序列.txt"
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfile=default_name
        )
        
        if not filepath:
            return
        
        try:
            missing_list = [s.strip() for s in missing_content.split('\n') if s.strip()]
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"缺失序列 (共 {len(missing_list)} 个)\n\n")
                for seq in missing_list:
                    f.write(f"{seq}\n")
            
            self.status_var.set(f"缺失序列已保存到: {os.path.basename(filepath)}")
            messagebox.showinfo("成功", f"缺失序列已保存！\n路径: {filepath}\n共 {len(missing_list)} 个")
            
        except Exception as e:
            messagebox.showerror("保存失败", str(e))


def main():
    root = tk.Tk()
    app = RegexGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
