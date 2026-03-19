import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

import pandas as pd
import pdfplumber


class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("文件转换工具 - Excel转CSV / PDF转TXT")
        self.root.geometry("820x620")
        self.root.resizable(True, True)

        style = ttk.Style()
        style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"))
        style.configure("Sub.TLabel", font=("Microsoft YaHei", 10))
        style.configure("Action.TButton", font=("Microsoft YaHei", 10), padding=6)

        self._build_ui()

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="📄 文件转换工具", style="Title.TLabel").pack(pady=(0, 10))

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        tab_excel = ttk.Frame(notebook, padding=15)
        notebook.add(tab_excel, text="  Excel ➜ CSV  ")
        self._build_excel_tab(tab_excel)

        tab_pdf = ttk.Frame(notebook, padding=15)
        notebook.add(tab_pdf, text="  PDF ➜ TXT  ")
        self._build_pdf_tab(tab_pdf)

        log_frame = ttk.LabelFrame(main_frame, text="运行日志", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=8, font=("Consolas", 9),
            state=tk.DISABLED, wrap=tk.WORD
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.progress = ttk.Progressbar(main_frame, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(8, 0))

    def _build_excel_tab(self, parent):
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="Excel 文件:", style="Sub.TLabel").pack(side=tk.LEFT)
        self.excel_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.excel_path_var, width=50).pack(
            side=tk.LEFT, padx=8, fill=tk.X, expand=True
        )
        ttk.Button(file_frame, text="浏览...", command=self._browse_excel).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="批量选择", command=self._browse_excel_multi).pack(side=tk.LEFT, padx=(5, 0))

        out_frame = ttk.Frame(parent)
        out_frame.pack(fill=tk.X, pady=5)
        ttk.Label(out_frame, text="输出目录:", style="Sub.TLabel").pack(side=tk.LEFT)
        self.excel_out_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.excel_out_var, width=50).pack(
            side=tk.LEFT, padx=8, fill=tk.X, expand=True
        )
        ttk.Button(out_frame, text="浏览...", command=self._browse_excel_out).pack(side=tk.LEFT)

        opt_frame = ttk.Frame(parent)
        opt_frame.pack(fill=tk.X, pady=8)
        ttk.Label(opt_frame, text="编码:").pack(side=tk.LEFT)
        self.csv_encoding_var = tk.StringVar(value="utf-8-sig")
        ttk.Combobox(
            opt_frame, textvariable=self.csv_encoding_var, width=12,
            values=["utf-8-sig", "utf-8", "gbk", "gb2312", "latin-1"], state="readonly"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Label(opt_frame, text="分隔符:").pack(side=tk.LEFT, padx=(15, 0))
        self.csv_sep_var = tk.StringVar(value=",")
        ttk.Combobox(
            opt_frame, textvariable=self.csv_sep_var, width=6,
            values=[",", ";", "\\t", "|"], state="readonly"
        ).pack(side=tk.LEFT, padx=5)

        self.all_sheets_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opt_frame, text="转换所有Sheet", variable=self.all_sheets_var).pack(side=tk.LEFT, padx=15)

        ttk.Button(parent, text="🚀 开始转换", style="Action.TButton",
                   command=self._convert_excel).pack(pady=15)
        self.excel_files = []

    def _build_pdf_tab(self, parent):
        file_frame = ttk.Frame(parent)
        file_frame.pack(fill=tk.X, pady=5)
        ttk.Label(file_frame, text="PDF 文件:", style="Sub.TLabel").pack(side=tk.LEFT)
        self.pdf_path_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.pdf_path_var, width=50).pack(
            side=tk.LEFT, padx=8, fill=tk.X, expand=True
        )
        ttk.Button(file_frame, text="浏览...", command=self._browse_pdf).pack(side=tk.LEFT)
        ttk.Button(file_frame, text="批量选择", command=self._browse_pdf_multi).pack(side=tk.LEFT, padx=(5, 0))

        out_frame = ttk.Frame(parent)
        out_frame.pack(fill=tk.X, pady=5)
        ttk.Label(out_frame, text="输出目录:", style="Sub.TLabel").pack(side=tk.LEFT)
        self.pdf_out_var = tk.StringVar()
        ttk.Entry(out_frame, textvariable=self.pdf_out_var, width=50).pack(
            side=tk.LEFT, padx=8, fill=tk.X, expand=True
        )
        ttk.Button(out_frame, text="浏览...", command=self._browse_pdf_out).pack(side=tk.LEFT)

        opt_frame = ttk.Frame(parent)
        opt_frame.pack(fill=tk.X, pady=8)
        ttk.Label(opt_frame, text="页码范围:").pack(side=tk.LEFT)
        self.pdf_pages_var = tk.StringVar(value="全部")
        ttk.Entry(opt_frame, textvariable=self.pdf_pages_var, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(opt_frame, text="(如: 1-5 或 1,3,5 或 全部)", foreground="gray").pack(side=tk.LEFT, padx=5)

        ttk.Label(opt_frame, text="编码:").pack(side=tk.LEFT, padx=(15, 0))
        self.txt_encoding_var = tk.StringVar(value="utf-8")
        ttk.Combobox(
            opt_frame, textvariable=self.txt_encoding_var, width=12,
            values=["utf-8", "gbk", "gb2312", "latin-1"], state="readonly"
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(parent, text="🚀 开始转换", style="Action.TButton",
                   command=self._convert_pdf).pack(pady=15)
        self.pdf_files = []

    # ==================== 文件浏览 ====================
    def _browse_excel(self):
        path = filedialog.askopenfilename(
            title="选择 Excel 文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls *.xlsm"), ("所有文件", "*.*")]
        )
        if path:
            self.excel_path_var.set(path)
            self.excel_files = [path]
            if not self.excel_out_var.get():
                self.excel_out_var.set(os.path.dirname(path))

    def _browse_excel_multi(self):
        paths = filedialog.askopenfilenames(
            title="批量选择 Excel 文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls *.xlsm"), ("所有文件", "*.*")]
        )
        if paths:
            self.excel_files = list(paths)
            self.excel_path_var.set(f"已选择 {len(paths)} 个文件")
            if not self.excel_out_var.get():
                self.excel_out_var.set(os.path.dirname(paths[0]))

    def _browse_excel_out(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.excel_out_var.set(path)

    def _browse_pdf(self):
        path = filedialog.askopenfilename(
            title="选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        if path:
            self.pdf_path_var.set(path)
            self.pdf_files = [path]
            if not self.pdf_out_var.get():
                self.pdf_out_var.set(os.path.dirname(path))

    def _browse_pdf_multi(self):
        paths = filedialog.askopenfilenames(
            title="批量选择 PDF 文件",
            filetypes=[("PDF 文件", "*.pdf"), ("所有文件", "*.*")]
        )
        if paths:
            self.pdf_files = list(paths)
            self.pdf_path_var.set(f"已选择 {len(paths)} 个文件")
            if not self.pdf_out_var.get():
                self.pdf_out_var.set(os.path.dirname(paths[0]))

    def _browse_pdf_out(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.pdf_out_var.set(path)

    # ==================== 日志 ====================
    def _log(self, message):
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    # ==================== 解析页码 ====================
    def _parse_pages(self, pages_str, total_pages):
        pages_str = pages_str.strip()
        if pages_str in ("全部", "all", ""):
            return list(range(total_pages))
        pages = set()
        parts = pages_str.replace("，", ",").split(",")
        for part in parts:
            part = part.strip()
            if "-" in part:
                start, end = part.split("-", 1)
                start = max(1, int(start.strip()))
                end = min(total_pages, int(end.strip()))
                for i in range(start, end + 1):
                    pages.add(i - 1)
            else:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
        return sorted(pages)

    # ==================== Excel 转换 ====================
    def _convert_excel(self):
        if not self.excel_files:
            messagebox.showwarning("提示", "请先选择 Excel 文件！")
            return
        out_dir = self.excel_out_var.get().strip()
        if not out_dir:
            messagebox.showwarning("提示", "请选择输出目录！")
            return
        os.makedirs(out_dir, exist_ok=True)
        self.progress.start(10)

        def task():
            encoding = self.csv_encoding_var.get()
            sep = self.csv_sep_var.get()
            if sep == "\\t":
                sep = "\t"
            all_sheets = self.all_sheets_var.get()
            success, fail = 0, 0

            for filepath in self.excel_files:
                try:
                    filename = os.path.splitext(os.path.basename(filepath))[0]
                    self._log(f"[Excel] 正在处理: {os.path.basename(filepath)}")
                    if all_sheets:
                        xls = pd.ExcelFile(filepath)
                        sheet_names = xls.sheet_names
                        for sheet in sheet_names:
                            df = pd.read_excel(filepath, sheet_name=sheet)
                            out_name = f"{filename}_{sheet}.csv" if len(sheet_names) > 1 else f"{filename}.csv"
                            df.to_csv(os.path.join(out_dir, out_name), index=False, encoding=encoding, sep=sep)
                            self._log(f"  ✅ Sheet '{sheet}' -> {out_name} ({len(df)} 行)")
                    else:
                        df = pd.read_excel(filepath)
                        df.to_csv(os.path.join(out_dir, f"{filename}.csv"), index=False, encoding=encoding, sep=sep)
                        self._log(f"  ✅ -> {filename}.csv ({len(df)} 行)")
                    success += 1
                except Exception as e:
                    fail += 1
                    self._log(f"  ❌ 失败: {e}")

            self._log(f"[Excel] 完成！成功: {success}, 失败: {fail}\n{'=' * 50}")
            self.root.after(0, self._on_task_done, success, fail)

        threading.Thread(target=task, daemon=True).start()

    # ==================== PDF 转换 ====================
    def _convert_pdf(self):
        if not self.pdf_files:
            messagebox.showwarning("提示", "请先选择 PDF 文件！")
            return
        out_dir = self.pdf_out_var.get().strip()
        if not out_dir:
            messagebox.showwarning("提示", "请选择输出目录！")
            return
        os.makedirs(out_dir, exist_ok=True)
        self.progress.start(10)

        def task():
            encoding = self.txt_encoding_var.get()
            pages_str = self.pdf_pages_var.get()
            success, fail = 0, 0

            for filepath in self.pdf_files:
                try:
                    filename = os.path.splitext(os.path.basename(filepath))[0]
                    self._log(f"[PDF] 正在处理: {os.path.basename(filepath)}")
                    text_parts = []
                    with pdfplumber.open(filepath) as pdf:
                        total_pages = len(pdf.pages)
                        page_indices = self._parse_pages(pages_str, total_pages)
                        self._log(f"  共 {total_pages} 页, 提取 {len(page_indices)} 页")
                        for idx in page_indices:
                            page_text = pdf.pages[idx].extract_text()
                            if page_text:
                                text_parts.append(f"--- 第 {idx + 1} 页 ---\n{page_text}")
                            else:
                                text_parts.append(f"--- 第 {idx + 1} 页 ---\n[该页无可提取文字]")

                    full_text = "\n\n".join(text_parts)
                    with open(os.path.join(out_dir, f"{filename}.txt"), "w", encoding=encoding) as f:
                        f.write(full_text)
                    self._log(f"  ✅ -> {filename}.txt ({len(full_text)} 字符)")
                    success += 1
                except Exception as e:
                    fail += 1
                    self._log(f"  ❌ 失败: {e}")

            self._log(f"[PDF] 完成！成功: {success}, 失败: {fail}\n{'=' * 50}")
            self.root.after(0, self._on_task_done, success, fail)

        threading.Thread(target=task, daemon=True).start()

    def _on_task_done(self, success, fail):
        self.progress.stop()
        if fail == 0:
            messagebox.showinfo("完成", f"全部转换成功！共 {success} 个文件。")
        else:
            messagebox.showwarning("完成", f"成功: {success}, 失败: {fail}\n请查看日志了解详情。")


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()