#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRT / Torch .pth 子窗口。

只负责选路径、起子进程、收进度。这里和 main.py 都不会 import torch。
推理走旁边的 infer_vrt.py，用窗口里填的那个 Python 启动。
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
INFER_SCRIPT = APP_DIR / "infer_vrt.py"
SETUP_SCRIPT = APP_DIR / "setup_vrt.py"
CONFIG_PATH = APP_DIR / "presets" / "torch_pth.json"
DEFAULT_REPO = APP_DIR / "third_party" / "VRT"
DEFAULT_WEIGHTS = APP_DIR / "models" / "008_VRT_videodenoising_DAVIS.pth"
VRT_CLONE = "https://github.com/JingyunLiang/VRT"
VRT_WEIGHTS = "https://github.com/JingyunLiang/VRT/releases/tag/v0.0"

TASKS = [
    ("auto", "自动识别（看文件名）"),
    ("vrt_denoise", "VRT 视频降噪"),
    ("vrt_deblur", "VRT 视频去模糊"),
    ("vrt_sr", "VRT 视频超分 ×4"),
    ("jit", "TorchScript / 整模 .pt"),
]

_win: Optional["VrtWindow"] = None


CONTAINER_EXT = {
    "mp4": ".mp4",
    "mov": ".mov",
    "mkv": ".mkv",
    "avi": ".avi",
}


def _container_ext(fmt: str) -> str:
    return CONTAINER_EXT.get((fmt or "mp4").lower().lstrip("."), ".mp4")


def _apply_container(path: str, fmt: str) -> str:
    if not path:
        return path
    root, _ = os.path.splitext(path)
    return root + _container_ext(fmt)


def open_vrt_window(master: tk.Misc, input_path: str = "", output_hint: str = "",
                    encode_getter: Optional[Callable[[], dict]] = None) -> "VrtWindow":
    """main.py 的唯一入口。已打开则前置，不重复建窗。"""
    global _win
    if _win is not None:
        try:
            if _win.win.winfo_exists():
                if encode_getter is not None:
                    _win._encode_getter = encode_getter
                if input_path:
                    _win.fill_io(input_path, output_hint)
                _win._refresh_encode_follow()
                _win.win.deiconify()
                _win.win.lift()
                _win.win.focus_force()
                return _win
        except tk.TclError:
            _win = None
    _win = VrtWindow(master, input_path, output_hint, encode_getter)
    return _win


