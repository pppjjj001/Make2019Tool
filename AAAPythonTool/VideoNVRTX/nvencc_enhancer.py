#!/usr/bin/env python3
"""
NVEncC Video Enhancement GUI v3.8
基于 RTX 5060 Ti + NVEncC 9.12 实测验证

v3.8 修复:
- 移除 NVVFX 分辨率限制 (NVEncC 内部自动处理)
- 帧率检测: 三级精度 (metadata → 计算 → PTS采样)
- 码率检测: 四级回退 (视频流 → 总-音频 → 文件估算 → 默认)
- 详细信息面板: 显示帧率/码率的检测来源和置信度
"""

import os
import sys
import json
import subprocess
import threading
import re
import time
import tempfile
import shutil
import locale
import statistics
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

APP_VERSION = "3.8"


# ══════════════════════════════════════════════════════════════
#  系统编码 / 工具函数
# ══════════════════════════════════════════════════════════════

def get_system_encoding() -> str:
    if sys.platform == "win32":
        try:
            import ctypes
            cp = ctypes.windll.kernel32.GetConsoleOutputCP()
            if cp:
                return f"cp{cp}"
        except Exception:
            pass
        return locale.getpreferredencoding(False) or "gbk"
    return "utf-8"


def get_creation_flags():
    return subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def normalize_path(path: str) -> str:
    if not path:
        return path
    p = os.path.normpath(path)
    if sys.platform == "win32" and len(p) > 240 and not p.startswith("\\\\?\\"):
        p = "\\\\?\\" + os.path.abspath(p)
    return p


def safe_popen(cmd, **kwargs):
    env = kwargs.pop("env", None)
    if env is None:
        env = os.environ.copy()
    if sys.platform == "win32":
        env["PYTHONIOENCODING"] = "utf-8"
    if kwargs.get("text", False) and "encoding" not in kwargs:
        kwargs["encoding"] = "utf-8"
        kwargs["errors"] = "replace"
    kwargs["env"] = env
    kwargs.setdefault("creationflags", get_creation_flags())
    return subprocess.Popen(cmd, **kwargs)


def format_cmd_for_display(cmd: List[str]) -> str:
    parts = []
    for c in cmd:
        needs_quote = (" " in c or "&" in c or "(" in c or ")" in c
                       or any(ord(ch) > 127 for ch in c))
        parts.append(f'"{c}"' if needs_quote else c)
    return " ".join(parts)


def format_cmd_pretty(cmd: List[str]) -> str:
    lines = []
    i = 0
    while i < len(cmd):
        arg = cmd[i]
        if " " in arg or "&" in arg or "(" in arg or any(ord(ch) > 127 for ch in arg):
            arg = f'"{arg}"'
        if i == 0:
            lines.append(arg)
            i += 1
            continue
        if arg.startswith("-"):
            if i + 1 < len(cmd) and not cmd[i + 1].startswith("-"):
                val = cmd[i + 1]
                if " " in val or "&" in val or "(" in val or any(ord(ch) > 127 for ch in val):
                    val = f'"{val}"'
                lines.append(f"  {arg} {val}")
                i += 2
            else:
                lines.append(f"  {arg}")
                i += 1
        else:
            lines.append(f"  {arg}")
            i += 1
    return " ^\n".join(lines)


# ══════════════════════════════════════════════════════════════
#  视频信息
# ══════════════════════════════════════════════════════════════

@dataclass
class VideoInfo:
    filepath: str = ""
    file_size: int = 0        # 文件大小 (bytes)
    codec_name: str = ""
    width: int = 0
    height: int = 0

    # ── 帧率 (三级精度) ──
    fps: float = 0.0          # 最终采用的帧率
    fps_avg: float = 0.0      # avg_frame_rate (nb_frames/duration)
    fps_r: float = 0.0        # r_frame_rate (codec标称)
    fps_pts: float = 0.0      # PTS实测帧率 (最精确)
    fps_avg_raw: str = ""
    fps_r_raw: str = ""
    fps_source: str = ""      # 帧率来源标注
    is_vfr: bool = False

    # ── 码率 (四级回退) ──
    bitrate: int = 0          # 最终采用的视频码率 (bps)
    bitrate_stream: int = 0   # 视频流记录的码率
    bitrate_total: int = 0    # 容器总码率
    bitrate_calculated: int = 0  # 计算得到的视频码率
    bitrate_source: str = ""  # 码率来源标注

    duration: float = 0.0
    duration_source: str = ""
    pixel_format: str = ""
    color_space: str = ""
    color_transfer: str = ""
    color_primaries: str = ""
    profile: str = ""
    level: str = ""
    audio_codec: str = ""
    audio_bitrate: int = 0
    audio_sample_rate: int = 0
    audio_channels: int = 0
    total_frames: int = 0
    total_frames_source: str = ""
    hdr: bool = False
    bit_depth: int = 8
    start_time: float = 0.0   # 流起始时间偏移


@dataclass
class ProcessingConfig:
    denoise_method: str = "none"
    denoise_strength: str = "medium"
    enable_artifact_reduction: bool = False
    artifact_reduction_mode: int = 0
    enable_super_resolution: bool = False
    super_resolution_scale: int = 2
    super_resolution_algo: str = "spline64"
    enable_decimate: bool = False
    decimate_cycle: int = 5
    decimate_drop: int = 1
    decimate_thredup: float = 1.1
    decimate_thresc: float = 15.0
    interp_method: str = "none"
    fruc_mode: str = "double"
    fruc_target_fps: float = 60.0
    rife_multiplier: float = 2.0
    rife_model: str = "rife-v4.6"
    rife_uhd: bool = False
    rife_gpu: int = 0
    keep_original_codec: bool = True
    target_bitrate: int = 0
    cqp_value: int = 0
    preset: str = "quality"


# ══════════════════════════════════════════════════════════════
#  工具路径
# ══════════════════════════════════════════════════════════════

class ToolPaths:
    def __init__(self):
        self.nvencc_path = "NVEncC64"
        self.ffprobe_path = "ffprobe"
        self.ffmpeg_path = "ffmpeg"
        self.rife_path = "rife-ncnn-vulkan"

    def validate(self) -> Dict[str, bool]:
        results = {}
        for name, path, args in [
            ("NVEncC", self.nvencc_path, ["--version"]),
            ("FFprobe", self.ffprobe_path, ["-version"]),
            ("FFmpeg", self.ffmpeg_path, ["-version"]),
        ]:
            try:
                r = subprocess.run(
                    [normalize_path(path)] + args,
                    capture_output=True, timeout=10,
                    creationflags=get_creation_flags())
                results[name] = r.returncode in (0, 1)
            except Exception:
                results[name] = False

        # ★ RIFE 单独处理：更宽松的检测
        results["RIFE"] = self._check_rife()
        return results

    def _check_rife(self) -> bool:
        """
        RIFE 检测需要特殊处理：
        1. 不同版本的 -h 返回码不同（可能是 0, 1, -1, 255）
        2. 有些版本没有 -h，直接运行无参数会输出 usage
        3. 关键是能找到并执行，不是返回码
        """
        rife = normalize_path(self.rife_path)

        # 方法1：尝试 -h
        for args in [["-h"], ["--help"], []]:
            try:
                r = subprocess.run(
                    [rife] + args,
                    capture_output=True, timeout=10,
                    creationflags=get_creation_flags(),
                    text=True, encoding="utf-8", errors="replace")
                # ★ 不检查返回码，只要能执行且输出包含 rife 相关内容
                output = (r.stdout + r.stderr).lower()
                if any(kw in output for kw in ["rife", "usage", "input", "output", "model"]):
                    return True
                # 即使输出不匹配，能执行就算找到了
                if r.returncode is not None:
                    return True
            except FileNotFoundError:
                continue  # 文件不存在，试下一个
            except subprocess.TimeoutExpired:
                return True  # 超时说明至少能启动
            except OSError:
                continue
            except Exception:
                continue

        # 方法2：用 where/which 查找
        try:
            cmd = ["where"] if sys.platform == "win32" else ["which"]
            r = subprocess.run(
                cmd + [self.rife_path],
                capture_output=True, timeout=5,
                creationflags=get_creation_flags(),
                text=True, encoding="utf-8", errors="replace")
            if r.returncode == 0 and r.stdout.strip():
                return True
        except Exception:
            pass

        # 方法3：直接检查文件是否存在
        for ext in ["", ".exe"]:
            p = self.rife_path + ext
            if os.path.isfile(p):
                return True
            # 也检查 normalize 后的路径
            np = normalize_path(p)
            if os.path.isfile(np):
                return True

        return False


# ══════════════════════════════════════════════════════════════
#  ★ 精确视频探测 (核心修复)
# ══════════════════════════════════════════════════════════════

def _parse_frac(s: str) -> float:
    """解析分数字符串 '30000/1001' → 29.970"""
    if not s or s == "N/A" or s == "0/0":
        return 0.0
    try:
        if "/" in s:
            num, den = s.split("/")
            den = int(den)
            return round(int(num) / den, 6) if den else 0.0
        return round(float(s), 6)
    except (ValueError, ZeroDivisionError):
        return 0.0


