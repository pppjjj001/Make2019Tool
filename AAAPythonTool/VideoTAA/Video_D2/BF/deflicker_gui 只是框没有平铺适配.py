"""
视频去闪烁工具 - Video Deflicker Tool v2.0
基于 FFmpeg + OpenCV 的视频闪烁消除 GUI 工具
支持多种滤波模式、运动自适应处理、批量处理
"""

import os
import sys
import json
import subprocess
import threading
import re
import shutil
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Callable, Any
from enum import Enum

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ============================================================
#  可选依赖（安全导入）
# ============================================================

CV2_AVAILABLE = False
NP_AVAILABLE = False
SCIPY_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    np = None

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None

try:
    from scipy.signal import savgol_filter as _savgol
    SCIPY_AVAILABLE = True
except ImportError:
    _savgol = None

# ============================================================
#  常量
# ============================================================

APP_TITLE = "视频去闪烁工具 Video Deflicker"
APP_VERSION = "2.0.0"

SUPPORTED_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".vob",
}

# ============================================================
#  安全子进程调用（修复 Windows GBK 编码崩溃）
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
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, **kwargs)
        stdout = result.stdout
        stderr = result.stderr
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return subprocess.CompletedProcess(cmd, result.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, -1, "", "timeout")
    except Exception as e:
        return subprocess.CompletedProcess(cmd, -1, "", str(e))


def safe_popen(cmd: list) -> subprocess.Popen:
    kwargs = _get_popen_kwargs()
    return subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
    )


def safe_readline(stream) -> Optional[str]:
    try:
        raw = stream.readline()
        if not raw:
            return None
        for enc in ("utf-8", "gbk", "latin-1"):
            try:
                return raw.decode(enc).rstrip("\r\n")
            except (UnicodeDecodeError, AttributeError):
                continue
        return raw.decode("latin-1", errors="replace").rstrip("\r\n")
    except Exception:
        return None


# ============================================================
#  FFmpeg / FFprobe 检测
# ============================================================

def find_ffmpeg() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    for c in [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        os.path.join(here, "ffmpeg.exe"),
        os.path.join(here, "ffmpeg_bin", "ffmpeg.exe"),
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
    ]:
        if os.path.isfile(c):
            return c
    return None


def find_ffprobe() -> Optional[str]:
    path = shutil.which("ffprobe")
    if path:
        return path
    here = os.path.dirname(os.path.abspath(__file__))
    for c in [
        r"C:\ffmpeg\bin\ffprobe.exe",
        r"C:\Program Files\ffmpeg\bin\ffprobe.exe",
        os.path.join(here, "ffprobe.exe"),
        os.path.join(here, "ffmpeg_bin", "ffprobe.exe"),
        "/usr/bin/ffprobe",
        "/usr/local/bin/ffprobe",
    ]:
        if os.path.isfile(c):
            return c
    return None


def get_video_info(filepath: str) -> dict:
    ffprobe = find_ffprobe()
    if not ffprobe:
        return {}
    try:
        result = safe_run([
            ffprobe, "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", filepath,
        ], timeout=30)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}