def _load_config() -> dict:
    try:
        if CONFIG_PATH.is_file():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_config(data: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _bundled_defaults() -> dict:
    """已经 setup_vrt.py 落下的官方降噪方案。"""
    d = {"task": "vrt_denoise"}
    if (DEFAULT_REPO / "models" / "network_vrt.py").is_file():
        d["repo"] = str(DEFAULT_REPO)
    if DEFAULT_WEIGHTS.is_file():
        d["weights"] = str(DEFAULT_WEIGHTS)
    return d


def _python_candidates() -> list:
    names = []
    for folder in ("venv_torch", "venv"):
        names.append(APP_DIR / folder / "Scripts" / "python.exe")
        names.append(APP_DIR / folder / "bin" / "python")
    which = shutil.which("python")
    if which:
        names.append(Path(which))
    names.append(Path(sys.executable))
    seen = set()
    out = []
    for p in names:
        try:
            key = str(p.resolve()) if p.exists() else ""
        except Exception:
            key = ""
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _normalize_task(raw: str) -> str:
    """下拉框展示的是「vrt_deblur  ·  VRT 视频去模糊」，传给子进程只能是 key。"""
    text = (raw or "").strip()
    known = {k for k, _ in TASKS}
    if text in known:
        return text
    token = text.split()[0] if text else ""
    return token if token in known else "vrt_denoise"


def _suggest_output(src: str, hint: str, fmt: str = "mp4") -> str:
    ext = _container_ext(fmt)
    if hint:
        stem, _old = os.path.splitext(hint)
        if stem.endswith("_output"):
            return stem[: -len("_output")] + "_vrt" + ext
        if hint:
            return _apply_container(hint, fmt)
    if not src:
        return ""
    root, _ = os.path.splitext(src)
    return root + "_vrt" + ext


class VrtWindow:
    def __init__(self, master: tk.Misc, input_path: str, output_hint: str,
                 encode_getter: Optional[Callable[[], dict]] = None):
        self.win = tk.Toplevel(master)
        self.win.title("VRT / Torch .pth 降噪（独立进程）")
        self.win.geometry("760x680")
        self.win.minsize(680, 560)

        self._proc: Optional[subprocess.Popen] = None
        self._reader: Optional[threading.Thread] = None
        self._q: queue.Queue = queue.Queue()
        self._running = False
        self._encode_getter = encode_getter

        cfg = _load_config()
        bundled = _bundled_defaults()
        pythons = _python_candidates()
        default_py = (cfg.get("python") or "").strip() or (pythons[0] if pythons else sys.executable)

        self.var_python = tk.StringVar(value=default_py)
        self.var_repo = tk.StringVar(value=(cfg.get("repo") or bundled.get("repo") or ""))
        self.var_weights = tk.StringVar(value=(cfg.get("weights") or bundled.get("weights") or ""))
        self.var_task = tk.StringVar(value=_normalize_task(cfg.get("task") or bundled.get("task") or "vrt_denoise"))
        enc = self._encode_now()
        self.var_input = tk.StringVar(value=input_path or cfg.get("input", ""))
        self.var_output = tk.StringVar(
            value=_suggest_output(
                self.var_input.get(),
                output_hint or cfg.get("output", ""),
                enc.get("format", "mp4"),
            )
        )
        self.var_encode_follow = tk.StringVar(value="")
        self.var_sigma = tk.DoubleVar(value=float(cfg.get("sigma", 15)))
        self.var_tile = tk.IntVar(value=int(cfg.get("tile", 256)))
        self.var_temporal = tk.IntVar(value=int(cfg.get("temporal", 12)))
        self.var_device = tk.StringVar(value=cfg.get("device", "auto"))
        self.var_status = tk.StringVar(value="尚未检测 torch（点「检测环境」，不会加载到主程序）")
        self.var_progress = tk.DoubleVar(value=0.0)

        self._build()
        self._refresh_encode_follow()
        self.win.protocol("WM_DELETE_WINDOW", self._on_close)
        self.win.after(200, self.probe)
        self.win.after(80, self._poll)

    def _encode_now(self) -> dict:
        if self._encode_getter is not None:
            try:
                data = self._encode_getter() or {}
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {
            "format": "mp4",
            "codec": "auto",
            "rate_mode": "crf",
            "crf": 20,
            "bitrate": 4000,
            "preset": "medium",
            "keep_audio": True,
        }

    def _refresh_encode_follow(self) -> None:
        enc = self._encode_now()
        fmt = enc.get("format", "mp4")
        codec = enc.get("codec", "auto")
        if enc.get("rate_mode") == "bitrate":
            quality = f"{enc.get('bitrate', 4000)} kbps"
        else:
            quality = f"CRF {enc.get('crf', 20)}"
        audio = "留声" if enc.get("keep_audio") else "无声"
        self.var_encode_follow.set(
            f"编码跟随主窗口：{fmt.upper()} · {codec} · {quality} · {audio}"
        )
        current = self.var_output.get().strip()
        if current:
            self.var_output.set(_apply_container(current, fmt))

    def fill_io(self, input_path: str, output_hint: str = "") -> None:
        enc = self._encode_now()
        if input_path:
            self.var_input.set(input_path)
            if not self.var_output.get().strip() or output_hint:
                self.var_output.set(_suggest_output(input_path, output_hint, enc.get("format", "mp4")))
            else:
                self.var_output.set(_apply_container(self.var_output.get(), enc.get("format", "mp4")))
        self._refresh_encode_follow()

    def _build(self) -> None:
        pad = {"padx": 12, "pady": 3}
        root = ttk.Frame(self.win)
        root.pack(fill="both", expand=True)

        ttk.Label(
            root,
            text="主程序只打开这个窗口。torch 和 .pth 都在子进程里加载，关窗或取消会干掉那个进程。",
            wraplength=720, justify="left",
        ).pack(anchor="w", **pad)

        env = ttk.LabelFrame(root, text="推理环境（独立 Python）")
        env.pack(fill="x", padx=12, pady=6)
        self._path_row(env, "Python:", self.var_python, self._browse_python, extra="检测环境", extra_cmd=self.probe)
        ttk.Label(env, textvariable=self.var_status, wraplength=700, justify="left").pack(anchor="w", padx=8, pady=(0, 6))

        model = ttk.LabelFrame(root, text="模型")
        model.pack(fill="x", padx=12, pady=6)
        row = ttk.Frame(model)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="任务:").pack(side="left")
        self._task_box = ttk.Combobox(
            row, state="readonly", width=28,
            values=[f"{k}  ·  {v}" for k, v in TASKS],
        )
        self._task_box.pack(side="left", padx=6)
        self._sync_task_box()
        self._task_box.bind("<<ComboboxSelected>>", self._on_task_selected)
        ttk.Button(row, text="补全官方文件", command=self.prepare_files).pack(side="right")
        ttk.Button(row, text="权重说明", command=lambda: self._open_url(VRT_WEIGHTS)).pack(side="right", padx=4)

        self._path_row(model, "VRT 仓库:", self.var_repo, self._browse_repo)
        self._path_row(model, "权重 .pth:", self.var_weights, self._browse_weights)

        io = ttk.LabelFrame(root, text="输入 / 输出")
        io.pack(fill="x", padx=12, pady=6)
        self._path_row(io, "视频:", self.var_input, self._browse_input)
        self._path_row(io, "输出:", self.var_output, self._browse_output)
        ttk.Label(io, textvariable=self.var_encode_follow, wraplength=700, justify="left").pack(
            anchor="w", padx=8, pady=(0, 6)
        )

        opt = ttk.LabelFrame(root, text="参数")
        opt.pack(fill="x", padx=12, pady=6)
        grid = ttk.Frame(opt)
        grid.pack(fill="x", padx=8, pady=6)
        self._spin(grid, 0, "噪声 σ", self.var_sigma, 0, 50, 5)
        self._spin(grid, 1, "空间分块", self.var_tile, 0, 512, 64)
        self._spin(grid, 2, "时间窗", self.var_temporal, 4, 24, 2)
        ttk.Label(grid, text="设备").grid(row=0, column=6, sticky="w", padx=(16, 4))
        ttk.Combobox(grid, state="readonly", width=8, textvariable=self.var_device,
                     values=["auto", "cuda", "cpu"]).grid(row=0, column=7, sticky="w")
        ttk.Label(
            opt,
            text="默认接的是官方 008 VRT 视频降噪（DAVIS，σ 0–50）。分块 0 = 整帧；显存不够降到 128。日常请继续用主窗口 FastDVDnet。",
            wraplength=700, justify="left",
        ).pack(anchor="w", padx=8, pady=(0, 6))

        btn = ttk.Frame(root)
        btn.pack(fill="x", padx=12, pady=4)
        self.btn_start = ttk.Button(btn, text="开始（子进程）", command=self.start)
        self.btn_start.pack(side="left")
        self.btn_cancel = ttk.Button(btn, text="取消", command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=8)
        ttk.Button(btn, text="打开输出目录", command=self._open_out_dir).pack(side="right")

        ttk.Progressbar(root, variable=self.var_progress, maximum=1.0).pack(fill="x", padx=12, pady=4)

        log_fr = ttk.LabelFrame(root, text="子进程日志")
        log_fr.pack(fill="both", expand=True, padx=12, pady=(4, 10))
        self.log = tk.Text(log_fr, height=12, wrap="word", font=("Consolas", 9))
        scroll = ttk.Scrollbar(log_fr, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)

    def _path_row(self, parent, label, var, browse, extra="", extra_cmd=None) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=8, pady=3)
        ttk.Label(row, text=label, width=10).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(row, text="浏览", command=browse, width=6).pack(side="left")
        if extra and extra_cmd:
            ttk.Button(row, text=extra, command=extra_cmd).pack(side="left", padx=4)

    def _spin(self, parent, col, label, var, frm, to, step) -> None:
        ttk.Label(parent, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 4))
        ttk.Spinbox(parent, textvariable=var, from_=frm, to=to, increment=step, width=7).grid(
            row=0, column=col * 2 + 1, sticky="w", padx=(0, 10)
        )

    def _on_task_selected(self, _event=None) -> None:
        self.var_task.set(_normalize_task(self._task_box.get()))

    def _sync_task_box(self) -> None:
        key = _normalize_task(self.var_task.get())
        self.var_task.set(key)
        for i, (k, _) in enumerate(TASKS):
            if k == key:
                self._task_box.current(i)
                return

    def _append(self, text: str) -> None:
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")

    def _browse_python(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win, title="选择带 torch 的 python.exe",
            filetypes=[("Python", "python.exe python"), ("所有文件", "*.*")],
        )
        if path:
            self.var_python.set(path)

    def _browse_repo(self) -> None:
        path = filedialog.askdirectory(parent=self.win, title="选择 VRT 仓库根目录")
        if path:
            self.var_repo.set(path)

    def _browse_weights(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win, title="选择 .pth / .pt 权重",
            filetypes=[("PyTorch 权重", "*.pth *.pt"), ("所有文件", "*.*")],
            initialdir=str((APP_DIR / "models").absolute()),
        )
        if path:
            self.var_weights.set(path)

    def _browse_input(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.win, title="选择输入视频",
            filetypes=[("视频", "*.mp4 *.avi *.mov *.mkv *.wmv *.webm"), ("所有文件", "*.*")],
        )
        if path:
            self.var_input.set(path)
            if not self.var_output.get().strip():
                self.var_output.set(_suggest_output(path, "", self._encode_now().get("format", "mp4")))

    def _browse_output(self) -> None:
        fmt = self._encode_now().get("format", "mp4")
        ext = _container_ext(fmt)
        path = filedialog.asksaveasfilename(
            parent=self.win, title="输出视频", defaultextension=ext,
            filetypes=[(fmt.upper(), f"*{ext}"), ("所有文件", "*.*")],
        )
        if path:
            self.var_output.set(_apply_container(path, fmt))

    def _open_out_dir(self) -> None:
        dest = self.var_output.get().strip()
        folder = os.path.dirname(dest) if dest else ""
        if folder and os.path.isdir(folder):
            self._open_path(folder)
        else:
            messagebox.showinfo("提示", "还没有有效的输出路径", parent=self.win)

    def _open_path(self, path: str) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            messagebox.showerror("打不开", str(e), parent=self.win)

    def _open_url(self, url: str) -> None:
        import webbrowser
        webbrowser.open(url)

    def _persist(self) -> None:
        _save_config({
            "python": self.var_python.get().strip(),
            "repo": self.var_repo.get().strip(),
            "weights": self.var_weights.get().strip(),
            "task": _normalize_task(self.var_task.get()),
            "input": self.var_input.get().strip(),
            "output": self.var_output.get().strip(),
            "sigma": self.var_sigma.get(),
            "tile": self.var_tile.get(),
            "temporal": self.var_temporal.get(),
            "device": self.var_device.get(),
        })

    def _popen_kwargs(self) -> dict:
        kw = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "bufsize": 1,
            "env": {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
        }
        if sys.platform == "win32":
            kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return kw

    def _spawn(self, extra_args: list) -> subprocess.Popen:
        py = self.var_python.get().strip()
        if not py or not Path(py).exists():
            raise FileNotFoundError(f"Python 不存在: {py}")
        if not INFER_SCRIPT.is_file():
            raise FileNotFoundError(f"找不到推理脚本: {INFER_SCRIPT}")
        cmd = [py, "-u", str(INFER_SCRIPT), *extra_args]
        return subprocess.Popen(cmd, **self._popen_kwargs())

    def _read_pipe(self, proc: subprocess.Popen, tag: str) -> None:
        assert proc.stdout is not None
        try:
            for line in proc.stdout:
                self._q.put((tag, line.rstrip("\r\n")))
        except Exception as e:
            self._q.put((tag, f"#VT ERROR 读输出失败: {e}"))
        finally:
            code = proc.wait()
            self._q.put((tag, f"__EXIT__ {code}"))

    def prepare_files(self) -> None:
        if not SETUP_SCRIPT.is_file():
            messagebox.showerror("缺少脚本", f"找不到 {SETUP_SCRIPT}", parent=self.win)
            return
        self._append("正在补全官方 network_vrt.py 和 008 权重…")
        py = sys.executable

        def work():
            try:
                proc = subprocess.run(
                    [py, str(SETUP_SCRIPT)],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
                )
                out = (proc.stdout or "") + (proc.stderr or "")
                self._q.put(("prep", out.strip() or f"exit {proc.returncode}"))
                self._q.put(("prep", f"__EXIT__ {proc.returncode}"))
            except Exception as e:
                self._q.put(("prep", f"#VT ERROR {e}"))
                self._q.put(("prep", "__EXIT__ 1"))

        threading.Thread(target=work, daemon=True).start()

    def probe(self) -> None:
        if self._running:
            return
        self.var_status.set("正在子进程里检测 torch…")
        try:
            proc = self._spawn(["--probe"])
        except Exception as e:
            self.var_status.set(f"无法启动探测: {e}")
            return
        threading.Thread(target=self._read_pipe, args=(proc, "probe"), daemon=True).start()

    def start(self) -> None:
        if self._running:
            return
        src = self.var_input.get().strip()
        dst = self.var_output.get().strip()
        weights = self.var_weights.get().strip()
        if not src or not os.path.isfile(src):
            messagebox.showerror("缺输入", "请先选一个视频。", parent=self.win)
            return
        if not weights or not os.path.isfile(weights):
            messagebox.showerror("缺权重", "请先选 .pth / .pt。", parent=self.win)
            return
        if not dst:
            messagebox.showerror("缺输出", "请填输出路径。", parent=self.win)
            return
        enc = self._encode_now()
        dst = _apply_container(dst, enc.get("format", "mp4"))
        self.var_output.set(dst)
        self._refresh_encode_follow()
        task = _normalize_task(self.var_task.get())
        self.var_task.set(task)
        if task != "jit":
            repo = self.var_repo.get().strip()
            if repo and not (Path(repo) / "models" / "network_vrt.py").is_file():
                messagebox.showerror(
                    "仓库不对",
                    "这个目录下没有 models/network_vrt.py。\n请指向官方 VRT 仓库根目录。",
                    parent=self.win,
                )
                return
        self._persist()
        args = [
            "--input", src,
            "--output", dst,
            "--weights", weights,
            "--task", task,
            "--sigma", str(self.var_sigma.get()),
            "--tile", str(int(self.var_tile.get())),
            "--temporal", str(int(self.var_temporal.get())),
            "--device", self.var_device.get().strip(),
            "--codec", str(enc.get("codec") or "auto"),
            "--format", str(enc.get("format") or "mp4"),
            "--rate-mode", str(enc.get("rate_mode") or "crf"),
            "--crf", str(int(enc.get("crf") or 20)),
            "--bitrate", str(int(enc.get("bitrate") or 4000)),
            "--encode-preset", str(enc.get("preset") or "medium"),
        ]
        if enc.get("keep_audio"):
            args.append("--keep-audio")
        else:
            args.append("--no-keep-audio")
        repo = self.var_repo.get().strip()
        if repo:
            args += ["--repo", repo]
        try:
            self._proc = self._spawn(args)
        except Exception as e:
            messagebox.showerror("启动失败", str(e), parent=self.win)
            return
        self._running = True
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.var_progress.set(0)
        self._append("── 子进程已启动 ──")
        self._reader = threading.Thread(target=self._read_pipe, args=(self._proc, "run"), daemon=True)
        self._reader.start()

    def cancel(self) -> None:
        proc = self._proc
        if proc is None or proc.poll() is not None:
            return
        self._append("正在结束子进程…")
        try:
            proc.terminate()
        except Exception:
            pass
        try:
            proc.wait(timeout=4)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _set_idle(self) -> None:
        self._running = False
        self._proc = None
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")

    def _handle_vt(self, kind: str, payload: str, source: str) -> None:
        if kind == "PROBE":
            try:
                info = json.loads(payload)
            except Exception:
                self.var_status.set(payload)
                return
            if info.get("ok"):
                gpu = info.get("cuda_name") or ("CUDA" if info.get("cuda") else "仅 CPU")
                self.var_status.set(f"子进程 torch {info.get('torch')}  ·  {gpu}  ·  默认设备 {info.get('device')}")
            else:
                self.var_status.set(
                    f"这个 Python 里没有可用的 torch: {info.get('error', 'unknown')}\n"
                    "另建 venv_torch 后: pip install torch einops timm opencv-python"
                )
            return
        if kind == "STATUS":
            self.var_status.set(payload)
            self._append(f"[状态] {payload}")
            return
        if kind == "LOG":
            self._append(payload)
            return
        if kind == "PROGRESS":
            try:
                self.var_progress.set(max(0.0, min(1.0, float(payload))))
            except ValueError:
                pass
            return
        if kind == "FRAME":
            self._append(f"帧 {payload.replace(' ', '/')}")
            return
        if kind == "DONE":
            self.var_progress.set(1.0)
            self.var_status.set(f"完成: {payload}")
            self._append(f"完成: {payload}")
            if source == "run":
                messagebox.showinfo("完成", f"已写出:\n{payload}", parent=self.win)
            return
        if kind == "ERROR":
            self.var_status.set("失败")
            self._append(payload)
            if source == "run":
                messagebox.showerror("推理失败", payload[:800], parent=self.win)
            elif source == "probe":
                self.var_status.set(payload[:200])
            return
        self._append(f"{kind} {payload}".strip())

    def _poll(self) -> None:
        try:
            while True:
                source, line = self._q.get_nowait()
                if line.startswith("__EXIT__"):
                    code = line.split(" ", 1)[-1]
                    if source == "run":
                        self._append(f"── 子进程退出 {code} ──")
                        self._set_idle()
                    elif source == "prep":
                        bundled = _bundled_defaults()
                        if bundled.get("repo") and not self.var_repo.get().strip():
                            self.var_repo.set(bundled["repo"])
                        if bundled.get("weights") and not self.var_weights.get().strip():
                            self.var_weights.set(bundled["weights"])
                        if bundled.get("repo"):
                            self.var_repo.set(bundled["repo"])
                        if bundled.get("weights"):
                            self.var_weights.set(bundled["weights"])
                        self.var_task.set("vrt_denoise")
                        self._sync_task_box()
                    continue
                if line.startswith("#VT "):
                    rest = line[4:]
                    kind, _, payload = rest.partition(" ")
                    self._handle_vt(kind, payload, source)
                elif line.strip():
                    self._append(line)
        except queue.Empty:
            pass
        try:
            if self.win.winfo_exists():
                self.win.after(80, self._poll)
        except tk.TclError:
            pass

    def _on_close(self) -> None:
        if self._running:
            if not messagebox.askyesno("还在跑", "子进程还在推理。关闭窗口会结束它，确定？", parent=self.win):
                return
            self.cancel()
        self._persist()
        global _win
        _win = None
        self.win.destroy()
