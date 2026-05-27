import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import pyperclip


class SafePasteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CMD 安全粘贴工具 v1.0")
        self.root.geometry("900x650")
        self.root.configure(bg="#2b2b2b")
        
        # 设置窗口图标和样式
        self.setup_styles()
        self.create_widgets()
        
    def setup_styles(self):
        """设置深色主题样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TFrame', background='#2b2b2b')
        style.configure('TLabel', background='#2b2b2b', foreground='#e0e0e0', font=('Microsoft YaHei', 10))
        style.configure('Title.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground='#4ec9b0')
        style.configure('TButton', font=('Microsoft YaHei', 10), padding=6)
        style.configure('Accent.TButton', font=('Microsoft YaHei', 10, 'bold'))
        style.configure('TRadiobutton', background='#2b2b2b', foreground='#e0e0e0', 
                       font=('Microsoft YaHei', 9))
        style.map('TRadiobutton', background=[('active', '#2b2b2b')])
        
    def create_widgets(self):
        # 主容器
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title = ttk.Label(main_frame, text="🛡️ CMD 安全粘贴工具", style='Title.TLabel')
        title.pack(anchor='w', pady=(0, 5))
        
        subtitle = ttk.Label(main_frame, 
                            text="将代码转换为可安全粘贴到 CMD 的格式，防止误执行",
                            foreground='#888888')
        subtitle.pack(anchor='w', pady=(0, 15))
        
        # 输入区域
        input_label = ttk.Label(main_frame, text="📥 原始代码：")
        input_label.pack(anchor='w', pady=(0, 5))
        
        self.input_text = scrolledtext.ScrolledText(
            main_frame, height=10, 
            bg='#1e1e1e', fg='#d4d4d4',
            insertbackground='#ffffff',
            font=('Consolas', 10),
            borderwidth=0, relief='flat',
            wrap=tk.NONE
        )
        self.input_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 选项区域
        options_frame = ttk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(options_frame, text="🔧 保护方案：").pack(side=tk.LEFT, padx=(0, 10))
        
        self.mode = tk.StringVar(value="1")
        ttk.Radiobutton(options_frame, text="单行化（移除换行）", 
                       variable=self.mode, value="1",
                       command=self.auto_convert).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(options_frame, text="注释化（每行加 ::）", 
                       variable=self.mode, value="2",
                       command=self.auto_convert).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(options_frame, text="完全惰性化（最安全）", 
                       variable=self.mode, value="3",
                       command=self.auto_convert).pack(side=tk.LEFT, padx=5)
        
        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(btn_frame, text="🔄 转换", 
                  command=self.convert).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="📋 复制结果", 
                  command=self.copy_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="📥 从剪贴板导入", 
                  command=self.paste_from_clipboard).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🗑️ 清空", 
                  command=self.clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❓ 帮助", 
                  command=self.show_help).pack(side=tk.RIGHT)
        
        # 输出区域
        output_label = ttk.Label(main_frame, text="📤 安全代码（可粘贴到 CMD）：")
        output_label.pack(anchor='w', pady=(5, 5))
        
        self.output_text = scrolledtext.ScrolledText(
            main_frame, height=10,
            bg='#1e1e1e', fg='#4ec9b0',
            insertbackground='#ffffff',
            font=('Consolas', 10),
            borderwidth=0, relief='flat',
            wrap=tk.NONE
        )
        self.output_text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # 状态栏
        self.status_var = tk.StringVar(value="就绪 | 输入代码后点击「转换」")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, 
                              foreground='#888888', font=('Microsoft YaHei', 9))
        status_bar.pack(anchor='w', pady=(5, 0))
        
        # 绑定输入事件，实时转换
        self.input_text.bind('<KeyRelease>', lambda e: self.auto_convert())
    
    # ============ 核心转换逻辑 ============
    
    def safe_paste_singleline(self, code: str) -> str:
        """方案1：单行化"""
        return code.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')
    
    def safe_paste_comment(self, code: str) -> str:
        """方案2：每行注释"""
        lines = code.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        return '\r\n'.join(f':: {line}' for line in lines)
    
    def safe_paste_inert(self, code: str) -> str:
        """方案3：完全惰性化"""
        escaped = code.replace('^', '^^')
        for ch in ['&', '|', '<', '>', '"']:
            escaped = escaped.replace(ch, f'^{ch}')
        escaped = escaped.replace('%', '%%')
        escaped = escaped.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return f'rem {escaped}'
    
    # ============ 事件处理 ============
    
    def auto_convert(self):
        """实时自动转换"""
        code = self.input_text.get("1.0", tk.END).rstrip()
        if not code:
            self.output_text.delete("1.0", tk.END)
            return
        self.convert(silent=True)
    
    def convert(self, silent=False):
        """执行转换"""
        code = self.input_text.get("1.0", tk.END).rstrip()
        if not code:
            if not silent:
                messagebox.showwarning("提示", "请先输入要转换的代码")
            return
        
        mode = self.mode.get()
        if mode == "1":
            result = self.safe_paste_singleline(code)
            desc = "单行化"
        elif mode == "2":
            result = self.safe_paste_comment(code)
            desc = "注释化"
        else:
            result = self.safe_paste_inert(code)
            desc = "完全惰性化"
        
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", result)
        
        char_count = len(result)
        self.status_var.set(f"✓ 转换完成 [{desc}] | 输出长度: {char_count} 字符")
    
    def copy_result(self):
        """复制结果到剪贴板"""
        result = self.output_text.get("1.0", tk.END).rstrip()
        if not result:
            messagebox.showwarning("提示", "没有可复制的内容，请先转换")
            return
        try:
            pyperclip.copy(result)
            self.status_var.set("✓ 已复制到剪贴板，可直接 Ctrl+V 粘贴到 CMD")
            messagebox.showinfo("成功", "已复制到剪贴板！\n现在可以安全地粘贴到 CMD 了。")
        except Exception as e:
            messagebox.showerror("错误", f"复制失败: {e}")
    
    def paste_from_clipboard(self):
        """从剪贴板导入"""
        try:
            content = pyperclip.paste()
            if not content:
                messagebox.showwarning("提示", "剪贴板为空")
                return
            self.input_text.delete("1.0", tk.END)
            self.input_text.insert("1.0", content)
            self.auto_convert()
            self.status_var.set(f"✓ 已从剪贴板导入 {len(content)} 字符")
        except Exception as e:
            messagebox.showerror("错误", f"读取剪贴板失败: {e}")
    
    def clear_all(self):
        """清空所有内容"""
        self.input_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self.status_var.set("已清空")
    
    def show_help(self):
        """显示帮助"""
        help_text = """🛡️ CMD 安全粘贴工具 - 使用说明

【工作原理】
CMD 在粘贴多行内容时会立即执行带换行符的命令。
本工具通过移除换行符或注释化代码，避免误执行。

【三种方案】

▸ 单行化（推荐）
  将所有换行替换为 \\n 字面量
  保留代码可读性，且不会执行

▸ 注释化
  每行前加 :: 注释符
  保留多行格式，每行都是注释

▸ 完全惰性化（最安全）
  整体包装为 rem 注释
  适合敏感代码，绝对不会执行

【使用步骤】
1. 在「原始代码」区粘贴代码
2. 选择保护方案（实时预览）
3. 点击「复制结果」
4. 在 CMD 中 Ctrl+V 粘贴

【快捷操作】
• Ctrl+V 在输入框直接粘贴
• 输入时自动实时转换"""
        messagebox.showinfo("使用帮助", help_text)


def main():
    root = tk.Tk()
    app = SafePasteApp(root)
    
    # 居中窗口
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()


if __name__ == '__main__':
    main()