def format_duration(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"


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
#  滤波方案
# ============================================================

class FilterMode(Enum):
    # FFmpeg 原生
    TMEDIAN = "tmedian"
    TMIX = "tmix"
    DEFLICKER = "deflicker"
    TMEDIAN_PLUS_DEFLICKER = "tmedian+deflicker"
    EMA = "ema"
    CUSTOM = "custom"
    # Python/OpenCV
    MOTION_ADAPTIVE = "motion_adaptive"
    OPTICAL_FLOW = "optical_flow"
    FREQUENCY_LOWPASS = "frequency_lowpass"
    GLOBAL_LUMA_PYTHON = "global_luma_python"


OPENCV_MODES = {
    FilterMode.MOTION_ADAPTIVE,
    FilterMode.OPTICAL_FLOW,
    FilterMode.FREQUENCY_LOWPASS,
    FilterMode.GLOBAL_LUMA_PYTHON,
}


@dataclass
class FilterPreset:
    name: str
    mode: FilterMode
    description: str
    # FFmpeg 参数
    tmedian_radius: int = 1
    tmix_frames: int = 3
    tmix_weights: str = "1 2 1"
    deflicker_mode: str = "am"
    deflicker_size: int = 5
    ema_alpha: float = 0.3
    extra_filters: str = ""
    custom_vf: str = ""
    # 运动自适应
    flicker_threshold: float = 5.0
    motion_threshold: float = 25.0
    temporal_strength: float = 0.7
    temporal_window: int = 3
    spatial_blur: int = 5
    # 光流
    flow_quality: str = "medium"
    # 频域
    freq_cutoff: float = 0.3
    # 亮度
    luma_smoothing: int = 11
    # 锐化
    sharpen_amount: float = 0.0
    # 编码
    codec: str = "libx264"
    crf: int = 18
    preset: str = "medium"
    copy_audio: bool = True

    def build_vf(self) -> str:
        filters: list = []
        if self.mode == FilterMode.CUSTOM:
            return self.custom_vf
        if self.mode == FilterMode.TMEDIAN:
            filters.append(f"tmedian=radius={self.tmedian_radius}")
        elif self.mode == FilterMode.TMIX:
            filters.append(f"tmix=frames={self.tmix_frames}:weights='{self.tmix_weights}'")
        elif self.mode == FilterMode.DEFLICKER:
            filters.append(f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}")
        elif self.mode == FilterMode.TMEDIAN_PLUS_DEFLICKER:
            filters.append(f"tmedian=radius={self.tmedian_radius}")
            filters.append(f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}")
        elif self.mode == FilterMode.EMA:
            n = 5
            alpha = self.ema_alpha
            w = [f"{alpha * ((1 - alpha) ** i):.3f}" for i in range(n)]
            w.reverse()
            filters.append(f"tmix=frames={n}:weights='{' '.join(w)}'")
        if self.extra_filters.strip():
            filters.append(self.extra_filters.strip())
        return ",".join(filters)

    @property
    def needs_opencv(self) -> bool:
        return self.mode in OPENCV_MODES


DEFAULT_PRESETS: List[FilterPreset] = [
    FilterPreset(
        name="[FFmpeg] 轻度去闪 - 时域中值 (推荐)",
        mode=FilterMode.TMEDIAN,
        description="3帧窗口取中值，消除±1像素跳变\n速度快，运动保持优秀\n推荐首选方案",
        tmedian_radius=1,
    ),
    FilterPreset(
        name="[FFmpeg] 中度去闪 - 时域中值(加强)",
        mode=FilterMode.TMEDIAN,
        description="5帧窗口中值，更强去闪能力\n快速运动可能轻微模糊",
        tmedian_radius=2,
    ),
    FilterPreset(
        name="[FFmpeg] 全局亮度补偿 - Deflicker",
        mode=FilterMode.DEFLICKER,
        description="分析全帧亮度变化并补偿\n适合整帧亮度周期性波动",
        deflicker_mode="am", deflicker_size=5,
    ),
    FilterPreset(
        name="[FFmpeg] 组合 - 中值+亮度补偿",
        mode=FilterMode.TMEDIAN_PLUS_DEFLICKER,
        description="先中值去像素跳变，再全局亮度补偿\n最全面的FFmpeg方案",
        tmedian_radius=1, deflicker_mode="am", deflicker_size=5,
    ),
    FilterPreset(
        name="[FFmpeg] 时域加权平均 - TMix",
        mode=FilterMode.TMIX,
        description="帧间加权平均，中心帧权重高\n运动场景会产生拖影",
        tmix_frames=3, tmix_weights="1 2 1",
    ),
    FilterPreset(
        name="[FFmpeg] EMA指数平滑",
        mode=FilterMode.EMA,
        description="指数移动平均，alpha越小越平滑",
        ema_alpha=0.3,
    ),
    FilterPreset(
        name="[Python] 运动自适应去闪 (推荐★)",
        mode=FilterMode.MOTION_ADAPTIVE,
        description="★ 核心方案：逐像素判断闪烁/运动\n静止区强力去闪，运动区完全保留\n需要: pip install opencv-python numpy",
        flicker_threshold=5.0, motion_threshold=25.0,
        temporal_strength=0.7, temporal_window=3, spatial_blur=5,
    ),
    FilterPreset(
        name="[Python] 光流引导去闪 (最高质量)",
        mode=FilterMode.OPTICAL_FLOW,
        description="光流追踪运动→对齐→中值滤波\n质量最高速度最慢\n需要: pip install opencv-python numpy",
        temporal_window=5, flow_quality="medium",
    ),
    FilterPreset(
        name="[Python] 频域时域低通",
        mode=FilterMode.FREQUENCY_LOWPASS,
        description="FFT低通滤波消除时域高频波动\n适合周期性闪烁\n需要: pip install opencv-python numpy",
        freq_cutoff=0.3,
    ),
    FilterPreset(
        name="[Python] 全局亮度补偿(Python版)",
        mode=FilterMode.GLOBAL_LUMA_PYTHON,
        description="Python实现全局亮度补偿\n完全不影响空间细节\n需要: pip install opencv-python numpy",
        luma_smoothing=11,
    ),
    FilterPreset(
        name="[FFmpeg] 自定义滤镜",
        mode=FilterMode.CUSTOM,
        description="手动输入FFmpeg -vf滤镜字符串\n示例: tmedian=radius=1,deflicker=size=7",
        custom_vf="tmedian=radius=1",
    ),
]


# ============================================================
#  Python/OpenCV 处理引擎
# ============================================================

class PythonProcessor:
    """OpenCV 原生处理引擎"""

    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def process_video(
        self,
        input_path: str,
        output_path: str,
        preset: FilterPreset,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
    ) -> bool:
        self.cancelled = False

        if not CV2_AVAILABLE or not NP_AVAILABLE:
            if log_callback:
                log_callback("[错误] 需要安装 opencv-python 和 numpy:\n  pip install opencv-python numpy")
            return False

        dispatch = {
            FilterMode.MOTION_ADAPTIVE: self._motion_adaptive,
            FilterMode.OPTICAL_FLOW: self._optical_flow,
            FilterMode.FREQUENCY_LOWPASS: self._frequency_lowpass,
            FilterMode.GLOBAL_LUMA_PYTHON: self._global_luma,
        }
        handler = dispatch.get(preset.mode)
        if not handler:
            if log_callback:
                log_callback(f"[错误] 未知处理模式: {preset.mode}")
            return False

        try:
            return handler(input_path, output_path, preset, progress_callback, log_callback)
        except Exception as e:
            if log_callback:
                log_callback(f"[异常] {e}")
            import traceback
            if log_callback:
                log_callback(traceback.format_exc())
            return False

    # --- 辅助 ---

    @staticmethod
    def _open_video(path: str):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return cap, fps, w, h, total

    @staticmethod
    def _create_writer(path: str, fps: float, w: int, h: int):
        # 使用 FFV1 无损编码作为中间格式（如果可用）
        # 回退到 MJPEG（近无损）或 mp4v
        for fourcc_str, ext in [("FFV1", ".avi"), ("MJPG", ".avi"), ("mp4v", ".mp4")]:
            fourcc = cv2.VideoWriter_fourcc(*fourcc_str)
            writer = cv2.VideoWriter(path, fourcc, fps, (w, h))
            if writer.isOpened():
                return writer
        raise RuntimeError("无法创建视频写入器")

    def _read_all_frames(self, cap, total, log_cb=None, progress_cb=None):
        frames = []
        idx = 0
        while True:
            if self.cancelled:
                return None
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            idx += 1
            if progress_cb and total > 0 and idx % 30 == 0:
                progress_cb(idx / total * 30, idx, total)
        if log_cb:
            log_cb(f"  已读取 {len(frames)} 帧")
        return frames

    @staticmethod
    def _sharpen(frame, amount: float):
        """轻度锐化补偿（参数用 Any 类型避免 np 未定义）"""
        if amount <= 0:
            return frame
        blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.0)
        result = np.clip(
            frame.astype(np.float64) * (1.0 + amount)
            - blurred.astype(np.float64) * amount,
            0, 255,
        ).astype(np.uint8)
        return result

    # # --- 方案1: 运动自适应 ---
    # ============================================================
    #  修复后的 _motion_adaptive 方法
    #  替换 PythonProcessor 类中的同名方法即可
    # ============================================================

    def _motion_adaptive(self, input_path, output_path, preset, progress_cb, log_cb):
        if log_cb:
            log_cb("[运动自适应] 开始处理...")
            log_cb(f"  闪烁阈值={preset.flicker_threshold} 运动阈值={preset.motion_threshold}")
            log_cb(f"  时域强度={preset.temporal_strength} 窗口={preset.temporal_window}")

        cap, fps, w, h, total = self._open_video(input_path)
        writer = self._create_writer(output_path, fps, w, h)
        half = preset.temporal_window // 2
        buf = []

        # 填充初始缓冲区
        for _ in range(preset.temporal_window):
            ret, frame = cap.read()
            if not ret:
                break
            buf.append(frame.astype(np.float64))

        if not buf:
            if log_cb:
                log_cb("[错误] 无法读取任何帧")
            cap.release()
            writer.release()
            return False

        if log_cb:
            log_cb(f"  初始缓冲: {len(buf)} 帧, 视频总帧数: {total}")

        frame_idx = 0
        while buf:
            if self.cancelled:
                cap.release()
                writer.release()
                if log_cb:
                    log_cb("[取消]")
                return False

            center = min(half, len(buf) - 1)
            curr = buf[center]

            # ============================================================
            #  核心修复: 只有1帧时直接输出原始帧，不做差异计算
            # ============================================================
            if len(buf) <= 1:
                out_frame = np.clip(curr, 0, 255).astype(np.uint8)
                if preset.sharpen_amount > 0:
                    out_frame = self._sharpen(out_frame, preset.sharpen_amount)
                writer.write(out_frame)
                frame_idx += 1

                # 尝试读取下一帧
                ret, frame = cap.read()
                if not ret:
                    break
                buf = [frame.astype(np.float64)]
                continue

            # ============================================================
            #  正常处理: buffer >= 2 帧
            # ============================================================

            # 计算当前帧与缓冲区内其他帧的差异
            diffs = []
            for i in range(len(buf)):
                if i != center:
                    diffs.append(np.abs(buf[i] - curr))

            # 取所有差异的逐像素最大值
            max_diff = np.max(np.stack(diffs, axis=0), axis=0)

            # ---- 运动权重掩码 ----
            # motion_weight = 1.0 → 运动区域，保留原始
            # motion_weight = 0.0 → 闪烁区域，使用滤波结果
            motion_weight = np.clip(
                (max_diff - preset.flicker_threshold)
                / max(preset.motion_threshold - preset.flicker_threshold, 1e-6),
                0.0,
                1.0,
            )

            # 空间平滑运动掩码（减少边缘伪影）
            if preset.spatial_blur > 1:
                k = preset.spatial_blur
                if k % 2 == 0:
                    k += 1
                for c in range(motion_weight.shape[2]):
                    motion_weight[:, :, c] = cv2.GaussianBlur(
                        motion_weight[:, :, c], (k, k), 0
                    )

            # ---- 时域中值滤波 ----
            stack = np.stack(buf, axis=0)
            temporal_filtered = np.median(stack, axis=0)

            # 与当前帧混合（控制平滑强度）
            filtered = (
                preset.temporal_strength * temporal_filtered
                + (1 - preset.temporal_strength) * curr
            )

            # ---- 自适应混合 ----
            result = motion_weight * curr + (1 - motion_weight) * filtered

            out_frame = np.clip(result, 0, 255).astype(np.uint8)
            if preset.sharpen_amount > 0:
                out_frame = self._sharpen(out_frame, preset.sharpen_amount)

            writer.write(out_frame)
            frame_idx += 1

            # 进度回调
            if progress_cb and total > 0 and frame_idx % 10 == 0:
                pct = frame_idx / total * 100
                progress_cb(pct, frame_idx, total)

            # ---- 滑动窗口 ----
            ret, frame = cap.read()
            if not ret:
                # 视频读完，缩小缓冲区继续处理剩余帧
                buf.pop(0)
            else:
                buf.append(frame.astype(np.float64))
                if len(buf) > preset.temporal_window:
                    buf.pop(0)

        cap.release()
        writer.release()

        if progress_cb:
            progress_cb(100.0, frame_idx, total)
        if log_cb:
            log_cb(f"[运动自适应] 完成，共处理 {frame_idx} 帧")
        return True

    # --- 方案2: 光流引导 ---

    def _optical_flow(self, input_path, output_path, preset, progress_cb, log_cb):
        if log_cb:
            log_cb("[光流引导] 开始处理（速度较慢）...")

        cap, fps, w, h, total = self._open_video(input_path)
        frames = self._read_all_frames(cap, total, log_cb, progress_cb)
        cap.release()
        if frames is None or not frames:
            return False

        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        fp_map = {
            "fast": dict(pyr_scale=0.5, levels=1, winsize=5, iterations=1, poly_n=5, poly_sigma=1.1, flags=0),
            "medium": dict(pyr_scale=0.5, levels=3, winsize=15, iterations=3, poly_n=5, poly_sigma=1.2, flags=0),
            "high": dict(pyr_scale=0.5, levels=5, winsize=21, iterations=5, poly_n=7, poly_sigma=1.5, flags=0),
        }
        fp = fp_map.get(preset.flow_quality, fp_map["medium"])
        grid_y, grid_x = np.mgrid[0:h, 0:w].astype(np.float32)
        half = preset.temporal_window // 2
        writer = self._create_writer(output_path, fps, w, h)

        for i in range(len(frames)):
            if self.cancelled:
                writer.release()
                return False
            aligned = []
            for j in range(max(0, i - half), min(len(frames), i + half + 1)):
                if j == i:
                    aligned.append(frames[i].astype(np.float64))
                    continue
                flow = cv2.calcOpticalFlowFarneback(grays[j], grays[i], None, **fp)
                map_x = grid_x + flow[:, :, 0]
                map_y = grid_y + flow[:, :, 1]
                warped = cv2.remap(frames[j], map_x, map_y,
                                   interpolation=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_REFLECT)
                aligned.append(warped.astype(np.float64))
            stack = np.stack(aligned, axis=0)
            filtered = np.median(stack, axis=0)
            out_frame = np.clip(filtered, 0, 255).astype(np.uint8)
            if preset.sharpen_amount > 0:
                out_frame = self._sharpen(out_frame, preset.sharpen_amount)
            writer.write(out_frame)
            if progress_cb and i % 5 == 0:
                progress_cb(30 + i / len(frames) * 70, i, len(frames))

        writer.release()
        if progress_cb:
            progress_cb(100.0, len(frames), len(frames))
        if log_cb:
            log_cb(f"[光流引导] 完成，{len(frames)} 帧")
        return True

    # --- 方案3: 频域低通 ---

    def _frequency_lowpass(self, input_path, output_path, preset, progress_cb, log_cb):
        if log_cb:
            log_cb(f"[频域低通] 截止比例={preset.freq_cutoff}")

        cap, fps, w, h, total = self._open_video(input_path)
        frames = self._read_all_frames(cap, total, log_cb, progress_cb)
        cap.release()
        if frames is None or not frames:
            return False

        if log_cb:
            log_cb(f"  对 {len(frames)} 帧做时域FFT...")
        arr = np.stack(frames, axis=0).astype(np.float64)
        T = arr.shape[0]
        freq = np.fft.rfft(arr, axis=0)
        n_freq = freq.shape[0]
        cutoff = int(n_freq * preset.freq_cutoff)

        filt = np.ones(n_freq)
        if cutoff < n_freq:
            tr = n_freq - cutoff
            filt[cutoff:] = 0.5 * (1 + np.cos(np.pi * np.arange(tr) / max(tr, 1)))
        filt[0] = 1.0
        filt = filt[:, np.newaxis, np.newaxis, np.newaxis]
        result = np.fft.irfft(freq * filt, n=T, axis=0)
        result = np.clip(result, 0, 255).astype(np.uint8)

        writer = self._create_writer(output_path, fps, w, h)
        for i in range(T):
            if self.cancelled:
                writer.release()
                return False
            out_f = result[i]
            if preset.sharpen_amount > 0:
                out_f = self._sharpen(out_f, preset.sharpen_amount)
            writer.write(out_f)
            if progress_cb and i % 30 == 0:
                progress_cb(70 + i / T * 30, i, T)
        writer.release()
        if progress_cb:
            progress_cb(100.0, T, T)
        if log_cb:
            log_cb("[频域低通] 完成")
        return True

    # --- 方案4: 全局亮度 ---

    def _global_luma(self, input_path, output_path, preset, progress_cb, log_cb):
        if log_cb:
            log_cb(f"[全局亮度补偿] 平滑窗口={preset.luma_smoothing}")

        cap, fps, w, h, total = self._open_video(input_path)
        frames = self._read_all_frames(cap, total, log_cb, progress_cb)
        cap.release()
        if frames is None or not frames:
            return False

        lumas = np.array([np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)) for f in frames])
        if log_cb:
            log_cb(f"  亮度范围: {lumas.min():.1f}~{lumas.max():.1f}, std={np.std(lumas):.2f}")

        win = min(preset.luma_smoothing, len(lumas))
        if win % 2 == 0:
            win -= 1
        win = max(win, 3)

        if SCIPY_AVAILABLE and _savgol is not None:
            smoothed = _savgol(lumas, win, min(2, win - 1))
        else:
            kernel = np.ones(win) / win
            smoothed = np.convolve(lumas, kernel, mode="same")

        writer = self._create_writer(output_path, fps, w, h)
        for i, f in enumerate(frames):
            if self.cancelled:
                writer.release()
                return False
            if lumas[i] > 1:
                ratio = np.clip(smoothed[i] / lumas[i], 0.8, 1.2)
                corrected = np.clip(f.astype(np.float64) * ratio, 0, 255).astype(np.uint8)
            else:
                corrected = f.copy()
            if preset.sharpen_amount > 0:
                corrected = self._sharpen(corrected, preset.sharpen_amount)
            writer.write(corrected)
            if progress_cb and i % 30 == 0:
                progress_cb(70 + i / len(frames) * 30, i, len(frames))
        writer.release()
        if progress_cb:
            progress_cb(100.0, len(frames), len(frames))
        if log_cb:
            log_cb("[全局亮度补偿] 完成")
        return True


