"""
视频去闪烁工具 - Video Deflicker Tool
基于 FFmpeg 的视频闪烁消除 GUI 工具
支持多种滤波模式、实时预览、批量处理、阈值控制

修复：
- Windows 下 FFmpeg 输出编码问题 (UnicodeDecodeError)
- 所有 subprocess 调用统一使用 UTF-8 + errors='replace'
新增：
- 阈值控制：只处理变化量在阈值范围内的像素，保护运动区域
"""

import os
import sys
import json
import subprocess
import threading
import re
import shutil
import tempfile
import time
import locale
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Callable
from enum import Enum

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ============================================================
#  常量与配置
# ============================================================

APP_TITLE = "视频去闪烁工具 Video Deflicker"
APP_VERSION = "1.2.0"  # ← 版本号更新

SUPPORTED_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".vob"
}

# ============================================================
#  安全子进程调用（核心修复）
# ============================================================

def _get_popen_kwargs() -> dict:
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        kwargs["env"] = env
    return kwargs


def safe_run(cmd: list, timeout: int = 30) -> subprocess.CompletedProcess:
    kwargs = _get_popen_kwargs()
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout, **kwargs,
        )
        result.stdout = result.stdout.decode("utf-8", errors="replace") \
            if isinstance(result.stdout, bytes) else result.stdout
        result.stderr = result.stderr.decode("utf-8", errors="replace") \
            if isinstance(result.stderr, bytes) else result.stderr
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", "timeout")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


def safe_popen(cmd: list) -> subprocess.Popen:
    kwargs = _get_popen_kwargs()
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs,
    )


def safe_readline(stream) -> Optional[str]:
    try:
        raw = stream.readline()
        if not raw:
            return None
        for encoding in ("utf-8", "gbk", "latin-1"):
            try:
                return raw.decode(encoding).rstrip("\r\n")
            except (UnicodeDecodeError, AttributeError):
                continue
        return raw.decode("latin-1", errors="replace").rstrip("\r\n")
    except Exception:
        return None


# ============================================================
#  FFmpeg 检测
# ============================================================

def find_ffmpeg() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    candidates = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg_bin", "ffmpeg.exe"),
        "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def find_ffprobe() -> Optional[str]:
    path = shutil.which("ffprobe")
    if path:
        return path
    candidates = [
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffprobe.exe"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg_bin", "ffprobe.exe"),
        "/usr/bin/ffprobe", "/usr/local/bin/ffprobe",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def get_video_info(filepath: str) -> dict:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return {}
    try:
        cmd = [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams", filepath,
        ]
        result = safe_run(cmd, timeout=30)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except (json.JSONDecodeError, Exception):
        pass
    return {}


def format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:05.2f}" if h > 0 else f"{m:02d}:{s:05.2f}"


def format_filesize(size_bytes) -> str:
    try:
        size_bytes = float(size_bytes)
    except (ValueError, TypeError):
        return "? B"
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ============================================================
#  ★ 阈值模式枚举（新增）
# ============================================================

class ThresholdMode(Enum):
    """阈值实现策略"""
    NONE = "none"                # 不使用阈值（原始行为）
    HQDN3D = "hqdn3d"           # hqdn3d 时域降噪（内置阈值）
    NLMEANS = "nlmeans"          # nlmeans 非局部均值（内置阈值）
    MASKING = "masking"          # 运动遮罩混合（高级）


# ============================================================
#  滤波方案定义（增强版）
# ============================================================

class FilterMode(Enum):
    TMEDIAN = "tmedian"
    TMIX = "tmix"
    DEFLICKER = "deflicker"
    TMEDIAN_PLUS_DEFLICKER = "tmedian+deflicker"
    EMA = "ema"
    CUSTOM = "custom"


