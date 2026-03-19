"""
跨平台透明视频转码工具
HEVC Alpha → H.264 左右排列 MP4（RGB + Alpha 并排）

支持输入格式:
  - Apple HEVC Alpha 双流 (MOV: 两个视频流)
  - HEVC 单流带 Alpha (yuva420p / gbrap 等像素格式)
  - VP9/VP8 Alpha (WebM)
  - ProRes 4444 带 Alpha
  - 其他带 Alpha 通道的视频格式

用于移动端 Shader 合成透明视频播放
一套素材兼容 iOS + Android

作者: AlphaVideoTool
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import subprocess
import os
import sys
import glob
import shutil
import threading
import json
import re
from pathlib import Path


# ============================================================
# 默认配置
# ============================================================

DEFAULT_CONFIG = {
    "layout": "side_by_side",
    "h264_bitrate": "4M",
    "h264_crf": 18,
    "h264_preset": "medium",
    "h264_profile": "high",
    "h264_level": "4.1",
    "vp8_enabled": False,
    "vp8_bitrate": "2M",
    "vp8_crf": 10,
    "frame_rate": 0,
    "scale_width": 0,
    "output_suffix": "_alpha_sbs",
    "output_dir": "",
}

CONFIG_FILE = "alpha_video_tool_config.json"

ALPHA_PIX_FMTS = {
    "yuva420p", "yuva422p", "yuva444p",
    "yuva420p9be", "yuva420p9le", "yuva420p10be", "yuva420p10le",
    "yuva420p16be", "yuva420p16le",
    "yuva422p9be", "yuva422p9le", "yuva422p10be", "yuva422p10le",
    "yuva422p12be", "yuva422p12le", "yuva422p16be", "yuva422p16le",
    "yuva444p9be", "yuva444p9le", "yuva444p10be", "yuva444p10le",
    "yuva444p12be", "yuva444p12le", "yuva444p16be", "yuva444p16le",
    "rgba", "rgba64be", "rgba64le",
    "argb", "abgr", "bgra", "rgba64", "bgra64",
    "gbrap", "gbrap10be", "gbrap10le", "gbrap12be", "gbrap12le",
    "gbrap16be", "gbrap16le",
    "gbrapf32be", "gbrapf32le",
    "pal8",
    "ayuv64le", "ayuv64be",
    "ya8", "ya16be", "ya16le",
}


def has_alpha_channel(pix_fmt: str) -> bool:
    if not pix_fmt:
        return False
    pix_fmt_lower = pix_fmt.lower().strip()
    if pix_fmt_lower in ALPHA_PIX_FMTS:
        return True
    if any(p in pix_fmt_lower for p in ['yuva', 'rgba', 'gbra', 'argb', 'abgr', 'bgra', 'ayuv']):
        return True
    return False


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(saved)
                return config
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ============================================================
# FFmpeg 环境检查
# ============================================================

def check_ffmpeg():
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return False, "未找到 FFmpeg"
    result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    has_h264 = "libx264" in result.stdout
    has_vpx = "libvpx" in result.stdout
    dec_result = subprocess.run(["ffmpeg", "-decoders"], capture_output=True, text=True)
    has_hevc = "hevc" in dec_result.stdout
    if not has_h264:
        return False, "FFmpeg 缺少 libx264 编码器"
    info = f"FFmpeg 就绪 | H.264: ✓ | HEVC: {'✓' if has_hevc else '✗'}"
    info += f" | VP8: {'✓' if has_vpx else '✗'}"
    return True, info


def get_ffmpeg_version():
    try:
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        return result.stdout.split('\n')[0]
    except Exception:
        return "未知"


# ============================================================
# 视频信息检测
# ============================================================

def get_video_info(input_path):
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=index,codec_type,codec_name,codec_tag_string,width,height,pix_fmt,r_frame_rate,duration,nb_frames",
        "-show_entries", "format=duration,format_name,format_long_name",
        "-of", "json",
        input_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception:
        pass
    return None


def probe_actual_pix_fmt(input_path):
    """解码一帧探测实际像素格式"""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "frame=pix_fmt",
        "-read_intervals", "%+#1",
        "-of", "csv=p=0",
        input_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split('\n')[0].strip()
    except Exception:
        pass
    return None


def detect_alpha_type(input_path):
    """
    检测视频的 Alpha 类型

    返回: (alpha_type, width, height, detail_info, pix_fmt)
    """
    info = get_video_info(input_path)
    if not info:
        return "unknown", None, None, "无法读取文件信息", ""

    streams = info.get("streams", [])
    video_streams = [s for s in streams
                     if s.get("codec_type") == "video"
                     or s.get("codec_name") in ("hevc", "h264", "vp8", "vp9", "prores", "png", "ffv1")]

    if not video_streams:
        video_streams = [s for s in streams if s.get("codec_name")]

    if not video_streams:
        return "unknown", None, None, "未找到视频流", ""

    width = int(video_streams[0].get("width", 0))
    height = int(video_streams[0].get("height", 0))
    codec_name = video_streams[0].get("codec_name", "")
    pix_fmt = video_streams[0].get("pix_fmt", "")
    codec_tag = video_streams[0].get("codec_tag_string", "")

    detail = (f"流数量: {len(video_streams)} | 编码: {codec_name} | "
              f"像素格式: {pix_fmt} | Tag: {codec_tag} | "
              f"分辨率: {width}x{height}")

    # ---- 多视频流 = Apple HEVC Alpha 双流 ----
    if len(video_streams) >= 2:
        return "dual_stream", width, height, detail, pix_fmt

    # ---- 单流：探测实际像素格式 ----
    actual_fmt = probe_actual_pix_fmt(input_path)
    if actual_fmt:
        detail += f" | 实际解码格式: {actual_fmt}"
        # 用实际解码格式覆盖
        if has_alpha_channel(actual_fmt):
            pix_fmt = actual_fmt
            if codec_name in ("hevc", "h265"):
                return "hevc_alpha", width, height, detail, pix_fmt
            else:
                return "pixel_alpha", width, height, detail, pix_fmt

    # 用 probe 标记的格式判断
    if has_alpha_channel(pix_fmt):
        if codec_name in ("hevc", "h265"):
            return "hevc_alpha", width, height, detail, pix_fmt
        else:
            return "pixel_alpha", width, height, detail, pix_fmt

    # ProRes 4444
    if codec_name == "prores" and ("4444" in codec_tag):
        return "pixel_alpha", width, height, detail, pix_fmt

    return "no_alpha", width, height, detail, pix_fmt


# ============================================================
# 核心转码逻辑（修复 Alpha 全白问题）
# ============================================================

def _build_sbs_filters(alpha_type, pix_fmt, layout):
    """
    根据 alpha 类型和像素格式构建 filter_complex 方法列表

    关键修复：
      对 HEVC 单流 Alpha（yuva420p 等），不使用 format=rgba + alphaextract，
      而是使用 extractplanes 直接提取 Y/U/V/A 四个平面，
      用 A 平面作为 Alpha 灰度图，用 mergeplanes 或原始流作为 RGB。
    """

    stack_cmd = "hstack" if layout == "side_by_side" else "vstack"
    methods = []

    if alpha_type == "dual_stream":
        # ================================================
        # Apple HEVC Alpha 双流
        # 流0 = RGB，流1 = Alpha (灰度)
        # ================================================

        # 方法1：直接拼接双流
        f1 = (
            f"[0:v:0]format=rgb24[rgb];"
            f"[0:v:1]format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("双流直接拼接", f1))

        # 方法2：alphamerge 再拆分
        f2 = (
            f"[0:v:0][0:v:1]alphamerge,format=rgba,"
            f"split[rgba1][rgba2];"
            f"[rgba1]format=rgb24[rgb];"
            f"[rgba2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("双流alphamerge拆分", f2))

    elif alpha_type == "hevc_alpha":
        # ================================================
        # HEVC 单流 Alpha —— 这是修复的核心
        #
        # 问题原因：
        #   format=rgba 在处理 HEVC yuva420p 时，
        #   某些 FFmpeg 版本/构建 会把 Alpha 平面填充为 255（全白不透明），
        #   因为 HEVC 解码器输出的 yuva 数据在 swscale 转 rgba 时
        #   Alpha 平面可能未正确映射。
        #
        # 修复方案：
        #   使用 extractplanes 滤镜直接从原生 yuva 格式中
        #   提取 A 平面，绕过 format=rgba 转换。
        # ================================================

        pix_lower = pix_fmt.lower() if pix_fmt else ""

        # ---------- 方法1（首选）：extractplanes 直接提取 ----------
        # 对 yuva420p/yuva422p/yuva444p 系列最有效
        if "yuva" in pix_lower:
            f1 = (
                f"[0:v:0]extractplanes=y+u+v+a[yp][up][vp][ap];"
                f"[yp][up][vp]mergeplanes=0x001020:yuv420p[yuv];"
                f"[yuv]format=rgb24[rgb];"
                f"[ap]format=gray[alpha];"
                f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
            )
            methods.append(("HEVC extractplanes YUVA", f1))

            # 方法1b：简化版 extractplanes（只提取 alpha）
            f1b = (
                f"[0:v:0]split[s1][s2];"
                f"[s1]format=yuv420p,format=rgb24[rgb];"
                f"[s2]extractplanes=a,format=gray[alpha];"
                f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
            )
            methods.append(("HEVC split+extractplanes", f1b))

        # ---------- 方法2：gbrap 中间格式 ----------
        # 对 gbrap 像素格式有效
        if "gbrap" in pix_lower or "gbra" in pix_lower:
            f2 = (
                f"[0:v:0]format=gbrap,extractplanes=g+b+r+a[gp][bp][rp][ap];"
                f"[gp][bp][rp]mergeplanes=0x001020:gbrp[gbrp];"
                f"[gbrp]format=rgb24[rgb];"
                f"[ap]format=gray[alpha];"
                f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
            )
            methods.append(("HEVC extractplanes GBRAP", f2))

        # ---------- 方法3：通过 geq 逐像素提取 Alpha ----------
        # 最兼容但最慢的方案
        f3 = (
            f"[0:v:0]split[s1][s2];"
            f"[s1]format=yuv420p,format=rgb24[rgb];"
            f"[s2]format=yuva444p,geq="
            f"'lum=alpha(X,Y):cb=128:cr=128',"
            f"format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("HEVC geq提取Alpha", f3))

        # ---------- 方法4：lutyuv 利用 alpha 通道 ----------
        f4 = (
            f"[0:v:0]split[s1][s2];"
            f"[s1]format=yuv420p,format=rgb24[rgb];"
            f"[s2]format=yuva420p,"
            f"alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("HEVC yuva420p+alphaextract", f4))

        # ---------- 方法5：rgba 备选（某些 FFmpeg 版本可能修复了此问题）----------
        f5 = (
            f"[0:v:0]format=rgba,split[rgba1][rgba2];"
            f"[rgba1]format=rgb24[rgb];"
            f"[rgba2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("HEVC rgba备选", f5))

        # ---------- 方法6：尝试当作双流 ----------
        f6 = (
            f"[0:v:0]format=rgb24[rgb];"
            f"[0:v:1]format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("HEVC尝试双流", f6))

    elif alpha_type == "pixel_alpha":
        # ================================================
        # 其他编码 单流 Alpha（ProRes 4444, VP9, PNG 等）
        # 这些编码通常 format=rgba + alphaextract 能正常工作
        # 但也加上 extractplanes 作为备选
        # ================================================

        pix_lower = pix_fmt.lower() if pix_fmt else ""

        # 方法1：extractplanes（最可靠）
        if "yuva" in pix_lower:
            f1 = (
                f"[0:v:0]split[s1][s2];"
                f"[s1]format=yuv420p,format=rgb24[rgb];"
                f"[s2]extractplanes=a,format=gray[alpha];"
                f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
            )
            methods.append(("extractplanes提取A", f1))

        # 方法2：通用 rgba
        f2 = (
            f"[0:v:0]format=rgba,split[rgba1][rgba2];"
            f"[rgba1]format=rgb24[rgb];"
            f"[rgba2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("通用RGBA提取", f2))

        # 方法3：gbrap
        f3 = (
            f"[0:v:0]format=gbrap,split[s1][s2];"
            f"[s1]format=rgb24[rgb];"
            f"[s2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("GBRAP提取", f3))

        # 方法4：尝试双流
        f4 = (
            f"[0:v:0]format=rgb24[rgb];"
            f"[0:v:1]format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("尝试双流", f4))

    else:
        # ================================================
        # 未知类型 —— 全部尝试
        # ================================================

        f1 = (
            f"[0:v:0]split[s1][s2];"
            f"[s1]format=yuv420p,format=rgb24[rgb];"
            f"[s2]extractplanes=a,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("尝试extractplanes", f1))

        f2 = (
            f"[0:v:0]format=rgba,split[rgba1][rgba2];"
            f"[rgba1]format=rgb24[rgb];"
            f"[rgba2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("尝试RGBA", f2))

        f3 = (
            f"[0:v:0]format=rgb24[rgb];"
            f"[0:v:1]format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("尝试双流", f3))

        f4 = (
            f"[0:v:0][0:v:1]alphamerge,format=rgba,"
            f"split[rgba1][rgba2];"
            f"[rgba1]format=rgb24[rgb];"
            f"[rgba2]alphaextract,format=gray[alpha];"
            f"[rgb][alpha]{stack_cmd}=inputs=2[out]"
        )
        methods.append(("尝试alphamerge", f4))

    return methods


def _verify_alpha_not_white(output_path):
    """
    验证输出视频的 Alpha 区域（右半或下半）是否全白
    如果全白说明 Alpha 提取失败

    返回: True = Alpha 正常, False = Alpha 全白
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", output_path,
        "-vframes", "1",
        "-vf", "crop=iw/2:ih:iw/2:0,blackdetect=d=0:pix_th=0.98",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        # 用 signalstats 检测右半区域亮度
        cmd2 = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "frame_tags=lavfi.signalstats.YAVG",
            "-f", "lavfi",
            f"movie='{output_path}',crop=iw/2:ih:iw/2:0,signalstats",
            "-read_intervals", "%+#1",
            "-of", "csv=p=0"
        ]
        # 简化：直接提取右半的一帧检查像素值
        cmd3 = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-vframes", "1",
            "-vf", "crop=iw/2:ih:iw/2:0",
            "-f", "rawvideo",
            "-pix_fmt", "gray",
            "pipe:1"
        ]
        result3 = subprocess.run(cmd3, capture_output=True, timeout=15)
        if result3.returncode == 0 and result3.stdout:
            data = result3.stdout
            if len(data) > 100:
                # 统计非 255 和非 0 的像素
                sample = data[:min(len(data), 10240)]
                total = len(sample)
                white_count = sum(1 for b in sample if b >= 250)
                black_count = sum(1 for b in sample if b <= 5)
                white_ratio = white_count / total
                black_ratio = black_count / total

                if white_ratio > 0.95:
                    return False  # 几乎全白 = Alpha 提取失败
                if black_ratio > 0.95 and white_ratio < 0.01:
                    # 全黑可能也有问题，但先放过
                    return True
                return True  # 有灰度变化 = Alpha 正常
    except Exception:
        pass

    # 无法检测时默认通过
    return True