# ============================================================
#  FFmpeg 处理引擎
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

    def process_video(self, input_path, output_path, preset, progress_callback=None, log_callback=None) -> bool:
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

        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-vf", vf]
        if preset.codec == "copy":
            cmd.extend(["-c:v", "copy"])
        else:
            cmd.extend(["-c:v", preset.codec])
            if preset.codec in ("libx264", "libx265"):
                cmd.extend(["-crf", str(preset.crf), "-preset", preset.preset])
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
                    self.process.terminate()
                    if log_callback:
                        log_callback("[取消]")
                    return False
                line = safe_readline(self.process.stderr)
                if line is None:
                    if self.process.poll() is not None:
                        break
                    continue
                if log_callback and line.strip():
                    log_callback(line.strip())
                m = re.search(r"time=(\d+):(\d+):(\d+\.?\d*)", line)
                if m and total_duration > 0 and progress_callback:
                    cur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
                    progress_callback(min(cur / total_duration * 100, 99.9), cur, total_duration)
            self.process.wait()
            if self.process.returncode == 0:
                if progress_callback:
                    progress_callback(100.0, total_duration, total_duration)
                if log_callback:
                    log_callback("\n[完成] 处理成功！")
                return True
            else:
                if log_callback:
                    log_callback(f"\n[失败] 返回码: {self.process.returncode}")
                return False
        except Exception as e:
            if log_callback:
                log_callback(f"\n[异常] {e}")
            return False
        finally:
            if self.process:
                try:
                    self.process.stdout.close()
                    self.process.stderr.close()
                except Exception:
                    pass

    def generate_preview(self, input_path, output_path, preset, start_time=0, duration=3, log_callback=None) -> bool:
        if not self.ffmpeg_path:
            return False
        vf = preset.build_vf()
        if not vf:
            return False
        cmd = [
            self.ffmpeg_path, "-y", "-ss", str(start_time), "-i", input_path,
            "-t", str(duration), "-vf", vf, "-c:v", preset.codec,
        ]
        if preset.codec in ("libx264", "libx265"):
            cmd.extend(["-crf", str(preset.crf), "-preset", "ultrafast"])
        if preset.copy_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])
        cmd.append(output_path)
        if log_callback:
            log_callback(f"[预览] {' '.join(cmd)}")
        result = safe_run(cmd, timeout=120)
        if result.returncode != 0 and log_callback:
            log_callback(f"[预览错误] {result.stderr}")
        return result.returncode == 0


