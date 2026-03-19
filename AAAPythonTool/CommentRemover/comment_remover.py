import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import re
from collections import defaultdict


class CommentInfo:
    """存储单条注释的信息"""
    def __init__(self, text, comment_type, line_num, start_pos, end_pos, has_chinese, has_english, is_pure_english):
        self.text = text
        self.comment_type = comment_type  # 'single_line_slash', 'single_line_hash', 'multi_line_slash', 'multi_line_hash', 'html_comment'
        self.line_num = line_num
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.has_chinese = has_chinese
        self.has_english = has_english
        self.is_pure_english = is_pure_english
        self.is_pure_chinese = has_chinese and not has_english


class CommentScanner:
    """注释扫描器，支持多种语言的注释格式"""

    CHINESE_PATTERN = re.compile(r'[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]')
    ENGLISH_PATTERN = re.compile(r'[a-zA-Z]')

    def __init__(self):
        self.comments = []

    def has_chinese(self, text):
        return bool(self.CHINESE_PATTERN.search(text))

    def has_english(self, text):
        return bool(self.ENGLISH_PATTERN.search(text))

    def scan(self, code):
        """扫描代码中的所有注释"""
        self.comments = []
        self._scan_single_line_slash(code)
        self._scan_single_line_hash(code)
        self._scan_multi_line_slash(code)
        self._scan_html_comments(code)
        self._scan_triple_quote_comments(code)

        # 去重 (按位置)
        seen = set()
        unique = []
        for c in self.comments:
            key = (c.start_pos, c.end_pos)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        # 处理重叠：如果一个注释被另一个包含，只保留外层的
        unique.sort(key=lambda c: (c.start_pos, -c.end_pos))
        filtered = []
        max_end = -1
        for c in unique:
            if c.start_pos >= max_end:
                filtered.append(c)
                max_end = c.end_pos
            # 如果被包含则跳过

        self.comments = filtered
        self.comments.sort(key=lambda c: c.start_pos)
        return self.comments

    def _make_comment(self, text, comment_type, line_num, start_pos, end_pos):
        hc = self.has_chinese(text)
        he = self.has_english(text)
        pure_eng = he and not hc
        return CommentInfo(text, comment_type, line_num, start_pos, end_pos, hc, he, pure_eng)

    def _scan_single_line_slash(self, code):
        """扫描 // 单行注释"""
        # 需要排除在字符串内部的情况
        for match in re.finditer(r'//[^\n]*', code):
            if not self._is_in_string(code, match.start()):
                line_num = code[:match.start()].count('\n') + 1
                self.comments.append(
                    self._make_comment(match.group(), 'single_line_slash', line_num, match.start(), match.end())
                )

    def _scan_single_line_hash(self, code):
        """扫描 # 单行注释"""
        for match in re.finditer(r'#[^\n]*', code):
            if not self._is_in_string(code, match.start()):
                # 排除 #! (shebang), #include, #define 等预处理指令
                stripped = match.group().strip()
                if stripped.startswith('#!') or stripped.startswith('#include') or \
                   stripped.startswith('#define') or stripped.startswith('#ifdef') or \
                   stripped.startswith('#ifndef') or stripped.startswith('#endif') or \
                   stripped.startswith('#pragma') or stripped.startswith('#if ') or \
                   stripped.startswith('#else') or stripped.startswith('#elif'):
                    continue
                line_num = code[:match.start()].count('\n') + 1
                self.comments.append(
                    self._make_comment(match.group(), 'single_line_hash', line_num, match.start(), match.end())
                )

    def _scan_multi_line_slash(self, code):
        """扫描 /* */ 多行注释"""
        for match in re.finditer(r'/\*[\s\S]*?\*/', code):
            if not self._is_in_string(code, match.start()):
                line_num = code[:match.start()].count('\n') + 1
                self.comments.append(
                    self._make_comment(match.group(), 'multi_line_slash', line_num, match.start(), match.end())
                )

    def _scan_html_comments(self, code):
        """扫描 <!-- --> HTML注释"""
        for match in re.finditer(r'<!--[\s\S]*?-->', code):
            line_num = code[:match.start()].count('\n') + 1
            self.comments.append(
                self._make_comment(match.group(), 'html_comment', line_num, match.start(), match.end())
            )

    def _scan_triple_quote_comments(self, code):
        """扫描 Python 三引号注释/文档字符串"""
        for match in re.finditer(r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\')', code):
            line_num = code[:match.start()].count('\n') + 1
            self.comments.append(
                self._make_comment(match.group(), 'triple_quote', line_num, match.start(), match.end())
            )

    def _is_in_string(self, code, pos):
        """简单判断某个位置是否在字符串内部"""
        in_single = False
        in_double = False
        i = 0
        while i < pos:
            ch = code[i]
            if ch == '\\':
                i += 2
                continue
            if ch == "'" and not in_double:
                in_single = not in_single
            elif ch == '"' and not in_single:
                in_double = not in_double
            i += 1
        return in_single or in_double

    def classify(self):
        """将注释分类统计"""
        categories = {
            'type': defaultdict(list),
            'lang': defaultdict(list),
            'content': defaultdict(list),
        }

        for c in self.comments:
            # 按注释语法类型
            categories['type'][c.comment_type].append(c)

            # 按内容语言
            if c.has_chinese and c.has_english:
                categories['lang']['mixed'].append(c)
            elif c.has_chinese:
                categories['lang']['chinese'].append(c)
            elif c.has_english:
                categories['lang']['english'].append(c)
            else:
                categories['lang']['other'].append(c)

            # 按内容特征
            stripped = c.text.strip().lstrip('/#*<!-> ').strip()
            if stripped == '' or all(ch in ' \t\n\r/*#-!<>' for ch in c.text):
                categories['content']['empty'].append(c)
            elif stripped.upper().startswith('TODO') or stripped.upper().startswith('FIXME') or \
                stripped.upper().startswith('HACK') or stripped.upper().startswith('XXX') or \
                stripped.upper().startswith('BUG') or stripped.upper().startswith('NOTE'):
                categories['content']['todo_fixme'].append(c)

        return categories