def _pts_sample_fps(ffprobe_path: str, filepath: str,
                     sample_sec: float = 5.0) -> dict:
    """
    ★ 通过读取实际帧的 PTS 时间戳来测量真实帧率
    这是最精确的方法, 不依赖 metadata

    原理:
      读取前 N 秒的每一帧的 PTS → 算帧间隔 → 求中位数 → 1/中位数 = fps

    为什么 nb_frames/duration 不精确:
      1. duration 可能包含 start_time 偏移
      2. nb_frames 可能包含 非显示帧(如 SPS/PPS)
      3. VFR 视频的"平均"帧率不代表任何一秒的实际情况
      4. NTSC 29.97 vs 30 的精度问题
    """
    try:
        cmd = [
            normalize_path(ffprobe_path),
            "-v", "quiet",
            "-select_streams", "v:0",
            "-show_entries", "packet=pts_time",
            "-of", "csv=p=0",
            "-read_intervals", f"%+{sample_sec}",
            normalize_path(filepath)
        ]
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=60, creationflags=get_creation_flags())

        if result.returncode != 0:
            return {}

        timestamps = []
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if line and line != "N/A":
                try:
                    timestamps.append(float(line))
                except ValueError:
                    continue

        if len(timestamps) < 10:
            return {}

        # 排序 (PTS 不一定单调递增, 如 B帧)
        timestamps.sort()

        # 计算帧间隔
        deltas = []
        for i in range(1, len(timestamps)):
            d = timestamps[i] - timestamps[i - 1]
            if d > 0.0001:  # 排除重复 PTS (< 0.1ms)
                deltas.append(d)

        if len(deltas) < 5:
            return {}

        # ★ 用中位数而不是平均值 (对异常值更鲁棒)
        median_delta = statistics.median(deltas)
        mean_delta = statistics.mean(deltas)
        stdev_delta = statistics.stdev(deltas) if len(deltas) >= 3 else 0.0

        fps_median = round(1.0 / median_delta, 6) if median_delta > 0 else 0.0
        fps_mean = round(1.0 / mean_delta, 6) if mean_delta > 0 else 0.0

        # VFR 判定: 变异系数 > 5%
        cv = stdev_delta / mean_delta if mean_delta > 0 else 0
        is_vfr = cv > 0.05

        return {
            "fps_median": fps_median,
            "fps_mean": fps_mean,
            "is_vfr": is_vfr,
            "cv": round(cv, 4),          # 变异系数
            "sampled_frames": len(timestamps),
            "sampled_deltas": len(deltas),
            "median_delta_ms": round(median_delta * 1000, 3),
            "mean_delta_ms": round(mean_delta * 1000, 3),
            "stdev_delta_ms": round(stdev_delta * 1000, 3),
            "min_delta_ms": round(min(deltas) * 1000, 3),
            "max_delta_ms": round(max(deltas) * 1000, 3),
        }
    except Exception as e:
        print(f"PTS sample error: {e}")
        return {}


def probe_video(ffprobe_path: str, filepath: str) -> Optional[VideoInfo]:
    """
    ★ 精确视频探测

    帧率策略 (三级精度):
      1. PTS 实测帧率 (最精确, 但需要解码几秒)
      2. r_frame_rate (codec 标称, 对 CFR 视频准确)
      3. avg_frame_rate (nb_frames/duration, 受多种因素影响)

    为什么优先 PTS > r_frame_rate > avg_frame_rate:
      - avg = nb_frames / duration, 受 start_time、非显示帧、VFR 影响
      - r   = codec 层面的标称帧率, 对 CFR 准确, VFR 时可能是最大帧率
      - PTS = 直接测量每帧时间戳, 最接近播放器看到的真实帧率

    码率策略 (四级回退):
      1. 视频流 bit_rate (最准, 但 MKV 等容器常缺失)
      2. 总码率 - 音频码率 (较准, 但音频码率可能也缺失)
      3. 文件大小 / 时长 - 音频估算 (有一定误差)
      4. 默认值 (兜底)
    """
    try:
        filepath = normalize_path(filepath)
        ffprobe = normalize_path(ffprobe_path)

        cmd = [ffprobe, "-v", "quiet", "-print_format", "json",
               "-show_format", "-show_streams", filepath]

        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=30, creationflags=get_creation_flags())

        if result.returncode != 0:
            sys_enc = get_system_encoding()
            if sys_enc != "utf-8":
                result = subprocess.run(
                    cmd, capture_output=True, text=True,
                    encoding=sys_enc, errors="replace",
                    timeout=30, creationflags=get_creation_flags())
            if result.returncode != 0:
                return None

        data = json.loads(result.stdout)
        info = VideoInfo(filepath=filepath)

        # 文件大小
        try:
            info.file_size = os.path.getsize(filepath)
        except OSError:
            pass

        # 查找视频流和音频流
        vs = as_ = None
        for s in data.get("streams", []):
            if s.get("codec_type") == "video" and vs is None:
                vs = s
            elif s.get("codec_type") == "audio" and as_ is None:
                as_ = s
        if vs is None:
            return None

        info.codec_name = vs.get("codec_name", "unknown")
        info.width = int(vs.get("width", 0))
        info.height = int(vs.get("height", 0))
        info.pixel_format = vs.get("pix_fmt", "")
        info.profile = vs.get("profile", "")
        info.level = str(vs.get("level", ""))
        info.color_space = vs.get("color_space", "")
        info.color_transfer = vs.get("color_transfer", "")
        info.color_primaries = vs.get("color_primaries", "")

        bits = vs.get("bits_per_raw_sample")
        if bits and bits != "N/A":
            info.bit_depth = int(bits)
        elif "10" in info.pixel_format:
            info.bit_depth = 10
        elif "12" in info.pixel_format:
            info.bit_depth = 12

        if info.color_transfer in ("smpte2084", "arib-std-b67"):
            info.hdr = True

        # ── start_time ──
        st = vs.get("start_time")
        if st and st != "N/A":
            try:
                info.start_time = float(st)
            except ValueError:
                pass

        format_info = data.get("format", {})

        # ════════════════════════════════════════
        #  ★ 时长检测
        # ════════════════════════════════════════
        dur = vs.get("duration")
        if dur and dur != "N/A":
            info.duration = float(dur)
            info.duration_source = "video_stream"
        elif format_info.get("duration"):
            info.duration = float(format_info["duration"])
            info.duration_source = "format"
        else:
            info.duration_source = "unknown"

        # ════════════════════════════════════════
        #  ★ 总帧数检测
        # ════════════════════════════════════════
        nb = vs.get("nb_frames")
        if nb and nb != "N/A":
            info.total_frames = int(nb)
            info.total_frames_source = "metadata"
        else:
            info.total_frames_source = "estimated"

        # ════════════════════════════════════════
        #  ★ 帧率检测 (三级精度)
        # ════════════════════════════════════════

        # 级别1: metadata 中的两种帧率
        avg_str = vs.get("avg_frame_rate", "0/1")
        r_str = vs.get("r_frame_rate", "0/1")
        info.fps_avg_raw = avg_str
        info.fps_r_raw = r_str
        info.fps_avg = _parse_frac(avg_str)
        info.fps_r = _parse_frac(r_str)

        # 级别2: PTS 实测
        pts_info = _pts_sample_fps(ffprobe_path, filepath, 3.0)
        if pts_info:
            info.fps_pts = pts_info.get("fps_median", 0.0)

        # ★ 选择最佳帧率
        #
        # 为什么不直接用 avg_frame_rate:
        #   avg = nb_frames / duration
        #   假设 nb_frames=3597, duration=120.12s
        #   avg = 3597/120.12 = 29.945... fps
        #   但实际标称是 29.970 (30000/1001)
        #   差异来自: duration 包含尾部空白、nb_frames 可能不含最后的不完整GOP
        #
        # 为什么不直接用 r_frame_rate:
        #   对 VFR 视频, r_frame_rate 可能是 90000/1 (时间基的倒数)
        #   或者是所有帧率的最小公倍数
        #
        # 最佳策略:
        #   CFR 视频: r_frame_rate 最准 (codec 级别的标称帧率)
        #   VFR 视频: PTS 实测的中位数最准 (直接测量)
        #   兜底: avg_frame_rate

        # 先做 VFR 判定
        if pts_info and pts_info.get("is_vfr"):
            info.is_vfr = True
        elif info.fps_r > 1000:
            # r_frame_rate 异常大, 几乎肯定是 VFR
            info.is_vfr = True
        elif info.fps_avg > 0 and info.fps_r > 0:
            ratio = abs(info.fps_avg - info.fps_r) / max(info.fps_r, 0.001)
            if ratio > 0.05:
                info.is_vfr = True

        # 选择帧率
        if info.is_vfr:
            # VFR: PTS中位数 > avg > 30.0
            if info.fps_pts > 0:
                info.fps = round(info.fps_pts, 3)
                info.fps_source = "PTS中位数(VFR最佳)"
            elif info.fps_avg > 0:
                info.fps = round(info.fps_avg, 3)
                info.fps_source = "avg_frame_rate(VFR回退)"
            else:
                info.fps = 30.0
                info.fps_source = "默认值(无法检测)"
        else:
            # CFR: r_frame_rate 优先
            if info.fps_r > 0 and info.fps_r < 1000:
                info.fps = round(info.fps_r, 3)
                info.fps_source = "r_frame_rate(CFR标称)"
                # 用 PTS 验证
                if info.fps_pts > 0:
                    diff = abs(info.fps - info.fps_pts)
                    if diff > 1.0:
                        info.fps = round(info.fps_pts, 3)
                        info.fps_source = "PTS中位数(r偏差过大)"
            elif info.fps_pts > 0:
                info.fps = round(info.fps_pts, 3)
                info.fps_source = "PTS中位数"
            elif info.fps_avg > 0:
                info.fps = round(info.fps_avg, 3)
                info.fps_source = "avg_frame_rate"
            else:
                info.fps = 30.0
                info.fps_source = "默认值"

        # 补充总帧数 (如果 metadata 缺失)
        if info.total_frames == 0 and info.fps > 0 and info.duration > 0:
            info.total_frames = round(info.fps * info.duration)
            info.total_frames_source = "fps×duration估算"

        # ════════════════════════════════════════
        #  ★ 码率检测 (四级回退)
        # ════════════════════════════════════════

        # 先解析音频码率 (后面要用)
        audio_br = 0
        if as_:
            info.audio_codec = as_.get("codec_name", "")
            abr = as_.get("bit_rate")
            if abr and abr != "N/A":
                info.audio_bitrate = int(abr)
                audio_br = info.audio_bitrate
            sr = as_.get("sample_rate")
            if sr and sr != "N/A":
                info.audio_sample_rate = int(sr)
            ch = as_.get("channels")
            if ch and str(ch) != "N/A":
                info.audio_channels = int(ch)
            # 音频码率估算 (如果缺失)
            if audio_br == 0 and info.audio_codec:
                # 常见默认值
                defaults = {
                    "aac": 128000, "mp3": 128000, "ac3": 384000,
                    "eac3": 640000, "dts": 768000, "flac": 800000,
                    "opus": 128000, "vorbis": 128000,
                }
                audio_br = defaults.get(info.audio_codec, 128000)

        # 容器总码率
        total_br_str = format_info.get("bit_rate")
        if total_br_str and total_br_str != "N/A":
            info.bitrate_total = int(total_br_str)

        # 级别1: 视频流自带码率
        v_br = vs.get("bit_rate")
        if v_br and v_br != "N/A":
            info.bitrate_stream = int(v_br)
            info.bitrate = info.bitrate_stream
            info.bitrate_source = "视频流metadata"

        # 级别2: 总码率 - 音频码率
        if info.bitrate == 0 and info.bitrate_total > 0:
            info.bitrate_calculated = max(0, info.bitrate_total - audio_br)
            info.bitrate = info.bitrate_calculated
            info.bitrate_source = f"总码率{info.bitrate_total//1000}k - 音频{audio_br//1000}k"

        # 级别3: 文件大小 / 时长
        if info.bitrate == 0 and info.file_size > 0 and info.duration > 0:
            total_from_file = int(info.file_size * 8 / info.duration)
            info.bitrate_calculated = max(0, total_from_file - audio_br)
            info.bitrate = info.bitrate_calculated
            size_mb = info.file_size / (1024 * 1024)
            info.bitrate_source = (
                f"文件{size_mb:.1f}MB÷{info.duration:.1f}s"
                f" - 音频{audio_br//1000}k")

        # 级别4: 兜底
        if info.bitrate == 0:
            info.bitrate = 5000000  # 5 Mbps
            info.bitrate_source = "默认值5Mbps"

        return info

    except Exception as e:
        print(f"Probe error: {e}")
        return None