# ============================================================
#  音频合并辅助
# ============================================================

def copy_audio_to_output(ffmpeg_path, original, processed, final_out, log_cb=None) -> bool:
    cmd = [
        ffmpeg_path, "-y", "-i", processed, "-i", original,
        "-c:v", "copy", "-c:a", "copy",
        "-map", "0:v:0", "-map", "1:a:0?", "-shortest", final_out,
    ]
    if log_cb:
        log_cb(f"[音频合并] {' '.join(cmd)}")
    result = safe_run(cmd, timeout=300)
    if result.returncode == 0:
        return True
    if log_cb:
        log_cb(f"[音频合并失败] {result.stderr}")
    return False


# ============================================================
#  GUI
# ============================================================

class DeflickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1000x820")
        self.root.minsize(860, 700)

        self.ffmpeg_processor = FFmpegProcessor()
        self.python_processor = PythonProcessor()
        self.input_files: List[str] = []
        self.output_dir: str = ""
        self.is_processing = False
        self.presets = list(DEFAULT_PRESETS)

        self._create_variables()
        self._setup_styles()
        self._build_ui()
        self._on_preset_changed()
        self.root.after(100, self._check_environment)

    # --- 变量 ---
    def _create_variables(self):
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="(与输入文件相同目录)")
        self.file_info_var = tk.StringVar(value="请选择输入视频文件")
        self.preset_var = tk.StringVar()
        self.vf_preview_var = tk.StringVar()
        # FFmpeg
        self.radius_var = tk.IntVar(value=1)
        self.deflicker_size_var = tk.IntVar(value=5)
        self.deflicker_mode_var = tk.StringVar(value="am")
        self.tmix_frames_var = tk.IntVar(value=3)
        self.tmix_weights_var = tk.StringVar(value="1 2 1")
        self.custom_vf_var = tk.StringVar(value="tmedian=radius=1")
        # Python
        self.flicker_thresh_var = tk.DoubleVar(value=5.0)
        self.motion_thresh_var = tk.DoubleVar(value=25.0)
        self.temporal_strength_var = tk.DoubleVar(value=0.7)
        self.temporal_window_var = tk.IntVar(value=3)
        self.spatial_blur_var = tk.IntVar(value=5)
        self.flow_quality_var = tk.StringVar(value="medium")
        self.freq_cutoff_var = tk.DoubleVar(value=0.3)
        self.luma_smoothing_var = tk.IntVar(value=11)
        self.sharpen_var = tk.DoubleVar(value=0.0)
        # 编码
        self.codec_var = tk.StringVar(value="libx264")
        self.crf_var = tk.IntVar(value=18)
        self.enc_preset_var = tk.StringVar(value="medium")
        self.copy_audio_var = tk.BooleanVar(value=True)
        self.suffix_var = tk.StringVar(value="_deflickered")
        # 预览
        self.preview_start_var = tk.DoubleVar(value=0)
        self.preview_duration_var = tk.DoubleVar(value=3)
        # FFmpeg 路径
        self.ffmpeg_path_var = tk.StringVar(value=self.ffmpeg_processor.ffmpeg_path or "未找到")
        # 进度
        self.progress_var = tk.DoubleVar(value=0)

    # --- 样式 ---
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

    # --- 构建 UI ---
    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(side=tk.LEFT)
        ttk.Label(header, text=f"v{APP_VERSION}", style="Subtitle.TLabel").pack(side=tk.LEFT, padx=10)
        self.env_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.env_label.pack(side=tk.RIGHT)

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)

        self.tab_main = ttk.Frame(nb, padding=6)
        nb.add(self.tab_main, text="  处理  ")
        self.tab_advanced = ttk.Frame(nb, padding=6)
        nb.add(self.tab_advanced, text="  高级设置  ")
        self.tab_log = ttk.Frame(nb, padding=6)
        nb.add(self.tab_log, text="  日志  ")

        self._build_main_tab()
        self._build_advanced_tab()
        self._build_log_tab()

    def _build_main_tab(self):
        tab = self.tab_main

        # 滚动区域
        canvas = tk.Canvas(tab, highlightthickness=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        c = scroll_frame  # 内容区

        # === 文件 ===
        ff = ttk.LabelFrame(c, text=" 文件选择 ", padding=8)
        ff.pack(fill=tk.X, pady=(0, 6))

        r1 = ttk.Frame(ff)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="输入视频:").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.input_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(r1, text="选择文件", command=self._select_input).pack(side=tk.LEFT, padx=2)
        ttk.Button(r1, text="批量添加", command=self._select_inputs_batch).pack(side=tk.LEFT)

        ttk.Label(ff, textvariable=self.file_info_var, style="Info.TLabel").pack(fill=tk.X, pady=2)

        r2 = ttk.Frame(ff)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="输出目录:").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.output_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(r2, text="选择目录", command=self._select_output_dir).pack(side=tk.LEFT)

        # === 方案 ===
        sf = ttk.LabelFrame(c, text=" 滤波方案 ", padding=8)
        sf.pack(fill=tk.X, pady=(0, 6))

        pr = ttk.Frame(sf)
        pr.pack(fill=tk.X, pady=2)
        ttk.Label(pr, text="选择方案:").pack(side=tk.LEFT)
        self.preset_combo = ttk.Combobox(
            pr, textvariable=self.preset_var,
            values=[p.name for p in self.presets], state="readonly", width=45,
        )
        self.preset_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.preset_combo.current(0)
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)

        self.desc_text = tk.Text(sf, height=4, wrap=tk.WORD, state="disabled",
                                  font=("Microsoft YaHei UI", 9), bg="#f5f5f5")
        self.desc_text.pack(fill=tk.X, pady=4)

        vr = ttk.Frame(sf)
        vr.pack(fill=tk.X, pady=2)
        ttk.Label(vr, text="滤镜/模式:").pack(side=tk.LEFT)
        ttk.Entry(vr, textvariable=self.vf_preview_var, state="readonly", font=("Consolas", 9)).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # === FFmpeg参数 ===
        self.ffmpeg_param_frame = ttk.LabelFrame(c, text=" FFmpeg 滤镜参数 ", padding=8)
        self.ffmpeg_param_frame.pack(fill=tk.X, pady=(0, 6))
        g1 = ttk.Frame(self.ffmpeg_param_frame)
        g1.pack(fill=tk.X)

        ttk.Label(g1, text="中值半径:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g1, from_=1, to=10, textvariable=self.radius_var, width=8,
                     command=self._on_param_changed).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g1, text="(1=3帧, 2=5帧)").grid(row=0, column=2, sticky="w")

        ttk.Label(g1, text="Deflicker窗口:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g1, from_=2, to=129, textvariable=self.deflicker_size_var, width=8,
                     command=self._on_param_changed).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(g1, text="Deflicker模式:").grid(row=1, column=3, sticky="w", padx=5, pady=2)
        dm = ttk.Combobox(g1, textvariable=self.deflicker_mode_var,
                           values=["am", "gm", "hm", "qm", "cm", "pm", "median"],
                           state="readonly", width=8)
        dm.grid(row=1, column=4, sticky="w", padx=5, pady=2)
        dm.bind("<<ComboboxSelected>>", lambda e: self._on_param_changed())

        ttk.Label(g1, text="TMix帧数:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g1, from_=2, to=20, textvariable=self.tmix_frames_var, width=8,
                     command=self._on_param_changed).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g1, text="TMix权重:").grid(row=2, column=3, sticky="w", padx=5, pady=2)
        we = ttk.Entry(g1, textvariable=self.tmix_weights_var, width=15)
        we.grid(row=2, column=4, sticky="w", padx=5, pady=2)
        we.bind("<KeyRelease>", lambda e: self._on_param_changed())

        ttk.Label(g1, text="自定义-vf:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ce = ttk.Entry(g1, textvariable=self.custom_vf_var, width=50)
        ce.grid(row=3, column=1, columnspan=4, sticky="we", padx=5, pady=2)
        ce.bind("<KeyRelease>", lambda e: self._on_param_changed())

        # === Python参数 ===
        self.python_param_frame = ttk.LabelFrame(c, text=" Python 处理参数 ", padding=8)
        self.python_param_frame.pack(fill=tk.X, pady=(0, 6))
        g2 = ttk.Frame(self.python_param_frame)
        g2.pack(fill=tk.X)

        row = 0
        ttk.Label(g2, text="闪烁阈值:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=1, to=50, textvariable=self.flicker_thresh_var, width=8, increment=1.0,
                     command=self._on_param_changed).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text="<此值=闪烁").grid(row=row, column=2, sticky="w", padx=5)
        ttk.Label(g2, text="运动阈值:").grid(row=row, column=3, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=5, to=100, textvariable=self.motion_thresh_var, width=8, increment=1.0,
                     command=self._on_param_changed).grid(row=row, column=4, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text=">此值=运动").grid(row=row, column=5, sticky="w", padx=5)

        row += 1
        ttk.Label(g2, text="时域强度:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.1, to=1.0, textvariable=self.temporal_strength_var, width=8, increment=0.05,
                     command=self._on_param_changed).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text="时域窗口:").grid(row=row, column=3, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=3, to=11, textvariable=self.temporal_window_var, width=8, increment=2,
                     command=self._on_param_changed).grid(row=row, column=4, sticky="w", padx=5, pady=2)

        row += 1
        ttk.Label(g2, text="掩码模糊:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=1, to=15, textvariable=self.spatial_blur_var, width=8, increment=2,
                     command=self._on_param_changed).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text="光流质量:").grid(row=row, column=3, sticky="w", padx=5, pady=2)
        fq = ttk.Combobox(g2, textvariable=self.flow_quality_var,
                           values=["fast", "medium", "high"], state="readonly", width=8)
        fq.grid(row=row, column=4, sticky="w", padx=5, pady=2)

        row += 1
        ttk.Label(g2, text="频域截止:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.05, to=0.95, textvariable=self.freq_cutoff_var, width=8, increment=0.05,
                     command=self._on_param_changed).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text="亮度平滑:").grid(row=row, column=3, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=3, to=51, textvariable=self.luma_smoothing_var, width=8, increment=2,
                     command=self._on_param_changed).grid(row=row, column=4, sticky="w", padx=5, pady=2)

        row += 1
        ttk.Label(g2, text="输出锐化:").grid(row=row, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.0, to=2.0, textvariable=self.sharpen_var, width=8, increment=0.1,
                     command=self._on_param_changed).grid(row=row, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g2, text="0=不锐化 0.3=轻 1.0=强").grid(row=row, column=2, columnspan=2, sticky="w", padx=5)

        # === 操作 ===
        af = ttk.Frame(c)
        af.pack(fill=tk.X, pady=8)
        self.preview_btn = ttk.Button(af, text="生成预览(3秒)", command=self._generate_preview)
        self.preview_btn.pack(side=tk.LEFT, padx=5)
        self.start_btn = ttk.Button(af, text="开始处理", command=self._start_processing, style="Accent.TButton")
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.cancel_btn = ttk.Button(af, text="取消", command=self._cancel_processing, state="disabled")
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        ttk.Button(af, text="打开输出目录", command=self._open_output_dir).pack(side=tk.RIGHT, padx=5)

        # === 进度 ===
        pf = ttk.Frame(c)
        pf.pack(fill=tk.X, pady=(0, 5))
        self.progress_bar = ttk.Progressbar(pf, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 10))
        self.progress_label = ttk.Label(pf, text="就绪", width=35)
        self.progress_label.pack(side=tk.RIGHT)

    def _build_advanced_tab(self):
        tab = self.tab_advanced

        ef = ttk.LabelFrame(tab, text=" 编码设置 ", padding=8)
        ef.pack(fill=tk.X, pady=(0, 8))
        g = ttk.Frame(ef)
        g.pack(fill=tk.X)

        ttk.Label(g, text="编码器:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(g, textvariable=self.codec_var,
                      values=["libx264", "libx265", "libsvtav1", "libvpx-vp9", "mpeg4", "copy"],
                      state="readonly", width=15).grid(row=0, column=1, sticky="w", padx=5, pady=3)
        ttk.Label(g, text="CRF:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        ttk.Spinbox(g, from_=0, to=51, textvariable=self.crf_var, width=8).grid(row=0, column=3, sticky="w", padx=5, pady=3)
        ttk.Label(g, text="(0=无损 18=高 23=默认)").grid(row=0, column=4, sticky="w", padx=5)

        ttk.Label(g, text="速度:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Combobox(g, textvariable=self.enc_preset_var,
                      values=["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"],
                      state="readonly", width=15).grid(row=1, column=1, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(g, text="复制音频", variable=self.copy_audio_var).grid(row=1, column=2, columnspan=3, sticky="w", padx=5, pady=3)

        nf = ttk.LabelFrame(tab, text=" 输出设置 ", padding=8)
        nf.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(nf, text="后缀:").pack(side=tk.LEFT)
        ttk.Entry(nf, textvariable=self.suffix_var, width=20).pack(side=tk.LEFT, padx=5)

        pf = ttk.LabelFrame(tab, text=" 预览设置 ", padding=8)
        pf.pack(fill=tk.X, pady=(0, 8))
        pg = ttk.Frame(pf)
        pg.pack(fill=tk.X)
        ttk.Label(pg, text="起始(秒):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Spinbox(pg, from_=0, to=9999, textvariable=self.preview_start_var, width=10, increment=1.0).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(pg, text="时长(秒):").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Spinbox(pg, from_=1, to=30, textvariable=self.preview_duration_var, width=10, increment=1.0).grid(row=0, column=3, sticky="w", padx=5)

        fff = ttk.LabelFrame(tab, text=" FFmpeg 路径 ", padding=8)
        fff.pack(fill=tk.X, pady=(0, 8))
        fr = ttk.Frame(fff)
        fr.pack(fill=tk.X)
        ttk.Label(fr, text="FFmpeg:").pack(side=tk.LEFT)
        ttk.Entry(fr, textvariable=self.ffmpeg_path_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(fr, text="浏览", command=self._browse_ffmpeg).pack(side=tk.LEFT)

        envf = ttk.LabelFrame(tab, text=" 环境信息 ", padding=8)
        envf.pack(fill=tk.X, pady=(0, 8))
        self.env_detail_label = ttk.Label(envf, text="", style="Info.TLabel", wraplength=700)
        self.env_detail_label.pack(fill=tk.X)

    def _build_log_tab(self):
        tab = self.tab_log
        br = ttk.Frame(tab)
        br.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(br, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT)
        self.log_text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Consolas", 9), height=25, state="disabled")
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # --- 环境检查 ---
    def _check_environment(self):
        parts = []
        if self.ffmpeg_processor.is_available():
            parts.append("FFmpeg:OK")
        else:
            parts.append("FFmpeg:缺失")
        if CV2_AVAILABLE:
            parts.append(f"OpenCV:{cv2.__version__}")
        else:
            parts.append("OpenCV:未装")
        if SCIPY_AVAILABLE:
            parts.append("SciPy:OK")

        self.env_label.config(text=" | ".join(parts))

        detail = (
            f"FFmpeg: {'已找到 - ' + (self.ffmpeg_processor.ffmpeg_path or '') if self.ffmpeg_processor.is_available() else '未找到'}\n"
            f"OpenCV: {'v' + cv2.__version__ if CV2_AVAILABLE else '未安装 (pip install opencv-python numpy)'}\n"
            f"SciPy:  {'已安装' if SCIPY_AVAILABLE else '未安装 (可选)'}\n"
            f"NumPy:  {'已安装' if NP_AVAILABLE else '未安装'}\n"
        )
        self.env_detail_label.config(text=detail)

        if not self.ffmpeg_processor.is_available() and not CV2_AVAILABLE:
            messagebox.showwarning("环境缺失",
                "FFmpeg 和 OpenCV 均未找到！\n\n"
                "至少需要其一：\n"
                "· FFmpeg: https://ffmpeg.org\n"
                "· OpenCV: pip install opencv-python numpy")

    # --- 事件 ---
    def _select_input(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        p = filedialog.askopenfilename(title="选择视频", filetypes=[("视频", exts), ("所有", "*.*")])
        if p:
            self.input_files = [p]
            self.input_var.set(p)
            self._update_file_info()

    def _select_inputs_batch(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        ps = filedialog.askopenfilenames(title="选择视频(多选)", filetypes=[("视频", exts), ("所有", "*.*")])
        if ps:
            self.input_files = list(ps)
            self.input_var.set(ps[0] if len(ps) == 1 else f"已选择 {len(ps)} 个文件")
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
                        parts.append(f"{s.get('width', '?')}x{s.get('height', '?')}")
                        parts.append(f"编码:{s.get('codec_name', '?')}")
                        fps_s = s.get("r_frame_rate", "")
                        if "/" in fps_s:
                            try:
                                n, d = fps_s.split("/")
                                parts.append(f"{int(n)/int(d):.2f}fps")
                            except Exception:
                                pass
                        break
            if info and "format" in info:
                try:
                    parts.append(f"时长:{format_duration(float(info['format'].get('duration', 0)))}")
                except Exception:
                    pass
            self.file_info_var.set("  |  ".join(parts) if parts else fp)
        else:
            total = sum(os.path.getsize(f) for f in self.input_files if os.path.exists(f))
            self.file_info_var.set(f"共 {len(self.input_files)} 个文件 | 总大小: {format_filesize(total)}")

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_dir = d
            self.output_var.set(d)

    def _on_preset_changed(self, event=None):
        idx = self.preset_combo.current()
        if idx < 0:
            return
        p = self.presets[idx]
        self.desc_text.config(state="normal")
        self.desc_text.delete("1.0", tk.END)
        self.desc_text.insert("1.0", p.description)
        self.desc_text.config(state="disabled")

        self.radius_var.set(p.tmedian_radius)
        self.deflicker_size_var.set(p.deflicker_size)
        self.deflicker_mode_var.set(p.deflicker_mode)
        self.tmix_frames_var.set(p.tmix_frames)
        self.tmix_weights_var.set(p.tmix_weights)
        self.custom_vf_var.set(p.custom_vf)
        self.flicker_thresh_var.set(p.flicker_threshold)
        self.motion_thresh_var.set(p.motion_threshold)
        self.temporal_strength_var.set(p.temporal_strength)
        self.temporal_window_var.set(p.temporal_window)
        self.spatial_blur_var.set(p.spatial_blur)
        self.flow_quality_var.set(p.flow_quality)
        self.freq_cutoff_var.set(p.freq_cutoff)
        self.luma_smoothing_var.set(p.luma_smoothing)
        self.sharpen_var.set(p.sharpen_amount)

        is_py = p.needs_opencv
        if is_py:
            self.python_param_frame.pack(fill=tk.X, pady=(0, 6))
            self.ffmpeg_param_frame.pack_forget()
        else:
            self.ffmpeg_param_frame.pack(fill=tk.X, pady=(0, 6))
            self.python_param_frame.pack_forget()
        self._update_vf_preview()

    def _on_param_changed(self, *_):
        self._update_vf_preview()

    def _update_vf_preview(self):
        p = self._build_current_preset()
        self.vf_preview_var.set(f"[Python] {p.mode.value}" if p.needs_opencv else p.build_vf())

    def _build_current_preset(self) -> FilterPreset:
        idx = self.preset_combo.current()
        base = self.presets[max(idx, 0)]
        return FilterPreset(
            name=base.name, mode=base.mode, description=base.description,
            tmedian_radius=self.radius_var.get(),
            tmix_frames=self.tmix_frames_var.get(),
            tmix_weights=self.tmix_weights_var.get(),
            deflicker_mode=self.deflicker_mode_var.get(),
            deflicker_size=self.deflicker_size_var.get(),
            ema_alpha=getattr(base, "ema_alpha", 0.3),
            custom_vf=self.custom_vf_var.get(),
            flicker_threshold=self.flicker_thresh_var.get(),
            motion_threshold=self.motion_thresh_var.get(),
            temporal_strength=self.temporal_strength_var.get(),
            temporal_window=self.temporal_window_var.get(),
            spatial_blur=self.spatial_blur_var.get(),
            flow_quality=self.flow_quality_var.get(),
            freq_cutoff=self.freq_cutoff_var.get(),
            luma_smoothing=self.luma_smoothing_var.get(),
            sharpen_amount=self.sharpen_var.get(),
            codec=self.codec_var.get(), crf=self.crf_var.get(),
            preset=self.enc_preset_var.get(), copy_audio=self.copy_audio_var.get(),
        )

    def _get_output_path(self, input_path: str) -> str:
        p = Path(input_path)
        s = self.suffix_var.get() or "_deflickered"
        name = f"{p.stem}{s}{p.suffix}"
        return str(Path(self.output_dir) / name) if self.output_dir else str(p.parent / name)

    def _log(self, msg: str):
        def _a():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, _a)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def _update_progress(self, pct, current, total):
        def _u():
            self.progress_var.set(pct)
            self.progress_label.config(text=f"{pct:.1f}% | {int(current)}/{int(total)}")
        self.root.after(0, _u)

    # --- 处理 ---
    def _start_processing(self):
        if self.is_processing:
            return
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择输入视频！")
            return
        preset = self._build_current_preset()
        if preset.needs_opencv and not CV2_AVAILABLE:
            messagebox.showerror("缺依赖", "此方案需要：\npip install opencv-python numpy")
            return
        if not preset.needs_opencv and not self.ffmpeg_processor.is_available():
            messagebox.showerror("错误", "未找到 FFmpeg！")
            return
        if not preset.needs_opencv and not preset.build_vf():
            messagebox.showwarning("提示", "滤镜为空！")
            return

        engine = "Python/OpenCV" if preset.needs_opencv else "FFmpeg"
        info_msg = f"引擎: {engine}\n"
        if len(self.input_files) == 1:
            info_msg += f"输入: {self.input_files[0]}\n输出: {self._get_output_path(self.input_files[0])}\n"
        else:
            info_msg += f"共 {len(self.input_files)} 个文件\n"
        if not messagebox.askyesno("确认", info_msg + "\n开始处理？"):
            return

        self.is_processing = True
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.progress_var.set(0)
        threading.Thread(target=self._process_thread, args=(preset,), daemon=True).start()

    def _process_thread(self, preset):
        ok_count = fail_count = 0
        for i, fp in enumerate(self.input_files):
            if self.ffmpeg_processor.cancelled or self.python_processor.cancelled:
                break
            out = self._get_output_path(fp)
            self._log(f"\n{'='*60}\n[{i+1}/{len(self.input_files)}] {os.path.basename(fp)}\n输出: {out}\n{'='*60}")
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

            if preset.needs_opencv:
                ok = self._process_with_python(fp, out, preset)
            else:
                ok = self.ffmpeg_processor.process_video(fp, out, preset,
                    progress_callback=self._update_progress, log_callback=self._log)

            if ok:
                ok_count += 1
                if os.path.exists(out):
                    self._log(f"输出: {format_filesize(os.path.getsize(out))}")
            else:
                fail_count += 1

        self.root.after(0, self._processing_done, ok_count, fail_count)

    # def _process_with_python(self, input_path, output_path, preset):
        # tmp = output_path + ".tmp_video.mp4"
        # ok = self.python_processor.process_video(input_path, tmp, preset,
            # progress_callback=self._update_progress, log_callback=self._log)
        # if not ok:
            # if os.path.exists(tmp):
                # os.remove(tmp)
            # return False

        # if preset.copy_audio and self.ffmpeg_processor.is_available():
            # self._log("\n[合并音频]...")
            # merged = copy_audio_to_output(self.ffmpeg_processor.ffmpeg_path,
                # input_path, tmp, output_path, log_cb=self._log)
            # if os.path.exists(tmp):
                # os.remove(tmp)
            # if merged:
                # self._log("[完成] 视频+音频")
                # return True
            # self._log("[警告] 音频合并失败")
            # return True
        # else:
            # if os.path.exists(tmp):
                # shutil.move(tmp, output_path)
            # return True
    def _process_with_python(self, input_path, output_path, preset):
        # 临时文件用无损/高质量格式
        tmp = output_path + ".tmp_video.avi"  # AVI容器兼容性好
    
        ok = self.python_processor.process_video(
            input_path, tmp, preset,
            progress_callback=self._update_progress, 
            log_callback=self._log
        )
        if not ok:
            if os.path.exists(tmp):
                os.remove(tmp)
            return False

        # ★ 关键修复：用 FFmpeg 按用户设置重新编码 + 合并音频
        if self.ffmpeg_processor.is_available():
            self._log("\n[重编码] 按用户设置编码...")
            cmd = [
                self.ffmpeg_processor.ffmpeg_path, "-y",
                "-i", tmp,           # Python处理后的视频
                "-i", input_path,    # 原始文件（取音频）
            ]
        
            # ★ 响应用户的编码设置
            if preset.codec == "copy":
                cmd.extend(["-c:v", "copy"])
            else:
                cmd.extend(["-c:v", preset.codec])
                if preset.codec in ("libx264", "libx265"):
                    cmd.extend(["-crf", str(preset.crf)])
                    cmd.extend(["-preset", preset.preset])
        
            # 音频
            if preset.copy_audio:
                cmd.extend(["-c:a", "copy", "-map", "0:v:0", "-map", "1:a:0?"])
            else:
                cmd.extend(["-an", "-map", "0:v:0"])
        
            cmd.extend(["-shortest", output_path])
        
            self._log(f"[命令] {' '.join(cmd)}")
            result = safe_run(cmd, timeout=3600)
        
            if os.path.exists(tmp):
                os.remove(tmp)
        
            if result.returncode == 0:
                self._log("[完成] 编码+音频合并成功")
                return True
            else:
                self._log(f"[失败] {result.stderr}")
                return False
        else:
            # 无FFmpeg，只能用OpenCV的低质量输出
            self._log("[警告] 无FFmpeg，输出质量受限（mp4v编码）")
            if os.path.exists(tmp):
                shutil.move(tmp, output_path)
            return True        

    def _processing_done(self, ok, fail):
        self.is_processing = False
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        total = ok + fail
        if fail == 0:
            self.progress_label.config(text=f"完成 ({ok}/{total})")
            messagebox.showinfo("完成", f"成功 {ok} 个文件")
        else:
            self.progress_label.config(text=f"完成 (成功{ok}/失败{fail})")
            messagebox.showwarning("部分失败", f"成功: {ok}\n失败: {fail}")

    def _cancel_processing(self):
        if self.is_processing:
            self.ffmpeg_processor.cancel()
            self.python_processor.cancel()
            self.progress_label.config(text="取消中...")

    def _generate_preview(self):
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择视频！")
            return
        preset = self._build_current_preset()
        if preset.needs_opencv:
            messagebox.showinfo("提示", "Python模式暂不支持快速预览")
            return
        if not self.ffmpeg_processor.is_available():
            messagebox.showerror("错误", "未找到FFmpeg！")
            return

        preset.preset = "ultrafast"
        fp = self.input_files[0]
        p = Path(fp)
        prev = str(p.parent / f"{p.stem}_preview{p.suffix}")
        self.preview_btn.config(state="disabled")

        def _do():
            ok = self.ffmpeg_processor.generate_preview(fp, prev, preset,
                start_time=self.preview_start_var.get(),
                duration=self.preview_duration_var.get(), log_callback=self._log)
            self.root.after(0, lambda: self._preview_done(ok, prev))

        threading.Thread(target=_do, daemon=True).start()

    def _preview_done(self, ok, path):
        self.preview_btn.config(state="normal")
        if ok and os.path.exists(path):
            if messagebox.askyesno("预览完成", f"打开?\n{path}"):
                self._open_file(path)
        else:
            messagebox.showerror("失败", "预览失败")

    def _open_file(self, path):
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
        t = self.output_dir or (str(Path(self.input_files[0]).parent) if self.input_files else None)
        if t:
            self._open_file(t)

    def _browse_ffmpeg(self):
        ft = [("exe", "*.exe")] if sys.platform == "win32" else [("所有", "*")]
        p = filedialog.askopenfilename(title="选择FFmpeg", filetypes=ft)
        if p:
            self.ffmpeg_processor.ffmpeg_path = p
            self.ffmpeg_path_var.set(p)
            self._check_environment()


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
    DeflickerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()