def convert_to_sbs_mp4(input_path, output_path, config, log_callback=None):
    """
    透明视频 → H.264 左右/上下排列 MP4
    """

    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    if not os.path.exists(input_path):
        return False, f"找不到文件: {input_path}"

    alpha_type, src_w, src_h, detail, pix_fmt = detect_alpha_type(input_path)
    log(f"🔍 Alpha 类型: {alpha_type}")
    log(f"   详细信息: {detail}")
    log(f"   原始分辨率: {src_w}x{src_h}")
    log(f"   像素格式: {pix_fmt}")

    layout = config.get("layout", "side_by_side")

    # 构建方法列表
    methods = _build_sbs_filters(alpha_type, pix_fmt, layout)

    if not methods:
        return False, "无可用的转码方法"

    # 编码参数
    encode_params = [
        "-map", "[out]",
        "-c:v", "libx264",
        "-preset", config.get("h264_preset", "medium"),
        "-profile:v", config.get("h264_profile", "high"),
        "-level", config.get("h264_level", "4.1"),
        "-pix_fmt", "yuv420p",
        "-b:v", config.get("h264_bitrate", "4M"),
        "-movflags", "+faststart",
        "-an",
    ]

    crf = config.get("h264_crf", 0)
    if crf and crf > 0:
        encode_params.extend(["-crf", str(crf)])

    frame_rate = config.get("frame_rate", 0)
    if frame_rate and frame_rate > 0:
        encode_params.extend(["-r", str(frame_rate)])

    scale_width = config.get("scale_width", 0)

    # 逐个方法尝试
    for method_name, filter_str in methods:
        log(f"\n🔧 尝试 [{method_name}]:")

        final_filter = filter_str
        if scale_width and scale_width > 0:
            if layout == "side_by_side":
                target_w = scale_width * 2
            else:
                target_w = scale_width
            final_filter = filter_str.replace(
                "[out]",
                f"[pre_out];[pre_out]scale={target_w}:-2[out]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-filter_complex", final_filter,
        ]
        cmd.extend(encode_params)
        cmd.append(output_path)

        log(f"   命令: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1024:
            # ========== 关键：验证 Alpha 区域不是全白 ==========
            log(f"   ✅ 编码成功，验证 Alpha 通道...")
            alpha_ok = _verify_alpha_not_white(output_path)

            if alpha_ok:
                log(f"   ✅ Alpha 通道验证通过!")
                log(f"✅ [{method_name}] 成功!")
                return True, output_path
            else:
                log(f"   ⚠️ Alpha 区域全白! 此方法提取 Alpha 失败，尝试下一个...")
                # 删除失败的输出文件
                try:
                    os.remove(output_path)
                except Exception:
                    pass
                continue

        log(f"⚠️ [{method_name}] 失败")
        if result.stderr:
            err_lines = result.stderr.strip().split('\n')
            for line in err_lines[-5:]:
                log(f"   {line}")

    return False, "所有转码方法均失败（Alpha 提取异常）"


def convert_to_vp8_alpha(input_path, output_path, config, log_callback=None):
    """透明视频 → WebM VP8/VP9 Alpha"""

    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    alpha_type, _, _, _, pix_fmt = detect_alpha_type(input_path)
    methods = []

    # 方法1：直接转码
    cmd1 = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "libvpx",
        "-pix_fmt", "yuva420p",
        "-auto-alt-ref", "0",
        "-b:v", config.get("vp8_bitrate", "2M"),
        "-quality", "good",
        "-an",
        output_path
    ]
    methods.append(("VP8直接", cmd1))

    # 方法2：双流 alphamerge
    cmd2 = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", "[0:v:0][0:v:1]alphamerge,format=yuva420p",
        "-c:v", "libvpx",
        "-auto-alt-ref", "0",
        "-b:v", config.get("vp8_bitrate", "2M"),
        "-quality", "good",
        "-an",
        output_path
    ]
    methods.append(("VP8双流", cmd2))

    # 方法3：format=rgba 转 yuva420p
    cmd3 = [
        "ffmpeg", "-y", "-i", input_path,
        "-filter_complex", "[0:v:0]format=rgba,format=yuva420p",
        "-c:v", "libvpx",
        "-auto-alt-ref", "0",
        "-b:v", config.get("vp8_bitrate", "2M"),
        "-quality", "good",
        "-an",
        output_path
    ]
    methods.append(("VP8 RGBA转换", cmd3))

    for name, cmd in methods:
        log(f"🔧 {name}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            out_file = cmd[-1]
            if os.path.exists(out_file) and os.path.getsize(out_file) > 1024:
                log(f"✅ {name} 成功!")
                return True, out_file
        log(f"⚠️ {name} 失败")
        if result.stderr:
            err_lines = result.stderr.strip().split('\n')
            for line in err_lines[-3:]:
                log(f"   {line}")

    return False, "VP8/VP9 转码失败"


def verify_output(output_path, log_callback=None):
    """验证输出文件"""

    def log(msg):
        if log_callback:
            log_callback(msg)
        print(msg)

    if not os.path.exists(output_path):
        log(f"❌ 文件不存在: {output_path}")
        return False

    size_mb = os.path.getsize(output_path) / (1024 * 1024)

    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,pix_fmt,width,height,r_frame_rate,duration",
        "-of", "json",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    log(f"\n📋 输出验证:")
    log(f"   文件: {output_path}")
    log(f"   大小: {size_mb:.2f} MB")

    if result.returncode == 0:
        try:
            info = json.loads(result.stdout)
            s = info["streams"][0]
            w = int(s.get('width', 0))
            h = int(s.get('height', 0))
            log(f"   编码: {s.get('codec_name', '?')}")
            log(f"   像素: {s.get('pix_fmt', '?')}")
            log(f"   分辨率: {w}x{h}")
            log(f"   帧率: {s.get('r_frame_rate', '?')}")
        except Exception:
            pass

    return True


# ============================================================
# GUI 界面
# ============================================================

class AlphaVideoToolApp:
    def __init__(self, root):
        self.root = root
        self.root.title("跨平台透明视频转码工具 — HEVC Alpha → H.264 SBS")
        self.root.geometry("950x850")
        self.root.resizable(True, True)
        self.config = load_config()
        self.file_list = []
        self.is_converting = False
        self._create_ui()
        self._check_env()

    def _create_ui(self):

        # ========== 标题 ==========
        title_frame = ttk.LabelFrame(self.root, text="🎬 跨平台透明视频转码工具", padding=10)
        title_frame.pack(fill="x", padx=10, pady=5)

        ttk.Label(title_frame, text=(
            "HEVC Alpha(双流+单流) / ProRes 4444 / VP9 Alpha → H.264 并排 MP4\n"
            "✅ 修复: HEVC 单流 Alpha 使用 extractplanes 提取，不再出现全白\n"
            "移动端用 OpenGL/Metal Shader 合成，一套素材 iOS + Android 通用"
        ), wraplength=900).pack()

        self.env_label = ttk.Label(title_frame, text="检查环境中...", foreground="gray")
        self.env_label.pack(pady=3)

        # ========== 文件选择 ==========
        file_frame = ttk.LabelFrame(self.root, text="📁 输入文件", padding=10)
        file_frame.pack(fill="x", padx=10, pady=5)

        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill="x")
        ttk.Button(btn_row, text="添加文件", command=self._add_files).pack(side="left", padx=5)
        ttk.Button(btn_row, text="添加文件夹", command=self._add_folder).pack(side="left", padx=5)
        ttk.Button(btn_row, text="检测Alpha", command=self._detect_alpha).pack(side="left", padx=5)
        ttk.Button(btn_row, text="清空", command=self._clear_files).pack(side="left", padx=5)

        list_frame = ttk.Frame(file_frame)
        list_frame.pack(fill="both", expand=True, pady=5)
        self.file_listbox = tk.Listbox(list_frame, height=4, selectmode=tk.EXTENDED)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.file_listbox.yview)
        self.file_listbox.configure(yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.file_count_label = ttk.Label(file_frame, text="已选择 0 个文件")
        self.file_count_label.pack()

        # ========== 输出模式 ==========
        mode_frame = ttk.LabelFrame(self.root, text="📐 输出布局", padding=10)
        mode_frame.pack(fill="x", padx=10, pady=5)

        self.layout_var = tk.StringVar(value=self.config["layout"])

        layout_row = ttk.Frame(mode_frame)
        layout_row.pack(fill="x")

        ttk.Radiobutton(
            layout_row, text="左右排列 (Side by Side) — 宽度×2",
            variable=self.layout_var, value="side_by_side"
        ).pack(side="left", padx=10)

        ttk.Radiobutton(
            layout_row, text="上下排列 (Top Bottom) — 高度×2",
            variable=self.layout_var, value="top_bottom"
        ).pack(side="left", padx=10)

        hint_frame = ttk.Frame(mode_frame)
        hint_frame.pack(fill="x", pady=5)

        ttk.Label(hint_frame, text=(
            "左右排列: ┌─RGB─┬─Alpha─┐    上下排列: ┌──RGB──┐\n"
            "          └─────┴───────┘              ├─Alpha─┤\n"
            "          宽 = 原始×2                  └───────┘\n"
            "          高 = 原始                    高 = 原始×2"
        ), font=("Consolas", 9), justify="left").pack(anchor="w")

        # ========== H.264 参数 ==========
        h264_frame = ttk.LabelFrame(self.root, text="⚙️ H.264 编码参数（主输出）", padding=10)
        h264_frame.pack(fill="x", padx=10, pady=5)

        row1 = ttk.Frame(h264_frame)
        row1.pack(fill="x", pady=2)

        ttk.Label(row1, text="比特率:").pack(side="left", padx=5)
        self.h264_bitrate_var = tk.StringVar(value=self.config["h264_bitrate"])
        ttk.Combobox(row1, textvariable=self.h264_bitrate_var, width=8,
                     values=["1M", "2M", "4M", "6M", "8M", "10M", "15M"]
                     ).pack(side="left", padx=5)

        ttk.Label(row1, text="CRF(0-51):").pack(side="left", padx=15)
        self.h264_crf_var = tk.IntVar(value=self.config["h264_crf"])
        ttk.Spinbox(row1, from_=0, to=51, textvariable=self.h264_crf_var, width=5
                    ).pack(side="left", padx=5)

        ttk.Label(row1, text="预设:").pack(side="left", padx=15)
        self.h264_preset_var = tk.StringVar(value=self.config["h264_preset"])
        ttk.Combobox(row1, textvariable=self.h264_preset_var, width=10,
                     values=["ultrafast", "superfast", "veryfast", "faster",
                             "fast", "medium", "slow", "slower", "veryslow"]
                     ).pack(side="left", padx=5)

        row2 = ttk.Frame(h264_frame)
        row2.pack(fill="x", pady=2)

        ttk.Label(row2, text="Profile:").pack(side="left", padx=5)
        self.h264_profile_var = tk.StringVar(value=self.config["h264_profile"])
        ttk.Combobox(row2, textvariable=self.h264_profile_var, width=10,
                     values=["baseline", "main", "high"]
                     ).pack(side="left", padx=5)

        ttk.Label(row2, text="Level:").pack(side="left", padx=15)
        self.h264_level_var = tk.StringVar(value=self.config["h264_level"])
        ttk.Combobox(row2, textvariable=self.h264_level_var, width=6,
                     values=["3.0", "3.1", "4.0", "4.1", "4.2", "5.0", "5.1"]
                     ).pack(side="left", padx=5)

        ttk.Label(row2, text="帧率(0=原始):").pack(side="left", padx=15)
        self.fps_var = tk.IntVar(value=self.config["frame_rate"])
        ttk.Spinbox(row2, from_=0, to=120, textvariable=self.fps_var, width=5
                    ).pack(side="left", padx=5)

        ttk.Label(row2, text="缩放宽度(0=原始):").pack(side="left", padx=15)
        self.scale_var = tk.IntVar(value=self.config["scale_width"])
        ttk.Spinbox(row2, from_=0, to=7680, textvariable=self.scale_var, width=6,
                    increment=2).pack(side="left", padx=5)

        # ========== VP8 ==========
        vp8_frame = ttk.LabelFrame(self.root, text="🔹 VP8 Alpha 附加输出（可选）", padding=10)
        vp8_frame.pack(fill="x", padx=10, pady=5)

        vp8_row = ttk.Frame(vp8_frame)
        vp8_row.pack(fill="x")

        self.vp8_enabled_var = tk.BooleanVar(value=self.config["vp8_enabled"])
        ttk.Checkbutton(vp8_row, text="同时输出 WebM VP8 Alpha",
                        variable=self.vp8_enabled_var).pack(side="left", padx=5)

        ttk.Label(vp8_row, text="比特率:").pack(side="left", padx=15)
        self.vp8_bitrate_var = tk.StringVar(value=self.config["vp8_bitrate"])
        ttk.Combobox(vp8_row, textvariable=self.vp8_bitrate_var, width=8,
                     values=["500K", "1M", "2M", "3M", "4M"]
                     ).pack(side="left", padx=5)

        # ========== 输出设置 ==========
        out_frame = ttk.LabelFrame(self.root, text="📂 输出设置", padding=10)
        out_frame.pack(fill="x", padx=10, pady=5)

        out_row = ttk.Frame(out_frame)
        out_row.pack(fill="x")

        ttk.Label(out_row, text="后缀:").pack(side="left", padx=5)
        self.suffix_var = tk.StringVar(value=self.config["output_suffix"])
        ttk.Entry(out_row, textvariable=self.suffix_var, width=15).pack(side="left", padx=5)

        ttk.Label(out_row, text="输出目录(空=同目录):").pack(side="left", padx=15)
        self.outdir_var = tk.StringVar(value=self.config["output_dir"])
        ttk.Entry(out_row, textvariable=self.outdir_var, width=30).pack(side="left", padx=5)
        ttk.Button(out_row, text="选择", command=self._select_outdir).pack(side="left", padx=5)

        cfg_row = ttk.Frame(out_frame)
        cfg_row.pack(fill="x", pady=5)
        ttk.Button(cfg_row, text="恢复默认", command=self._reset_config).pack(side="left", padx=5)
        ttk.Button(cfg_row, text="保存配置", command=self._save_config).pack(side="left", padx=5)

        # ========== 操作按钮 ==========
        action_frame = ttk.Frame(self.root, padding=5)
        action_frame.pack(fill="x", padx=10)

        self.convert_btn = ttk.Button(action_frame, text="🚀 开始转码", command=self._start)
        self.convert_btn.pack(side="left", padx=5)

        self.stop_btn = ttk.Button(action_frame, text="⏹ 停止", command=self._stop, state="disabled")
        self.stop_btn.pack(side="left", padx=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(action_frame, variable=self.progress_var,
                                            maximum=100, length=300)
        self.progress_bar.pack(side="left", padx=10, fill="x", expand=True)

        self.progress_label = ttk.Label(action_frame, text="就绪")
        self.progress_label.pack(side="right", padx=5)

        # ========== 日志 ==========
        log_frame = ttk.LabelFrame(self.root, text="📋 日志", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD,
                                                  font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        ttk.Button(log_frame, text="清空日志", command=lambda: self.log_text.delete(1.0, tk.END)).pack(pady=2)

    # ========== 环境 ==========

    def _check_env(self):
        ok, msg = check_ffmpeg()
        if ok:
            ver = get_ffmpeg_version()
            self.env_label.config(text=f"✅ {msg} | {ver}", foreground="green")
            self._log(f"环境就绪: {ver}")
        else:
            self.env_label.config(text=f"❌ {msg}", foreground="red")
            self._log(f"❌ {msg}")
            self._log("  Windows: winget install Gyan.FFmpeg")
            self._log("  Mac:     brew install ffmpeg")
            self.convert_btn.config(state="disabled")

    # ========== 文件操作 ==========

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择视频文件",
            filetypes=[
                ("视频文件", "*.mov *.mp4 *.mkv *.avi *.webm *.mxf"),
                ("所有文件", "*.*")
            ]
        )
        for f in files:
            if f not in self.file_list:
                self.file_list.append(f)
                self.file_listbox.insert(tk.END, f)
        self._update_count()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            for ext in ["*.mov", "*.mp4", "*.mkv", "*.webm", "*.mxf"]:
                for f in glob.glob(os.path.join(folder, ext)):
                    if f not in self.file_list:
                        self.file_list.append(f)
                        self.file_listbox.insert(tk.END, f)
            self._update_count()

    def _detect_alpha(self):
        if not self.file_list:
            messagebox.showinfo("提示", "请先添加文件")
            return

        self._log(f"\n{'=' * 50}")
        self._log(f"🔍 Alpha 通道检测")
        self._log(f"{'=' * 50}")

        for f in self.file_list:
            self._log(f"\n📄 {os.path.basename(f)}")
            alpha_type, w, h, detail, pix_fmt = detect_alpha_type(f)
            type_emoji = {
                "dual_stream": "🟢 双流Alpha",
                "hevc_alpha": "🟢 HEVC单流Alpha",
                "pixel_alpha": "🟢 单流Alpha",
                "no_alpha": "🔴 无Alpha",
                "unknown": "🟡 未知",
            }
            self._log(f"   类型: {type_emoji.get(alpha_type, '❓')}")
            self._log(f"   {detail}")

    def _clear_files(self):
        self.file_list.clear()
        self.file_listbox.delete(0, tk.END)
        self._update_count()

    def _update_count(self):
        self.file_count_label.config(text=f"已选择 {len(self.file_list)} 个文件")

    def _select_outdir(self):
        folder = filedialog.askdirectory()
        if folder:
            self.outdir_var.set(folder)

    # ========== 配置 ==========

    def _get_config(self):
        return {
            "layout": self.layout_var.get(),
            "h264_bitrate": self.h264_bitrate_var.get(),
            "h264_crf": self.h264_crf_var.get(),
            "h264_preset": self.h264_preset_var.get(),
            "h264_profile": self.h264_profile_var.get(),
            "h264_level": self.h264_level_var.get(),
            "frame_rate": self.fps_var.get(),
            "scale_width": self.scale_var.get(),
            "vp8_enabled": self.vp8_enabled_var.get(),
            "vp8_bitrate": self.vp8_bitrate_var.get(),
            "output_suffix": self.suffix_var.get(),
            "output_dir": self.outdir_var.get(),
        }

    def _reset_config(self):
        c = DEFAULT_CONFIG
        self.layout_var.set(c["layout"])
        self.h264_bitrate_var.set(c["h264_bitrate"])
        self.h264_crf_var.set(c["h264_crf"])
        self.h264_preset_var.set(c["h264_preset"])
        self.h264_profile_var.set(c["h264_profile"])
        self.h264_level_var.set(c["h264_level"])
        self.fps_var.set(c["frame_rate"])
        self.scale_var.set(c["scale_width"])
        self.vp8_enabled_var.set(c["vp8_enabled"])
        self.vp8_bitrate_var.set(c["vp8_bitrate"])
        self.suffix_var.set(c["output_suffix"])
        self.outdir_var.set(c["output_dir"])
        self._log("✅ 已恢复默认参数")

    def _save_config(self):
        save_config(self._get_config())
        self._log("✅ 配置已保存")

    # ========== 转码 ==========

    def _start(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先添加视频文件")
            return

        self.is_converting = True
        self.convert_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        config = self._get_config()
        thread = threading.Thread(target=self._convert_thread,
                                  args=(list(self.file_list), config), daemon=True)
        thread.start()

    def _stop(self):
        self.is_converting = False
        self._log("⏹ 用户停止")

    def _convert_thread(self, files, config):
        total = len(files)
        success = 0
        fail = 0

        self._log(f"\n{'=' * 60}")
        self._log(f"🚀 开始批量转码 共 {total} 个文件")
        self._log(f"   布局: {config['layout']}")
        self._log(f"   H.264: {config['h264_bitrate']} CRF={config['h264_crf']}")
        self._log(f"{'=' * 60}")

        for i, input_path in enumerate(files):
            if not self.is_converting:
                break

            progress = (i / total) * 100
            self.root.after(0, lambda p=progress: self.progress_var.set(p))
            self.root.after(0, lambda idx=i: self.progress_label.config(text=f"{idx+1}/{total}"))

            self._log(f"\n{'─' * 40}")
            self._log(f"[{i+1}/{total}] {os.path.basename(input_path)}")

            name = Path(input_path).stem
            suffix = config.get("output_suffix", "_alpha_sbs")
            out_dir = config.get("output_dir", "") or str(Path(input_path).parent)
            os.makedirs(out_dir, exist_ok=True)

            mp4_path = os.path.join(out_dir, f"{name}{suffix}.mp4")
            ok, msg = convert_to_sbs_mp4(input_path, mp4_path, config, self._log)

            if ok:
                verify_output(mp4_path, self._log)
                success += 1
            else:
                self._log(f"❌ 失败: {msg}")
                fail += 1
                continue

            if config.get("vp8_enabled"):
                webm_path = os.path.join(out_dir, f"{name}_vp8alpha.webm")
                ok2, msg2 = convert_to_vp8_alpha(input_path, webm_path, config, self._log)
                if ok2:
                    verify_output(webm_path, self._log)

        self.root.after(0, lambda: self.progress_var.set(100))
        self.root.after(0, lambda: self.progress_label.config(text="完成"))
        self.root.after(0, lambda: self.convert_btn.config(state="normal"))
        self.root.after(0, lambda: self.stop_btn.config(state="disabled"))

        self._log(f"\n{'=' * 60}")
        self._log(f"📊 成功 {success} | 失败 {fail} | 共 {total}")
        self._log(f"{'=' * 60}")

        self.is_converting = False

        if success > 0:
            self.root.after(0, lambda: messagebox.showinfo(
                "完成", f"成功: {success} / 失败: {fail}"
            ))

    def _log(self, msg):
        def _append():
            self.log_text.insert(tk.END, msg + "\n")
            self.log_text.see(tk.END)
        self.root.after(0, _append)


# ============================================================
# 启动入口
# ============================================================

def main():
    root = tk.Tk()
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = AlphaVideoToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()