def probe_detailed_fps(ffprobe_path: str, filepath: str,
                        sample_sec: float = 10.0) -> Optional[dict]:
    """深度帧率检测 (更长采样)"""
    return _pts_sample_fps(ffprobe_path, filepath, sample_sec)


# ══════════════════════════════════════════════════════════════
#  NVEncC 命令构建器 (已移除 NVVFX 分辨率限制)
# ══════════════════════════════════════════════════════════════

class NVEncCCommandBuilder:
    KNN_PRESETS = {
        "weak":   "radius=3,strength=0.04,lerp=0.25,th_lerp=0.8",
        "medium": "radius=3,strength=0.08,lerp=0.20,th_lerp=0.8",
        "strong": "radius=3,strength=0.15,lerp=0.15,th_lerp=0.9",
    }
    PMD_PRESETS = {
        "weak":   "apply_count=2,strength=60,threshold=60",
        "medium": "apply_count=2,strength=100,threshold=100",
        "strong": "apply_count=3,strength=150,threshold=120",
    }
    NLMEANS_PRESETS = {
        "weak":   "sigma=3,h=3,patch=5,search=11",
        "medium": "sigma=5,h=5,patch=5,search=11",
        "strong": "sigma=8,h=8,patch=7,search=15",
    }

    def __init__(self, nvencc_path: str):
        self.nvencc_path = nvencc_path

    def build_command(self, input_file, output_file, video_info, config,
                      skip_interp=False):
        cmd = [normalize_path(self.nvencc_path)]
        warnings = []
        cmd.extend(["-i", normalize_path(input_file)])
        encoder = self._select_encoder(video_info, config)
        cmd.extend(["--codec", encoder])
        cmd.extend(self._build_quality(video_info, config, encoder))
        cmd.extend(self._build_color(video_info))
        vpp, vw = self._build_vpp(video_info, config, skip_interp)
        cmd.extend(vpp)
        warnings.extend(vw)
        cmd.extend(["--audio-copy", "-o", normalize_path(output_file)])
        return cmd, warnings

    def _select_encoder(self, info, config):
        m = {"h264": "h264", "avc": "h264", "hevc": "hevc",
             "h265": "hevc", "av1": "av1"}
        if config.keep_original_codec:
            e = m.get(info.codec_name.lower())
            if e:
                return e
        return "hevc"

    def _build_quality(self, info, config, encoder):
        p = []
        pm = {"quality": "quality", "balanced": "default",
              "performance": "performance"}
        p.extend(["--preset", pm.get(config.preset, "quality")])
        if config.cqp_value > 0:
            p.extend(["--cqp", str(config.cqp_value)])
        elif config.target_bitrate > 0:
            p.extend(["--vbr", str(config.target_bitrate)])
        else:
            if info.bitrate > 0:
                br = info.bitrate // 1000
                if config.enable_super_resolution:
                    br = int(br * config.super_resolution_scale * 1.5)
                p.extend(["--vbr", str(max(br, 1000))])
            else:
                dq = {"h264": "20", "hevc": "23", "av1": "25"}
                p.extend(["--cqp", dq.get(encoder, "23")])
        if info.bit_depth >= 10:
            p.extend(["--output-depth", "10"])
        p.extend(["--multipass", "2pass-full", "--lookahead", "32",
                   "--aq", "--aq-temporal"])
        if encoder in ("h264", "hevc"):
            p.extend(["--bframes", "3", "--ref", "4"])
        return p

    def _build_color(self, info):
        p = []
        if info.color_space and info.color_space not in ("unknown", ""):
            p.extend(["--colormatrix", info.color_space])
        if info.color_transfer and info.color_transfer not in ("unknown", ""):
            p.extend(["--transfer", info.color_transfer])
        if info.color_primaries and info.color_primaries not in ("unknown", ""):
            p.extend(["--colorprim", info.color_primaries])
        if info.hdr:
            p.extend(["--max-cll", "copy", "--master-display", "copy"])
        return p

    def _build_vpp(self, info, config, skip_interp=False):
        """
        ★ 已移除 NVVFX 分辨率限制
        NVEncC 内部自动处理 NVVFX 滤镜的分辨率适配
        """
        params = []
        warnings = []

        # 1. 降噪
        if config.denoise_method == "knn":
            p = self.KNN_PRESETS.get(config.denoise_strength,
                                     self.KNN_PRESETS["medium"])
            params.extend(["--vpp-knn", p])
        elif config.denoise_method == "pmd":
            p = self.PMD_PRESETS.get(config.denoise_strength,
                                     self.PMD_PRESETS["medium"])
            params.extend(["--vpp-pmd", p])
        elif config.denoise_method == "nlmeans":
            p = self.NLMEANS_PRESETS.get(config.denoise_strength,
                                         self.NLMEANS_PRESETS["medium"])
            params.extend(["--vpp-nlmeans", p])

        # 2. 去伪影 (★ 不再手动限制分辨率)
        if config.enable_artifact_reduction:
            mode = max(0, min(1, config.artifact_reduction_mode))
            params.extend(["--vpp-nvvfx-artifact-reduction", f"mode={mode}"])

        # 3. 去重复帧
        if config.enable_decimate:
            cycle = max(2, config.decimate_cycle)
            drop = max(1, min(cycle - 1, config.decimate_drop))
            params.extend(["--vpp-decimate",
                           f"cycle={cycle},drop={drop},"
                           f"thredup={config.decimate_thredup},"
                           f"thresc={config.decimate_thresc}"])

        # 4. 超分
        if config.enable_super_resolution:
            nw = info.width * config.super_resolution_scale // 2 * 2
            nh = info.height * config.super_resolution_scale // 2 * 2
            params.extend(["--output-res", f"{nw}x{nh}",
                           "--vpp-resize", config.super_resolution_algo])

        # 5. 补帧 (仅 FRUC, RIFE 在外部)
        if not skip_interp and config.interp_method == "fruc":
            if config.fruc_mode == "double":
                params.extend(["--vpp-fruc", "double"])
            else:
                params.extend(["--vpp-fruc", f"fps={config.fruc_target_fps}"])

        return params, warnings


# ══════════════════════════════════════════════════════════════
#  RIFE 插帧引擎
# ══════════════════════════════════════════════════════════════

class RIFEInterpolator:
    def __init__(self, tools: ToolPaths):
        self.tools = tools

    def is_available(self) -> bool:
        """★ 使用与 ToolPaths 相同的宽松检测"""
        return self.tools._check_rife()

    def interpolate_pipe(self, input_video, output_video, video_info,
                         config, log_cb=None, progress_cb=None,
                         cancel_check=None):
        tmpdir = tempfile.mkdtemp(prefix="rife_work_")
        frames_in = os.path.join(tmpdir, "in")
        frames_out = os.path.join(tmpdir, "out")
        os.makedirs(frames_in, exist_ok=True)
        os.makedirs(frames_out, exist_ok=True)

        try:
            if log_cb:
                log_cb("[RIFE] 阶段1/3: 抽取帧序列...\n")
            extract_cmd = [
                normalize_path(self.tools.ffmpeg_path),
                "-hide_banner",
                "-i", normalize_path(input_video),
                "-vsync", "0", "-pix_fmt", "rgb24",
                os.path.join(frames_in, "frame_%08d.png")
            ]
            if log_cb:
                log_cb(f"[CMD] {format_cmd_for_display(extract_cmd)}\n")

            proc = safe_popen(extract_cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
            for line in iter(proc.stdout.readline, ""):
                if cancel_check and cancel_check():
                    proc.kill(); raise RuntimeError("用户取消")
                line = line.strip()
                if line and log_cb:
                    log_cb(f"  {line}\n")
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"ffmpeg 抽帧失败 (code={proc.returncode})")

            input_frame_count = len([f for f in os.listdir(frames_in) if f.endswith(".png")])
            if log_cb:
                log_cb(f"[RIFE] 抽取了 {input_frame_count} 帧\n")
            if input_frame_count == 0:
                raise RuntimeError("未抽取到帧")
            if progress_cb:
                progress_cb(20.0)

            if log_cb:
                log_cb(f"[RIFE] 阶段2/3: RIFE {config.rife_multiplier}x "
                       f"插帧 (模型: {config.rife_model})...\n")
            target_count = int(input_frame_count * config.rife_multiplier)
            rife_cmd = [
                normalize_path(self.tools.rife_path),
                "-i", frames_in, "-o", frames_out,
                "-m", config.rife_model, "-g", str(config.rife_gpu),
                "-j", "1:2:2", "-v", "-n", str(target_count),
            ]
            if config.rife_uhd:
                rife_cmd.append("-u")
            if log_cb:
                log_cb(f"[CMD] {format_cmd_for_display(rife_cmd)}\n")

            proc = safe_popen(rife_cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
            for line in iter(proc.stdout.readline, ""):
                if cancel_check and cancel_check():
                    proc.kill(); raise RuntimeError("用户取消")
                line = line.strip()
                if not line:
                    continue
                if log_cb:
                    log_cb(f"[RIFE] {line}\n")
                m = re.search(r'(\d+)/(\d+)', line)
                if m and progress_cb:
                    done = int(m.group(1))
                    total = int(m.group(2))
                    progress_cb(min(70, 20 + (done / max(1, total)) * 50))
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"RIFE 失败 (code={proc.returncode})")

            output_frame_count = len([f for f in os.listdir(frames_out) if f.endswith(".png")])
            if log_cb:
                log_cb(f"[RIFE] 插帧完成: {input_frame_count} → {output_frame_count} 帧\n")
            if progress_cb:
                progress_cb(70.0)

            if log_cb:
                log_cb(f"[RIFE] 阶段3/3: 编码...\n")
            new_fps = video_info.fps * config.rife_multiplier

            first_frame = sorted(os.listdir(frames_out))[0]
            if first_frame.startswith("frame_"):
                pattern = os.path.join(frames_out, "frame_%08d.png")
            else:
                pattern = os.path.join(frames_out, "%08d.png")

            encode_cmd = [
                normalize_path(self.tools.ffmpeg_path),
                "-y", "-hide_banner",
                "-framerate", str(new_fps),
                "-i", pattern,
                "-i", normalize_path(input_video),
                "-map", "0:v", "-map", "1:a?",
                "-c:v", "hevc_nvenc", "-preset", "p7", "-cq", "23",
                "-c:a", "copy", "-shortest",
                normalize_path(output_video)
            ]
            if log_cb:
                log_cb(f"[CMD] {format_cmd_for_display(encode_cmd)}\n")

            proc = safe_popen(encode_cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
            for line in iter(proc.stdout.readline, ""):
                if cancel_check and cancel_check():
                    proc.kill(); raise RuntimeError("用户取消")
                line = line.strip()
                if not line:
                    continue
                if log_cb:
                    log_cb(f"  {line}\n")
                m = re.search(r'frame=\s*(\d+)', line)
                if m and progress_cb:
                    done = int(m.group(1))
                    progress_cb(min(98, 70 + (done / max(1, output_frame_count)) * 28))
            proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"编码失败 (code={proc.returncode})")

            if progress_cb:
                progress_cb(100.0)
            if log_cb:
                log_cb(f"[RIFE] ✅ 完成! {video_info.fps}fps → {new_fps}fps\n")
            return True, "RIFE 插帧完成"

        except Exception as e:
            if log_cb:
                log_cb(f"[RIFE] ❌ 错误: {e}\n")
            return False, str(e)
        finally:
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
#  统一处理引擎
# ══════════════════════════════════════════════════════════════

