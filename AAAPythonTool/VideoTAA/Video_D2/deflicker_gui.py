"""
视频去闪烁工具 - Video Deflicker Tool v2.1
基于 FFmpeg + OpenCV 的视频闪烁消除 GUI 工具

v2.1 更新：
- 自动检测原视频编码格式/码率/像素格式
- 高级设置自动匹配原视频参数
- Python方案输出使用高级设置中的编码参数
- 处理面板显示原视频详细编码信息
- 修复 np 未定义、buffer 不足等问题
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
from typing import Optional, List, Callable
from enum import Enum

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ============================================================
#  可选依赖（安全导入）
# ============================================================

CV2_AVAILABLE = False
np = None
cv2 = None
try:
    import numpy as np
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    pass

SCIPY_AVAILABLE = False
_savgol = None
try:
    from scipy.signal import savgol_filter as _savgol

    SCIPY_AVAILABLE = True
except ImportError:
    pass

# ============================================================
#  常量
# ============================================================

APP_TITLE = "视频去闪烁工具 Video Deflicker"
APP_VERSION = "2.1.0"

SUPPORTED_EXTENSIONS = {
    ".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv",
    ".webm", ".m4v", ".mpg", ".mpeg", ".ts", ".vob",
}

# 原始编码 → FFmpeg 编码器映射
CODEC_TO_ENCODER = {
    "h264": "libx264", "avc1": "libx264",
    "hevc": "libx265", "h265": "libx265", "hev1": "libx265",
    "av1": "libsvtav1", "av01": "libsvtav1",
    "vp9": "libvpx-vp9", "vp8": "libvpx",
    "mpeg4": "mpeg4", "mpeg2video": "mpeg2video",
    "prores": "prores_ks",
}

# 编码器 → CRF 默认值
ENCODER_DEFAULT_CRF = {
    "libx264": 18, "libx265": 22, "libsvtav1": 28,
    "libvpx-vp9": 24, "mpeg4": 4,
}

# ============================================================
#  安全子进程
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
        result.stdout = (
            result.stdout.decode("utf-8", errors="replace")
            if isinstance(result.stdout, bytes)
            else result.stdout
        )
        result.stderr = (
            result.stderr.decode("utf-8", errors="replace")
            if isinstance(result.stderr, bytes)
            else result.stderr
        )
        return result
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
#  FFmpeg / FFprobe
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
        result = safe_run(
            [
                ffprobe, "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", filepath,
            ],
            timeout=30,
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except Exception:
        pass
    return {}

# 原始编码 → FFmpeg 编码器
CODEC_ENCODER_MAP = {
    "h264": "libx264", "avc1": "libx264",
    "hevc": "libx265", "h265": "libx265", "hev1": "libx265",
    "av1": "libsvtav1", "av01": "libsvtav1",
    "vp9": "libvpx-vp9", "vp8": "libvpx",
    "mpeg4": "mpeg4", "mpeg2video": "mpeg2video",
    "prores": "prores_ks",
}


def get_source_encoding(filepath: str) -> dict:
    """
    检测原视频的完整编码信息
    返回: codec_name, encoder, width, height, fps, bitrate, pix_fmt, duration
    """
    info = get_video_info(filepath)
    result = {
        "codec_name": "", "encoder": "libx264",
        "width": 0, "height": 0, "fps": 0.0,
        "bitrate": 0, "pix_fmt": "yuv420p",
        "duration": 0.0, "has_audio": False,
    }
    if not info:
        return result

    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            codec = s.get("codec_name", "").lower()
            result["codec_name"] = codec
            result["width"] = int(s.get("width", 0))
            result["height"] = int(s.get("height", 0))
            result["pix_fmt"] = s.get("pix_fmt", "yuv420p")
            result["encoder"] = CODEC_ENCODER_MAP.get(codec, "libx264")
            fps_str = s.get("r_frame_rate", "0/1")
            try:
                if "/" in fps_str:
                    n, d = fps_str.split("/")
                    result["fps"] = int(n) / max(int(d), 1)
                else:
                    result["fps"] = float(fps_str)
            except (ValueError, ZeroDivisionError):
                pass
            try:
                result["bitrate"] = int(s.get("bit_rate", 0))
            except (ValueError, TypeError):
                pass
        elif s.get("codec_type") == "audio":
            result["has_audio"] = True

    fmt = info.get("format", {})
    try:
        result["duration"] = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        pass
    # 流级别没码率时用容器级别
    if result["bitrate"] == 0:
        try:
            result["bitrate"] = int(fmt.get("bit_rate", 0))
        except (ValueError, TypeError):
            pass

    return result

def parse_source_encoding(filepath: str) -> dict:
    """
    解析源视频的完整编码信息，供自动匹配使用。
    返回字典:
      codec_name, encoder, width, height, fps,
      bitrate, pix_fmt, duration, has_audio, audio_codec
    """
    info = get_video_info(filepath)
    result = {
        "codec_name": "", "encoder": "libx264",
        "width": 0, "height": 0, "fps": 0.0,
        "bitrate": 0, "pix_fmt": "yuv420p",
        "duration": 0.0, "has_audio": False, "audio_codec": "",
        "container": Path(filepath).suffix.lower(),
    }
    if not info:
        return result
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            codec = s.get("codec_name", "").lower()
            result["codec_name"] = codec
            result["width"] = int(s.get("width", 0))
            result["height"] = int(s.get("height", 0))
            result["pix_fmt"] = s.get("pix_fmt", "yuv420p")
            result["encoder"] = CODEC_TO_ENCODER.get(codec, "libx264")
            fps_str = s.get("r_frame_rate", "0/1")
            try:
                if "/" in fps_str:
                    n, d = fps_str.split("/")
                    result["fps"] = int(n) / max(int(d), 1)
                else:
                    result["fps"] = float(fps_str)
            except (ValueError, ZeroDivisionError):
                pass
            try:
                result["bitrate"] = int(s.get("bit_rate", 0))
            except (ValueError, TypeError):
                pass
        elif s.get("codec_type") == "audio":
            result["has_audio"] = True
            result["audio_codec"] = s.get("codec_name", "")
    fmt = info.get("format", {})
    try:
        result["duration"] = float(fmt.get("duration", 0))
    except (ValueError, TypeError):
        pass
    if result["bitrate"] == 0:
        try:
            result["bitrate"] = int(fmt.get("bit_rate", 0))
        except (ValueError, TypeError):
            pass
    return result


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
#  码率 → CRF 智能估算
# ============================================================

def estimate_crf_from_bitrate(codec: str, bitrate_bps: int, width: int, height: int, fps: float) -> int:
    """
    根据原片码率反推合适的CRF值
    原理：像素数×帧率 = 数据密度基准，与原片码率对比得到质量等级
    
    返回: 推荐的CRF值
    """
    if bitrate_bps <= 0 or width <= 0 or height <= 0 or fps <= 0:
        # 信息不足，返回编码器默认值
        defaults = {"libx264": 18, "libx265": 22, "libsvtav1": 28, "libvpx-vp9": 24, "mpeg4": 4}
        return defaults.get(codec, 18)

    pixels = width * height
    # 每像素每帧的比特数 = 码率 / (像素数 × 帧率)
    bpp = bitrate_bps / (pixels * fps)

    #                  bpp 范围        质量等级
    # H.264:  bpp > 0.15  → 极高质量   CRF 14-16
    #         bpp 0.08-0.15 → 高质量    CRF 17-19
    #         bpp 0.04-0.08 → 中高      CRF 20-22
    #         bpp 0.02-0.04 → 中等      CRF 23-25
    #         bpp < 0.02    → 低码率    CRF 26-28

    if codec in ("libx264",):
        if   bpp > 0.15:  return 14
        elif bpp > 0.10:  return 16
        elif bpp > 0.07:  return 18
        elif bpp > 0.04:  return 20
        elif bpp > 0.025: return 22
        elif bpp > 0.015: return 24
        else:              return 26

    elif codec in ("libx265",):
        # H.265 同等质量 CRF 约比 H.264 高 4-6
        if   bpp > 0.12:  return 18
        elif bpp > 0.07:  return 20
        elif bpp > 0.04:  return 22
        elif bpp > 0.025: return 24
        elif bpp > 0.015: return 26
        else:              return 28

    elif codec in ("libsvtav1",):
        # AV1 同等质量 CRF 约比 H.264 高 8-10
        if   bpp > 0.10:  return 22
        elif bpp > 0.06:  return 25
        elif bpp > 0.03:  return 28
        elif bpp > 0.015: return 32
        else:              return 35

    elif codec in ("libvpx-vp9",):
        if   bpp > 0.10:  return 20
        elif bpp > 0.06:  return 24
        elif bpp > 0.03:  return 28
        else:              return 31

    elif codec in ("mpeg4", "mpeg2video"):
        # qscale 模式, 1=最高 31=最低
        if   bpp > 0.15:  return 2
        elif bpp > 0.08:  return 3
        elif bpp > 0.04:  return 4
        elif bpp > 0.02:  return 6
        else:              return 8

    return 18  # fallback

def format_bitrate(bps: int) -> str:
    if bps <= 0:
        return "未知"
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} Mbps"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} Kbps"
    return f"{bps} bps"


# ============================================================
#  滤波方案
# ============================================================


class FilterMode(Enum):
    TMEDIAN = "tmedian"
    TMIX = "tmix"
    DEFLICKER = "deflicker"
    TMEDIAN_PLUS_DEFLICKER = "tmedian+deflicker"
    EMA = "ema"
    CUSTOM = "custom"
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
    tmedian_radius: int = 1
    tmix_frames: int = 3
    tmix_weights: str = "1 2 1"
    deflicker_mode: str = "am"
    deflicker_size: int = 5
    ema_alpha: float = 0.3
    extra_filters: str = ""
    custom_vf: str = ""
    flicker_threshold: float = 5.0
    motion_threshold: float = 25.0
    temporal_strength: float = 0.7
    temporal_window: int = 3
    spatial_blur: int = 5
    flow_quality: str = "medium"
    freq_cutoff: float = 0.3
    luma_smoothing: int = 11
    sharpen_amount: float = 0.0
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
            filters.append(
                f"tmix=frames={self.tmix_frames}:weights='{self.tmix_weights}'"
            )
        elif self.mode == FilterMode.DEFLICKER:
            filters.append(
                f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}"
            )
        elif self.mode == FilterMode.TMEDIAN_PLUS_DEFLICKER:
            filters.append(f"tmedian=radius={self.tmedian_radius}")
            filters.append(
                f"deflicker=mode={self.deflicker_mode}:size={self.deflicker_size}"
            )
        elif self.mode == FilterMode.EMA:
            n = 5
            a = self.ema_alpha
            w = [f"{a * ((1 - a) ** i):.3f}" for i in range(n)]
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
        deflicker_mode="am",
        deflicker_size=5,
    ),
    FilterPreset(
        name="[FFmpeg] 组合 - 中值+亮度补偿",
        mode=FilterMode.TMEDIAN_PLUS_DEFLICKER,
        description="先中值去像素跳变，再全局亮度补偿\n最全面的FFmpeg方案",
        tmedian_radius=1,
        deflicker_mode="am",
        deflicker_size=5,
    ),
    FilterPreset(
        name="[FFmpeg] 时域加权平均 - TMix",
        mode=FilterMode.TMIX,
        description="帧间加权平均，中心帧权重高\n运动场景会产生拖影",
        tmix_frames=3,
        tmix_weights="1 2 1",
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
        flicker_threshold=5.0,
        motion_threshold=25.0,
        temporal_strength=0.7,
        temporal_window=3,
        spatial_blur=5,
    ),
    FilterPreset(
        name="[Python] 光流引导去闪",
        mode=FilterMode.OPTICAL_FLOW,
        description="光流追踪→对齐→中值滤波\n质量高但速度慢\n需要: pip install opencv-python numpy",
        temporal_window=5,
        flow_quality="medium",
    ),
    FilterPreset(
        name="[Python] 频域时域低通",
        mode=FilterMode.FREQUENCY_LOWPASS,
        description="FFT低通滤波消除时域高频波动\n适合周期性闪烁",
        freq_cutoff=0.3,
    ),
    FilterPreset(
        name="[Python] 全局亮度补偿(Python版)",
        mode=FilterMode.GLOBAL_LUMA_PYTHON,
        description="Python实现全局亮度补偿\n完全不影响空间细节",
        luma_smoothing=11,
    ),
    FilterPreset(
        name="[FFmpeg] 自定义滤镜",
        mode=FilterMode.CUSTOM,
        description="手动输入FFmpeg -vf滤镜字符串",
        custom_vf="tmedian=radius=1",
    ),
]


# ============================================================
#  Python/OpenCV 处理引擎
# ============================================================


class PythonProcessor:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def process_video(
        self, input_path, output_path, preset,
        progress_callback=None, log_callback=None,
    ) -> bool:
        self.cancelled = False
        if not CV2_AVAILABLE:
            if log_callback:
                log_callback("[错误] 需要: pip install opencv-python numpy")
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
                log_callback(f"[错误] 未知模式: {preset.mode}")
            return False
        try:
            return handler(
                input_path, output_path, preset,
                progress_callback, log_callback,
            )
        except Exception as e:
            if log_callback:
                log_callback(f"[异常] {e}")
                import traceback
                log_callback(traceback.format_exc())
            return False

    @staticmethod
    def _open_video(path):
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开: {path}")
        fps = cap.get(cv2.CAP_PROP_FPS)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return cap, fps, w, h, total

    @staticmethod
    def _create_writer(path, fps, w, h):
        return cv2.VideoWriter(
            path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h)
        )

    def _read_all(self, cap, total, log_cb=None, prog_cb=None):
        frames = []
        idx = 0
        while True:
            if self.cancelled:
                return None
            ret, f = cap.read()
            if not ret:
                break
            frames.append(f)
            idx += 1
            if prog_cb and total > 0 and idx % 30 == 0:
                prog_cb(idx / total * 30, idx, total)
        if log_cb:
            log_cb(f"  已读取 {len(frames)} 帧")
        return frames

    @staticmethod
    def _sharpen(frame, amount):
        if amount <= 0:
            return frame
        blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=1.0)
        return np.clip(
            frame.astype(np.float64) * (1 + amount)
            - blurred.astype(np.float64) * amount,
            0, 255,
        ).astype(np.uint8)

    # --- 运动自适应 ---
    def _motion_adaptive(self, inp, out, preset, prog_cb, log_cb):
        if log_cb:
            log_cb(
                f"[运动自适应] 闪烁={preset.flicker_threshold} "
                f"运动={preset.motion_threshold} "
                f"强度={preset.temporal_strength} 窗口={preset.temporal_window}"
            )
        cap, fps, w, h, total = self._open_video(inp)
        writer = self._create_writer(out, fps, w, h)
        half = preset.temporal_window // 2
        buf = []
        for _ in range(preset.temporal_window):
            ret, f = cap.read()
            if not ret:
                break
            buf.append(f.astype(np.float64))
        if not buf:
            if log_cb:
                log_cb("[错误] 无法读取帧")
            cap.release()
            writer.release()
            return False
        idx = 0
        while buf:
            if self.cancelled:
                cap.release()
                writer.release()
                return False
            center = min(half, len(buf) - 1)
            curr = buf[center]
            if len(buf) <= 1:
                out_f = np.clip(curr, 0, 255).astype(np.uint8)
                if preset.sharpen_amount > 0:
                    out_f = self._sharpen(out_f, preset.sharpen_amount)
                writer.write(out_f)
                idx += 1
                ret, f = cap.read()
                if not ret:
                    break
                buf = [f.astype(np.float64)]
                continue
            diffs = [
                np.abs(buf[i] - curr)
                for i in range(len(buf))
                if i != center
            ]
            max_diff = np.max(np.stack(diffs, axis=0), axis=0)
            motion_w = np.clip(
                (max_diff - preset.flicker_threshold)
                / max(
                    preset.motion_threshold - preset.flicker_threshold,
                    1e-6,
                ),
                0, 1,
            )
            if preset.spatial_blur > 1:
                k = preset.spatial_blur | 1
                for c in range(motion_w.shape[2]):
                    motion_w[:, :, c] = cv2.GaussianBlur(
                        motion_w[:, :, c], (k, k), 0
                    )
            stack = np.stack(buf, axis=0)
            filtered = (
                preset.temporal_strength * np.median(stack, axis=0)
                + (1 - preset.temporal_strength) * curr
            )
            result = motion_w * curr + (1 - motion_w) * filtered
            out_f = np.clip(result, 0, 255).astype(np.uint8)
            if preset.sharpen_amount > 0:
                out_f = self._sharpen(out_f, preset.sharpen_amount)
            writer.write(out_f)
            idx += 1
            if prog_cb and total > 0 and idx % 10 == 0:
                prog_cb(idx / total * 100, idx, total)
            ret, f = cap.read()
            if not ret:
                buf.pop(0)
            else:
                buf.append(f.astype(np.float64))
                if len(buf) > preset.temporal_window:
                    buf.pop(0)
        cap.release()
        writer.release()
        if prog_cb:
            prog_cb(100, idx, total)
        if log_cb:
            log_cb(f"[运动自适应] 完成 {idx} 帧")
        return True

    # --- 光流 ---
    def _optical_flow(self, inp, out, preset, prog_cb, log_cb):
        if log_cb:
            log_cb("[光流引导] 开始...")
        cap, fps, w, h, total = self._open_video(inp)
        frames = self._read_all(cap, total, log_cb, prog_cb)
        cap.release()
        if not frames:
            return False
        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        fp_map = {
            "fast": dict(
                pyr_scale=0.5, levels=1, winsize=5,
                iterations=1, poly_n=5, poly_sigma=1.1, flags=0,
            ),
            "medium": dict(
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
            ),
            "high": dict(
                pyr_scale=0.5, levels=5, winsize=21,
                iterations=5, poly_n=7, poly_sigma=1.5, flags=0,
            ),
        }
        fp = fp_map.get(preset.flow_quality, fp_map["medium"])
        gy, gx = np.mgrid[0:h, 0:w].astype(np.float32)
        half = preset.temporal_window // 2
        writer = self._create_writer(out, fps, w, h)
        for i in range(len(frames)):
            if self.cancelled:
                writer.release()
                return False
            aligned = []
            for j in range(
                max(0, i - half), min(len(frames), i + half + 1)
            ):
                if j == i:
                    aligned.append(frames[i].astype(np.float64))
                else:
                    flow = cv2.calcOpticalFlowFarneback(
                        grays[j], grays[i], None, **fp
                    )
                    warped = cv2.remap(
                        frames[j],
                        gx + flow[:, :, 0],
                        gy + flow[:, :, 1],
                        cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REFLECT,
                    )
                    aligned.append(warped.astype(np.float64))
            out_f = np.clip(
                np.median(np.stack(aligned), axis=0), 0, 255
            ).astype(np.uint8)
            if preset.sharpen_amount > 0:
                out_f = self._sharpen(out_f, preset.sharpen_amount)
            writer.write(out_f)
            if prog_cb and i % 5 == 0:
                prog_cb(30 + i / len(frames) * 70, i, len(frames))
        writer.release()
        if prog_cb:
            prog_cb(100, len(frames), len(frames))
        if log_cb:
            log_cb(f"[光流] 完成 {len(frames)} 帧")
        return True

    # --- 频域低通 ---
    def _frequency_lowpass(self, inp, out, preset, prog_cb, log_cb):
        if log_cb:
            log_cb(f"[频域低通] 截止={preset.freq_cutoff}")
        cap, fps, w, h, total = self._open_video(inp)
        frames = self._read_all(cap, total, log_cb, prog_cb)
        cap.release()
        if not frames:
            return False
        arr = np.stack(frames).astype(np.float64)
        T = arr.shape[0]
        freq = np.fft.rfft(arr, axis=0)
        n = freq.shape[0]
        cutoff = int(n * preset.freq_cutoff)
        filt = np.ones(n)
        if cutoff < n:
            tr = n - cutoff
            filt[cutoff:] = 0.5 * (
                1 + np.cos(np.pi * np.arange(tr) / max(tr, 1))
            )
        filt[0] = 1.0
        result = np.clip(
            np.fft.irfft(freq * filt[:, None, None, None], n=T, axis=0),
            0, 255,
        ).astype(np.uint8)
        writer = self._create_writer(out, fps, w, h)
        for i in range(T):
            if self.cancelled:
                writer.release()
                return False
            f = result[i]
            if preset.sharpen_amount > 0:
                f = self._sharpen(f, preset.sharpen_amount)
            writer.write(f)
            if prog_cb and i % 30 == 0:
                prog_cb(70 + i / T * 30, i, T)
        writer.release()
        if prog_cb:
            prog_cb(100, T, T)
        if log_cb:
            log_cb("[频域低通] 完成")
        return True

    # --- 全局亮度 ---
    def _global_luma(self, inp, out, preset, prog_cb, log_cb):
        if log_cb:
            log_cb(f"[亮度补偿] 窗口={preset.luma_smoothing}")
        cap, fps, w, h, total = self._open_video(inp)
        frames = self._read_all(cap, total, log_cb, prog_cb)
        cap.release()
        if not frames:
            return False
        lumas = np.array(
            [np.mean(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)) for f in frames]
        )
        win = min(preset.luma_smoothing, len(lumas))
        if win % 2 == 0:
            win -= 1
        win = max(win, 3)
        if SCIPY_AVAILABLE and _savgol is not None:
            smoothed = _savgol(lumas, win, min(2, win - 1))
        else:
            smoothed = np.convolve(
                lumas, np.ones(win) / win, mode="same"
            )
        writer = self._create_writer(out, fps, w, h)
        for i, f in enumerate(frames):
            if self.cancelled:
                writer.release()
                return False
            ratio = np.clip(smoothed[i] / max(lumas[i], 1), 0.8, 1.2)
            corrected = np.clip(
                f.astype(np.float64) * ratio, 0, 255
            ).astype(np.uint8)
            if preset.sharpen_amount > 0:
                corrected = self._sharpen(corrected, preset.sharpen_amount)
            writer.write(corrected)
            if prog_cb and i % 30 == 0:
                prog_cb(70 + i / len(frames) * 30, i, len(frames))
        writer.release()
        if prog_cb:
            prog_cb(100, len(frames), len(frames))
        if log_cb:
            log_cb("[亮度补偿] 完成")
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

    def _build_encode_args(self, preset: FilterPreset) -> list:
        """统一编码参数构建"""
        args = []
        if preset.codec == "copy":
            args.extend(["-c:v", "copy"])
        else:
            args.extend(["-c:v", preset.codec])
            if preset.codec in ("libx264", "libx265"):
                args.extend([
                    "-crf", str(preset.crf),
                    "-preset", preset.preset,
                ])
            elif preset.codec == "libsvtav1":
                args.extend(["-crf", str(preset.crf)])
            elif preset.codec == "libvpx-vp9":
                args.extend(["-crf", str(preset.crf), "-b:v", "0"])
            elif preset.codec in ("mpeg4", "mpeg2video"):
                args.extend(["-q:v", str(preset.crf)])
        if preset.copy_audio:
            args.extend(["-c:a", "copy"])
        else:
            args.extend(["-an"])
        return args

    def process_video(
        self, input_path, output_path, preset,
        progress_callback=None, log_callback=None,
    ) -> bool:
        self.cancelled = False
        if not self.ffmpeg_path:
            if log_callback:
                log_callback("[错误] 未找到 FFmpeg！")
            return False
        vf = preset.build_vf()
        if not vf:
            if log_callback:
                log_callback("[错误] 滤镜为空！")
            return False
        total_duration = 0.0
        info = get_video_info(input_path)
        if info and "format" in info:
            try:
                total_duration = float(info["format"].get("duration", 0))
            except (ValueError, TypeError):
                pass
        cmd = [self.ffmpeg_path, "-y", "-i", input_path, "-vf", vf]
        cmd.extend(self._build_encode_args(preset))
        cmd.append(output_path)
        if log_callback:
            log_callback(f"[编码] {preset.codec} CRF={preset.crf} preset={preset.preset}")
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
                    cur = (
                        int(m.group(1)) * 3600
                        + int(m.group(2)) * 60
                        + float(m.group(3))
                    )
                    progress_callback(
                        min(cur / total_duration * 100, 99.9),
                        cur, total_duration,
                    )
            self.process.wait()
            if self.process.returncode == 0:
                if progress_callback:
                    progress_callback(100, total_duration, total_duration)
                if log_callback:
                    log_callback("\n[完成]")
                return True
            else:
                if log_callback:
                    log_callback(
                        f"\n[失败] 返回码: {self.process.returncode}"
                    )
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

    def reencode_with_audio(
        self, original_video, processed_video, output_path, preset,
        log_callback=None,
    ) -> bool:
        """
        将 Python 处理后的视频按高级设置重新编码，并合并原始音频。
        这样 Python 方案也能使用用户选择的编码器/CRF/preset。
        """
        if not self.ffmpeg_path:
            if log_callback:
                log_callback("[警告] FFmpeg不可用，无法重编码")
            return False

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", processed_video,
            "-i", original_video,
            "-map", "0:v:0",
            "-map", "1:a:0?",
        ]

        # 编码参数（不用 copy，要重新编码）
        if preset.codec == "copy":
            cmd.extend(["-c:v", "libx264", "-crf", "18", "-preset", "medium"])
        else:
            cmd.extend(["-c:v", preset.codec])
            if preset.codec in ("libx264", "libx265"):
                cmd.extend([
                    "-crf", str(preset.crf),
                    "-preset", preset.preset,
                ])
            elif preset.codec == "libsvtav1":
                cmd.extend(["-crf", str(preset.crf)])
            elif preset.codec == "libvpx-vp9":
                cmd.extend(["-crf", str(preset.crf), "-b:v", "0"])
            elif preset.codec in ("mpeg4", "mpeg2video"):
                cmd.extend(["-q:v", str(preset.crf)])

        if preset.copy_audio:
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-an"])

        cmd.extend(["-shortest", output_path])

        if log_callback:
            log_callback(f"[重编码] {preset.codec} CRF={preset.crf} preset={preset.preset}")
            log_callback(f"[命令] {' '.join(cmd)}")

        result = safe_run(cmd, timeout=600)
        if result.returncode == 0:
            if log_callback:
                log_callback("[重编码+音频合并] 完成")
            return True
        else:
            if log_callback:
                log_callback(f"[重编码失败] {result.stderr[-500:]}")
            return False

    def generate_preview(
        self, input_path, output_path, preset,
        start_time=0, duration=3, log_callback=None,
    ) -> bool:
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
            "-vf", vf,
        ]
        cmd.extend(self._build_encode_args(preset))
        cmd.append(output_path)
        if log_callback:
            log_callback(f"[预览] {' '.join(cmd)}")
        result = safe_run(cmd, timeout=120)
        if result.returncode != 0 and log_callback:
            log_callback(f"[预览错误] {result.stderr}")
        return result.returncode == 0


# ============================================================
#  GUI
# ============================================================


class DeflickerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1020x860")
        self.root.minsize(880, 720)

        self.ffmpeg_processor = FFmpegProcessor()
        self.python_processor = PythonProcessor()
        self.input_files: List[str] = []
        self.output_dir: str = ""
        self.is_processing = False
        self.presets = list(DEFAULT_PRESETS)
        self.source_info: dict = {}

        self._create_variables()
        self._setup_styles()
        self._build_ui()
        self._on_preset_changed()
        self.root.after(100, self._check_environment)

    def _create_variables(self):
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar(value="(与输入文件相同目录)")
        self.file_info_var = tk.StringVar(value="请选择输入视频文件")
        self.source_enc_var = tk.StringVar(value="—")
        self.preset_var = tk.StringVar()
        self.vf_preview_var = tk.StringVar()
        # FFmpeg 滤镜
        self.radius_var = tk.IntVar(value=1)
        self.deflicker_size_var = tk.IntVar(value=5)
        self.deflicker_mode_var = tk.StringVar(value="am")
        self.tmix_frames_var = tk.IntVar(value=3)
        self.tmix_weights_var = tk.StringVar(value="1 2 1")
        self.custom_vf_var = tk.StringVar(value="tmedian=radius=1")
        # Python 参数
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
        self.auto_match_var = tk.BooleanVar(value=True)
        self.suffix_var = tk.StringVar(value="_deflickered")
        # 预览
        self.preview_start_var = tk.DoubleVar(value=0)
        self.preview_duration_var = tk.DoubleVar(value=3)
        # FFmpeg 路径
        self.ffmpeg_path_var = tk.StringVar(
            value=self.ffmpeg_processor.ffmpeg_path or "未找到"
        )
        # 进度
        self.progress_var = tk.DoubleVar(value=0)

    def _setup_styles(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Title.TLabel", font=("Microsoft YaHei UI", 14, "bold")
        )
        style.configure(
            "Subtitle.TLabel", font=("Microsoft YaHei UI", 10)
        )
        style.configure("Info.TLabel", font=("Consolas", 9))
        style.configure("Source.TLabel", foreground="#0066CC", font=("Consolas", 9))
        style.configure("Success.TLabel", foreground="green")
        style.configure("Error.TLabel", foreground="red")
        style.configure(
            "Accent.TButton", font=("Microsoft YaHei UI", 10, "bold")
        )

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Frame(main)
        header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(
            side=tk.LEFT
        )
        ttk.Label(
            header, text=f"v{APP_VERSION}", style="Subtitle.TLabel"
        ).pack(side=tk.LEFT, padx=10)
        self.env_label = ttk.Label(header, text="", style="Subtitle.TLabel")
        self.env_label.pack(side=tk.RIGHT)

        nb = ttk.Notebook(main)
        nb.pack(fill=tk.BOTH, expand=True)
        self.tab_main = ttk.Frame(nb, padding=0)
        nb.add(self.tab_main, text="  处理  ")
        self.tab_advanced = ttk.Frame(nb, padding=6)
        nb.add(self.tab_advanced, text="  高级设置  ")
        self.tab_log = ttk.Frame(nb, padding=6)
        nb.add(self.tab_log, text="  日志  ")

        self._build_main_tab()
        self._build_advanced_tab()
        self._build_log_tab()

    # ================================================================
    #  处理页
    # ================================================================
    def _build_main_tab(self):
        tab = self.tab_main
        canvas = tk.Canvas(tab, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, padding=(8, 6))
        self._scroll_wid = canvas.create_window(
            (0, 0), window=scroll_frame, anchor="nw"
        )
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfig(self._scroll_wid, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            elif event.num == 4:
                canvas.yview_scroll(-3, "units")
            elif event.num == 5:
                canvas.yview_scroll(3, "units")

        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel)
        canvas.bind_all("<Button-5>", _wheel)

        c = scroll_frame

        # === 文件 ===
        ff = ttk.LabelFrame(c, text=" 文件选择 ", padding=8)
        ff.pack(fill=tk.X, pady=(0, 6))

        r1 = ttk.Frame(ff)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="输入视频:").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.input_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(r1, text="选择文件", command=self._select_input).pack(
            side=tk.LEFT, padx=2
        )
        ttk.Button(r1, text="批量添加", command=self._select_inputs_batch).pack(
            side=tk.LEFT
        )

        # 文件信息行
        ttk.Label(ff, textvariable=self.file_info_var, style="Info.TLabel").pack(
            fill=tk.X, pady=2
        )

        # ★ 源编码信息行
        src_row = ttk.Frame(ff)
        src_row.pack(fill=tk.X, pady=2)
        ttk.Label(src_row, text="原片编码:").pack(side=tk.LEFT)
        self.source_enc_label = ttk.Label(
            src_row, textvariable=self.source_enc_var, style="Source.TLabel"
        )
        self.source_enc_label.pack(side=tk.LEFT, padx=5)

        r2 = ttk.Frame(ff)
        r2.pack(fill=tk.X, pady=2)
        ttk.Label(r2, text="输出目录:").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.output_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(r2, text="选择目录", command=self._select_output_dir).pack(
            side=tk.LEFT
        )

        # === 方案 ===
        sf = ttk.LabelFrame(c, text=" 滤波方案 ", padding=8)
        sf.pack(fill=tk.X, pady=(0, 6))

        pr = ttk.Frame(sf)
        pr.pack(fill=tk.X, pady=2)
        ttk.Label(pr, text="选择方案:").pack(side=tk.LEFT)
        self.preset_combo = ttk.Combobox(
            pr,
            textvariable=self.preset_var,
            values=[p.name for p in self.presets],
            state="readonly",
            width=45,
        )
        self.preset_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.preset_combo.current(0)
        self.preset_combo.bind("<<ComboboxSelected>>", self._on_preset_changed)

        self.desc_text = tk.Text(
            sf, height=4, wrap=tk.WORD, state="disabled",
            font=("Microsoft YaHei UI", 9), bg="#f5f5f5",
        )
        self.desc_text.pack(fill=tk.X, pady=4)

        vr = ttk.Frame(sf)
        vr.pack(fill=tk.X, pady=2)
        ttk.Label(vr, text="滤镜/模式:").pack(side=tk.LEFT)
        ttk.Entry(
            vr, textvariable=self.vf_preview_var,
            state="readonly", font=("Consolas", 9),
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        # === FFmpeg 参数 ===
        self.ffmpeg_param_frame = ttk.LabelFrame(
            c, text=" FFmpeg 滤镜参数 ", padding=8
        )
        self.ffmpeg_param_frame.pack(fill=tk.X, pady=(0, 6))
        g1 = ttk.Frame(self.ffmpeg_param_frame)
        g1.pack(fill=tk.X)
        g1.columnconfigure(2, weight=1)
        g1.columnconfigure(4, weight=1)

        ttk.Label(g1, text="中值半径:").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(
            g1, from_=1, to=10, textvariable=self.radius_var, width=8,
            command=self._on_param_changed,
        ).grid(row=0, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g1, text="(1=3帧 2=5帧)").grid(row=0, column=2, sticky="w")

        ttk.Label(g1, text="Deflicker窗口:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(
            g1, from_=2, to=129, textvariable=self.deflicker_size_var,
            width=8, command=self._on_param_changed,
        ).grid(row=1, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g1, text="Deflicker模式:").grid(row=1, column=3, sticky="w", padx=5, pady=2)
        dm = ttk.Combobox(
            g1, textvariable=self.deflicker_mode_var,
            values=["am", "gm", "hm", "qm", "cm", "pm", "median"],
            state="readonly", width=8,
        )
        dm.grid(row=1, column=4, sticky="w", padx=5, pady=2)
        dm.bind("<<ComboboxSelected>>", lambda e: self._on_param_changed())

        ttk.Label(g1, text="TMix帧数:").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(
            g1, from_=2, to=20, textvariable=self.tmix_frames_var,
            width=8, command=self._on_param_changed,
        ).grid(row=2, column=1, sticky="w", padx=5, pady=2)
        ttk.Label(g1, text="TMix权重:").grid(row=2, column=3, sticky="w", padx=5, pady=2)
        we = ttk.Entry(g1, textvariable=self.tmix_weights_var, width=15)
        we.grid(row=2, column=4, sticky="w", padx=5, pady=2)
        we.bind("<KeyRelease>", lambda e: self._on_param_changed())

        ttk.Label(g1, text="自定义-vf:").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        ce = ttk.Entry(g1, textvariable=self.custom_vf_var, width=50)
        ce.grid(row=3, column=1, columnspan=4, sticky="we", padx=5, pady=2)
        ce.bind("<KeyRelease>", lambda e: self._on_param_changed())

        # === Python 参数 ===
        self.python_param_frame = ttk.LabelFrame(
            c, text=" Python 处理参数 ", padding=8
        )
        self.python_param_frame.pack(fill=tk.X, pady=(0, 6))
        g2 = ttk.Frame(self.python_param_frame)
        g2.pack(fill=tk.X)
        g2.columnconfigure(2, weight=1)
        g2.columnconfigure(5, weight=1)

        r = 0
        ttk.Label(g2, text="闪烁阈值:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=1, to=50, textvariable=self.flicker_thresh_var, width=8, increment=1.0).grid(row=r, column=1, sticky="w", padx=5)
        ttk.Label(g2, text="<此值=闪烁").grid(row=r, column=2, sticky="w", padx=5)
        ttk.Label(g2, text="运动阈值:").grid(row=r, column=3, sticky="w", padx=5)
        ttk.Spinbox(g2, from_=5, to=100, textvariable=self.motion_thresh_var, width=8, increment=1.0).grid(row=r, column=4, sticky="w", padx=5)
        ttk.Label(g2, text=">此值=运动").grid(row=r, column=5, sticky="w", padx=5)

        r += 1
        ttk.Label(g2, text="时域强度:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.1, to=1.0, textvariable=self.temporal_strength_var, width=8, increment=0.05).grid(row=r, column=1, sticky="w", padx=5)
        ttk.Label(g2, text="时域窗口:").grid(row=r, column=3, sticky="w", padx=5)
        ttk.Spinbox(g2, from_=3, to=11, textvariable=self.temporal_window_var, width=8, increment=2).grid(row=r, column=4, sticky="w", padx=5)

        r += 1
        ttk.Label(g2, text="掩码模糊:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=1, to=15, textvariable=self.spatial_blur_var, width=8, increment=2).grid(row=r, column=1, sticky="w", padx=5)
        ttk.Label(g2, text="光流质量:").grid(row=r, column=3, sticky="w", padx=5)
        ttk.Combobox(g2, textvariable=self.flow_quality_var, values=["fast", "medium", "high"], state="readonly", width=8).grid(row=r, column=4, sticky="w", padx=5)

        r += 1
        ttk.Label(g2, text="频域截止:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.05, to=0.95, textvariable=self.freq_cutoff_var, width=8, increment=0.05).grid(row=r, column=1, sticky="w", padx=5)
        ttk.Label(g2, text="亮度平滑:").grid(row=r, column=3, sticky="w", padx=5)
        ttk.Spinbox(g2, from_=3, to=51, textvariable=self.luma_smoothing_var, width=8, increment=2).grid(row=r, column=4, sticky="w", padx=5)

        r += 1
        ttk.Label(g2, text="输出锐化:").grid(row=r, column=0, sticky="w", padx=5, pady=2)
        ttk.Spinbox(g2, from_=0.0, to=2.0, textvariable=self.sharpen_var, width=8, increment=0.1).grid(row=r, column=1, sticky="w", padx=5)
        ttk.Label(g2, text="0=关 0.3=轻 1.0=强").grid(row=r, column=2, columnspan=2, sticky="w", padx=5)

        # === 按钮 ===
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

    # ================================================================
    #  高级设置页
    # ================================================================
    def _build_advanced_tab(self):
        tab = self.tab_advanced

        # 自动匹配
        auto_frame = ttk.Frame(tab)
        auto_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Checkbutton(
            auto_frame, text="选择文件时自动匹配原视频编码格式",
            variable=self.auto_match_var,
        ).pack(side=tk.LEFT)
        ttk.Label(
            auto_frame,
            text="(取消勾选可手动指定编码参数)",
            style="Info.TLabel",
        ).pack(side=tk.LEFT, padx=10)

        # 编码
        ef = ttk.LabelFrame(tab, text=" 输出编码设置（FFmpeg 和 Python 方案共用） ", padding=8)
        ef.pack(fill=tk.X, pady=(0, 8))
        g = ttk.Frame(ef)
        g.pack(fill=tk.X)

        ttk.Label(g, text="编码器:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.codec_combo = ttk.Combobox(
            g, textvariable=self.codec_var,
            values=[
                "libx264", "libx265", "libsvtav1",
                "libvpx-vp9", "mpeg4", "copy",
            ],
            state="readonly", width=15,
        )
        self.codec_combo.grid(row=0, column=1, sticky="w", padx=5, pady=3)

        ttk.Label(g, text="CRF:").grid(row=0, column=2, sticky="w", padx=5, pady=3)
        self.crf_spin = ttk.Spinbox(
            g, from_=0, to=63, textvariable=self.crf_var, width=8
        )
        self.crf_spin.grid(row=0, column=3, sticky="w", padx=5, pady=3)
        self.crf_hint_label = ttk.Label(g, text="(0=无损 18=高 23=默认)", style="Info.TLabel")
        self.crf_hint_label.grid(row=0, column=4, sticky="w", padx=5)

        ttk.Label(g, text="速度:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.enc_preset_combo = ttk.Combobox(
            g, textvariable=self.enc_preset_var,
            values=[
                "ultrafast", "superfast", "veryfast", "faster", "fast",
                "medium", "slow", "slower", "veryslow",
            ],
            state="readonly", width=15,
        )
        self.enc_preset_combo.grid(row=1, column=1, sticky="w", padx=5, pady=3)
        ttk.Checkbutton(g, text="复制音频", variable=self.copy_audio_var).grid(
            row=1, column=2, columnspan=3, sticky="w", padx=5, pady=3
        )

        # 当前编码计划预览
        plan_frame = ttk.LabelFrame(tab, text=" 当前编码计划 ", padding=8)
        plan_frame.pack(fill=tk.X, pady=(0, 8))
        self.enc_plan_label = ttk.Label(
            plan_frame, text="选择文件后显示", style="Info.TLabel", wraplength=700,
        )
        self.enc_plan_label.pack(fill=tk.X)

        # 输出
        nf = ttk.LabelFrame(tab, text=" 输出设置 ", padding=8)
        nf.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(nf, text="后缀:").pack(side=tk.LEFT)
        ttk.Entry(nf, textvariable=self.suffix_var, width=20).pack(side=tk.LEFT, padx=5)

        # 预览
        prf = ttk.LabelFrame(tab, text=" 预览设置 ", padding=8)
        prf.pack(fill=tk.X, pady=(0, 8))
        pg = ttk.Frame(prf)
        pg.pack(fill=tk.X)
        ttk.Label(pg, text="起始(秒):").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Spinbox(pg, from_=0, to=9999, textvariable=self.preview_start_var, width=10, increment=1.0).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(pg, text="时长(秒):").grid(row=0, column=2, sticky="w", padx=5)
        ttk.Spinbox(pg, from_=1, to=30, textvariable=self.preview_duration_var, width=10, increment=1.0).grid(row=0, column=3, sticky="w", padx=5)

        # FFmpeg
        fff = ttk.LabelFrame(tab, text=" FFmpeg 路径 ", padding=8)
        fff.pack(fill=tk.X, pady=(0, 8))
        fr = ttk.Frame(fff)
        fr.pack(fill=tk.X)
        ttk.Label(fr, text="FFmpeg:").pack(side=tk.LEFT)
        ttk.Entry(fr, textvariable=self.ffmpeg_path_var, state="readonly").pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=5
        )
        ttk.Button(fr, text="浏览", command=self._browse_ffmpeg).pack(side=tk.LEFT)

        envf = ttk.LabelFrame(tab, text=" 环境信息 ", padding=8)
        envf.pack(fill=tk.X, pady=(0, 8))
        self.env_detail_label = ttk.Label(
            envf, text="", style="Info.TLabel", wraplength=700
        )
        self.env_detail_label.pack(fill=tk.X)

    # ---- 日志 ----
    def _build_log_tab(self):
        tab = self.tab_log
        br = ttk.Frame(tab)
        br.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(br, text="清空日志", command=self._clear_log).pack(side=tk.RIGHT)
        self.log_text = scrolledtext.ScrolledText(
            tab, wrap=tk.WORD, font=("Consolas", 9), height=25, state="disabled",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    # ================================================================
    #  环境
    # ================================================================
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
        )
        self.env_detail_label.config(text=detail)

    # ================================================================
    #  事件
    # ================================================================
    def _select_input(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        p = filedialog.askopenfilename(
            title="选择视频", filetypes=[("视频", exts), ("所有", "*.*")]
        )
        if p:
            self.input_files = [p]
            self.input_var.set(p)
            self._on_file_selected()

    def _select_inputs_batch(self):
        exts = " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS)
        ps = filedialog.askopenfilenames(
            title="选择视频(多选)", filetypes=[("视频", exts), ("所有", "*.*")]
        )
        if ps:
            self.input_files = list(ps)
            self.input_var.set(
                ps[0] if len(ps) == 1 else f"已选择 {len(ps)} 个文件"
            )
            self._on_file_selected()

    def _on_file_selected(self):
        """选择文件后：更新信息 + 自动匹配编码"""
        self._update_file_info()
        if self.input_files:
            self.source_info = parse_source_encoding(self.input_files[0])
            self._update_source_display()
            if self.auto_match_var.get():
                self._auto_match_encoding()
            self._update_encoding_plan()

    # def _update_file_info(self):
        # if not self.input_files:
            # self.file_info_var.set("请选择输入视频文件")
            # self.source_enc_var.set("—")
            # return
        # if len(self.input_files) == 1:
            # fp = self.input_files[0]
            # si = parse_source_encoding(fp)
            # parts = []
            # if os.path.exists(fp):
                # parts.append(format_filesize(os.path.getsize(fp)))
            # if si["width"]:
                # parts.append(f"{si['width']}x{si['height']}")
            # if si["codec_name"]:
                # parts.append(f"编码:{si['codec_name']}")
            # if si["fps"] > 0:
                # parts.append(f"{si['fps']:.2f}fps")
            # if si["bitrate"] > 0:
                # parts.append(f"码率:{format_bitrate(si['bitrate'])}")
            # if si["pix_fmt"]:
                # parts.append(f"像素:{si['pix_fmt']}")
            # if si["duration"] > 0:
                # parts.append(f"时长:{format_duration(si['duration'])}")
            # self.file_info_var.set("  |  ".join(parts) if parts else fp)
        # else:
            # total = sum(
                # os.path.getsize(f)
                # for f in self.input_files
                # if os.path.exists(f)
            # )
            # self.file_info_var.set(
                # f"共 {len(self.input_files)} 个文件 | 总大小: {format_filesize(total)}"
            # )
    def _update_file_info(self):
        if not self.input_files:
            self.file_info_var.set("请选择输入视频文件")
            return

        # ---------- 原有的文件信息显示代码保持不变 ----------
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
                        # ★ 新增：显示码率
                        try:
                            br = int(s.get("bit_rate", 0))
                            if br > 0:
                                if br > 1_000_000:
                                    parts.append(f"码率:{br/1_000_000:.1f}Mbps")
                                else:
                                    parts.append(f"码率:{br/1_000:.0f}Kbps")
                        except (ValueError, TypeError):
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

        
    def _update_source_display(self):
        si = self.source_info
        if not si or not si.get("codec_name"):
            self.source_enc_var.set("—")
            return
        txt = f"{si['codec_name']} → 推荐编码器: {si['encoder']}"
        if si["bitrate"] > 0:
            txt += f" | 码率: {format_bitrate(si['bitrate'])}"
        if si["pix_fmt"]:
            txt += f" | 像素: {si['pix_fmt']}"
        if si["has_audio"]:
            txt += f" | 音频: {si['audio_codec']}"
        self.source_enc_var.set(txt)

    # def _auto_match_encoding(self):
        # """根据源视频自动设置编码参数"""
        # si = self.source_info
        # if not si or not si.get("codec_name"):
            # return
        # encoder = si.get("encoder", "libx264")
        # self.codec_var.set(encoder)
        # default_crf = ENCODER_DEFAULT_CRF.get(encoder, 18)
        # self.crf_var.set(default_crf)
        # self._log_quiet(
            # f"[自动匹配] {si['codec_name']} → {encoder} CRF={default_crf}"
        # )
    def _auto_match_encoding(self):
        """根据源视频编码格式和码率自动设置编码参数"""
        si = self.source_info
        if not si or not si.get("codec_name"):
            return

        # ---- 匹配编码器 ----
        encoder = si.get("encoder", "libx264")
        self.codec_var.set(encoder)

        # ---- 根据码率智能估算 CRF ----
        bitrate = si.get("bitrate", 0)
        width   = si.get("width", 0)
        height  = si.get("height", 0)
        fps     = si.get("fps", 0.0)

        crf = estimate_crf_from_bitrate(encoder, bitrate, width, height, fps)
        self.crf_var.set(crf)

        # ---- 日志输出 ----
        bpp_str = ""
        if bitrate > 0 and width > 0 and height > 0 and fps > 0:
            bpp = bitrate / (width * height * fps)
            bpp_str = f"  bpp={bpp:.4f}"

        self._log_quiet(
            f"[自动匹配] {si['codec_name']} → {encoder}"
            f"  码率={format_bitrate(si.get('bitrate', 0))}"
            f"  {width}x{height}@{fps:.1f}fps"
            f"{bpp_str}"
            f"  → CRF={crf}"
        )
    def _update_encoding_plan(self):
        """更新高级设置中的编码计划显示"""
        si = self.source_info
        codec = self.codec_var.get()
        crf = self.crf_var.get()
        preset_speed = self.enc_preset_var.get()
        if si and si.get("codec_name"):
            plan = (
                f"原片: {si['codec_name']} {si['width']}x{si['height']} "
                f"{si['pix_fmt']} {format_bitrate(si['bitrate'])}\n"
                f"输出: 编码器={codec}  CRF={crf}  速度={preset_speed}"
            )
        else:
            plan = f"输出: 编码器={codec}  CRF={crf}  速度={preset_speed}"
        self.enc_plan_label.config(text=plan)

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
        if p.needs_opencv:
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
        if p.needs_opencv:
            self.vf_preview_var.set(f"[Python] {p.mode.value}")
        else:
            self.vf_preview_var.set(p.build_vf())

    def _build_current_preset(self) -> FilterPreset:
        idx = self.preset_combo.current()
        base = self.presets[max(idx, 0)]
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
            flicker_threshold=self.flicker_thresh_var.get(),
            motion_threshold=self.motion_thresh_var.get(),
            temporal_strength=self.temporal_strength_var.get(),
            temporal_window=self.temporal_window_var.get(),
            spatial_blur=self.spatial_blur_var.get(),
            flow_quality=self.flow_quality_var.get(),
            freq_cutoff=self.freq_cutoff_var.get(),
            luma_smoothing=self.luma_smoothing_var.get(),
            sharpen_amount=self.sharpen_var.get(),
            codec=self.codec_var.get(),
            crf=self.crf_var.get(),
            preset=self.enc_preset_var.get(),
            copy_audio=self.copy_audio_var.get(),
        )

    def _get_output_path(self, input_path: str) -> str:
        p = Path(input_path)
        s = self.suffix_var.get() or "_deflickered"
        name = f"{p.stem}{s}{p.suffix}"
        if self.output_dir:
            return str(Path(self.output_dir) / name)
        return str(p.parent / name)

    def _log(self, msg: str):
        def _a():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, _a)

    def _log_quiet(self, msg: str):
        """日志但不弹到前台"""
        self._log(msg)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

    def _update_progress(self, pct, current, total):
        def _u():
            self.progress_var.set(pct)
            self.progress_label.config(
                text=f"{pct:.1f}% | {int(current)}/{int(total)}"
            )
        self.root.after(0, _u)

    # ================================================================
    #  处理
    # ================================================================
    def _start_processing(self):
        if self.is_processing:
            return
        if not self.input_files:
            messagebox.showwarning("提示", "请先选择输入视频！")
            return
        preset = self._build_current_preset()
        if preset.needs_opencv and not CV2_AVAILABLE:
            messagebox.showerror("缺依赖", "需要: pip install opencv-python numpy")
            return
        if not preset.needs_opencv and not self.ffmpeg_processor.is_available():
            messagebox.showerror("错误", "未找到 FFmpeg！")
            return

        engine = "Python/OpenCV" if preset.needs_opencv else "FFmpeg"
        info_msg = f"引擎: {engine}\n"
        info_msg += f"编码: {preset.codec} CRF={preset.crf} preset={preset.preset}\n"
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
        threading.Thread(
            target=self._process_thread, args=(preset,), daemon=True
        ).start()

    def _process_thread(self, preset):
        ok_count = fail_count = 0
        for i, fp in enumerate(self.input_files):
            if (
                self.ffmpeg_processor.cancelled
                or self.python_processor.cancelled
            ):
                break
            out = self._get_output_path(fp)
            self._log(
                f"\n{'=' * 60}\n"
                f"[{i + 1}/{len(self.input_files)}] {os.path.basename(fp)}\n"
                f"输出: {out}\n"
                f"{'=' * 60}"
            )
            os.makedirs(
                os.path.dirname(os.path.abspath(out)), exist_ok=True
            )

            # 获取每个文件的编码信息
            src = parse_source_encoding(fp)
            self._log(
                f"[源] {src['codec_name']} {src['width']}x{src['height']} "
                f"{src['pix_fmt']} {format_bitrate(src['bitrate'])}"
            )
            self._log(
                f"[输出] {preset.codec} CRF={preset.crf} preset={preset.preset}"
            )

            if preset.needs_opencv:
                ok = self._process_with_python(fp, out, preset)
            else:
                ok = self.ffmpeg_processor.process_video(
                    fp, out, preset,
                    progress_callback=self._update_progress,
                    log_callback=self._log,
                )
            if ok:
                ok_count += 1
                if os.path.exists(out):
                    self._log(f"输出: {format_filesize(os.path.getsize(out))}")
            else:
                fail_count += 1
        self.root.after(0, self._processing_done, ok_count, fail_count)

    def _process_with_python(self, input_path, output_path, preset):
        """
        Python 处理流程：
        1. OpenCV 处理 → 临时文件 (mp4v)
        2. FFmpeg 重编码(用户选择的编码器) + 合并音频 → 最终输出
        """
        tmp = output_path + ".tmp_video.mp4"
        ok = self.python_processor.process_video(
            input_path, tmp, preset,
            progress_callback=self._update_progress,
            log_callback=self._log,
        )
        if not ok:
            if os.path.exists(tmp):
                os.remove(tmp)
            return False

        # 用 FFmpeg 重编码 + 合并音频
        if self.ffmpeg_processor.is_available():
            self._log("\n[步骤2] 重编码+合并音频...")
            merged = self.ffmpeg_processor.reencode_with_audio(
                input_path, tmp, output_path, preset,
                log_callback=self._log,
            )
            if os.path.exists(tmp):
                os.remove(tmp)
            if merged:
                return True
            else:
                self._log("[警告] 重编码失败，尝试仅复制流...")
                # 回退：直接复制
                if os.path.exists(tmp):
                    shutil.move(tmp, output_path)
                return True
        else:
            self._log("[警告] FFmpeg 不可用，输出为 mp4v 原始编码")
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
            messagebox.showwarning(
                "部分失败", f"成功: {ok}\n失败: {fail}"
            )

    def _cancel_processing(self):
        if self.is_processing:
            self.ffmpeg_processor.cancel()
            self.python_processor.cancel()

    def _generate_preview(self):
        if not self.input_files:
            messagebox.showwarning("提示", "请选择视频！")
            return
        preset = self._build_current_preset()
        if preset.needs_opencv:
            messagebox.showinfo("提示", "Python模式暂不支持快速预览")
            return
        if not self.ffmpeg_processor.is_available():
            messagebox.showerror("错误", "未找到FFmpeg！")
            return
        fp = self.input_files[0]
        prev = str(
            Path(fp).parent / f"{Path(fp).stem}_preview{Path(fp).suffix}"
        )
        self.preview_btn.config(state="disabled")

        def _do():
            ok = self.ffmpeg_processor.generate_preview(
                fp, prev, preset,
                start_time=self.preview_start_var.get(),
                duration=self.preview_duration_var.get(),
                log_callback=self._log,
            )
            self.root.after(0, lambda: self._preview_done(ok, prev))

        threading.Thread(target=_do, daemon=True).start()

    def _preview_done(self, ok, path):
        self.preview_btn.config(state="normal")
        if ok and os.path.exists(path):
            if messagebox.askyesno("预览完成", f"打开?\n{path}"):
                self._open_file(path)

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
        t = self.output_dir or (
            str(Path(self.input_files[0]).parent) if self.input_files else None
        )
        if t:
            self._open_file(t)

    def _browse_ffmpeg(self):
        ft = (
            [("exe", "*.exe")]
            if sys.platform == "win32"
            else [("所有", "*")]
        )
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