@dataclass
class FilterPreset:
    name: str
    mode: FilterMode
    description: str
    tmedian_radius: int = 1
    tmix_frames: int = 3
    tmix_weights: str = "1 2 1"
    deflicker_mode: str = "am"
    deflicker_size: int = 5
    ema_alpha: float = 0.3
    extra_filters: str = ""
    custom_vf: str = ""
    codec: str = "libx264"
    crf: int = 18
    preset: str = "medium"
    copy_audio: bool = True

    # ★ 新增阈值相关参数
    threshold_mode: ThresholdMode = ThresholdMode.NONE
    threshold_value: float = 0.0        # 通用阈值 0~255
    temporal_strength: float = 0.0      # 时域降噪强度
    spatial_strength: float = 0.0       # 空域降噪强度
    motion_threshold: float = 30.0      # 运动遮罩阈值

    def build_vf(self) -> str:
        """
        构建完整的 -vf 滤镜字符串
        根据阈值模式决定是否包裹/附加阈值滤镜
        """
        filters = []

        if self.mode == FilterMode.CUSTOM:
            base_vf = self.custom_vf
        else:
            base_filters = []

            if self.mode == FilterMode.TMEDIAN:
                base_filters.append(f"tmedian=radius={self.tmedian_radius}")

            elif self.mode == FilterMode.TMIX:
                base_filters.append(
                    f"tmix=frames={self.tmix_frames}:weights='{self.tmix_weights}'"
                )

            elif self.mode == FilterMode.DEFLICKER:
                base_filters.append(
                    f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}"
                )

            elif self.mode == FilterMode.TMEDIAN_PLUS_DEFLICKER:
                base_filters.append(f"tmedian=radius={self.tmedian_radius}")
                base_filters.append(
                    f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}"
                )

            elif self.mode == FilterMode.EMA:
                n = 5
                alpha = self.ema_alpha
                weights = []
                for i in range(n):
                    w = alpha * ((1 - alpha) ** i)
                    weights.append(f"{w:.3f}")
                weights.reverse()
                w_str = " ".join(weights)
                base_filters.append(f"tmix=frames={n}:weights='{w_str}'")

            if self.extra_filters.strip():
                base_filters.append(self.extra_filters.strip())

            base_vf = ",".join(base_filters)

        # ★ 根据阈值模式包裹滤镜
        return self._apply_threshold(base_vf)

    def _apply_threshold(self, base_vf: str) -> str:
        """
        ★ 核心：根据阈值模式对基础滤镜进行增强

        策略说明：
        ┌─────────────┬────────────────────────────────────────────┐
        │ NONE        │ 直接返回原始滤镜（无阈值）                   │
        │ HQDN3D      │ 在滤镜后追加 hqdn3d 时域降噪                │
        │ NLMEANS     │ 在滤镜后追加 nlmeans 时域降噪                │
        │ MASKING     │ 运动遮罩 + 三重平滑条件混合：                │
        │             │   ① 模糊帧差 → 消除噪声碎片                 │
        │             │   ② 软阈值   → 消除硬边界                   │
        │             │   ③ 模糊遮罩 → 羽化边缘                     │
        └─────────────┴────────────────────────────────────────────┘
        """
        if self.threshold_mode == ThresholdMode.NONE or self.threshold_value <= 0:
            return base_vf

        if self.threshold_mode == ThresholdMode.HQDN3D:
            lt = self.threshold_value
            ct = lt * 0.7
            ls = self.spatial_strength
            cs = ls * 0.7
            hqdn3d_str = f"hqdn3d={ls:.1f}:{cs:.1f}:{lt:.1f}:{ct:.1f}"
            return f"{base_vf},{hqdn3d_str}" if base_vf else hqdn3d_str

        if self.threshold_mode == ThresholdMode.NLMEANS:
            s = self.threshold_value
            nlm_str = f"nlmeans=s={s:.1f}:p=7:pc=5:r=3:rc=3"
            return f"{base_vf},{nlm_str}" if base_vf else nlm_str

        if self.threshold_mode == ThresholdMode.MASKING:
            # ★★★ 三重平滑运动遮罩 ★★★
            thresh = int(self.motion_threshold)

            # 软过渡区间
            low = max(int(thresh * 0.4), 2)
            high = min(int(thresh * 1.8), 254)
            span = max(high - low, 1)

            # 软阈值 LUT
            lut_expr = f"clip((val-{low})*255/{span},0,255)"

            complex_filter = (
                f"split=3[orig][proc][mask];"
                f"[proc]{base_vf}[deflickered];"
                f"[mask]tpad=start=1:start_mode=clone[delayed];"
                f"[mask][delayed]blend=all_mode=difference[diff];"
                f"[diff]gblur=sigma=3,"
                f"lutyuv=y='{lut_expr}',"
                f"gblur=sigma=5[motion_mask];"
                f"[deflickered][orig][motion_mask]maskedmerge"
            )
            return complex_filter

        return base_vf


DEFAULT_PRESETS: List[FilterPreset] = [
    FilterPreset(
        name="轻度去闪 - 时域中值 (推荐)",
        mode=FilterMode.TMEDIAN,
        description="对间歇性像素跳变最有效，几乎不影响画质和运动\n"
                    "原理：3帧窗口取中值，自动排除异常跳变帧\n"
                    "适用：精度导致的±1像素值闪烁\n"
                    "★ 可开启阈值控制保护运动区域",
        tmedian_radius=1,
    ),
    FilterPreset(
        name="中度去闪 - 时域中值(加强)",
        mode=FilterMode.TMEDIAN,
        description="5帧窗口中值滤波，更强的去闪能力\n"
                    "适用：闪烁较明显或持续多帧的情况\n"
                    "注意：快速运动可能轻微模糊\n"
                    "★ 建议开启阈值保护",
        tmedian_radius=2,
    ),
    FilterPreset(
        name="全局亮度补偿 - Deflicker",
        mode=FilterMode.DEFLICKER,
        description="分析全帧亮度变化并补偿\n"
                    "适用：整帧亮度周期性波动（日光延时摄影闪烁）\n"
                    "对局部像素闪烁效果有限",
        deflicker_mode="am",
        deflicker_size=5,
    ),
    FilterPreset(
        name="组合方案 - 中值+亮度补偿",
        mode=FilterMode.TMEDIAN_PLUS_DEFLICKER,
        description="先中值去除像素级跳变，再全局亮度补偿\n"
                    "最全面的去闪方案\n"
                    "适用：同时存在像素闪烁和亮度波动",
        tmedian_radius=1,
        deflicker_mode="am",
        deflicker_size=5,
    ),
    FilterPreset(
        name="时域加权平均 - TMix",
        mode=FilterMode.TMIX,
        description="帧间加权平均，中心帧权重更高\n"
                    "效果柔和，适合静态或慢速场景\n"
                    "注意：运动场景会产生拖影",
        tmix_frames=3,
        tmix_weights="1 2 1",
    ),
    FilterPreset(
        name="EMA指数平滑",
        mode=FilterMode.EMA,
        description="指数移动平均，近期帧权重更高\n"
                    "适合需要低延迟的实时感场景\n"
                    "alpha越小平滑越强",
        ema_alpha=0.3,
    ),
    FilterPreset(
        name="自定义滤镜",
        mode=FilterMode.CUSTOM,
        description="手动输入 FFmpeg -vf 滤镜字符串\n"
                    "完全自由控制滤镜链\n"
                    "示例：tmedian=radius=1,deflicker=size=7",
        custom_vf="tmedian=radius=1",
    ),
]


# ============================================================
#  FFmpeg 处理核心
# ============================================================