class ProcessingEngine:
    def __init__(self, tools):
        self.tools = tools
        self.builder = NVEncCCommandBuilder(tools.nvencc_path)
        self.rife = RIFEInterpolator(tools)
        self.process = None
        self.is_running = False
        self.is_cancelled = False

    def start_processing(self, input_file, output_file, video_info, config,
                         progress_callback=None, log_callback=None,
                         done_callback=None):
        self.is_running = True
        self.is_cancelled = False
        threading.Thread(
            target=self._run, daemon=True,
            args=(input_file, output_file, video_info, config,
                  progress_callback, log_callback, done_callback)).start()

    def _run(self, input_file, output_file, video_info, config,
             progress_cb, log_cb, done_cb):
        try:
            if config.interp_method == "rife":
                self._run_rife_pipeline(
                    input_file, output_file, video_info, config,
                    progress_cb, log_cb, done_cb)
            else:
                self._run_nvencc(
                    input_file, output_file, video_info, config,
                    progress_cb, log_cb, done_cb)
        except Exception as e:
            if log_cb:
                log_cb(f"[ERROR] {e}\n")
            if done_cb:
                done_cb(False, str(e))
        finally:
            self.is_running = False

    def _run_rife_pipeline(self, input_file, output_file, video_info,
                           config, progress_cb, log_cb, done_cb):
        has_nvencc = any([
            config.denoise_method != "none",
            config.enable_artifact_reduction,
            config.enable_super_resolution,
            config.enable_decimate,
        ])
        temp_path = None

        if has_nvencc:
            if log_cb:
                log_cb("═══ 阶段1: NVEncC 视频处理 ═══\n")
            tmpfile = tempfile.NamedTemporaryFile(
                suffix=".mp4", delete=False, prefix="rife_s1_",
                dir=tempfile.gettempdir())
            tmpfile.close()
            temp_path = tmpfile.name

            try:
                cmd, warns = self.builder.build_command(
                    input_file, temp_path, video_info, config, skip_interp=True)
                if log_cb and warns:
                    for w in warns:
                        log_cb(f"  ⚠ {w}\n")
                if log_cb:
                    log_cb(f"[CMD] {format_cmd_for_display(cmd)}\n\n")

                self.process = safe_popen(
                    cmd, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, bufsize=1)
                for line in iter(self.process.stdout.readline, ""):
                    if self.is_cancelled:
                        self.process.kill(); break
                    line = line.strip()
                    if not line:
                        continue
                    if log_cb:
                        log_cb(line + "\n")
                    m = re.search(r'\[(\d+\.?\d*)%\]', line)
                    if m and progress_cb:
                        progress_cb(float(m.group(1)) * 0.3)
                self.process.wait()
                if self.process.returncode != 0:
                    raise RuntimeError(f"NVEncC 阶段1失败 (code={self.process.returncode})")
                rife_input = temp_path
                rife_info = probe_video(self.tools.ffprobe_path, temp_path) or video_info
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        else:
            rife_input = input_file
            rife_info = video_info

        if self.is_cancelled:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            if done_cb:
                done_cb(False, "用户取消")
            return

        if log_cb:
            log_cb("\n═══ 阶段2: RIFE AI 插帧 ═══\n")

        def rife_progress(pct):
            if progress_cb:
                base = 30 if has_nvencc else 0
                scale = 70 if has_nvencc else 100
                progress_cb(base + pct * scale / 100)

        ok, msg = self.rife.interpolate_pipe(
            rife_input, output_file, rife_info, config,
            log_cb=log_cb, progress_cb=rife_progress,
            cancel_check=lambda: self.is_cancelled)

        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        if done_cb:
            done_cb(ok, msg)

    def _run_nvencc(self, input_file, output_file, video_info, config,
                    progress_cb, log_cb, done_cb):
        try:
            cmd, warnings = self.builder.build_command(
                input_file, output_file, video_info, config)
            if log_cb and warnings:
                for w in warnings:
                    log_cb(f"  ⚠ {w}\n")
                log_cb("\n")
            if log_cb:
                log_cb(f"[CMD] {format_cmd_for_display(cmd)}\n\n[INFO] 开始处理...\n")

            self.process = safe_popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            total = video_info.total_frames or 1
            for line in iter(self.process.stdout.readline, ""):
                if self.is_cancelled:
                    self.process.kill()
                    if log_cb:
                        log_cb("[INFO] 用户取消\n")
                    break
                line = line.strip()
                if not line:
                    continue
                if log_cb:
                    log_cb(line + "\n")
                prog = self._parse_progress(line, total)
                if prog is not None and progress_cb:
                    progress_cb(prog)
            self.process.wait()
            rc = self.process.returncode

            if self.is_cancelled:
                if done_cb:
                    done_cb(False, "用户取消")
            elif rc == 0:
                if log_cb:
                    log_cb(f"\n[INFO] ✅ 完成！\n")
                if done_cb:
                    done_cb(True, "处理完成")
            else:
                if done_cb:
                    done_cb(False, f"NVEncC 错误码: {rc}")
        except Exception as e:
            if log_cb:
                log_cb(f"[ERROR] {e}\n")
            if done_cb:
                done_cb(False, str(e))
        finally:
            self.process = None

    def _parse_progress(self, line, total):
        m = re.search(r'\[(\d+\.?\d*)%\]', line)
        if m:
            return float(m.group(1))
        m = re.search(r'(\d+)\s*frames', line, re.IGNORECASE)
        if m and total > 0:
            return min(100.0, int(m.group(1)) / total * 100)
        return None

    def cancel(self):
        self.is_cancelled = True
        if self.process:
            try:
                self.process.kill()
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════

class VideoEnhancerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"NVEncC Video Enhancer v{APP_VERSION}")
        self.root.geometry("1200x950")
        self.root.minsize(1050, 800)
        self.tools = ToolPaths()
        self.video_info = None
        self.engine = ProcessingEngine(self.tools)
        self._init_vars()
        self._build_ui()
        self._apply_style()
        self.root.after(500, self._validate_tools)

    def _init_vars(self):
        self.var_input = tk.StringVar()
        self.var_output = tk.StringVar()
        self.var_nvencc = tk.StringVar(value="NVEncC64")
        self.var_ffprobe = tk.StringVar(value="ffprobe")
        self.var_ffmpeg = tk.StringVar(value="ffmpeg")
        self.var_rife = tk.StringVar(value="rife-ncnn-vulkan")

        self.var_denoise = tk.StringVar(value="none")
        self.var_denoise_str = tk.StringVar(value="medium")
        self.var_artifact = tk.BooleanVar(value=False)
        self.var_artifact_mode = tk.IntVar(value=0)
        self.var_superres = tk.BooleanVar(value=False)
        self.var_sr_scale = tk.IntVar(value=2)
        self.var_sr_algo = tk.StringVar(value="spline64")
        self.var_decimate = tk.BooleanVar(value=False)
        self.var_dec_cycle = tk.IntVar(value=5)
        self.var_dec_drop = tk.IntVar(value=1)
        self.var_dec_thredup = tk.StringVar(value="1.1")
        self.var_dec_thresc = tk.StringVar(value="15.0")

        self.var_interp = tk.StringVar(value="none")
        self.var_fruc_mode = tk.StringVar(value="double")
        self.var_fruc_fps = tk.StringVar(value="60")
        self.var_rife_mult = tk.StringVar(value="2")
        self.var_rife_model = tk.StringVar(value="rife-v4.6")
        self.var_rife_uhd = tk.BooleanVar(value=False)
        self.var_rife_gpu = tk.IntVar(value=0)

        self.var_keep_codec = tk.BooleanVar(value=True)
        self.var_bitrate = tk.StringVar(value="0")
        self.var_cqp = tk.StringVar(value="0")
        self.var_preset = tk.StringVar(value="quality")

    def _apply_style(self):
        style = ttk.Style()
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except Exception:
            style.theme_use("clam")
        style.configure("Info.TLabel", font=("Consolas", 9))
        style.configure("Status.TLabel", font=("Segoe UI", 9))
        style.configure("Hint.TLabel", font=("Segoe UI", 8), foreground="gray")
        style.configure("Good.TLabel", font=("Segoe UI", 8), foreground="green")
        style.configure("Rife.TLabel", font=("Segoe UI", 8), foreground="#8B5CF6")
        style.configure("VFR.TLabel", font=("Segoe UI", 8), foreground="#E67E22")

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=5)
        main.pack(fill=tk.BOTH, expand=True)
        self._build_file_section(main)

        mid = ttk.Frame(main)
        mid.pack(fill=tk.BOTH, expand=True, pady=5)

        left = ttk.Frame(mid, width=600)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 5))
        left.pack_propagate(False)

        canvas = tk.Canvas(left, highlightthickness=0)
        sb = ttk.Scrollbar(left, orient="vertical", command=canvas.yview)
        self.sf = ttk.Frame(canvas)
        self.sf.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.sf, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        self._build_settings(self.sf)

        right = ttk.Frame(mid)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self._build_log_panel(right)

        self._build_controls(main)

    def _build_file_section(self, parent):
        f = ttk.LabelFrame(parent, text="📁 文件", padding=8)
        f.pack(fill=tk.X, pady=(0, 5))
        for label, var, cmd in [
            ("输入视频:", self.var_input, self._browse_input),
            ("输出视频:", self.var_output, self._browse_output),
        ]:
            r = ttk.Frame(f)
            r.pack(fill=tk.X, pady=2)
            ttk.Label(r, text=label, width=10).pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=var).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ttk.Button(r, text="浏览...", command=cmd, width=8).pack(side=tk.RIGHT)

        info_frame = ttk.Frame(f)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        self.info_label = ttk.Label(info_frame, text="请选择输入视频",
                                     style="Info.TLabel", foreground="gray")
        self.info_label.pack(fill=tk.X)
        self.info_detail = ttk.Label(info_frame, text="", style="Hint.TLabel")
        self.info_detail.pack(fill=tk.X)
        self.vfr_warning = ttk.Label(info_frame, text="", style="VFR.TLabel")
        self.vfr_warning.pack(fill=tk.X)
    def _diagnose_rife(self):
        """详细诊断 RIFE 为什么找不到"""
        self._sync_tools()
        rife_path = self.tools.rife_path
        report = []
        report.append(f"RIFE 路径设置: {rife_path}")
        report.append(f"normalize后: {normalize_path(rife_path)}")
        report.append("")

        # 1. 检查 PATH
        report.append("【PATH 检查】")
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        found_in_path = False
        for d in path_dirs:
            for ext in ["", ".exe"]:
                full = os.path.join(d, rife_path + ext)
                if os.path.isfile(full):
                    report.append(f"  ✅ 找到: {full}")
                    found_in_path = True
        if not found_in_path:
            report.append(f"  ❌ 在 PATH 中未找到 {rife_path}")
            report.append(f"  PATH 共 {len(path_dirs)} 个目录")

        # 2. 检查直接路径
        report.append("")
        report.append("【直接路径检查】")
        for ext in ["", ".exe"]:
            p = rife_path + ext
            report.append(f"  {p}: {'✅ 存在' if os.path.isfile(p) else '❌ 不存在'}")
            np = normalize_path(p)
            if np != p:
                report.append(f"  {np}: {'✅ 存在' if os.path.isfile(np) else '❌ 不存在'}")

        # 3. where 命令
        report.append("")
        report.append("【where 命令】")
        try:
            cmd = ["where"] if sys.platform == "win32" else ["which"]
            r = subprocess.run(
                cmd + [rife_path],
                capture_output=True, timeout=5,
                creationflags=get_creation_flags(),
                text=True, encoding="utf-8", errors="replace")
            report.append(f"  返回码: {r.returncode}")
            report.append(f"  stdout: {r.stdout.strip()}")
            if r.stderr.strip():
                report.append(f"  stderr: {r.stderr.strip()}")
        except Exception as e:
            report.append(f"  异常: {e}")

        # 4. 尝试执行
        report.append("")
        report.append("【执行测试】")
        for args_name, args in [("-h", ["-h"]), ("无参数", [])]:
            try:
                r = subprocess.run(
                    [normalize_path(rife_path)] + args,
                    capture_output=True, timeout=10,
                    creationflags=get_creation_flags(),
                    text=True, encoding="utf-8", errors="replace")
                report.append(f"  {args_name}: 返回码={r.returncode}")
                out = (r.stdout[:200] + r.stderr[:200]).strip()
                if out:
                    report.append(f"    输出: {out[:300]}")
            except FileNotFoundError:
                report.append(f"  {args_name}: ❌ FileNotFoundError (文件不存在)")
            except subprocess.TimeoutExpired:
                report.append(f"  {args_name}: ⚠ 超时 (但说明能启动)")
            except OSError as e:
                report.append(f"  {args_name}: ❌ OSError: {e}")
            except Exception as e:
                report.append(f"  {args_name}: ❌ {type(e).__name__}: {e}")

        # 5. 当前工作目录
        report.append("")
        report.append(f"【工作目录】 {os.getcwd()}")
        report.append(f"【Python】 {sys.executable}")

        messagebox.showinfo("RIFE 诊断报告", "\n".join(report))
    def _build_settings(self, parent):
        # ═══ 工具路径 ═══
        tf = ttk.LabelFrame(parent, text="🔧 工具路径", padding=5)
        tf.pack(fill=tk.X, pady=3, padx=2)
        for label, var, tt in [
            ("NVEncC:", self.var_nvencc, "nvencc"),
            ("FFprobe:", self.var_ffprobe, "ffprobe"),
            ("FFmpeg:", self.var_ffmpeg, "ffmpeg"),
            ("RIFE:", self.var_rife, "rife"),
        ]:
            r = ttk.Frame(tf)
            r.pack(fill=tk.X, pady=1)
            ttk.Label(r, text=label, width=10).pack(side=tk.LEFT)
            ttk.Entry(r, textvariable=var, width=30).pack(
                side=tk.LEFT, fill=tk.X, expand=True, padx=3)
            ttk.Button(r, text="...", width=3,
                       command=lambda t=tt: self._browse_tool(t)).pack(side=tk.RIGHT)
        self.tool_status = ttk.Label(tf, text="", style="Status.TLabel")
        self.tool_status.pack(fill=tk.X, pady=(3, 0))
        diag_btn = ttk.Button(tf, text="🔍 诊断RIFE", command=self._diagnose_rife)
        diag_btn.pack(anchor=tk.W, pady=(2, 0))

        # ═══ 降噪 ═══
        df = ttk.LabelFrame(parent, text="🔇 降噪", padding=5)
        df.pack(fill=tk.X, pady=3, padx=2)
        for val, text in [
            ("none", "不使用"),
            ("knn", "KNN (GPU, 快速)"),
            ("pmd", "PMD (GPU, 平滑)"),
            ("nlmeans", "NLMeans (GPU, 高质量/慢)"),
        ]:
            ttk.Radiobutton(df, text=text, variable=self.var_denoise,
                            value=val, command=self._on_denoise_change
                            ).pack(anchor=tk.W, pady=1)
        sf = ttk.Frame(df)
        sf.pack(fill=tk.X, pady=(3, 0))
        ttk.Label(sf, text="  强度:").pack(side=tk.LEFT)
        self.w_denoise_str = ttk.Combobox(
            sf, textvariable=self.var_denoise_str,
            values=["weak", "medium", "strong"], state="disabled", width=10)
        self.w_denoise_str.pack(side=tk.LEFT, padx=5)

        # ═══ 去伪影 (★ 移除分辨率限制标注) ═══
        af = ttk.LabelFrame(parent, text="✨ AI 去伪影 (NVVFX)", padding=5)
        af.pack(fill=tk.X, pady=3, padx=2)
        ar = ttk.Frame(af)
        ar.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(ar, text="启用", variable=self.var_artifact,
                         command=self._on_artifact_toggle).pack(side=tk.LEFT)
        ttk.Label(ar, text="模式:").pack(side=tk.LEFT, padx=(15, 3))
        self.w_art_mode = ttk.Combobox(
            ar, textvariable=self.var_artifact_mode,
            values=["0", "1"], state="disabled", width=4)
        self.w_art_mode.pack(side=tk.LEFT)
        ttk.Label(ar, text="(0=低 1=高)",
                  style="Hint.TLabel").pack(side=tk.LEFT, padx=5)

        # ═══ 超分 ═══
        srf = ttk.LabelFrame(parent, text="🔍 超分辨率", padding=5)
        srf.pack(fill=tk.X, pady=3, padx=2)
        sr1 = ttk.Frame(srf)
        sr1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(sr1, text="启用", variable=self.var_superres,
                         command=self._on_sr_toggle).pack(side=tk.LEFT)
        sr2 = ttk.Frame(srf)
        sr2.pack(fill=tk.X, pady=2)
        ttk.Label(sr2, text="  倍率:").pack(side=tk.LEFT)
        self.w_sr_scale = ttk.Combobox(
            sr2, textvariable=self.var_sr_scale,
            values=["2", "3", "4"], state="disabled", width=4)
        self.w_sr_scale.pack(side=tk.LEFT, padx=3)
        ttk.Label(sr2, text="算法:").pack(side=tk.LEFT, padx=(10, 3))
        self.w_sr_algo = ttk.Combobox(
            sr2, textvariable=self.var_sr_algo,
            values=["spline64", "lanczos3", "nvvfx-superres", "ngx-vsr"],
            state="disabled", width=16)
        self.w_sr_algo.pack(side=tk.LEFT, padx=3)
        self.sr_output_label = ttk.Label(sr2, text="", foreground="blue")
        self.sr_output_label.pack(side=tk.LEFT, padx=5)

        # ═══ 去重复帧 ═══
        decf = ttk.LabelFrame(parent, text="🎬 去重复帧", padding=5)
        decf.pack(fill=tk.X, pady=3, padx=2)
        dr1 = ttk.Frame(decf)
        dr1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(dr1, text="启用", variable=self.var_decimate,
                         command=self._on_dec_toggle).pack(side=tk.LEFT)
        dr2 = ttk.Frame(decf)
        dr2.pack(fill=tk.X, pady=2)
        ttk.Label(dr2, text="  cycle:").pack(side=tk.LEFT)
        self.w_dec_cycle = ttk.Spinbox(
            dr2, from_=2, to=25, textvariable=self.var_dec_cycle,
            width=4, state="disabled")
        self.w_dec_cycle.pack(side=tk.LEFT, padx=3)
        ttk.Label(dr2, text="drop:").pack(side=tk.LEFT, padx=(8, 2))
        self.w_dec_drop = ttk.Spinbox(
            dr2, from_=1, to=10, textvariable=self.var_dec_drop,
            width=4, state="disabled")
        self.w_dec_drop.pack(side=tk.LEFT, padx=3)

        # ═══ 补帧 ═══
        ff = ttk.LabelFrame(parent,
                            text="🎞️ 补帧 (FRUC光流 / RIFE深度学习)",
                            padding=5)
        ff.pack(fill=tk.X, pady=3, padx=2)
        ttk.Radiobutton(ff, text="不补帧", variable=self.var_interp,
                         value="none", command=self._on_interp_change
                         ).pack(anchor=tk.W, pady=1)
        ttk.Radiobutton(ff, text="FRUC 光流补帧 (NVEncC内置, 快速, 质量一般)",
                         variable=self.var_interp, value="fruc",
                         command=self._on_interp_change).pack(anchor=tk.W, pady=1)
        ttk.Radiobutton(ff, text="🧠 RIFE AI 插帧 (深度学习, 高质量, 较慢)",
                         variable=self.var_interp, value="rife",
                         command=self._on_interp_change).pack(anchor=tk.W, pady=1)

        self.fruc_frame = ttk.LabelFrame(ff, text="FRUC 设置", padding=3)
        self.fruc_frame.pack(fill=tk.X, pady=(5, 2), padx=10)
        fr = ttk.Frame(self.fruc_frame)
        fr.pack(fill=tk.X)
        ttk.Label(fr, text="模式:").pack(side=tk.LEFT)
        self.w_fruc_mode = ttk.Combobox(
            fr, textvariable=self.var_fruc_mode,
            values=["double", "fps"], state="disabled", width=8)
        self.w_fruc_mode.pack(side=tk.LEFT, padx=3)
        ttk.Label(fr, text="目标FPS:").pack(side=tk.LEFT, padx=(10, 3))
        self.w_fruc_fps = ttk.Entry(
            fr, textvariable=self.var_fruc_fps, width=8, state="disabled")
        self.w_fruc_fps.pack(side=tk.LEFT)

        self.rife_frame = ttk.LabelFrame(ff, text="🧠 RIFE 设置", padding=3)
        self.rife_frame.pack(fill=tk.X, pady=(2, 2), padx=10)
        rr1 = ttk.Frame(self.rife_frame)
        rr1.pack(fill=tk.X, pady=2)
        ttk.Label(rr1, text="倍率:").pack(side=tk.LEFT)
        self.w_rife_mult = ttk.Entry(
            rr1, textvariable=self.var_rife_mult, width=6, state="disabled")
        self.w_rife_mult.pack(side=tk.LEFT, padx=3)
        ttk.Label(rr1, text="(1.0~8.0)", style="Hint.TLabel").pack(side=tk.LEFT)
        self.w_rife_mult.pack(side=tk.LEFT, padx=3)
        ttk.Label(rr1, text="模型:").pack(side=tk.LEFT, padx=(10, 3))
        self.w_rife_model = ttk.Combobox(
            rr1, textvariable=self.var_rife_model,
            values=["rife-v4.6", "rife-v4.7", "rife-v4.22-lite",
                    "rife-v4", "rife-v4.26"],
            state="disabled", width=18)
        self.w_rife_model.pack(side=tk.LEFT, padx=3)

        rr2 = ttk.Frame(self.rife_frame)
        rr2.pack(fill=tk.X, pady=2)
        self.w_rife_uhd = ttk.Checkbutton(
            rr2, text="UHD模式(>1080p)", variable=self.var_rife_uhd,
            state="disabled")
        self.w_rife_uhd.pack(side=tk.LEFT)
        ttk.Label(rr2, text="  GPU:").pack(side=tk.LEFT, padx=(10, 3))
        self.w_rife_gpu = ttk.Spinbox(
            rr2, from_=0, to=7, textvariable=self.var_rife_gpu,
            width=3, state="disabled")
        self.w_rife_gpu.pack(side=tk.LEFT)

        self.rife_info = ttk.Label(self.rife_frame, text="", style="Rife.TLabel")
        self.rife_info.pack(fill=tk.X, pady=(3, 0))

        ttk.Label(ff, text="  💡 RIFE比FRUC质量高很多, 尤其遮挡和运动模糊场景",
                  style="Rife.TLabel").pack(anchor=tk.W, pady=(3, 0))
        ttk.Label(ff, text="  下载: github.com/nihui/rife-ncnn-vulkan/releases",
                  style="Hint.TLabel").pack(anchor=tk.W)
        self.interp_info = ttk.Label(ff, text="", style="Hint.TLabel")
        self.interp_info.pack(fill=tk.X, pady=(3, 0))

        # ═══ 编码 ═══
        ef = ttk.LabelFrame(parent, text="⚙️ 编码设置", padding=5)
        ef.pack(fill=tk.X, pady=3, padx=2)
        ttk.Checkbutton(ef, text="保持原编码格式",
                         variable=self.var_keep_codec).pack(anchor=tk.W)
        er1 = ttk.Frame(ef)
        er1.pack(fill=tk.X, pady=2)
        ttk.Label(er1, text="预设:").pack(side=tk.LEFT)
        ttk.Combobox(er1, textvariable=self.var_preset,
                     values=["quality", "balanced", "performance"],
                     state="readonly", width=12).pack(side=tk.LEFT, padx=5)
        ttk.Label(er1, text="码率(kbps,0=自动):").pack(side=tk.LEFT, padx=(15, 3))
        ttk.Entry(er1, textvariable=self.var_bitrate, width=8).pack(side=tk.LEFT)
        er2 = ttk.Frame(ef)
        er2.pack(fill=tk.X, pady=2)
        ttk.Label(er2, text="CQP(0=VBR):").pack(side=tk.LEFT)
        ttk.Entry(er2, textvariable=self.var_cqp, width=6).pack(side=tk.LEFT, padx=5)
        ttk.Label(er2, text="(H264推荐18-23, HEVC推荐20-28)",
                  foreground="gray").pack(side=tk.LEFT, padx=5)

    def _build_log_panel(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill=tk.BOTH, expand=True)

        lf = ttk.Frame(nb, padding=3)
        nb.add(lf, text="📋 处理日志")
        self.log_text = scrolledtext.ScrolledText(
            lf, wrap=tk.WORD, font=("Consolas", 9),
            state="disabled", bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white")
        self.log_text.pack(fill=tk.BOTH, expand=True)

        cf = ttk.Frame(nb, padding=3)
        nb.add(cf, text="🖥️ 命令预览")
        self.cmd_text = scrolledtext.ScrolledText(
            cf, wrap=tk.WORD, font=("Consolas", 9),
            state="disabled", bg="#0c0c0c", fg="#cccccc")
        self.cmd_text.pack(fill=tk.BOTH, expand=True)
        btn_row = ttk.Frame(cf)
        btn_row.pack(fill=tk.X, pady=3)
        ttk.Button(btn_row, text="📋 复制命令",
                   command=self._copy_cmd).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_row, text="🔄 刷新",
                   command=self._refresh_cmd).pack(side=tk.LEFT, padx=3)

        inf = ttk.Frame(nb, padding=3)
        nb.add(inf, text="ℹ️ 视频信息")
        self.detail_text = scrolledtext.ScrolledText(
            inf, wrap=tk.WORD, font=("Consolas", 9),
            state="disabled", bg="#f5f5f5", fg="#333333")
        self.detail_text.pack(fill=tk.BOTH, expand=True)

    def _build_controls(self, parent):
        cf = ttk.Frame(parent)
        cf.pack(fill=tk.X, pady=(5, 0))
        pf = ttk.Frame(cf)
        pf.pack(fill=tk.X, pady=(0, 5))
        self.progress = ttk.Progressbar(pf, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, side=tk.LEFT, expand=True, padx=(0, 10))
        self.prog_label = ttk.Label(pf, text="0%", width=8, style="Status.TLabel")
        self.prog_label.pack(side=tk.RIGHT)
        bf = ttk.Frame(cf)
        bf.pack(fill=tk.X)
        self.status = ttk.Label(bf, text="就绪", style="Status.TLabel")
        self.status.pack(side=tk.LEFT)
        self.btn_cancel = ttk.Button(bf, text="取消", command=self._cancel,
                                      state="disabled", width=10)
        self.btn_cancel.pack(side=tk.RIGHT, padx=5)
        self.btn_start = ttk.Button(bf, text="▶ 开始处理",
                                     command=self._start, width=15)
        self.btn_start.pack(side=tk.RIGHT, padx=5)
        self.btn_probe = ttk.Button(bf, text="🔍 深度帧率检测",
                                     command=self._deep_probe, width=18)
        self.btn_probe.pack(side=tk.RIGHT, padx=5)
        ttk.Button(bf, text="🔄 刷新预览",
                   command=self._refresh_cmd, width=10
                   ).pack(side=tk.RIGHT, padx=5)

    # ═══ 事件 ═══

    def _browse_input(self):
        p = filedialog.askopenfilename(filetypes=[
            ("视频", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.ts *.m2ts"),
            ("所有", "*.*")])
        if p:
            self.var_input.set(normalize_path(p))
            self._on_input(p)

    def _browse_output(self):
        ext = Path(self.var_input.get()).suffix if self.var_input.get() else ".mp4"
        p = filedialog.asksaveasfilename(defaultextension=ext, filetypes=[
            ("MP4", "*.mp4"), ("MKV", "*.mkv"), ("所有", "*.*")])
        if p:
            self.var_output.set(normalize_path(p))

    def _browse_tool(self, t):
        p = filedialog.askopenfilename(filetypes=[
            ("exe", "*.exe"), ("所有", "*.*")])
        if p:
            p = normalize_path(p)
            {"nvencc": self.var_nvencc, "ffprobe": self.var_ffprobe,
             "ffmpeg": self.var_ffmpeg, "rife": self.var_rife}[t].set(p)
            self._sync_tools()
            self._validate_tools()

    def _sync_tools(self):
        self.tools.nvencc_path = self.var_nvencc.get()
        self.tools.ffprobe_path = self.var_ffprobe.get()
        self.tools.ffmpeg_path = self.var_ffmpeg.get()
        self.tools.rife_path = self.var_rife.get()
        self.engine.builder.nvencc_path = self.tools.nvencc_path

    def _on_input(self, path):
        self._sync_tools()
        self.info_label.config(text="分析中...", foreground="orange")
        self.info_detail.config(text="")
        self.vfr_warning.config(text="")

        def probe():
            info = probe_video(self.tools.ffprobe_path, path)
            self.root.after(0, lambda: self._on_probe(info, path))
        threading.Thread(target=probe, daemon=True).start()

    def _on_probe(self, info, path):
        if info is None:
            self.info_label.config(text="❌ 无法解析视频", foreground="red")
            self.video_info = None
            return

        self.video_info = info

        # 主信息行
        hdr = " [HDR]" if info.hdr else ""
        vfr = " [VFR]" if info.is_vfr else ""
        br_kbps = info.bitrate // 1000 if info.bitrate else 0
        self.info_label.config(
            text=f"📹 {info.codec_name.upper()} "
                 f"{info.width}×{info.height} @ {info.fps:.3f}fps{vfr} | "
                 f"{info.bit_depth}bit{hdr} | {br_kbps}kbps | "
                 f"{info.duration:.1f}s | {info.total_frames}帧",
            foreground="dark green")

        # 详细行
        detail = (
            f"帧率: {info.fps:.3f}fps ({info.fps_source}) | "
            f"码率: {br_kbps}kbps ({info.bitrate_source})")
        if info.audio_codec:
            detail += (f" | 音频: {info.audio_codec} "
                       f"{info.audio_bitrate//1000 if info.audio_bitrate else '?'}kbps")
        self.info_detail.config(text=detail)

        # VFR 警告
        if info.is_vfr:
            self.vfr_warning.config(
                text=f"⚠️ VFR! 补帧可能不准, 建议先: "
                     f"ffmpeg -i input -vsync cfr -r {info.fps:.0f} output.mp4")
        else:
            self.vfr_warning.config(text="")

        # 自动输出路径
        p = Path(path)
        self.var_output.set(normalize_path(str(p.parent / f"{p.stem}_enhanced{p.suffix}")))

        if info.width > 1920 or info.height > 1080:
            self.var_rife_uhd.set(True)

        self._update_detail(info)
        self._update_interp_info()
        self._update_sr_label()
        self._refresh_cmd()

    def _update_detail(self, info: VideoInfo):
        """★ 详细视频信息 (含帧率/码率检测原理说明)"""
        self.detail_text.config(state="normal")
        self.detail_text.delete("1.0", tk.END)

        br_kbps = info.bitrate // 1000 if info.bitrate else 0
        br_total_kbps = info.bitrate_total // 1000 if info.bitrate_total else 0
        size_mb = info.file_size / (1024*1024) if info.file_size else 0

        details = f"""═══════════════════════════════════════
  视频文件详细信息
═══════════════════════════════════════
文件: {info.filepath}
大小: {size_mb:.1f} MB ({info.file_size:,} bytes)

【视频流】
  编码:       {info.codec_name.upper()} (Profile: {info.profile or 'N/A'}, Level: {info.level or 'N/A'})
  分辨率:     {info.width} × {info.height}
  像素格式:   {info.pixel_format} ({info.bit_depth}bit)
  HDR:        {'是 (' + info.color_transfer + ')' if info.hdr else '否'}
  start_time: {info.start_time:.6f}s

【帧率检测】 ← 采用: {info.fps:.6f} fps ({info.fps_source})
  r_frame_rate:   {info.fps_r:.6f} fps ({info.fps_r_raw})
    → codec标称帧率, CFR视频最准确
    → VFR视频可能是时间基倒数, 不可靠
  avg_frame_rate: {info.fps_avg:.6f} fps ({info.fps_avg_raw})
    → nb_frames / duration 计算
    → 受 start_time偏移、非显示帧、尾部填充影响
  PTS实测:        {info.fps_pts:.6f} fps
    → 读取前3秒帧的PTS时间戳, 取帧间隔中位数
    → 最接近播放器实际渲染的帧率
  VFR:            {'⚠ 是 (可变帧率)' if info.is_vfr else '✅ 否 (恒定帧率)'}

  为什么 总帧数/时长 ≠ 每秒实际帧率:
    1. NTSC: 29.97fps=30000/1001, 不是整数30
    2. duration 可能含 start_time 偏移 ({info.start_time:.3f}s)
    3. nb_frames 可能含非显示帧(SPS/PPS)
    4. 容器的 duration 精度有限
    5. 最后一个GOP可能不完整

【码率检测】 ← 采用: {br_kbps} kbps ({info.bitrate_source})
  视频流bit_rate: {info.bitrate_stream//1000 if info.bitrate_stream else 'N/A'} kbps
    → 直接从视频流metadata读取, 最准确
    → MKV等容器常缺失此字段
  容器总码率:     {br_total_kbps if br_total_kbps else 'N/A'} kbps
    → 包含视频+音频+字幕+容器开销
  计算值:         {info.bitrate_calculated//1000 if info.bitrate_calculated else 'N/A'} kbps
    → 总码率 - 音频码率, 或 文件大小/时长 - 音频

【时间】
  时长:       {info.duration:.6f}s ({info.duration/60:.1f}分) ({info.duration_source})
  总帧数:     {info.total_frames} ({info.total_frames_source})

【色彩空间】
  矩阵: {info.color_space or 'N/A'} | 传输: {info.color_transfer or 'N/A'} | 原色: {info.color_primaries or 'N/A'}

【音频流】
  编码: {info.audio_codec or 'N/A'} | {info.audio_bitrate//1000 if info.audio_bitrate else 'N/A'}kbps | {info.audio_sample_rate}Hz | {info.audio_channels}ch

【NVEnc兼容性】
  {info.codec_name.upper()} → {'✅ 支持' if info.codec_name.lower() in ('h264','avc','hevc','h265','av1') else '❌ 不支持, 将转HEVC'}
"""
        self.detail_text.insert("1.0", details)
        self.detail_text.config(state="disabled")

    def _refresh_cmd(self):
        self._sync_tools()
        inp = self.var_input.get() or "<输入文件>"
        out = self.var_output.get() or "<输出文件>"
        dummy = self.video_info or VideoInfo(
            filepath=inp, codec_name="hevc",
            width=1920, height=1080, fps=30.0, bitrate=10000000, bit_depth=8)
        config = self._collect()
        try:
            cmd, warnings = self.engine.builder.build_command(inp, out, dummy, config)
            self.cmd_text.config(state="normal")
            self.cmd_text.delete("1.0", tk.END)
            text = "REM ═══ NVEncC 命令 ═══\n\n"
            if warnings:
                for w in warnings:
                    text += f"REM {w}\n"
                text += "\n"
            desc = []
            if config.denoise_method != "none":
                desc.append(f"{config.denoise_method}降噪")
            if config.enable_artifact_reduction:
                desc.append(f"AI去伪影(mode={config.artifact_reduction_mode})")
            if config.enable_super_resolution:
                desc.append(f"超分{config.super_resolution_scale}x")
            if config.enable_decimate:
                desc.append("去重复帧")
            if config.interp_method == "fruc":
                desc.append("FRUC补帧")
            elif config.interp_method == "rife":
                desc.append(f"RIFE {config.rife_multiplier}x")
                text += "REM ⚠ RIFE 需多阶段, 此处仅显示NVEncC阶段\n\n"
            if desc:
                text += f"REM 处理: {' → '.join(desc)}\n\n"
            text += f"REM === 单行 ===\n{format_cmd_for_display(cmd)}\n\n"
            text += f"REM === 多行 ===\n{format_cmd_pretty(cmd)}\n"
            self.cmd_text.insert("1.0", text)
            self.cmd_text.config(state="disabled")
        except Exception as e:
            self.cmd_text.config(state="normal")
            self.cmd_text.delete("1.0", tk.END)
            self.cmd_text.insert("1.0", f"REM 错误: {e}")
            self.cmd_text.config(state="disabled")

    def _copy_cmd(self):
        self._sync_tools()
        inp = self.var_input.get() or "<输入>"
        out = self.var_output.get() or "<输出>"
        dummy = self.video_info or VideoInfo(
            filepath=inp, codec_name="hevc",
            width=1920, height=1080, fps=30.0, bitrate=10000000, bit_depth=8)
        config = self._collect()
        try:
            cmd, _ = self.engine.builder.build_command(inp, out, dummy, config)
            self.root.clipboard_clear()
            self.root.clipboard_append(format_cmd_for_display(cmd))
            self.status.config(text="✅ 已复制", foreground="green")
            self.root.after(3000, lambda: self.status.config(text="就绪", foreground="black"))
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _deep_probe(self):
        if not self.var_input.get():
            messagebox.showwarning("提示", "请先选择输入视频")
            return
        self._sync_tools()
        self.status.config(text="深度帧率检测中...", foreground="blue")

        def do_probe():
            result = probe_detailed_fps(
                self.tools.ffprobe_path,
                normalize_path(self.var_input.get()), 10.0)
            self.root.after(0, lambda: self._on_deep(result))
        threading.Thread(target=do_probe, daemon=True).start()

    def _on_deep(self, result):
        self.status.config(text="就绪", foreground="black")
        if not result:
            messagebox.showerror("错误", "帧率检测失败")
            return
        msg = (
            f"PTS实测帧率 (中位数): {result['fps_median']:.6f} fps\n"
            f"PTS实测帧率 (平均值): {result['fps_mean']:.6f} fps\n"
            f"VFR: {'是' if result['is_vfr'] else '否'} "
            f"(变异系数={result['cv']:.4f})\n"
            f"\n采样帧数: {result['sampled_frames']}\n"
            f"有效帧间隔: {result['sampled_deltas']}\n"
            f"\n帧间隔 中位数: {result['median_delta_ms']:.3f} ms\n"
            f"帧间隔 平均值: {result['mean_delta_ms']:.3f} ms\n"
            f"帧间隔 标准差: {result['stdev_delta_ms']:.3f} ms\n"
            f"帧间隔 最小:   {result['min_delta_ms']:.3f} ms\n"
            f"帧间隔 最大:   {result['max_delta_ms']:.3f} ms\n")
        if self.video_info:
            msg += (f"\n标称帧率: {self.video_info.fps:.6f} fps "
                    f"({self.video_info.fps_source})\n"
                    f"差异: {abs(result['fps_median'] - self.video_info.fps):.6f} fps")
        messagebox.showinfo("深度帧率检测", msg)

    # ═══ 控件联动 ═══

    def _on_denoise_change(self):
        m = self.var_denoise.get()
        self.w_denoise_str.config(
            state="readonly" if m in ("knn", "pmd", "nlmeans") else "disabled")
        self._refresh_cmd()

    def _on_artifact_toggle(self):
        self.w_art_mode.config(
            state="readonly" if self.var_artifact.get() else "disabled")
        self._refresh_cmd()

    def _on_sr_toggle(self):
        st = "readonly" if self.var_superres.get() else "disabled"
        self.w_sr_scale.config(state=st)
        self.w_sr_algo.config(state=st)
        self._update_sr_label()
        self._refresh_cmd()

    def _on_dec_toggle(self):
        st = "normal" if self.var_decimate.get() else "disabled"
        self.w_dec_cycle.config(state=st)
        self.w_dec_drop.config(state=st)
        self._refresh_cmd()

    def _on_interp_change(self):
        method = self.var_interp.get()
        self.w_fruc_mode.config(state="readonly" if method == "fruc" else "disabled")
        self.w_fruc_fps.config(state="normal" if method == "fruc" else "disabled")
        rife = method == "rife"
        self.w_rife_mult.config(state="normal" if rife else "disabled")
        self.w_rife_model.config(state="readonly" if rife else "disabled")
        self.w_rife_uhd.config(state="normal" if rife else "disabled")
        self.w_rife_gpu.config(state="normal" if rife else "disabled")
        self._update_interp_info()
        self._refresh_cmd()

    def _update_interp_info(self):
        if not self.video_info:
            self.interp_info.config(text="")
            self.rife_info.config(text="")
            return
        method = self.var_interp.get()
        fps = self.video_info.fps
        if method == "fruc":
            if self.var_fruc_mode.get() == "double":
                self.interp_info.config(text=f"  {fps:.3f} → {fps*2:.3f} fps")
            else:
                self.interp_info.config(text=f"  {fps:.3f} → {self.var_fruc_fps.get()} fps")
            self.rife_info.config(text="")
        elif method == "rife":
            try:
                mult = max(1.0, min(8.0, float(self.var_rife_mult.get())))
            except Exception:
                mult = 2.0
            self.interp_info.config(text=f"  {fps:.3f} → {fps*mult:.3f} fps (RIFE {mult}x)")
            self.rife_info.config(
                text=f"  {self.var_rife_model.get()} | "
                     f"{'UHD' if self.var_rife_uhd.get() else '标准'} | "
                     f"GPU:{self.var_rife_gpu.get()}")
        else:
            self.interp_info.config(text="")
            self.rife_info.config(text="")

    def _update_sr_label(self):
        if self.video_info and self.var_superres.get():
            try:
                scale = int(self.var_sr_scale.get())
            except Exception:
                scale = 2
            nw = self.video_info.width * scale // 2 * 2
            nh = self.video_info.height * scale // 2 * 2
            self.sr_output_label.config(text=f"→ {nw}×{nh}")
        else:
            self.sr_output_label.config(text="")

    def _validate_tools(self):
        self._sync_tools()
        def v():
            r = self.tools.validate()
            self.root.after(0, lambda: self.tool_status.config(
                text="  |  ".join(f"{n}: {'✅' if ok else '❌'}" for n, ok in r.items()),
                foreground="green" if all(ok for n, ok in r.items() if n != "RIFE") else "orange"))
        threading.Thread(target=v, daemon=True).start()

    # ═══ 配置收集 ═══

    def _collect(self) -> ProcessingConfig:
        c = ProcessingConfig()
        c.denoise_method = self.var_denoise.get()
        c.denoise_strength = self.var_denoise_str.get()
        c.enable_artifact_reduction = self.var_artifact.get()
        try: c.artifact_reduction_mode = int(self.var_artifact_mode.get())
        except: c.artifact_reduction_mode = 0
        c.enable_super_resolution = self.var_superres.get()
        try: c.super_resolution_scale = int(self.var_sr_scale.get())
        except: c.super_resolution_scale = 2
        c.super_resolution_algo = self.var_sr_algo.get()
        c.enable_decimate = self.var_decimate.get()
        try: c.decimate_cycle = int(self.var_dec_cycle.get())
        except: c.decimate_cycle = 5
        try: c.decimate_drop = int(self.var_dec_drop.get())
        except: c.decimate_drop = 1
        try: c.decimate_thredup = float(self.var_dec_thredup.get())
        except: c.decimate_thredup = 1.1
        try: c.decimate_thresc = float(self.var_dec_thresc.get())
        except: c.decimate_thresc = 15.0
        c.interp_method = self.var_interp.get()
        c.fruc_mode = self.var_fruc_mode.get()
        try: c.fruc_target_fps = float(self.var_fruc_fps.get())
        except: c.fruc_target_fps = 60.0
        try:
            val = float(self.var_rife_mult.get())
            c.rife_multiplier = max(1.0, min(8.0, val))  # 限定 1.0~8.0
        except:
            c.rife_multiplier = 2.0
        c.rife_model = self.var_rife_model.get()
        c.rife_uhd = self.var_rife_uhd.get()
        try: c.rife_gpu = int(self.var_rife_gpu.get())
        except: c.rife_gpu = 0
        c.keep_original_codec = self.var_keep_codec.get()
        try: c.target_bitrate = int(self.var_bitrate.get())
        except: c.target_bitrate = 0
        try: c.cqp_value = int(self.var_cqp.get())
        except: c.cqp_value = 0
        c.preset = self.var_preset.get()
        return c

    # ═══ 日志/进度 ═══

    def _log(self, msg):
        def u():
            self.log_text.config(state="normal")
            self.log_text.insert(tk.END, msg)
            self.log_text.see(tk.END)
            self.log_text.config(state="disabled")
        self.root.after(0, u)

    def _update_progress(self, v):
        def u():
            self.progress["value"] = v
            self.prog_label.config(text=f"{v:.1f}%")
        self.root.after(0, u)

    # ═══ 开始/取消/完成 ═══

    def _start(self):
        inp = self.var_input.get()
        out = self.var_output.get()
        if not inp or not os.path.exists(normalize_path(inp)):
            messagebox.showerror("错误", "请选择有效输入文件"); return
        if not out:
            messagebox.showerror("错误", "请指定输出路径"); return
        if not self.video_info:
            messagebox.showerror("错误", "视频信息未加载"); return
        if self.engine.is_running:
            messagebox.showwarning("警告", "正在处理中"); return

        config = self._collect()

        has_proc = any([config.denoise_method != "none",
                        config.enable_artifact_reduction,
                        config.enable_super_resolution,
                        config.enable_decimate,
                        config.interp_method != "none"])
        if not has_proc:
            if not messagebox.askyesno("提示", "未勾选处理选项, 仅重编码。继续？"):
                return

        if config.interp_method == "rife":
            self._sync_tools()
            if not self.engine.rife.is_available():
                messagebox.showerror("RIFE不可用",
                    f"找不到: {self.tools.rife_path}\n"
                    f"下载: github.com/nihui/rife-ncnn-vulkan/releases")
                return

        if self.video_info.is_vfr and config.interp_method != "none":
            if not messagebox.askyesno("VFR警告",
                "检测到VFR! 补帧可能不准。建议先转CFR。\n继续？"):
                return

        if os.path.exists(normalize_path(out)):
            if not messagebox.askyesno("确认", f"覆盖?\n{out}"):
                return

        out_dir = os.path.dirname(normalize_path(out))
        if out_dir and not os.path.exists(out_dir):
            try:
                os.makedirs(out_dir, exist_ok=True)
            except OSError as e:
                messagebox.showerror("错误", f"无法创建目录:\n{e}"); return

        self._sync_tools()
        self.btn_start.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.progress["value"] = 0
        self.prog_label.config(text="0%")
        self.status.config(text="处理中...", foreground="blue")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")

        vi = self.video_info
        self._log(f"═══ NVEncC Video Enhancer v{APP_VERSION} ═══\n")
        self._log(f"输入: {normalize_path(inp)}\n")
        self._log(f"输出: {normalize_path(out)}\n")
        self._log(f"源: {vi.codec_name} {vi.width}×{vi.height} "
                  f"@ {vi.fps:.3f}fps ({vi.bitrate//1000}kbps)\n")
        self._log(f"帧率来源: {vi.fps_source}\n")
        self._log(f"码率来源: {vi.bitrate_source}\n")

        desc = []
        if config.denoise_method != "none":
            desc.append(f"{config.denoise_method}降噪({config.denoise_strength})")
        if config.enable_artifact_reduction:
            desc.append(f"AI去伪影(mode={config.artifact_reduction_mode})")
        if config.enable_super_resolution:
            desc.append(f"超分{config.super_resolution_scale}x({config.super_resolution_algo})")
        if config.enable_decimate:
            desc.append("去重复帧")
        if config.interp_method == "fruc":
            desc.append("FRUC补帧")
        elif config.interp_method == "rife":
            desc.append(f"RIFE {config.rife_multiplier}x({config.rife_model})")
        if desc:
            self._log(f"处理: {' → '.join(desc)}\n")
        self._log("───────────────────────────\n\n")

        self._refresh_cmd()

        self.engine.start_processing(
            normalize_path(inp), normalize_path(out),
            self.video_info, config,
            self._update_progress, self._log, self._on_done)

    def _cancel(self):
        if self.engine.is_running:
            if messagebox.askyesno("确认", "取消处理？"):
                self.engine.cancel()
                self.status.config(text="取消中...", foreground="orange")

    def _on_done(self, ok, msg):
        def u():
            self.btn_start.config(state="normal")
            self.btn_cancel.config(state="disabled")
            if ok:
                self.status.config(text="✅ 完成", foreground="green")
                self.progress["value"] = 100
                self.prog_label.config(text="100%")
                out = normalize_path(self.var_output.get())
                size_msg = ""
                if os.path.exists(out):
                    size_msg = f"\n大小: {os.path.getsize(out)/(1024*1024):.1f} MB"
                messagebox.showinfo("完成", f"输出: {out}{size_msg}")
            else:
                self.status.config(text=f"❌ {msg}", foreground="red")
                if "取消" not in msg:
                    messagebox.showerror("失败", msg)
        self.root.after(0, u)


def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        root.tk.call('encoding', 'system', 'utf-8')
    except Exception:
        pass
    VideoEnhancerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()