class CommentRemoverApp:
    def __init__(self, root):
        self.root = root
        self.root.title("🔧 代码注释处理工具")
        self.root.geometry("1300x900")
        self.root.minsize(1100, 700)

        self.scanner = CommentScanner()
        self.comments = []
        self.categories = {}

        # 勾选变量
        self.filter_vars = {}

        self._build_ui()
        self._apply_style()

    def _apply_style(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Title.TLabel', font=('Microsoft YaHei', 14, 'bold'), foreground='#2c3e50')
        style.configure('Sub.TLabel', font=('Microsoft YaHei', 10), foreground='#555')
        style.configure('TButton', font=('Microsoft YaHei', 10), padding=6)
        style.configure('Accent.TButton', font=('Microsoft YaHei', 10, 'bold'))
        style.configure('TCheckbutton', font=('Microsoft YaHei', 10))
        style.configure('Treeview', font=('Consolas', 9), rowheight=24)
        style.configure('Treeview.Heading', font=('Microsoft YaHei', 10, 'bold'))

    def _build_ui(self):
        # ── 顶部工具栏 ──
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(fill=tk.X)

        ttk.Label(toolbar, text="🔧 代码注释处理工具", style='Title.TLabel').pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(toolbar)
        btn_frame.pack(side=tk.RIGHT)

        ttk.Button(btn_frame, text="📂 打开文件", command=self._open_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="💾 保存结果", command=self._save_file).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="📋 粘贴代码", command=self._paste_code).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_frame, text="🗑 清空", command=self._clear_all).pack(side=tk.LEFT, padx=3)

        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=5)

        # ── 主布局 (PanedWindow) ──
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # == 左侧面板：源代码 + 结果 ==
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=3)

        left_paned = ttk.PanedWindow(left_frame, orient=tk.VERTICAL)
        left_paned.pack(fill=tk.BOTH, expand=True)

        # 源代码区域
        src_frame = ttk.LabelFrame(left_frame, text="📝 源代码", padding=5)
        left_paned.add(src_frame, weight=1)

        self.source_text = scrolledtext.ScrolledText(
            src_frame, wrap=tk.NONE, font=('Consolas', 11),
            bg='#1e1e1e', fg='#d4d4d4', insertbackground='white',
            selectbackground='#264f78', selectforeground='white',
            undo=True
        )
        self.source_text.pack(fill=tk.BOTH, expand=True)

        # 水平滚动条
        h_scroll_src = ttk.Scrollbar(src_frame, orient=tk.HORIZONTAL, command=self.source_text.xview)
        h_scroll_src.pack(fill=tk.X)
        self.source_text.configure(xscrollcommand=h_scroll_src.set)

        # 操作按钮区域
        action_frame = ttk.Frame(left_frame, padding=5)
        left_paned.add(action_frame, weight=0)

        ttk.Button(action_frame, text="🔍 扫描注释", command=self._scan_comments,
                    style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="⚡ 执行移除", command=self._remove_comments,
                    style='Accent.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="👁 预览结果", command=self._preview_result).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="↩ 还原到源码", command=self._restore_source).pack(side=tk.LEFT, padx=5)

        self.status_label = ttk.Label(action_frame, text="就绪", style='Sub.TLabel')
        self.status_label.pack(side=tk.RIGHT, padx=10)

        # 结果区域
        result_frame = ttk.LabelFrame(left_frame, text="✅ 处理结果", padding=5)
        left_paned.add(result_frame, weight=1)

        self.result_text = scrolledtext.ScrolledText(
            result_frame, wrap=tk.NONE, font=('Consolas', 11),
            bg='#1a2332', fg='#9cdcfe', insertbackground='white',
            selectbackground='#264f78', selectforeground='white',
            state=tk.NORMAL
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        h_scroll_res = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=self.result_text.xview)
        h_scroll_res.pack(fill=tk.X)
        self.result_text.configure(xscrollcommand=h_scroll_res.set)

        # == 右侧面板：过滤选项 + 注释列表 ==
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)

        right_paned = ttk.PanedWindow(right_frame, orient=tk.VERTICAL)
        right_paned.pack(fill=tk.BOTH, expand=True)

        # 过滤选项区域
        filter_frame = ttk.LabelFrame(right_frame, text="⚙ 过滤选项 (勾选 = 要移除的类别)", padding=8)
        right_paned.add(filter_frame, weight=1)

        # -- 按注释语法分类 --
        ttk.Label(filter_frame, text="━━ 按注释语法类型 ━━", font=('Microsoft YaHei', 10, 'bold'),
                  foreground='#e67e22').pack(anchor=tk.W, pady=(2, 5))

        syntax_items = [
            ('remove_single_slash', '移除 // 单行注释', True),
            ('remove_single_hash', '移除 # 单行注释', True),
            ('remove_multi_slash', '移除 /* */ 多行注释', True),
            ('remove_html', '移除 <!-- --> HTML注释', True),
            ('remove_triple_quote', '移除 三引号注释/文档字符串', False),
        ]

        for key, label, default in syntax_items:
            var = tk.BooleanVar(value=default)
            self.filter_vars[key] = var
            cb = ttk.Checkbutton(filter_frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=15, pady=1)

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # -- 按内容语言分类 --
        ttk.Label(filter_frame, text="━━ 按内容语言 (保留) ━━", font=('Microsoft YaHei', 10, 'bold'),
                  foreground='#27ae60').pack(anchor=tk.W, pady=(2, 5))

        lang_items = [
            ('keep_chinese', '✅ 保留含中文的注释', False),
            ('keep_english', '✅ 保留纯英文的注释', False),
            ('keep_mixed', '✅ 保留中英混合的注释', False),
            ('keep_other', '✅ 保留其他注释(纯符号/数字)', False),
        ]

        for key, label, default in lang_items:
            var = tk.BooleanVar(value=default)
            self.filter_vars[key] = var
            cb = ttk.Checkbutton(filter_frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=15, pady=1)

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # -- 按内容特征 --
        ttk.Label(filter_frame, text="━━ 按内容特征 (保留) ━━", font=('Microsoft YaHei', 10, 'bold'),
                  foreground='#8e44ad').pack(anchor=tk.W, pady=(2, 5))

        content_items = [
            ('keep_todo', '✅ 保留 TODO/FIXME/NOTE 注释', True),
            ('keep_empty', '✅ 保留空注释(仅符号)', False),
        ]

        for key, label, default in content_items:
            var = tk.BooleanVar(value=default)
            self.filter_vars[key] = var
            cb = ttk.Checkbutton(filter_frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=15, pady=1)

        ttk.Separator(filter_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=8)

        # -- 额外选项 --
        ttk.Label(filter_frame, text="━━ 额外选项 ━━", font=('Microsoft YaHei', 10, 'bold'),
                  foreground='#2980b9').pack(anchor=tk.W, pady=(2, 5))

        extra_items = [
            ('remove_blank_lines', '移除因删注释产生的空行', True),
            ('remove_trailing_spaces', '移除行尾多余空格', True),
        ]

        for key, label, default in extra_items:
            var = tk.BooleanVar(value=default)
            self.filter_vars[key] = var
            cb = ttk.Checkbutton(filter_frame, text=label, variable=var)
            cb.pack(anchor=tk.W, padx=15, pady=1)

        # 快捷按钮
        quick_frame = ttk.Frame(filter_frame)
        quick_frame.pack(fill=tk.X, pady=8)
        ttk.Button(quick_frame, text="全移除", command=self._select_all_remove).pack(side=tk.LEFT, padx=3)
        ttk.Button(quick_frame, text="全保留", command=self._select_all_keep).pack(side=tk.LEFT, padx=3)
        ttk.Button(quick_frame, text="仅移除英文注释", command=self._preset_remove_english_only).pack(side=tk.LEFT, padx=3)

        # 注释列表区域
        list_frame = ttk.LabelFrame(right_frame, text="📋 扫描到的注释列表", padding=5)
        right_paned.add(list_frame, weight=2)

        # 统计信息
        self.stats_label = ttk.Label(list_frame, text="尚未扫描", style='Sub.TLabel')
        self.stats_label.pack(anchor=tk.W, pady=(0, 5))

        # Treeview
        columns = ('line', 'type', 'lang', 'preview')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', selectmode='extended')
        self.tree.heading('line', text='行号')
        self.tree.heading('type', text='类型')
        self.tree.heading('lang', text='语言')
        self.tree.heading('preview', text='注释内容预览')

        self.tree.column('line', width=50, minwidth=40)
        self.tree.column('type', width=100, minwidth=80)
        self.tree.column('lang', width=70, minwidth=60)
        self.tree.column('preview', width=400, minwidth=200)

        tree_scroll_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

        # 双击查看完整注释
        self.tree.bind('<Double-1>', self._show_comment_detail)

        # 源码高亮tag
        self.source_text.tag_configure('comment_highlight', background='#4a2020', foreground='#ff6b6b')
        self.source_text.tag_configure('kept_highlight', background='#1a3a1a', foreground='#6bff6b')

    # ──────── 功能方法 ────────

    def _open_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[
                ("所有支持的文件", "*.py *.js *.ts *.java *.c *.cpp *.h *.hpp *.cs *.go *.rs *.php *.html *.css *.xml *.sql *.rb *.swift *.kt *.lua *.sh *.txt"),
                ("Python", "*.py"),
                ("JavaScript/TypeScript", "*.js *.ts *.jsx *.tsx"),
                ("C/C++", "*.c *.cpp *.h *.hpp"),
                ("Java", "*.java"),
                ("HTML/CSS/XML", "*.html *.css *.xml"),
                ("所有文件", "*.*"),
            ]
        )
        if filepath:
            try:
                # 尝试多种编码
                content = None
                for encoding in ['utf-8', 'gbk', 'gb2312', 'utf-16', 'latin-1']:
                    try:
                        with open(filepath, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                if content is None:
                    messagebox.showerror("错误", "无法识别文件编码")
                    return

                self.source_text.delete('1.0', tk.END)
                self.source_text.insert('1.0', content)
                self.status_label.config(text=f"已加载: {filepath}")
                self._current_file = filepath
            except Exception as e:
                messagebox.showerror("错误", f"打开文件失败: {e}")

    def _save_file(self):
        content = self.result_text.get('1.0', tk.END).rstrip('\n')
        if not content.strip():
            messagebox.showwarning("提示", "结果区域为空，无内容可保存")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("所有文件", "*.*"), ("Python", "*.py"), ("文本文件", "*.txt")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.status_label.config(text=f"已保存: {filepath}")
                messagebox.showinfo("成功", "文件保存成功!")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}")

    def _paste_code(self):
        try:
            clipboard = self.root.clipboard_get()
            self.source_text.delete('1.0', tk.END)
            self.source_text.insert('1.0', clipboard)
            self.status_label.config(text="已从剪贴板粘贴")
        except tk.TclError:
            messagebox.showwarning("提示", "剪贴板为空")

    def _clear_all(self):
        self.source_text.delete('1.0', tk.END)
        self.result_text.delete('1.0', tk.END)
        self.tree.delete(*self.tree.get_children())
        self.comments = []
        self.stats_label.config(text="尚未扫描")
        self.status_label.config(text="已清空")

    def _scan_comments(self):
        code = self.source_text.get('1.0', tk.END)
        if not code.strip():
            messagebox.showwarning("提示", "请先输入或加载代码")
            return

        self.scanner = CommentScanner()
        self.comments = self.scanner.scan(code)
        self.categories = self.scanner.classify()

        # 清除旧高亮
        self.source_text.tag_remove('comment_highlight', '1.0', tk.END)
        self.source_text.tag_remove('kept_highlight', '1.0', tk.END)

        # 更新列表
        self.tree.delete(*self.tree.get_children())

        type_names = {
            'single_line_slash': '// 单行',
            'single_line_hash': '# 单行',
            'multi_line_slash': '/* */ 多行',
            'html_comment': 'HTML注释',
            'triple_quote': '三引号',
        }

        for i, c in enumerate(self.comments):
            lang = '中文' if c.has_chinese and not c.has_english else \
                   '英文' if c.is_pure_english else \
                   '中英混合' if c.has_chinese and c.has_english else '其他'

            preview = c.text.replace('\n', '↵ ')[:120]
            self.tree.insert('', tk.END, iid=str(i), values=(
                c.line_num,
                type_names.get(c.comment_type, c.comment_type),
                lang,
                preview
            ))

            # 在源码中高亮
            start_idx = f"1.0+{c.start_pos}c"
            end_idx = f"1.0+{c.end_pos}c"
            self.source_text.tag_add('comment_highlight', start_idx, end_idx)

        # 统计
        type_counts = {}
        for c in self.comments:
            t = type_names.get(c.comment_type, c.comment_type)
            type_counts[t] = type_counts.get(t, 0) + 1

        lang_counts = {'中文': 0, '英文': 0, '中英混合': 0, '其他': 0}
        for c in self.comments:
            if c.has_chinese and not c.has_english:
                lang_counts['中文'] += 1
            elif c.is_pure_english:
                lang_counts['英文'] += 1
            elif c.has_chinese and c.has_english:
                lang_counts['中英混合'] += 1
            else:
                lang_counts['其他'] += 1

        stats = f"共 {len(self.comments)} 条注释 | "
        stats += " | ".join(f"{k}:{v}" for k, v in type_counts.items())
        stats += " || "
        stats += " | ".join(f"{k}:{v}" for k, v in lang_counts.items() if v > 0)

        self.stats_label.config(text=stats)
        self.status_label.config(text=f"扫描完成: 发现 {len(self.comments)} 条注释")

    def _should_remove(self, comment):
        """根据过滤条件判断是否应该移除此注释"""
        fv = self.filter_vars

        # 第一步：检查该注释的语法类型是否被选中移除
        type_check = {
            'single_line_slash': fv['remove_single_slash'].get(),
            'single_line_hash': fv['remove_single_hash'].get(),
            'multi_line_slash': fv['remove_multi_slash'].get(),
            'html_comment': fv['remove_html'].get(),
            'triple_quote': fv['remove_triple_quote'].get(),
        }

        if not type_check.get(comment.comment_type, False):
            return False  # 这个类型未被勾选移除，保留

        # 第二步：检查"保留"规则，如果命中保留条件则不移除
        # 语言保留
        if fv['keep_chinese'].get() and comment.has_chinese and not comment.has_english:
            return False
        if fv['keep_english'].get() and comment.is_pure_english:
            return False
        if fv['keep_mixed'].get() and comment.has_chinese and comment.has_english:
            return False
        if fv['keep_other'].get() and not comment.has_chinese and not comment.has_english:
            return False

        # 内容特征保留
        stripped = comment.text.strip().lstrip('/#*<!-> ').strip().upper()
        is_todo = any(stripped.startswith(tag) for tag in ['TODO', 'FIXME', 'HACK', 'XXX', 'BUG', 'NOTE'])
        is_empty = all(ch in ' \t\n\r/*#-!<>' for ch in comment.text)

        if fv['keep_todo'].get() and is_todo:
            return False
        if fv['keep_empty'].get() and is_empty:
            return False

        return True

    def _remove_comments(self):
        if not self.comments:
            messagebox.showwarning("提示", "请先扫描注释")
            return

        code = self.source_text.get('1.0', tk.END)

        # 确定哪些注释要移除
        to_remove = []
        to_keep = []
        for c in self.comments:
            if self._should_remove(c):
                to_remove.append(c)
            else:
                to_keep.append(c)

        # 按位置倒序移除
        to_remove.sort(key=lambda c: c.start_pos, reverse=True)

        result = code
        for c in to_remove:
            before = result[:c.start_pos]
            after = result[c.end_pos:]

            # 如果注释占了整行（前面只有空白），移除整行
            line_start = before.rfind('\n') + 1
            line_prefix = before[line_start:]
            if line_prefix.strip() == '':
                # 检查注释后面到行尾是否也只有空白
                next_newline = after.find('\n')
                if next_newline == -1:
                    line_suffix = after
                else:
                    line_suffix = after[:next_newline]

                if line_suffix.strip() == '':
                    # 整行都是注释，移除整行
                    result = before[:line_start] + (after[next_newline + 1:] if next_newline != -1 else '')
                else:
                    result = before + after
            else:
                result = before + after

        # 后处理
        if self.filter_vars['remove_trailing_spaces'].get():
            lines = result.split('\n')
            lines = [line.rstrip() for line in lines]
            result = '\n'.join(lines)

        if self.filter_vars['remove_blank_lines'].get():
            # 移除连续超过2行的空行
            lines = result.split('\n')
            cleaned = []
            blank_count = 0
            for line in lines:
                if line.strip() == '':
                    blank_count += 1
                    if blank_count <= 1:
                        cleaned.append(line)
                else:
                    blank_count = 0
                    cleaned.append(line)
            result = '\n'.join(cleaned)

        # 显示结果
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert('1.0', result.rstrip('\n'))

        # 更新源码高亮
        self.source_text.tag_remove('comment_highlight', '1.0', tk.END)
        self.source_text.tag_remove('kept_highlight', '1.0', tk.END)

        for c in to_remove:
            start_idx = f"1.0+{c.start_pos}c"
            end_idx = f"1.0+{c.end_pos}c"
            self.source_text.tag_add('comment_highlight', start_idx, end_idx)

        for c in to_keep:
            start_idx = f"1.0+{c.start_pos}c"
            end_idx = f"1.0+{c.end_pos}c"
            self.source_text.tag_add('kept_highlight', start_idx, end_idx)

        self.status_label.config(text=f"完成: 移除 {len(to_remove)} 条, 保留 {len(to_keep)} 条注释")

    def _preview_result(self):
        """预览将要移除的注释（不实际移除，只标记）"""
        if not self.comments:
            messagebox.showwarning("提示", "请先扫描注释")
            return

        self.source_text.tag_remove('comment_highlight', '1.0', tk.END)
        self.source_text.tag_remove('kept_highlight', '1.0', tk.END)

        remove_count = 0
        keep_count = 0
        for c in self.comments:
            start_idx = f"1.0+{c.start_pos}c"
            end_idx = f"1.0+{c.end_pos}c"
            if self._should_remove(c):
                self.source_text.tag_add('comment_highlight', start_idx, end_idx)
                remove_count += 1
            else:
                self.source_text.tag_add('kept_highlight', start_idx, end_idx)
                keep_count += 1

        self.status_label.config(text=f"预览: 🔴将移除 {remove_count} 条 | 🟢将保留 {keep_count} 条 (红=移除, 绿=保留)")

    def _restore_source(self):
        """将源码区内容复制到结果区"""
        content = self.source_text.get('1.0', tk.END)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert('1.0', content.rstrip('\n'))
        self.status_label.config(text="已还原到源码")

    def _show_comment_detail(self, event):
        """双击注释查看完整内容"""
        selected = self.tree.selection()
        if not selected:
            return
        idx = int(selected[0])
        if idx < len(self.comments):
            c = self.comments[idx]
            detail_win = tk.Toplevel(self.root)
            detail_win.title(f"注释详情 - 第 {c.line_num} 行")
            detail_win.geometry("600x400")

            info_text = f"类型: {c.comment_type}\n"
            info_text += f"行号: {c.line_num}\n"
            info_text += f"含中文: {'是' if c.has_chinese else '否'}  |  含英文: {'是' if c.has_english else '否'}\n"
            info_text += f"将被移除: {'是' if self._should_remove(c) else '否'}\n"
            info_text += "─" * 40 + "\n"

            ttk.Label(detail_win, text=info_text, font=('Microsoft YaHei', 10), justify=tk.LEFT).pack(
                anchor=tk.W, padx=10, pady=5)

            text = scrolledtext.ScrolledText(detail_win, font=('Consolas', 11), wrap=tk.WORD,
                                             bg='#1e1e1e', fg='#d4d4d4')
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            text.insert('1.0', c.text)
            text.config(state=tk.DISABLED)

    # ──────── 预设方法 ────────

    def _select_all_remove(self):
        """全部移除"""
        for key, var in self.filter_vars.items():
            if key.startswith('remove_'):
                var.set(True)
            elif key.startswith('keep_'):
                var.set(False)

    def _select_all_keep(self):
        """全部保留"""
        for key, var in self.filter_vars.items():
            if key.startswith('remove_'):
                var.set(False)

    def _preset_remove_english_only(self):
        """仅移除英文注释，保留中文"""
        for key, var in self.filter_vars.items():
            if key.startswith('remove_'):
                var.set(True)
        self.filter_vars['keep_chinese'].set(True)
        self.filter_vars['keep_mixed'].set(True)
        self.filter_vars['keep_english'].set(False)
        self.filter_vars['keep_other'].set(False)
        self.filter_vars['keep_todo'].set(True)


def main():
    root = tk.Tk()

    # 尝试设置DPI缩放
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = CommentRemoverApp(root)

    # 插入示例代码
    sample_code = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
这是一个示例Python文件
用于演示注释处理工具的功能
"""

# 这是一个中文单行注释
# This is an English single line comment
# TODO: 这里需要优化性能

def hello():
    """文档字符串: 打印问候语"""
    print("Hello World")  # 行尾注释 inline comment
    x = 10  # 设置x的值
    return x

/*
 * 这是C风格的多行注释
 * 包含中英文 mixed content
 */

// 纯英文 C++ style comment
// 这是中文的双斜线注释

<!-- HTML注释: 这里是页面头部 -->
<!-- This is an English HTML comment -->

# FIXME: 修复这个bug
# NOTE: 注意这个边界条件

class MyClass:
    \'\'\'
    三引号文档字符串
    Triple quote docstring
    \'\'\'
    pass

# 纯符号注释 ####
## ========================
'''

    app.source_text.insert('1.0', sample_code)

    root.mainloop()


if __name__ == '__main__':
    main()