class FFmpegProcessor:

    def __init__(self):
        self.ffmpeg_path = find_ffmpeg()
        self.process: Optional[subprocess.Popen] = None
        self.cancelled = False

    def is_available(self) -> bool:
        return self.ffmpeg_path is not None

    def cancel(self):
        self.cancelled = True
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def process_video(
        self,
        input_path: str,
        output_path: str,
        preset: FilterPreset,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
    ) -> bool:
        self.cancelled = False

        if not self.ffmpeg_path:
            if log_callback:
                log_callback("[错误] 未找到 FFmpeg！")
            return False

        vf = preset.build_vf()
        if not vf:
            if log_callback:
                log_callback("[错误] 滤镜字符串为空！")
            return False

        total_duration = 0.0
        info = get_video_info(input_path)
        if info and "format" in info:
            try:
                total_duration = float(info["format"].get("duration", 0))
            except (ValueError, TypeError):
                pass

        # ★ 根据阈值模式选择 -vf 或 -filter_complex
        cmd = [self.ffmpeg_path, "-y", "-i", input_path]

        if preset.threshold_mode == ThresholdMode.MASKING and preset.threshold_value > 0:
            # 运动遮罩需要用 filter_complex
            cmd.extend(["-filter_complex", vf])
        else:
            cmd.extend(["-vf", vf])

        if preset.codec == "copy":
            cmd.extend(["-c:v", "copy"])
        else:
            cmd.extend(["-c:v", preset.codec])
            if preset.codec in ("libx264", "libx265"):
                cmd.extend(["-crf", str(preset.crf)])
                cmd.extend(["-preset", preset.preset])

        if preset.copy_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])

        cmd.append(output_path)

        if log_callback:
            log_callback(f"[命令] {' '.join(cmd)}\n")

        try:
            self.process = safe_popen(cmd)

            while True:
                if self.cancelled:
                    try:
                        self.process.terminate()
                    except Exception:
                        pass
                    if log_callback:
                        log_callback("[取消] 已取消处理。")
                    return False

                line = safe_readline(self.process.stderr)
                if line is None:
                    if self.process.poll() is not None:
                        break
                    continue

                if log_callback and line.strip():
                    log_callback(line.strip())

                time_match = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
                if time_match and total_duration > 0 and progress_callback:
                    h, m, s = time_match.groups()
                    current_time = int(h) * 3600 + int(m) * 60 + float(s)
                    pct = min(current_time / total_duration * 100, 99.9)
                    progress_callback(pct, current_time, total_duration)

            self.process.wait()

            if self.process.returncode == 0:
                if progress_callback:
                    progress_callback(100.0, total_duration, total_duration)
                if log_callback:
                    log_callback("\n[完成] 处理成功！")
                return True
            else:
                if log_callback:
                    remaining = safe_readline(self.process.stderr)
                    if remaining:
                        log_callback(remaining)
                    log_callback(f"\n[失败] FFmpeg 返回码: {self.process.returncode}")
                return False

        except Exception as e:
            if log_callback:
                log_callback(f"\n[异常] {str(e)}")
            return False
        finally:
            if self.process:
                try:
                    self.process.stdout.close()
                    self.process.stderr.close()
                except Exception:
                    pass

    def generate_preview(
        self,
        input_path: str,
        output_path: str,
        preset: FilterPreset,
        start_time: float = 0,
        duration: float = 3,
        log_callback: Optional[Callable] = None,
    ) -> bool:
        self.cancelled = False
        if not self.ffmpeg_path:
            return False

        vf = preset.build_vf()
        if not vf:
            return False

        cmd = [
            self.ffmpeg_path, "-y",
            "-ss", str(start_time),
            "-i", input_path,
            "-t", str(duration),
        ]

        # ★ 同样区分 -vf 和 -filter_complex
        if preset.threshold_mode == ThresholdMode.MASKING and preset.threshold_value > 0:
            cmd.extend(["-filter_complex", vf])
        else:
            cmd.extend(["-vf", vf])

        cmd.extend(["-c:v", preset.codec])
        if preset.codec in ("libx264", "libx265"):
            cmd.extend(["-crf", str(preset.crf), "-preset", "ultrafast"])
        if preset.copy_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])
        cmd.append(output_path)

        if log_callback:
            log_callback(f"[预览命令] {' '.join(cmd)}")

        try:
            result = safe_run(cmd, timeout=120)
            if result.returncode != 0 and log_callback:
                log_callback(f"[预览错误] {result.stderr}")
            return result.returncode == 0
        except Exception as e:
            if log_callback:
                log_callback(f"[预览异常] {e}")
            return False


# ============================================================
#  GUI 应用（增强版）
# ============================================================

class DeflickerApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("960x820")
        self.root.minsize(800, 700)

        self.processor = FFmpegProcessor()
        self.input_files: List[str] = []
        self.output_dir: str = ""
        self.is_processing = False
        self.presets = list(DEFAULT_PRESETS)

        self._create_variables()
        self._setup_styles()
        self._build_ui()
        self._on_preset_changed()

        self.root.after(100, self._check_ffmpeg)

    def _create_variables(self):
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="(与输入文件相同目录)")
        self.file_info_var = tk.StringVar(value="请选择输入视频文件")
        self.preset_var = tk.StringVar()
        self.vf_preview_var = tk.StringVar()
        self.radius_var = tk.IntVar(value=1)
        self.deflicker_size_var = tk.IntVar(value=5)
        self.deflicker_mode_var = tk.StringVar(value="am")
        self.tmix_frames_var = tk.IntVar(value=3)
        self.tmix_weights_var = tk.StringVar(value="1 2 1")
        self.custom_vf_var = tk.StringVar(value="tmedian=radius=1")
        self.codec_var = tk.StringVar(value="libx264")
        self.crf_var = tk.IntVar(value=18)
        self.enc_preset_var = tk.StringVar(value="medium")
        self.copy_audio_var = tk.BooleanVar(value=True)
        self.suffix_var = tk.StringVar(value="_deflickered")
        self.preview_start_var = tk.DoubleVar(value=0)
        self.preview_duration_var = tk.DoubleVar(value=3)
        self.ffmpeg_path_var = tk.StringVar(
            value=self.processor.ffmpeg_path or "未找到"
        )
        self.progress_var = tk.DoubleVar(value=0)

        # ★ 新增阈值控制变量
        self.threshold_enable_var = tk.BooleanVar(value=False)
        self.threshold_mode_var = tk.StringVar(value="hqdn3d")
        self.threshold_value_var = tk.DoubleVar(value=4.0)
        self.spatial_strength_var = tk.DoubleVar(value=0.0)
        self.motion_threshold_var = tk.DoubleVar(value=30.0)

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei UI", 14, "bold"))
        style.configure("Subtitle.TLabel", font=("Microsoft YaHei UI", 10))
        style.configure("Info.TLabel", font=("Consolas", 9))
        style.configure("Success.TLabel", foreground="green")
        style.configure("Error.TLabel", foreground="red")
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 10, "bold"))
        # ★ 阈值区域高亮
        style.configure("Threshold.TLabelframe.Label",
                        font=("Microsoft YaHei UI", 10, "bold"), foreground="#d35400")

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main_frame)
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text=f"v{APP_VERSION}", style="Subtitle.TLabel").pack(
            side=tk.LEFT, padx=10
        )
        self.ffmpeg_status_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.ffmpeg_status_label.pack(side=tk.RIGHT)

        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_main = ttk.Frame(notebook, padding=8)
        notebook.add(self.tab_main, text="  处理  ")

        self.tab_advanced = ttk.Frame(notebook, padding=8)
        notebook.add(self.tab_advanced, text="  高级设置  ")

        self.tab_log = ttk.Frame(notebook, padding=8)
        notebook.add(self.tab_log, text="  日志  ")

        self._build_main_tab()
        self._build_advanced_tab()
        self._build_log_tab()

    # ---- 主处理页 ----
    def _build_main_tab(self):
        # 使用 Canvas + Scrollbar 支持滚动（控件多时）
        tab = self.tab_main

        # 文件选择
        file_frame = ttk.LabelFrame(tab, text=" 文件选择 ", padding=8)
        file_frame.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(file_frame)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text="输入视频:").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.input_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row1, text="选择文件", command=self._select_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(row1, text="批量添加", command=self._select_inputs_batch).pack(side=tk.LEFT)

        ttk.Label(file_frame, textvariable=self.file_info_var, style="Info.TLabel").pack(
            fill=tk.X, pady=2
        )

        row2 = ttk.Frame(file_frame)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text="输出目录:").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.output_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(row2, text="选择目录", command=self._select_output_dir).pack(side=tk.LEFT)

        # 滤波方案
        filter_frame = ttk.LabelFrame(tab, text=" 滤波方案 ", padding=8)
        filter_frame.pack(fill=tk.X, pady=(0, 8))

        preset_row = ttk.Frame(filter_frame)
        preset_row.pack(fill=tk.X, pady=2)
        ttk.Label(preset_row, text="选择方案:").pack(side=tk.LEFT)

        preset_names = [p.name for p in self.presets]
        self.preset_combo = ttk.Combobox(
            preset_row, textvariable=self.preset_var,
            values=preset_names, state="readonly", width=40
        )
        self.preset_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.preset_combo.current(0)
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)

        self.desc_text = tk.Text(
            filter_frame, height=4, wrap=tk.WORD, state="disabled",
            font=("Microsoft YaHei UI", 9), bg="#f5f5f5"
        )
        self.desc_text.pack(fill=tk.X, pady=4)

        vf_row = ttk.Frame(filter_frame)
        vf_row.pack(fill=tk.X, pady=2)
        ttk.Label(vf_row, text="滤镜命令:").pack(side=tk.LEFT)
        ttk.Entry(
            vf_row, textvariable=self.vf_preview_var,
            state="readonly", font=("Consolas", 9)
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # 基础参数调整
        param_frame = ttk.LabelFrame(tab, text=" 滤波参数 ", padding=8)
        param_frame.pack(fill=tk.X, pady=(0, 8))

        g = ttk.Frame(param_frame)
        g.pack(fill=tk.X)

        ttk.Label(g, text="中值半径:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.radius_spin = ttk.Spinbox(
            g, from_=1, to=10, textvariable=self.radius_var,
            width=8, command=self._on_param_changed
        )
        self.radius_spin.grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g, text="(1=3帧, 2=5帧, 3=7帧)").grid(row=0, column=2, sticky="w")

        ttk.Label(g, text="Deflicker窗口:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.deflicker_size_spin = ttk.Spinbox(
            g, from_=2, to=129, textvariable=self.deflicker_size_var,
            width=8, command=self._on_param_changed
        )
        self.deflicker_size_spin.grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(g, text="Deflicker模式:").grid(row=1, column=3, sticky="w", padx=5, pady=2)
        dm_combo = ttk.Combobox(
            g, textvariable=self.deflicker_mode_var,
            values=["am", "gm", "hm", "qm", "cm", "pm", "median"],
            state="readonly", width=8
        )
        dm_combo.grid(row=1, column=4, sticky="w", padx=5, pady=2)
        dm_combo.bind("<<ComboboxSelected>>", lambda e: self._on_param_changed())

        ttk.Label(g, text="TMix帧数:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.tmix_frames_spin = ttk.Spinbox(
            g, from_=2, to=20, textvariable=self.tmix_frames_var,
            width=8, command=self._on_param_changed
        )
        self.tmix_frames_spin.grid(row=2, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(g, text="TMix权重:").grid(row=2, column=3, sticky="w", padx=5, pady=2)
        self.tmix_weights_entry = ttk.Entry(g, textvariable=self.tmix_weights_var, width=15)
        self.tmix_weights_entry.grid(row=2, column=4, sticky="w", padx=5, pady=2)
        self.tmix_weights_entry.bind("<KeyRelease>", lambda e: self._on_param_changed())

        ttk.Label(g, text="自定义-vf:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.custom_vf_entry = ttk.Entry(g, textvariable=self.custom_vf_var, width=50)
        self.custom_vf_entry.grid(row=3, column=1, columnspan=4, sticky="we", padx=5, pady=2)
        self.custom_vf_entry.bind("<KeyRelease>", lambda e: self._on_param_changed())

        # ★★★ 阈值控制区域（新增）★★★
        self._build_threshold_panel(tab)

        # 操作按钮
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=tk.X, pady=8)

        self.preview_btn = ttk.Button(
            action_frame, text="生成预览(3秒)", command=self._generate_preview
        )
        self.preview_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(
            action_frame, text="开始处理", command=self._start_processing,
            style="Accent.TButton"
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.cancel_btn = ttk.Button(
            action_frame, text="取消", command=self._cancel_processing,
            state="disabled"
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        self.open_output_btn = ttk.Button(
            action_frame, text="打开输出目录", command=self._open_output_dir
        )
        self.open_output_btn.pack(side=tk.RIGHT, padx=5)

        # 进度
        prog_frame = ttk.Frame(tab)
        prog_frame.pack(fill=tk.X, pady=(0, 5))

        self.progress_bar = ttk.Progressbar(
            prog_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 10))

        self.progress_label = ttk.Label(prog_frame, text="就绪", width=30)
        self.progress_label.pack(side=tk.RIGHT)

    def _build_threshold_panel(self, parent):
        """
        ★ 构建阈值控制面板
        
        这是新增的核心 UI 部分，让用户可以：
        1. 开启/关闭阈值
        2. 选择阈值实现方式
        3. 调整阈值大小
        """
        thresh_frame = ttk.LabelFrame(
            parent, text=" ★ 阈值控制（保护运动区域） ",
            padding=8, style="Threshold.TLabelframe"
        )
        thresh_frame.pack(fill=tk.X, pady=(0, 8))

        # 第一行：启用开关 + 模式选择
        row1 = ttk.Frame(thresh_frame)
        row1.pack(fill=tk.X, pady=2)

        self.threshold_check = ttk.Checkbutton(
            row1, text="启用阈值控制",
            variable=self.threshold_enable_var,
            command=self._on_threshold_toggled
        )
        self.threshold_check.pack(side=tk.LEFT)

        ttk.Label(row1, text="    模式:").pack(side=tk.LEFT, padx=(20, 5))
        self.threshold_mode_combo = ttk.Combobox(
            row1, textvariable=self.threshold_mode_var,
            values=["hqdn3d", "nlmeans", "masking"],
            state="readonly", width=12
        )
        self.threshold_mode_combo.pack(side=tk.LEFT, padx=5)
        self.threshold_mode_combo.bind("<<ComboboxSelected>>",
                                        lambda e: self._on_threshold_mode_changed())

        # 模式说明
        self.thresh_mode_desc = ttk.Label(row1, text="", style="Info.TLabel")
        self.thresh_mode_desc.pack(side=tk.LEFT, padx=10)

        # 第二行：参数滑块
        row2 = ttk.Frame(thresh_frame)
        row2.pack(fill=tk.X, pady=2)

        # 阈值/强度
        ttk.Label(row2, text="阈值:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.threshold_scale = ttk.Scale(
            row2, from_=0.5, to=50.0,
            variable=self.threshold_value_var,
            orient=tk.HORIZONTAL, length=200,
            command=lambda v: self._on_param_changed()
        )
        self.threshold_scale.grid(row=0, column=1, sticky="we", padx=5, pady=2)
        self.threshold_value_label = ttk.Label(row2, text="4.0", width=6)
        self.threshold_value_label.grid(row=0, column=2, sticky="w", padx=5)

        # 空域强度（仅 hqdn3d）
        ttk.Label(row2, text="空域降噪:").grid(row=0, column=3, sticky="w", padx=5, pady=2)
        self.spatial_scale = ttk.Scale(
            row2, from_=0.0, to=20.0,
            variable=self.spatial_strength_var,
            orient=tk.HORIZONTAL, length=150,
            command=lambda v: self._on_param_changed()
        )
        self.spatial_scale.grid(row=0, column=4, sticky="we", padx=5, pady=2)
        self.spatial_value_label = ttk.Label(row2, text="0.0", width=6)
        self.spatial_value_label.grid(row=0, column=5, sticky="w", padx=5)

        # 运动阈值（仅 masking）
        ttk.Label(row2, text="运动检测阈值:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.motion_scale = ttk.Scale(
            row2, from_=2, to=100,
            variable=self.motion_threshold_var,
            orient=tk.HORIZONTAL, length=200,
            command=lambda v: self._on_param_changed()
        )
        self.motion_scale.grid(row=1, column=1, sticky="we", padx=5, pady=2)
        self.motion_value_label = ttk.Label(row2, text="30", width=6)
        self.motion_value_label.grid(row=1, column=2, sticky="w", padx=5)

        row2.columnconfigure(1, weight=1)

        # 说明文字
        help_text = (
            "阈值说明：\n"
            "  • hqdn3d：时域降噪阈值，值越大去闪越强（推荐 2~8）\n"
            "  • nlmeans：降噪强度，值越大平滑越强（推荐 3~10）\n"
            "  • masking：运动遮罩方式，运动区域保持原样，"
            "静止区域用去闪结果（最精确但最慢）"
        )
        self.thresh_help = ttk.Label(
            thresh_frame, text=help_text,
            font=("Microsoft YaHei UI", 8), foreground="#666"
        )
        self.thresh_help.pack(fill=tk.X, pady=(4, 0))

        # 初始状态
        self._on_threshold_toggled()

    def _on_threshold_toggled(self):
        """阈值开关切换"""
        enabled = self.threshold_enable_var.get()
        state = "normal" if enabled else "disabled"

        self.threshold_mode_combo.config(state="readonly" if enabled else "disabled")
        self.threshold_scale.config(state=state)
        self.spatial_scale.config(state=state)
        self.motion_scale.config(state=state)

        self._on_threshold_mode_changed()
        self._on_param_changed()

    def _on_threshold_mode_changed(self):
        """阈值模式切换时更新说明和控件状态"""
        mode = self.threshold_mode_var.get()
        enabled = self.threshold_enable_var.get()

        descriptions = {
            "hqdn3d": "时域降噪（快速，推荐）",
            "nlmeans": "非局部均值降噪（高质量，较慢）",
            "masking": "运动遮罩混合（最精确，最慢）",
        }
        self.thresh_mode_desc.config(text=descriptions.get(mode, ""))

        # 控制哪些参数可用
        if enabled:
            if mode == "hqdn3d":
                self.spatial_scale.config(state="normal")
                self.motion_scale.config(state="disabled")
            elif mode == "nlmeans":
                self.spatial_scale.config(state="disabled")
                self.motion_scale.config(state="disabled")
            elif mode == "masking":
                self.spatial_scale.config(state="disabled")
                self.motion_scale.config(state="normal")

        self._on_param_changed()

    # ---- 高级设置页 ----
    def _build_advanced_tab(self):
        tab = self.tab_advanced

        enc_frame = ttk.LabelFrame(tab, text=" 编码设置 ", padding=8)
        enc_frame.pack(fill=tk.X, pady=(0, 8))

        g = ttk.Frame(enc_frame)
        g.pack(fill=tk.X)

        ttk.Label(g, text="视频编码器:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(
            g, textvariable=self.codec_var,
            values=["libx264", "libx265", "libsvtav1", "libvpx-vp9", "mpeg4", "copy"],
            state="readonly", width=15
        ).grid(row=0, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(g, text="CRF质量:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        ttk.Spinbox(g, from_=0, to=51, textvariable=self.crf_var, width=8).grid(
            row=0, column=3, sticky="w", padx=5, pady=3
        )
        ttk.Label(g, text="(0=无损 18=高质量 23=默认)").grid(
            row=0, column=4, sticky="w", padx=5
        )

        ttk.Label(g, text="编码速度:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(
            g, textvariable=self.enc_preset_var,
            values=["ultrafast", "superfast", "veryfast", "faster", "fast",
                    "medium", "slow", "slower", "veryslow"],
            state="readonly", width=15
        ).grid(row=1, column=1, sticky="w", padx=5, pady=3)

        ttk.Checkbutton(
            g, text="复制音频流(不重编码)", variable=self.copy_audio_var
        ).grid(row=1, column=2, columnspan=3, sticky="w", padx=5, pady=3)

        name_frame = ttk.LabelFrame(tab, text=" 输出设置 ", padding=8)
        name_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(name_frame, text="输出文件后缀:").pack(side=tk.LEFT)
        ttk.Entry(name_frame, textvariable=self.suffix_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(name_frame, text="(文件名后、扩展名前)").pack(side=tk.LEFT)

        prev_frame = ttk.LabelFrame(tab, text=" 预览设置 ", padding=8)
        prev_frame.pack(fill=tk.X, pady=(0, 8))

        pg = ttk.Frame(prev_frame)
        pg.pack(fill=tk.X)
        ttk.Label(pg, text="起始时间(秒):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Spinbox(
            pg, from_=0, to=9999, textvariable=self.preview_start_var,
            width=10, increment=1.0
        ).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(pg, text="预览时长(秒):").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Spinbox(
            pg, from_=1, to=30, textvariable=self.preview_duration_var,
            width=10, increment=1.0
        ).grid(row=0, column=3, sticky="w", padx=5)

        ff_frame = ttk.LabelFrame(tab, text=" FFmpeg 路径 ", padding=8)
        ff_frame.pack(fill=tk.X, pady=(0, 8))

        ff_row = ttk.Frame(ff_frame)
        ff_row.pack(fill=tk.X)
        ttk.Label(ff_row, text="FFmpeg:").pack(side=tk.LEFT)
        ttk.Entry(ff_row, textvariable=self.ffmpeg_path_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(ff_row, text="浏览", command=self._browse_ffmpeg).pack(side=tk.LEFT)

    # ---- 日志页 ----
    def _build_log_tab(self):
        tab = self.tab_log

        btn_row = ttk.Frame(tab)
        btn_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_row, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT)

        self.log_text = scrolledtext.ScrolledText(
            tab, wrap=tk.WORD, font=("Consolas", 9), height=25, state="disabled"
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    #  事件处理
    # ============================================================

    def _check_ffmpeg(self):
        if self.processor.is_available():
            self.ffmpeg_status_label.config(
                text="FFmpeg 已就绪", style="Success.TLabel"
            )
        else:
            self.ffmpeg_status_label.config(
                text="未找到 FFmpeg", style="Error.TLabel"
            )
            messagebox.showwarning(
                "缺少 FFmpeg",
                "未找到 FFmpeg！请安装 FFmpeg 并加入 PATH。\n\n"
                "下载: https://ffmpeg.org/download.html\n\n"
                "或在「高级设置」中手动指定路径。"
            )

    def _select_input(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        path = filedialog.askopenfilename(
            title="选择视频文件",
            filetypes=[("视频文件", exts), ("所有文件", "*.*")]
        )
        if path:
            self.input_files = [path]
            self.input_var.set(path)
            self._update_file_info()

    def _select_inputs_batch(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        paths = filedialog.askopenfilenames(
            title="选择视频文件(可多选)",
            filetypes=[("视频文件", exts), ("所有文件", "*.*")]
        )
        if paths:
            self.input_files = list(paths)
            if len(paths) == 1:
                self.input_var.set(paths[0])
            else:
                self.input_var.set(f"已选择 {len(paths)} 个文件")
            self._update_file_info()

    def _update_file_info(self):
        if not self.input_files:
            self.file_info_var.set("请选择输入视频文件")
            return

        if len(self.input_files) == 1:
            fp = self.input_files[0]
            info = get_video_info(fp)
            parts = []

            if os.path.exists(fp):
                parts.append(format_filesize(os.path.getsize(fp)))

            if info and "streams" in info:
                for s in info["streams"]:
                    if s.get("codec_type") == "video":
                        w = s.get("width", "?")
                        h = s.get("height", "?")
                        parts.append(f"{w}x{h}")
                        parts.append(f"编码:{s.get('codec_name', '?')}")
                        fps_str = s.get("r_frame_rate", "")
                        if fps_str and "/" in fps_str:
                            try:
                                num, den = fps_str.split("/")
                                parts.append(f"{int(num)/int(den):.2f}fps")
                            except (ValueError, ZeroDivisionError):
                                pass
                        break

            if info and "format" in info:
                try:
                    dur = float(info["format"].get("duration", 0))
                    parts.append(f"时长:{format_duration(dur)}")
                except (ValueError, TypeError):
                    pass

            self.file_info_var.set("  |  ".join(parts) if parts else fp)
        else:
            total = sum(os.path.getsize(f) for f in self.input_files if os.path.exists(f))
            self.file_info_var.set(
                f"共 {len(self.input_files)} 个文件  |  总大小: {format_filesize(total)}"
            )

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir = d
            self.output_var.set(d)

    def _on_preset_changed(self, event=None):
        idx = self.preset_combo.current()
        if idx < 0:
            return
        preset = self.presets[idx]

        self.desc_text.config(state="normal")
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", preset.description)
        self.desc_text.config(state="disabled")

        self.radius_var.set(preset.tmedian_radius)
        self.deflicker_size_var.set(preset.deflicker_size)
        self.deflicker_mode_var.set(preset.deflicker_mode)
        self.tmix_frames_var.set(preset.tmix_frames)
        self.tmix_weights_var.set(preset.tmix_weights)
        self.custom_vf_var.set(preset.custom_vf)

        self._update_vf_preview()

    def _on_param_changed(self, *_):
        """任何参数变化时更新预览"""
        # 更新阈值数值标签
        self.threshold_value_label.config(
            text=f"{self.threshold_value_var.get():.1f}"
        )
        self.spatial_value_label.config(
            text=f"{self.spatial_strength_var.get():.1f}"
        )
        self.motion_value_label.config(
            text=f"{int(self.motion_threshold_var.get())}"
        )

        self._update_vf_preview()

    def _update_vf_preview(self):
        preset = self._build_current_preset()
        self.vf_preview_var.set(preset.build_vf())

    def _build_current_preset(self) -> FilterPreset:
        idx = self.preset_combo.current()
        base = self.presets[max(idx, 0)]

        # ★ 确定阈值模式
        if self.threshold_enable_var.get():
            mode_str = self.threshold_mode_var.get()
            threshold_mode = {
                "hqdn3d": ThresholdMode.HQDN3D,
                "nlmeans": ThresholdMode.NLMEANS,
                "masking": ThresholdMode.MASKING,
            }.get(mode_str, ThresholdMode.NONE)
            threshold_value = self.threshold_value_var.get()
        else:
            threshold_mode = ThresholdMode.NONE
            threshold_value = 0.0

        return FilterPreset(
            name=base.name,
            mode=base.mode,
            description=base.description,
            tmedian_radius=self.radius_var.get(),
            tmix_frames=self.tmix_frames_var.get(),
            tmix_weights=self.tmix_weights_var.get(),
            deflicker_mode=self.deflicker_mode_var.get(),
            deflicker_size=self.deflicker_size_var.get(),
            ema_alpha=getattr(base, "ema_alpha", 0.3),
            custom_vf=self.custom_vf_var.get(),
            codec=self.codec_var.get(),
            crf=self.crf_var.get(),
            preset=self.enc_preset_var.get(),
            copy_audio=self.copy_audio_var.get(),
            # ★ 阈值参数
            threshold_mode=threshold_mode,
            threshold_value=threshold_value,
            spatial_strength=self.spatial_strength_var.get(),
            motion_threshold=self.motion_threshold_var.get(),
        )

    def _get_output_path(self, input_path: str) -> str:
        p = Path(input_path)
        suffix = self.suffix_var.get() or "_deflickered"
        out_name = f"{p.stem}{suffix}{p.suffix}"
        if self.output_dir:
            return str(Path(self.output_dir) / out_name)
        return str(p.parent / out_name)

    # ---- 日志 ----
    def _log(self, msg: str):
        def _append():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, _append)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    # ---- 进度 ----
    def _update_progress(self, pct: float, current: float, total: float):
        def _u():
            self.progress_var.set(pct)
            self.progress_label.config(
                text=f"{pct:.1f}%  |  {format_duration(current)} / {format_duration(total)}"
            )
        self.root.after(0, _u)

    # ---- 处理 ----
    def _start_processing(self):
        if self.is_processing:
            return
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择输入视频文件！")
            return
        if not self.processor.is_available():
            messagebox.showerror("错误", "未找到 FFmpeg！")
            return

        preset = self._build_current_preset()
        vf = preset.build_vf()
        if not vf:
            messagebox.showwarning("提示", "滤镜字符串为空！")
            return

        # ★ 确认信息中显示阈值状态
        thresh_info = ""
        if preset.threshold_mode != ThresholdMode.NONE:
            thresh_info = (
                f"\n阈值模式: {preset.threshold_mode.value}"
                f"\n阈值: {preset.threshold_value:.1f}"
            )

        if len(self.input_files) == 1:
            out = self._get_output_path(self.input_files[0])
            msg = (
                f"输入: {self.input_files[0]}\n"
                f"输出: {out}\n"
                f"滤镜: {vf}{thresh_info}\n\n"
                f"开始处理？"
            )
        else:
            msg = (
                f"共 {len(self.input_files)} 个文件\n"
                f"滤镜: {vf}{thresh_info}\n\n"
                f"开始批量处理？"
            )

        if not messagebox.askyesno("确认", msg):
            return

        self.is_processing = True
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress_var.set(0)

        thread = threading.Thread(target=self._process_thread, args=(preset,), daemon=True)
        thread.start()

    def _process_thread(self, preset: FilterPreset):
        total_files = len(self.input_files)
        success = 0
        failed = 0

        for i, input_path in enumerate(self.input_files):
            if self.processor.cancelled:
                break

            output_path = self._get_output_path(input_path)

            self._log(f"\n{'='*60}")
            self._log(f"[{i+1}/{total_files}] {os.path.basename(input_path)}")
            self._log(f"输出: {output_path}")
            if preset.threshold_mode != ThresholdMode.NONE:
                self._log(f"阈值模式: {preset.threshold_mode.value} | "
                          f"阈值: {preset.threshold_value:.1f}")
            self._log(f"{'='*60}")

            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

            ok = self.processor.process_video(
                input_path, output_path, preset,
                progress_callback=self._update_progress,
                log_callback=self._log,
            )

            if ok:
                success += 1
                if os.path.exists(output_path):
                    self._log(f"输出大小: {format_filesize(os.path.getsize(output_path))}")
            else:
                failed += 1

        self.root.after(0, self._processing_done, success, failed)

    def _processing_done(self, success: int, failed: int):
        self.is_processing = False
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")

        total = success + failed
        if failed == 0:
            self.progress_label.config(text=f"全部完成 ({success}/{total})")
            messagebox.showinfo("完成", f"处理完成！成功 {success} 个文件")
        else:
            self.progress_label.config(text=f"完成 (成功{success}/失败{failed})")
            messagebox.showwarning(
                "部分失败",
                f"成功: {success}\n失败: {failed}\n\n请查看日志。"
            )

    def _cancel_processing(self):
        if self.is_processing:
            self.processor.cancel()
            self.progress_label.config(text="正在取消...")

    # ---- 预览 ----
    def _generate_preview(self):
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择输入视频文件！")
            return
        if not self.processor.is_available():
            messagebox.showerror("错误", "未找到 FFmpeg！")
            return

        preset = self._build_current_preset()
        preset.preset = "ultrafast"
        input_path = self.input_files[0]
        start = self.preview_start_var.get()
        duration = self.preview_duration_var.get()

        p = Path(input_path)
        preview_path = str(p.parent / f"{p.stem}_preview{p.suffix}")

        self._log(f"\n生成预览: {start}s 起, 时长 {duration}s")
        self.preview_btn.config(state="disabled")

        def _do():
            ok = self.processor.generate_preview(
                input_path, preview_path, preset,
                start_time=start, duration=duration,
                log_callback=self._log,
            )
            self.root.after(0, lambda: self._preview_done(ok, preview_path))

        threading.Thread(target=_do, daemon=True).start()

    def _preview_done(self, success: bool, preview_path: str):
        self.preview_btn.config(state="normal")
        if success and os.path.exists(preview_path):
            self._log(f"预览已生成: {preview_path}")
            if messagebox.askyesno("预览完成", f"预览已生成:\n{preview_path}\n\n打开播放？"):
                self._open_file(preview_path)
        else:
            self._log("预览生成失败")
            messagebox.showerror("失败", "预览生成失败，请查看日志。")

    def _open_file(self, path: str):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.run(["open", path])
            else:
                subprocess.run(["xdg-open", path])
        except Exception as e:
            self._log(f"无法打开: {e}")

    def _open_output_dir(self):
        if self.output_dir:
            target = self.output_dir
        elif self.input_files:
            target = str(Path(self.input_files[0]).parent)
        else:
            return
        self._open_file(target)

    def _browse_ffmpeg(self):
        ftypes = [("可执行文件", "*.exe")] if sys.platform == "win32" else [("所有文件", "*")]
        path = filedialog.askopenfilename(title="选择 FFmpeg", filetypes=ftypes)
        if path:
            self.processor.ffmpeg_path = path
            self.ffmpeg_path_var.set(path)
            self._check_ffmpeg()


# ============================================================
#  入口
# ============================================================

def main():
    try:
        if sys.platform == "win32":
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    app = DeflickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()