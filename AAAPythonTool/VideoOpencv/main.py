#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VideoToolbox - Python GUI OpenCV 视频处理全家桶 (含 DNN 模块)
==============================================================

功能清单:
─────────────────────────────────────────
【基础处理】
  1. 视频裁剪 (时间段截取)
  2. 视频缩放 (分辨率调整)
  3. 视频旋转/翻转
  4. 视频拼接
  5. 帧率调整
  6. 视频转 GIF
  7. 提取帧画面

【画面调整】
  8. 亮度/对比度/饱和度
  9. 色彩空间转换 (灰度/HSV/LAB)
  10. 直方图均衡化
  11. 锐化/模糊/降噪

【特效滤镜】
  12. 铅笔素描
  13. 卡通化
  14. 浮雕效果
  15. 边缘检测 (Canny/Sobel/Laplacian)
  16. 怀旧/冷暖色调
  17. 马赛克/像素化
  18. 晕影效果

【DNN AI 功能】
  19. 人脸检测 (SSD/Caffe)
  20. 物体检测 (YOLOv4-tiny)
  21. 风格迁移 (Neural Style Transfer + 参考图模式)
  22. 人脸马赛克 (检测+模糊)
  23. 背景虚化 (人物分割)
  24. 文字检测 (EAST)
  25. 去马赛克/超分重建 (Real-ESRGAN)

【分析工具】
  26. 亮度曲线分析
  27. 颜色直方图
  28. 运动检测/热力图
  29. 视频信息查看

【高级功能】
  30. 流程组合 (多功能串联处理)

依赖: opencv-python>=4.5.0, numpy>=1.20.0, scipy>=1.7.0
GUI: tkinter (Python 内置)
"""

import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import threading
import queue
import copy
import os
import sys
import time
import json
import tempfile
import subprocess
import hashlib
import urllib.request
import urllib.error
from pathlib import Path
from collections import deque, OrderedDict
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Dict, Callable, Any
from enum import Enum, auto
import io
import re
import struct
import traceback

try:
    from scipy.signal import savgol_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from PIL import Image as PILImage, ImageTk, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── 文件拖拽 (可选) ──────────────────────────────────────────────
# tkinterdnd2 是跨平台首选；装不上时退回仅 Windows 的 windnd。
# 两个都没有时程序照常运行，只是拖拽失效。
DND_BACKEND: Optional[str] = None
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_BACKEND = "tkinterdnd2"
except Exception:
    TkinterDnD = None
    DND_FILES = None
    try:
        import windnd
        DND_BACKEND = "windnd"
    except Exception:
        windnd = None


def make_root_window() -> tk.Tk:
    """tkinterdnd2 必须由它自己的 Tk 子类创建根窗口，否则拖拽注册会失败"""
    if DND_BACKEND == "tkinterdnd2":
        try:
            return TkinterDnD.Tk()
        except Exception:
            pass
    return tk.Tk()


# ════════════════════════════════════════════════════════════════
#  常量与配置
# ════════════════════════════════════════════════════════════════

APP_NAME = "VideoToolbox"
APP_VERSION = "2.2.0"
APP_TITLE = f"{APP_NAME} v{APP_VERSION} - OpenCV 视频处理全家桶"

DNN_MODELS_DIR = Path("models")

# ── 模型注册表 (含校验信息) ──────────────────────────────────
MODEL_REGISTRY = {
    "face_detector": {
        "display_name": "人脸检测 (SSD-Caffe)",
        "files": {
            "deploy.prototxt": {
                "url": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt",
                "min_size_kb": 20,
                "description": "网络结构定义",
            },
            "res10_300x300_ssd_iter_140000.caffemodel": {
                "url": "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel",
                "min_size_kb": 10000,  # ~10MB
                "description": "预训练权重",
            },
        },
    },
    "yolov4_tiny": {
        "display_name": "YOLOv4-tiny (物体检测)",
        "files": {
            "yolov4-tiny.cfg": {
                "url": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg",
                "min_size_kb": 2,
                "description": "网络配置",
            },
            "yolov4-tiny.weights": {
                "url": "https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights",
                "min_size_kb": 20000,  # ~23MB
                "description": "预训练权重",
            },
            "coco.names": {
                "url": "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names",
                "min_size_kb": 0.5,
                "description": "类别名称",
            },
        },
    },
    "style_the_wave": {
        "display_name": "风格迁移 - The Wave",
        "files": {
            "the_wave.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/eccv16/the_wave.t7",
                "min_size_kb": 6000,
                "description": "ECCV16 风格模型",
            },
        },
    },
    "style_starry_night": {
        "display_name": "风格迁移 - Starry Night",
        "files": {
            "starry_night.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/eccv16/starry_night.t7",
                "min_size_kb": 6000,
                "description": "ECCV16 风格模型",
            },
        },
    },
    "style_la_muse": {
        "display_name": "风格迁移 - La Muse",
        "files": {
            "la_muse.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/eccv16/la_muse.t7",
                "min_size_kb": 6000,
                "description": "ECCV16 风格模型",
            },
        },
    },
    "style_composition_vii": {
        "display_name": "风格迁移 - Composition VII",
        "files": {
            "composition_vii.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/eccv16/composition_vii.t7",
                "min_size_kb": 6000,
                "description": "ECCV16 风格模型",
            },
        },
    },
    "style_mosaic": {
        "display_name": "风格迁移 - Mosaic",
        "files": {
            "mosaic.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/instance_norm/mosaic.t7",
                "min_size_kb": 1500,
                "description": "Instance Norm 风格模型",
            },
        },
    },
    "style_candy": {
        "display_name": "风格迁移 - Candy",
        "files": {
            "candy.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/instance_norm/candy.t7",
                "min_size_kb": 1500,
                "description": "Instance Norm 风格模型",
            },
        },
    },
    "style_rain_princess": {
        "display_name": "风格迁移 - Rain Princess",
        "files": {
            "rain_princess.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/instance_norm/rain_princess.t7",
                "min_size_kb": 1500,
                "description": "Instance Norm 风格模型",
            },
        },
    },
    "style_udnie": {
        "display_name": "风格迁移 - Udnie",
        "files": {
            "udnie.t7": {
                "url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/instance_norm/udnie.t7",
                "min_size_kb": 1500,
                "description": "Instance Norm 风格模型",
            },
        },
    },
    "east_text": {
        "display_name": "EAST (文字检测)",
        "files": {
            "frozen_east_text_detection.pb": {
                "url": "https://raw.githubusercontent.com/oyyd/frozen_east_text_detection.pb/master/frozen_east_text_detection.pb",
                "min_size_kb": 90000,  # ~95MB
                "description": "EAST 文字检测模型",
            },
        },
    },
    "espcn_x4": {
        "display_name": "ESPCN (超分辨率 4x)",
        "files": {
            "ESPCN_x4.pb": {
                "url": "https://raw.githubusercontent.com/fannymonori/TF-ESPCN/master/export/ESPCN_x4.pb",
                "min_size_kb": 50,
                "description": "ESPCN 超分辨率模型",
            },
        },
    },
    "real_esrgan_x4": {
        "display_name": "Real-ESRGAN x4 (去马赛克/超分重建)",
        "files": {
            "realesrgan-x4plus.onnx": {
                "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-x4plus.onnx",
                "alt_urls": [
                    "https://huggingface.co/ai-forever/Real-ESRGAN/resolve/main/RealESRGAN_x4.onnx",
                ],
                "min_size_kb": 60000,  # ~64MB
                "description": "Real-ESRGAN x4 去马赛克/超分辨率 ONNX 模型",
            },
        },
    },
    "real_esrgan_anime": {
        "display_name": "Real-ESRGAN Anime (动漫去马赛克)",
        "files": {
            "realesrgan-animevideov3.onnx": {
                "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-x4plus-anime.onnx",
                "alt_urls": [],
                "min_size_kb": 16000,  # ~17MB
                "description": "Real-ESRGAN 动漫专用超分辨率 ONNX 模型",
            },
        },
    },
    "rvm_matting": {
        "display_name": "RobustVideoMatting (人像分割 / 背景虚化)",
        "files": {
            "rvm_mobilenetv3_fp32.onnx": {
                "url": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx",
                "min_size_kb": 12000,  # ~14.6MB
                "description": "RVM MobileNetV3 人像抠图 (带帧间时序状态)",
            },
        },
    },
    "crnn_cn": {
        "display_name": "CRNN 中文识别 (字幕 OCR)",
        "files": {
            "text_recognition_CRNN_CN_2021nov.onnx": {
                "url": "https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_CN_2021nov.onnx",
                "min_size_kb": 60000,  # ~69MB
                "description": "数字 + 英文字母 + 3944 常用汉字",
            },
        },
    },
    "crnn_en": {
        "display_name": "CRNN 英文识别 (字幕 OCR)",
        "files": {
            "text_recognition_CRNN_EN_2021sep.onnx": {
                "url": "https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx",
                "min_size_kb": 28000,  # ~32MB
                "description": "仅数字 + 26 个字母，体积小、速度快",
            },
        },
    },
}

# 保留旧接口兼容
MODEL_URLS = {
    "face_detector": {
        "prototxt": MODEL_REGISTRY["face_detector"]["files"]["deploy.prototxt"]["url"],
        "caffemodel": MODEL_REGISTRY["face_detector"]["files"]["res10_300x300_ssd_iter_140000.caffemodel"]["url"],
        "local_prototxt": "deploy.prototxt",
        "local_model": "res10_300x300_ssd_iter_140000.caffemodel",
    },
    "yolov4_tiny": {
        "cfg": MODEL_REGISTRY["yolov4_tiny"]["files"]["yolov4-tiny.cfg"]["url"],
        "weights": MODEL_REGISTRY["yolov4_tiny"]["files"]["yolov4-tiny.weights"]["url"],
        "names": MODEL_REGISTRY["yolov4_tiny"]["files"]["coco.names"]["url"],
        "local_cfg": "yolov4-tiny.cfg",
        "local_weights": "yolov4-tiny.weights",
        "local_names": "coco.names",
    },
    "style_transfer": {
        "models": [
            "eccv16/the_wave.t7",
            "eccv16/starry_night.t7",
            "eccv16/la_muse.t7",
            "eccv16/composition_vii.t7",
            "instance_norm/mosaic.t7",
            "instance_norm/candy.t7",
            "instance_norm/rain_princess.t7",
            "instance_norm/udnie.t7",
        ],
        "base_url": "https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/",
    },
    "super_resolution": {
        "ESPCN_x4": {
            "url": MODEL_REGISTRY["espcn_x4"]["files"]["ESPCN_x4.pb"]["url"],
            "local": "ESPCN_x4.pb",
            "scale": 4,
        },
    },
    "east_text": {
        "url": MODEL_REGISTRY["east_text"]["files"]["frozen_east_text_detection.pb"]["url"],
        "local": "frozen_east_text_detection.pb",
    },
}


COCO_CLASSES = [
    "person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck",
    "boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra",
    "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove",
    "skateboard", "surfboard", "tennis racket", "bottle", "wine glass", "cup",
    "fork", "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "sofa",
    "pottedplant", "bed", "diningtable", "toilet", "tvmonitor", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush"
]

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.ts', '.3gp'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'}

SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa'}

LOG_DIR = Path("logs")
LOG_KEEP_FILES = 20          # 只保留最近这么多份日志，避免目录无限膨胀
PRESET_DIR = Path("presets")
CHARSET_DIR = Path("charsets")   # CRNN 的字符表，随项目一起分发
LUT_DIR = Path("luts")           # 用户放 .cube / LUT 贴图的地方

# ── 字体 ────────────────────────────────────────────────────────
# 水印和字幕都要写中文，而 cv2.putText 只有 Hershey 矢量字体、画不出 CJK，
# 所以必须借 PIL 加载系统 TTF/TTC。这里按平台列几个大概率存在的中文字体。
CJK_FONT_CANDIDATES = (
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",      # 黑体
    "C:/Windows/Fonts/simsun.ttc",      # 宋体
    "C:/Windows/Fonts/Deng.ttf",        # 等线
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
)

_cjk_font_cache: Optional[str] = None


def default_cjk_font() -> str:
    """找一个能写中文的系统字体，找不到返回空串。结果缓存"""
    global _cjk_font_cache
    if _cjk_font_cache is None:
        _cjk_font_cache = ""
        for candidate in CJK_FONT_CANDIDATES:
            if os.path.exists(candidate):
                _cjk_font_cache = candidate
                break
        if _cjk_font_cache:
            LOGGER.debug(f"中文字体: {_cjk_font_cache}")
        else:
            LOGGER.warn("未找到中文字体，水印/字幕里的中文会画不出来，"
                        "请在参数面板手动指定 .ttf/.ttc")
    return _cjk_font_cache


def imread_unicode(path: str, flags: int = cv2.IMREAD_COLOR) -> Optional[np.ndarray]:
    """
    读图片。cv2.imread 在 Windows 上遇到中文路径会直接返回 None
    （它用的是 ANSI 版文件 API），所以统一走 fromfile + imdecode。
    """
    try:
        buf = np.fromfile(path, dtype=np.uint8)
        if buf.size == 0:
            return None
        return cv2.imdecode(buf, flags)
    except Exception as e:
        LOGGER.warn(f"读取图片失败: {path} ({e})")
        return None


# ── 水印 / LUT / 字幕 的可选项 ──────────────────────────────────
WATERMARK_POSITIONS = OrderedDict([
    ("top-left", "左上"),
    ("top-center", "上中"),
    ("top-right", "右上"),
    ("middle-left", "左中"),
    ("center", "正中"),
    ("middle-right", "右中"),
    ("bottom-left", "左下"),
    ("bottom-center", "下中"),
    ("bottom-right", "右下"),
    ("custom", "自定义坐标"),
])

WM_REMOVE_METHODS = OrderedDict([
    ("telea", "Inpaint · Telea (快, 适合小 logo)"),
    ("ns", "Inpaint · Navier-Stokes (纹理背景更自然)"),
    ("blur", "高斯模糊遮盖 (不还原, 只糊掉)"),
    ("pixelate", "像素化遮盖 (不还原, 打码)"),
])

LUT_PRESETS = OrderedDict([
    ("cinematic", "电影感 (青橙调)"),
    ("warm_sun", "暖阳"),
    ("cool_blue", "冷调"),
    ("faded_film", "褪色胶片"),
    ("black_gold", "黑金"),
    ("mono_contrast", "高对比黑白"),
    ("vivid", "鲜艳增强"),
])

BG_MODES = OrderedDict([
    ("blur", "虚化背景"),
    ("color", "替换为纯色"),
    ("image", "替换为图片"),
])

OCR_MODELS = OrderedDict([
    ("crnn_cn", "中文 + 英文 (CRNN_CN, 69MB)"),
    ("crnn_en", "仅英文数字 (CRNN_EN, 32MB)"),
])

# ── 输出编码 ────────────────────────────────────────────────
VIDEO_CODEC_CHOICES = OrderedDict([
    ("auto", "自动 (mp4v / XVID，无需 FFmpeg)"),
    ("h264", "H.264 (libx264，需 FFmpeg)"),
    ("h265", "H.265 / HEVC (libx265，需 FFmpeg)"),
    ("mp4v", "MPEG-4 (mp4v)"),
    ("xvid", "XVID (适合 .avi)"),
])
FFMPEG_PRESETS = ("ultrafast", "superfast", "veryfast", "faster", "fast",
                  "medium", "slow", "slower", "veryslow")

# Windows 上用 pythonw 启动时，子进程会弹出一个黑色控制台窗口，这里屏蔽掉
if sys.platform == "win32":
    SUBPROCESS_FLAGS = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
else:
    SUBPROCESS_FLAGS = {}

_ffmpeg_available_cache: Optional[bool] = None


def ffmpeg_available() -> bool:
    """FFmpeg 是否可用。结果缓存，避免每次调用都 fork 一个进程"""
    global _ffmpeg_available_cache
    if _ffmpeg_available_cache is None:
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True,
                           check=True, timeout=15, **SUBPROCESS_FLAGS)
            _ffmpeg_available_cache = True
        except Exception:
            _ffmpeg_available_cache = False
    return _ffmpeg_available_cache


# ════════════════════════════════════════════════════════════════
#  日志
# ════════════════════════════════════════════════════════════════

class AppLogger:
    """
    进程级日志器：同时写内存环形缓冲和磁盘文件。

    处理线程和 GUI 线程都会写日志，所以所有状态都用一把锁保护。
    GUI 侧不注册回调而是按序号轮询 (records_since)，这样 Tk 控件只会
    在主线程里被碰到，不必担心跨线程调用 Tk 的问题。
    """

    LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")
    _LEVEL_INDEX = {name: i for i, name in enumerate(LEVELS)}

    def __init__(self, log_dir: Path = LOG_DIR, keep: int = LOG_KEEP_FILES,
                 buffer_size: int = 5000):
        self._log_dir = Path(log_dir)
        self._keep = keep
        self._lock = threading.Lock()
        self._records: deque = deque(maxlen=buffer_size)
        self._seq = 0
        self._fp = None
        self._file_ready = False
        self.log_path: Optional[Path] = None
        self.file_error: str = ""

    # ── 文件落盘 ────────────────────────────────────────────────

    def _ensure_file(self) -> None:
        """首次写日志时才创建文件，避免 import 阶段产生副作用"""
        if self._file_ready:
            return
        self._file_ready = True
        try:
            self._log_dir.mkdir(parents=True, exist_ok=True)
            self._prune_old_logs()
            self.log_path = self._log_dir / f"videotoolbox_{time.strftime('%Y%m%d_%H%M%S')}.log"
            self._fp = open(self.log_path, "a", encoding="utf-8", buffering=1)
            self._fp.write(
                f"# {APP_NAME} v{APP_VERSION} | Python {sys.version.split()[0]} | "
                f"OpenCV {cv2.__version__}\n")
        except OSError as e:
            self._fp = None
            self.file_error = str(e)

    def _prune_old_logs(self) -> None:
        try:
            files = sorted(self._log_dir.glob("videotoolbox_*.log"),
                           key=lambda p: p.stat().st_mtime)
        except OSError:
            return
        for old in files[:max(0, len(files) - self._keep + 1)]:
            try:
                old.unlink()
            except OSError:
                pass

    # ── 写入 ────────────────────────────────────────────────────

    def log(self, level: str, message: str, exc: bool = False) -> None:
        if exc:
            message = f"{message}\n{traceback.format_exc().rstrip()}"
        stamp = time.strftime("%H:%M:%S")
        with self._lock:
            self._ensure_file()
            self._seq += 1
            self._records.append((self._seq, stamp, level, message))
            if self._fp is not None:
                try:
                    self._fp.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] "
                                   f"{level:<5} {message}\n")
                except OSError as e:
                    self.file_error = str(e)
                    self._fp = None
        if level in ("WARN", "ERROR"):
            line = f"[{level}] {message}"
            try:
                print(line, file=sys.stderr)
            except UnicodeEncodeError:
                # Windows 控制台常常是 GBK，日志里的 emoji 会直接把 print 打挂，
                # 不能让一条日志弄崩正在处理的任务
                enc = getattr(sys.stderr, "encoding", None) or "ascii"
                print(line.encode(enc, "replace").decode(enc, "replace"), file=sys.stderr)

    def debug(self, message: str) -> None:
        self.log("DEBUG", message)

    def info(self, message: str) -> None:
        self.log("INFO", message)

    def warn(self, message: str) -> None:
        self.log("WARN", message)

    def error(self, message: str, exc: bool = False) -> None:
        self.log("ERROR", message, exc=exc)

    # ── 读取 ────────────────────────────────────────────────────

    def records_since(self, seq: int) -> List[Tuple[int, str, str, str]]:
        """返回序号大于 seq 的所有记录，供日志窗口增量刷新"""
        with self._lock:
            return [r for r in self._records if r[0] > seq]

    def all_records(self) -> List[Tuple[int, str, str, str]]:
        with self._lock:
            return list(self._records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    @classmethod
    def level_at_least(cls, level: str, minimum: str) -> bool:
        return cls._LEVEL_INDEX.get(level, 0) >= cls._LEVEL_INDEX.get(minimum, 0)

    def close(self) -> None:
        with self._lock:
            if self._fp is not None:
                try:
                    self._fp.close()
                except OSError:
                    pass
                self._fp = None


LOGGER = AppLogger()


# ════════════════════════════════════════════════════════════════
#  模型下载管理器
# ════════════════════════════════════════════════════════════════

class ModelFileStatus(Enum):
    """模型文件状态"""
    OK = "ok"                    # 正常可用
    MISSING = "missing"          # 缺失
    CORRUPTED = "corrupted"      # 损坏 (太小)
    UNKNOWN = "unknown"          # 未知


@dataclass
class ModelFileInfo:
    """单个模型文件的状态信息"""
    filename: str
    status: ModelFileStatus
    local_size_kb: float = 0
    min_size_kb: float = 0
    url: str = ""
    description: str = ""


@dataclass
class ModelGroupInfo:
    """一组模型的状态"""
    key: str
    display_name: str
    files: List[ModelFileInfo] = field(default_factory=list)

    @property
    def is_ok(self) -> bool:
        return all(f.status == ModelFileStatus.OK for f in self.files)

    @property
    def needs_download(self) -> bool:
        return any(f.status in (ModelFileStatus.MISSING, ModelFileStatus.CORRUPTED)
                   for f in self.files)

    @property
    def status_emoji(self) -> str:
        if self.is_ok:
            return "✅"
        elif any(f.status == ModelFileStatus.CORRUPTED for f in self.files):
            return "⚠️"
        else:
            return "❌"


class ModelManager:
    """模型文件管理器: 检查、下载、校验"""

    def __init__(self, models_dir: Path):
        self.models_dir = models_dir
        self.models_dir.mkdir(exist_ok=True)
        self._download_cancel = False

    def check_all_models(self) -> List[ModelGroupInfo]:
        """检查所有注册模型的状态"""
        results = []
        for key, reg in MODEL_REGISTRY.items():
            group = ModelGroupInfo(key=key, display_name=reg["display_name"])
            for filename, file_info in reg["files"].items():
                fpath = self.models_dir / filename
                min_kb = file_info.get("min_size_kb", 0)
                url = file_info.get("url", "")
                desc = file_info.get("description", "")

                if not fpath.exists():
                    status = ModelFileStatus.MISSING
                    local_kb = 0
                else:
                    local_kb = fpath.stat().st_size / 1024
                    if min_kb > 0 and local_kb < min_kb * 0.8:
                        status = ModelFileStatus.CORRUPTED
                    else:
                        status = ModelFileStatus.OK

                group.files.append(ModelFileInfo(
                    filename=filename,
                    status=status,
                    local_size_kb=local_kb,
                    min_size_kb=min_kb,
                    url=url,
                    description=desc,
                ))
            results.append(group)
        return results

    def get_downloadable_files(self) -> List[Tuple[str, ModelFileInfo]]:
        """获取需要下载的文件列表 (缺失 + 损坏)"""
        need = []
        groups = self.check_all_models()
        for group in groups:
            for f in group.files:
                if f.status in (ModelFileStatus.MISSING, ModelFileStatus.CORRUPTED):
                    need.append((group.key, f))
        return need

    def download_file(self, url: str, dest_path: Path,
                      progress_callback: Optional[Callable[[float, str], None]] = None,
                      alt_urls: Optional[List[str]] = None) -> bool:
        """
        下载单个文件，支持备用 URL
        """
        urls_to_try = [url]
        if alt_urls:
            urls_to_try.extend(alt_urls)

        for try_url in urls_to_try:
            if self._download_cancel:
                return False
            try:
                if progress_callback:
                    progress_callback(0, f"下载: {dest_path.name}\n{try_url}")

                req = urllib.request.Request(try_url, headers={
                    'User-Agent': 'Mozilla/5.0 (VideoToolbox Model Downloader)'
                })
                response = urllib.request.urlopen(req, timeout=30)
                total_size = int(response.headers.get('Content-Length', 0))

                tmp_path = dest_path.with_suffix(dest_path.suffix + '.tmp')
                downloaded = 0
                block_size = 8192

                with open(tmp_path, 'wb') as f:
                    while not self._download_cancel:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            pct = downloaded / total_size
                            size_mb = downloaded / 1024 / 1024
                            total_mb = total_size / 1024 / 1024
                            progress_callback(
                                pct,
                                f"下载: {dest_path.name}\n"
                                f"{size_mb:.1f}/{total_mb:.1f} MB ({pct * 100:.1f}%)"
                            )
                        elif progress_callback:
                            size_mb = downloaded / 1024 / 1024
                            progress_callback(-1, f"下载: {dest_path.name} ({size_mb:.1f} MB)")

                if self._download_cancel:
                    tmp_path.unlink(missing_ok=True)
                    return False

                # 下载完成，重命名
                if dest_path.exists():
                    dest_path.unlink()
                tmp_path.rename(dest_path)

                if progress_callback:
                    final_size = dest_path.stat().st_size / 1024 / 1024
                    progress_callback(1.0, f"✅ {dest_path.name} ({final_size:.2f} MB)")
                return True

            except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
                if progress_callback:
                    progress_callback(-1, f"❌ 下载失败: {e}\n尝试下一个URL...")
                continue
            except Exception as e:
                if progress_callback:
                    progress_callback(-1, f"❌ 未知错误: {e}")
                continue

        return False

    def cancel_download(self):
        self._download_cancel = True

    def reset_cancel(self):
        self._download_cancel = False


# ════════════════════════════════════════════════════════════════
#  数据类
# ════════════════════════════════════════════════════════════════

@dataclass
class VideoInfo:
    """视频信息"""
    path: str = ""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    frame_count: int = 0
    duration: float = 0.0
    codec: str = ""
    file_size: int = 0

    @property
    def resolution_str(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def duration_str(self) -> str:
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def size_str(self) -> str:
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 ** 2:
            return f"{self.file_size / 1024:.1f} KB"
        elif self.file_size < 1024 ** 3:
            return f"{self.file_size / 1024 ** 2:.1f} MB"
        else:
            return f"{self.file_size / 1024 ** 3:.2f} GB"


class ProcessingTask(Enum):
    """处理任务类型"""
    TRIM = auto()
    RESIZE = auto()
    ROTATE = auto()
    CONCAT = auto()
    FPS_CHANGE = auto()
    TO_GIF = auto()
    EXTRACT_FRAMES = auto()

    BRIGHTNESS_CONTRAST = auto()
    COLOR_SPACE = auto()
    HISTOGRAM_EQ = auto()
    SHARPEN_BLUR = auto()

    SKETCH = auto()
    CARTOON = auto()
    EMBOSS = auto()
    EDGE_DETECT = auto()
    COLOR_TONE = auto()
    MOSAIC = auto()
    VIGNETTE = auto()

    FACE_DETECT = auto()
    OBJECT_DETECT = auto()
    STYLE_TRANSFER = auto()
    STYLE_REFERENCE = auto()
    FACE_MOSAIC = auto()
    BG_BLUR = auto()
    TEXT_DETECT = auto()
    DEMOSAIC = auto()  # ★ 新增: 去马赛克/超分重建

    WATERMARK_ADD = auto()
    WATERMARK_REMOVE = auto()
    LUT_GRADE = auto()
    SUBTITLE_BURN = auto()
    SUBTITLE_OCR = auto()

    BRIGHTNESS_CURVE = auto()
    COLOR_HISTOGRAM = auto()
    MOTION_HEATMAP = auto()

    PIPELINE = auto()


VIDEO_OUTPUT_TASKS = {
    ProcessingTask.TRIM,
    ProcessingTask.RESIZE,
    ProcessingTask.ROTATE,
    ProcessingTask.FPS_CHANGE,
    ProcessingTask.BRIGHTNESS_CONTRAST,
    ProcessingTask.COLOR_SPACE,
    ProcessingTask.HISTOGRAM_EQ,
    ProcessingTask.SHARPEN_BLUR,
    ProcessingTask.SKETCH,
    ProcessingTask.CARTOON,
    ProcessingTask.EMBOSS,
    ProcessingTask.EDGE_DETECT,
    ProcessingTask.COLOR_TONE,
    ProcessingTask.MOSAIC,
    ProcessingTask.VIGNETTE,
    ProcessingTask.FACE_DETECT,
    ProcessingTask.OBJECT_DETECT,
    ProcessingTask.STYLE_TRANSFER,
    ProcessingTask.STYLE_REFERENCE,
    ProcessingTask.FACE_MOSAIC,
    ProcessingTask.BG_BLUR,
    ProcessingTask.TEXT_DETECT,
    ProcessingTask.DEMOSAIC,
    ProcessingTask.WATERMARK_ADD,
    ProcessingTask.WATERMARK_REMOVE,
    ProcessingTask.LUT_GRADE,
    ProcessingTask.SUBTITLE_BURN,
}

ANALYSIS_TASKS = {
    ProcessingTask.BRIGHTNESS_CURVE,
    ProcessingTask.COLOR_HISTOGRAM,
    ProcessingTask.MOTION_HEATMAP,
}

# 产出的是文本文件而不是视频/图片
TEXT_OUTPUT_TASKS = {
    ProcessingTask.SUBTITLE_OCR,
}

# 功能搜索用的英文/拼音别名，避免必须切回中文输入法才能搜
FUNCTION_KEYWORDS: Dict[ProcessingTask, str] = {
    ProcessingTask.TRIM: "trim cut clip caijian jianqie 剪辑 截取",
    ProcessingTask.RESIZE: "resize scale resolution suofang 分辨率",
    ProcessingTask.ROTATE: "rotate flip mirror xuanzhuan fanzhuan 镜像",
    ProcessingTask.CONCAT: "concat merge join pinjie 合并 合成",
    ProcessingTask.FPS_CHANGE: "fps framerate zhenlv 帧率",
    ProcessingTask.TO_GIF: "gif animation dongtu 动图",
    ProcessingTask.EXTRACT_FRAMES: "extract frames snapshot tiqu 截图 逐帧",
    ProcessingTask.BRIGHTNESS_CONTRAST: "brightness contrast saturation gamma liangdu duibidu 曝光",
    ProcessingTask.COLOR_SPACE: "colorspace gray hsv lab huidu 灰度",
    ProcessingTask.HISTOGRAM_EQ: "histogram equalize clahe zhifangtu 均衡",
    ProcessingTask.SHARPEN_BLUR: "sharpen blur denoise ruihua mohu jiangzao 降噪",
    ProcessingTask.SKETCH: "sketch pencil qianbi sumiao 素描",
    ProcessingTask.CARTOON: "cartoon anime katong 动漫",
    ProcessingTask.EMBOSS: "emboss relief fudiao",
    ProcessingTask.EDGE_DETECT: "edge canny sobel laplacian bianyuan 轮廓",
    ProcessingTask.COLOR_TONE: "tone warm cool sepia vintage setiao lvjing 滤镜",
    ProcessingTask.MOSAIC: "mosaic pixelate masaike xiangsuhua 打码 像素",
    ProcessingTask.VIGNETTE: "vignette yunying 暗角",
    ProcessingTask.FACE_DETECT: "face detect renlian 人脸 检测",
    ProcessingTask.OBJECT_DETECT: "object yolo detect wuti 目标 检测",
    ProcessingTask.STYLE_TRANSFER: "style transfer fengge qianyi 风格",
    ProcessingTask.STYLE_REFERENCE: "style reference fengge cankaotu 参考图 调色",
    ProcessingTask.FACE_MOSAIC: "face mosaic blur renlian masaike 打码 隐私",
    ProcessingTask.BG_BLUR: "background blur bokeh beijing xuhua 虚化 抠像",
    ProcessingTask.TEXT_DETECT: "text east ocr wenzi zimu 字幕 文字",
    ProcessingTask.DEMOSAIC: "demosaic deepmosaics esrgan superresolution qumasaike chaofen 去码 超分",
    ProcessingTask.WATERMARK_ADD: "watermark logo shuiyin ddtu 加水印 台标 版权",
    ProcessingTask.WATERMARK_REMOVE: "watermark remove inpaint qushuiyin xiufu 去水印 去台标 修补",
    ProcessingTask.LUT_GRADE: "lut cube grading colorgrade tiaose fenji 调色 分级 滤镜",
    ProcessingTask.SUBTITLE_BURN: "subtitle srt ass burn hardsub zimu shaolu 烧录 内嵌 硬字幕",
    ProcessingTask.SUBTITLE_OCR: "subtitle ocr crnn east recognize zimu shibie 识别 提取字幕 导出srt",
    ProcessingTask.BRIGHTNESS_CURVE: "brightness curve analyze liangdu quxian 分析",
    ProcessingTask.COLOR_HISTOGRAM: "color histogram yanse zhifangtu 分析",
    ProcessingTask.MOTION_HEATMAP: "motion heatmap yundong relitu 分析",
    ProcessingTask.PIPELINE: "pipeline chain batch liuchengzuhe 串联 组合",
}


@dataclass
class ProcessingParams:
    """处理参数"""
    task: ProcessingTask = ProcessingTask.TRIM

    input_path: str = ""
    output_path: str = ""
    start_time: float = 0.0
    end_time: float = -1.0

    target_width: int = 0
    target_height: int = 0
    keep_aspect: bool = True
    interpolation: int = cv2.INTER_LINEAR

    rotation: int = 0
    flip_h: bool = False
    flip_v: bool = False

    target_fps: float = 30.0

    brightness: int = 0
    contrast: float = 1.0
    saturation: float = 1.0
    gamma: float = 1.0

    color_space: str = "BGR"

    blur_type: str = "none"
    blur_ksize: int = 5
    sharpen_strength: float = 0.0
    denoise_strength: int = 0

    edge_type: str = "canny"
    canny_low: int = 50
    canny_high: int = 150

    tone_type: str = "none"

    mosaic_size: int = 15
    mosaic_region: Tuple[int, int, int, int] = (0, 0, 0, 0)

    dnn_confidence: float = 0.5
    dnn_nms_threshold: float = 0.4
    style_model_name: str = ""
    style_reference_path: str = ""
    style_strength: float = 1.0
    sr_scale: int = 4

    # ★ 去马赛克参数
    demosaic_model: str = "real_esrgan_x4"  # real_esrgan_x4 / real_esrgan_anime / espcn_x4
    demosaic_region: Tuple[int, int, int, int] = (0, 0, 0, 0)  # 局部去马赛克区域
    demosaic_full: bool = True  # True=全画面, False=局部区域
    demosaic_tile_size: int = 128  # 分块处理大小

    # ★ 水印添加
    watermark_type: str = "text"              # text / image
    watermark_text: str = ""
    watermark_image_path: str = ""
    watermark_font_path: str = ""             # 空=自动挑一个系统中文字体
    watermark_font_size: int = 42
    watermark_color: str = "#FFFFFF"
    watermark_outline_color: str = "#000000"
    watermark_outline_width: int = 2
    watermark_opacity: float = 0.75
    watermark_scale: float = 0.18             # 图片水印宽度占画面宽度的比例
    watermark_position: str = "bottom-right"
    watermark_margin: int = 24
    watermark_custom_x: int = 0
    watermark_custom_y: int = 0
    watermark_rotation: float = 0.0
    watermark_tile: bool = False              # 平铺满屏，用于防盗录
    watermark_tile_gap: int = 80

    # ★ 水印去除
    wm_remove_regions: str = ""               # "x,y,w,h" 多个区域用 ; 或换行分隔
    wm_remove_method: str = "telea"
    wm_remove_smart_mask: bool = True         # True=只修水印笔画, False=整块重绘
    wm_remove_sensitivity: int = 22
    wm_remove_radius: int = 4
    wm_remove_grow: int = 3                   # 蒙版向外扩张的像素数

    # ★ LUT 颜色分级
    lut_source: str = "preset"                # preset / file
    lut_preset: str = "cinematic"
    lut_path: str = ""
    lut_strength: float = 1.0
    lut_fast: bool = False                    # True=最近邻查表(快), False=三线性插值

    # ★ 字幕烧录
    subtitle_path: str = ""
    subtitle_font_path: str = ""
    subtitle_font_size: int = 0               # 0=按画面高度自动
    subtitle_color: str = "#FFFFFF"
    subtitle_outline_color: str = "#000000"
    subtitle_outline_width: int = 3
    subtitle_bottom_margin: int = 40
    subtitle_box_opacity: float = 0.0         # >0 时在文字后垫一层半透明黑条
    subtitle_time_offset: float = 0.0

    # ★ 背景虚化 / 人像分割
    seg_method: str = "rvm"                   # rvm (真分割) / face_box (人脸框启发式)
    seg_downsample: float = 0.0               # RVM 下采样比例, 0=按分辨率自动
    seg_feather: int = 3
    bg_mode: str = "blur"                     # blur / color / image
    bg_blur_strength: int = 35
    bg_color: str = "#1E1E1E"
    bg_image_path: str = ""

    # ★ 字幕 OCR
    ocr_model: str = "crnn_cn"
    ocr_band_top: float = 0.70                # 只在这个纵向区间里找字幕 (画面高度比例)
    ocr_band_bottom: float = 1.0
    ocr_sample_interval: float = 0.3          # 采样间隔 (秒)
    ocr_min_duration: float = 0.4             # 短于此的条目丢掉，多半是误检

    concat_files: List[str] = field(default_factory=list)

    gif_fps: int = 10
    gif_scale: float = 0.5
    gif_max_colors: int = 256

    extract_interval: float = 1.0
    extract_format: str = "jpg"

    # ★ 输出编码 (见 FrameSink)
    video_codec: str = "auto"        # auto / mp4v / xvid / h264 / h265
    rate_mode: str = "crf"           # crf (恒定质量) / bitrate (目标码率)
    crf: int = 20                    # 0=无损, 18~23 视觉无损, 越大越小越糊
    bitrate_kbps: int = 4000
    encode_preset: str = "medium"
    keep_audio: bool = True

    pipeline_tasks: List[ProcessingTask] = field(default_factory=list)


class BatchStatus(Enum):
    """批处理队列中单个任务的状态"""
    PENDING = "等待中"
    RUNNING = "处理中"
    DONE = "已完成"
    FAILED = "失败"
    SKIPPED = "已跳过"
    CANCELLED = "已取消"


@dataclass
class BatchJob:
    """批处理队列的一项：一个输入文件 + 它的输出路径和状态"""
    input_path: str
    output_path: str = ""
    status: BatchStatus = BatchStatus.PENDING
    message: str = ""

    @property
    def name(self) -> str:
        return os.path.basename(self.input_path)


# ════════════════════════════════════════════════════════════════
#  GIF 编码器 (纯 Python 实现，不依赖 FFmpeg)
# ════════════════════════════════════════════════════════════════

class GIFEncoder:
    """
    纯 Python GIF 编码器
    支持: 动画GIF、全局/局部色表、LZW压缩
    优先使用 PIL (如果可用)，否则用纯字节写入
    """

    @staticmethod
    def save_gif_pil(frames_bgr: List[np.ndarray], output_path: str,
                     fps: int = 10, loop: int = 0) -> bool:
        if not HAS_PIL:
            return False
        try:
            pil_frames = []
            for frame_bgr in frames_bgr:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                pil_img = PILImage.fromarray(frame_rgb)
                pil_img = pil_img.quantize(colors=256, method=PILImage.Quantize.MEDIANCUT)
                pil_frames.append(pil_img)
            if not pil_frames:
                return False
            duration_ms = max(20, int(1000 / fps))
            pil_frames[0].save(
                output_path, save_all=True, append_images=pil_frames[1:],
                duration=duration_ms, loop=loop, optimize=True
            )
            return True
        except Exception as e:
            LOGGER.warn(f"PIL GIF 保存失败: {e}")
            return False

    @staticmethod
    def save_gif_raw(frames_bgr: List[np.ndarray], output_path: str,
                     fps: int = 10, loop: int = 0, max_colors: int = 256) -> bool:
        if not frames_bgr:
            return False
        try:
            delay_cs = max(2, int(100 / fps))
            max_colors = min(256, max(2, max_colors))
            color_bits = 1
            while (1 << color_bits) < max_colors:
                color_bits += 1
            actual_colors = 1 << color_bits
            h, w = frames_bgr[0].shape[:2]
            with open(output_path, 'wb') as f:
                f.write(b'GIF89a')
                f.write(struct.pack('<HH', w, h))
                packed = 0x80 | ((color_bits - 1) << 4) | (color_bits - 1)
                f.write(struct.pack('BBB', packed, 0, 0))
                first_rgb = cv2.cvtColor(frames_bgr[0], cv2.COLOR_BGR2RGB)
                global_palette = GIFEncoder._median_cut_palette(first_rgb, actual_colors)
                for r, g, b in global_palette:
                    f.write(struct.pack('BBB', r, g, b))
                f.write(b'\x21\xFF\x0BNETSCAPE2.0')
                f.write(struct.pack('<BHB', 3, loop, 0))
                for frame_bgr in frames_bgr:
                    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                    if frame_rgb.shape[0] != h or frame_rgb.shape[1] != w:
                        frame_rgb = cv2.resize(frame_rgb, (w, h))
                    indices = GIFEncoder._quantize_frame(frame_rgb, global_palette)
                    f.write(b'\x21\xF9')
                    f.write(struct.pack('<BBHBB', 4, 0x00, delay_cs, 0, 0))
                    f.write(b'\x2C')
                    f.write(struct.pack('<HHHH', 0, 0, w, h))
                    f.write(b'\x00')
                    min_code_size = max(2, color_bits)
                    f.write(struct.pack('B', min_code_size))
                    compressed = GIFEncoder._lzw_compress(indices, min_code_size)
                    pos = 0
                    while pos < len(compressed):
                        chunk = compressed[pos:pos + 255]
                        f.write(struct.pack('B', len(chunk)))
                        f.write(chunk)
                        pos += 255
                    f.write(b'\x00')
                f.write(b'\x3B')
            return True
        except Exception as e:
            LOGGER.error(f"原始 GIF 编码失败: {e}", exc=True)
            return False

    @staticmethod
    def _median_cut_palette(img_rgb: np.ndarray, num_colors: int) -> List[Tuple[int, int, int]]:
        pixels = img_rgb.reshape(-1, 3).astype(np.float32)
        if len(pixels) > 50000:
            indices = np.random.choice(len(pixels), 50000, replace=False)
            pixels = pixels[indices]
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        k = min(num_colors, len(pixels))
        if k < 2:
            k = 2
        try:
            _, _, centers = cv2.kmeans(pixels, k, None, criteria, 3, cv2.KMEANS_PP_CENTERS)
            palette = [(int(c[0]), int(c[1]), int(c[2])) for c in centers]
        except Exception:
            palette = []
            step = max(1, len(pixels) // num_colors)
            for i in range(0, len(pixels), step):
                if len(palette) >= num_colors:
                    break
                p = pixels[i]
                palette.append((int(p[0]), int(p[1]), int(p[2])))
        while len(palette) < num_colors:
            palette.append((0, 0, 0))
        return palette[:num_colors]

    @staticmethod
    def _quantize_frame(img_rgb: np.ndarray,
                        palette: List[Tuple[int, int, int]]) -> np.ndarray:
        h, w = img_rgb.shape[:2]
        palette_arr = np.array(palette, dtype=np.float32)
        pixels = img_rgb.reshape(-1, 3).astype(np.float32)
        batch_size = 10000
        indices = np.zeros(len(pixels), dtype=np.uint8)
        for start in range(0, len(pixels), batch_size):
            end = min(start + batch_size, len(pixels))
            batch = pixels[start:end]
            diff = batch[:, np.newaxis, :] - palette_arr[np.newaxis, :, :]
            dist = np.sum(diff ** 2, axis=2)
            indices[start:end] = np.argmin(dist, axis=1).astype(np.uint8)
        return indices

    @staticmethod
    def _lzw_compress(indices: np.ndarray, min_code_size: int) -> bytes:
        clear_code = 1 << min_code_size
        eoi_code = clear_code + 1
        output_bits = []
        current_bit_size = min_code_size + 1
        table = {}
        next_code = eoi_code + 1
        max_code = (1 << current_bit_size)

        def emit(code):
            for bit in range(current_bit_size):
                output_bits.append((code >> bit) & 1)

        def reset_table():
            nonlocal table, next_code, current_bit_size, max_code
            table.clear()
            for i in range(clear_code):
                table[(i,)] = i
            next_code = eoi_code + 1
            current_bit_size = min_code_size + 1
            max_code = 1 << current_bit_size

        emit(clear_code)
        reset_table()

        if len(indices) == 0:
            emit(eoi_code)
        else:
            buffer = (int(indices[0]),)
            for i in range(1, len(indices)):
                symbol = int(indices[i])
                test = buffer + (symbol,)
                if test in table:
                    buffer = test
                else:
                    emit(table[buffer])
                    if next_code < 4096:
                        table[test] = next_code
                        next_code += 1
                        if next_code > max_code and current_bit_size < 12:
                            current_bit_size += 1
                            max_code = 1 << current_bit_size
                    else:
                        emit(clear_code)
                        reset_table()
                    buffer = (symbol,)
            if buffer in table:
                emit(table[buffer])
            emit(eoi_code)

        result = bytearray()
        for i in range(0, len(output_bits), 8):
            byte_val = 0
            for bit_idx in range(8):
                if i + bit_idx < len(output_bits):
                    byte_val |= output_bits[i + bit_idx] << bit_idx
            result.append(byte_val)
        return bytes(result)


# ════════════════════════════════════════════════════════════════
#  马赛克区域检测
# ════════════════════════════════════════════════════════════════

class MosaicDetector:
    """
    传统 CV 的马赛克区域检测，不依赖任何模型。

    分两步。先做粗筛：马赛克的独特之处是「局部对比度高，但绝大多数像素梯度为零」
    ——细节丰富的区域到处都有梯度，平滑区域则对比度低，只有马赛克两者兼具。
    这一步不需要知道块大小和相位。

    再逐区域确认：对每个候选连通域单独做梯度投影的周期检验，
    确认边缘确实落在规则栅格上才保留。投影限制在候选区域内做，
    否则画面其余部分的内容边缘会把栅格信号淹没。
    """

    MIN_BLOCK = 6
    MAX_BLOCK = 48

    CONCENTRATION_THRESH = 0.45

    @classmethod
    def _fold(cls, sig: np.ndarray, period: int) -> Optional[np.ndarray]:
        rows = sig.size // period
        if rows < 3:
            return None
        return sig[:rows * period].reshape(rows, period).sum(axis=0)

    @classmethod
    def _comb_period(cls, proj: np.ndarray) -> Tuple[int, float]:
        """
        返回 (周期, 集中度)。

        栅格线周期性地落在同一个相位上，把投影按候选周期折叠后能量会集中到
        单个 bin。真周期 b 的集中度接近 1；折成 2b 时能量分到两个 bin 只剩
        约 0.5，非整除的周期则接近均匀分布。b 的约数集中度同样很高，
        所以在超过阈值的候选里取最大的那个，避免落到约数上。
        """
        if proj.size < cls.MIN_BLOCK * 3:
            return 0, 0.0
        strong = np.where(proj > proj.mean() + proj.std(), proj, 0.0)
        if strong.sum() <= 1e-6:
            return 0, 0.0

        best = (0, 0.0)
        for period in range(cls.MIN_BLOCK, min(cls.MAX_BLOCK, proj.size // 3) + 1):
            folded = cls._fold(strong, period)
            if folded is None or folded.sum() <= 1e-6:
                continue
            concentration = float(folded.max() / folded.sum())
            if concentration >= cls.CONCENTRATION_THRESH:
                best = (period, concentration)
        return best

    @classmethod
    def _verify_grid(cls, gray_roi: np.ndarray) -> int:
        """在候选区域内确认存在规则栅格，返回块大小，0 表示不是马赛克"""
        if min(gray_roi.shape[:2]) < cls.MIN_BLOCK * 3:
            return 0
        gx = np.abs(cv2.Sobel(gray_roi, cv2.CV_32F, 1, 0, ksize=3)).sum(axis=0)
        gy = np.abs(cv2.Sobel(gray_roi, cv2.CV_32F, 0, 1, ksize=3)).sum(axis=1)
        bx, cx = cls._comb_period(gx)
        by, cy = cls._comb_period(gy)
        if not bx or not by:
            return 0
        # 真实马赛克的横竖周期一致；只有单方向成立多半是条纹或栏杆之类的误检
        if abs(bx - by) > max(1, min(bx, by) // 4):
            return 0
        return bx if cx >= cy else by

    @classmethod
    def _coarse_mask(cls, gray: np.ndarray, window: int = 33,
                     flat_ratio_thresh: float = 0.45,
                     contrast_thresh: float = 10.0) -> np.ndarray:
        """粗筛：梯度稀疏 且 局部对比度高"""
        grad = (np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) +
                np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)))
        flat = (grad < 12.0).astype(np.float32)

        win = (window, window)
        flat_ratio = cv2.boxFilter(flat, -1, win)
        mean = cv2.boxFilter(gray, -1, win)
        var = cv2.boxFilter(gray * gray, -1, win) - mean * mean
        std = np.sqrt(np.maximum(var, 0.0))

        mask = ((flat_ratio > flat_ratio_thresh) & (std > contrast_thresh))
        return mask.astype(np.uint8) * 255

    @staticmethod
    def _kernel(size: int) -> np.ndarray:
        size = max(3, int(size) | 1)
        return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))

    @classmethod
    def detect_regions(cls, frame: np.ndarray, min_area: int = 1500
                       ) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray, int]:
        """返回 (矩形区域列表, 掩膜, 块大小)，区域按面积从大到小排序"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        coarse = cls._coarse_mask(gray)
        coarse = cv2.morphologyEx(coarse, cv2.MORPH_OPEN, cls._kernel(9))
        coarse = cv2.morphologyEx(coarse, cv2.MORPH_CLOSE, cls._kernel(31))

        count, labels, stats, _ = cv2.connectedComponentsWithStats(coarse, connectivity=8)
        mask = np.zeros(frame.shape[:2], np.uint8)
        found: List[Tuple[int, int, int, int, int, int]] = []

        for i in range(1, count):
            if stats[i, cv2.CC_STAT_AREA] < min_area:
                continue
            x, y = int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP])
            w, h = int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
            block = cls._verify_grid(gray[y:y + h, x:x + w])
            if block <= 0:
                continue
            mask[labels == i] = 255
            found.append((x, y, w, h, int(stats[i, cv2.CC_STAT_AREA]), block))

        if not found:
            return [], mask, 0
        found.sort(key=lambda r: r[4], reverse=True)
        return [r[:4] for r in found], mask, found[0][5]


# ════════════════════════════════════════════════════════════════
#  DNN 引擎
# ════════════════════════════════════════════════════════════════
# 尝试导入 onnxruntime（去马赛克核心依赖）
try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

# onnx 用于重写 Real-ESRGAN 的输入尺寸，见 _build_static_onnx
try:
    import onnx as onnx_mod
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

class DNNEngine:
    """OpenCV DNN 模块管理器"""

    # ── DeepMosaics 常量 ──
    DM_DETECTOR_FILE = "mosaic_position.onnx"
    DM_GENERATOR_FILE = "clean_youknow_video.onnx"
    DM_DETECT_SIZE = 360   # BiSeNet 检测器输入
    DM_GEN_SIZE = 256      # BVDNet 生成器输入
    DM_GEN_T = 5           # 时序窗口帧数
    DM_GEN_N = 2           # 待重建帧在窗口中的下标
    DM_GEN_STRIDE = 3      # 窗口内抽帧间隔
    DM_HISTORY = DM_GEN_N * DM_GEN_STRIDE + 1  # 需要回溯的历史帧数

    # ── RobustVideoMatting (人像分割) ──
    RVM_FILE = "rvm_mobilenetv3_fp32.onnx"
    RVM_MAX_SIDE = 512     # 自动下采样时，推理内部长边不超过这个值

    # ── CRNN (文字识别) ──
    # (onnx 文件, 字符表文件, 是否喂彩色图)。EN 模型按灰度训练，CN 模型按 BGR。
    CRNN_MODELS = {
        "crnn_cn": ("text_recognition_CRNN_CN_2021nov.onnx", "charset_3944_CN.txt", True),
        "crnn_en": ("text_recognition_CRNN_EN_2021sep.onnx", "charset_36_EN.txt", False),
    }
    CRNN_INPUT_SIZE = (100, 32)   # 模型导出时就固定成这个尺寸了

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        self._nets: Dict[str, cv2.dnn.Net] = {}
        self._ort_model_paths: Dict[str, Path] = {}
        self._ort_sessions: Dict[Tuple[str, int], Any] = {}  # (模型key, 分块尺寸) → session
        self._dm_detector: Any = None
        self._dm_generator: Any = None
        self._dm_history: deque = deque(maxlen=self.DM_HISTORY)
        self._dm_previous: Optional[np.ndarray] = None
        self._coco_classes: List[str] = COCO_CLASSES
        self._coco_colors: Optional[np.ndarray] = None
        self._load_errors: Dict[str, str] = {}
        # 已经提示过「回退传统方法」的模型，避免每帧刷一条日志
        self._demosaic_fallback_warned: set = set()
        self._rvm: Any = None
        self._rvm_output_names: List[str] = []
        self._rvm_state: List[np.ndarray] = []
        self._rvm_failed = False
        self._crnn_charsets: Dict[str, str] = {}

    def _get_model_path(self, filename: str) -> Path:
        return self.models_dir / filename

    def _check_model_exists(self, *filenames: str) -> bool:
        return all((self.models_dir / f).exists() for f in filenames)

    def _check_model_valid(self, filepath: Path, min_size_kb: int = 10) -> bool:
        if not filepath.exists():
            return False
        return filepath.stat().st_size >= min_size_kb * 1024

    def get_load_error(self, key: str) -> str:
        return self._load_errors.get(key, "")

    def get_available_models(self) -> Dict[str, bool]:
        available = {}
        fc = MODEL_URLS["face_detector"]
        available["face_detector"] = self._check_model_exists(
            fc["local_prototxt"], fc["local_model"])
        yc = MODEL_URLS["yolov4_tiny"]
        available["yolov4_tiny"] = self._check_model_exists(
            yc["local_cfg"], yc["local_weights"])
        available["style_transfer"] = any(
            self._check_model_valid(self.models_dir / m.split("/")[-1], min_size_kb=100)
            for m in MODEL_URLS["style_transfer"]["models"])
        sr = MODEL_URLS["super_resolution"]["ESPCN_x4"]
        available["super_resolution"] = self._check_model_exists(sr["local"])
        et = MODEL_URLS["east_text"]
        available["east_text"] = self._check_model_exists(et["local"])
        # ★ 去马赛克模型
        available["real_esrgan"] = (
            self._check_model_valid(self.models_dir / "realesrgan-x4plus.onnx", 50000) or
            self._check_model_valid(self.models_dir / "realesrgan-animevideov3.onnx", 10000)
        )
        available["rvm_matting"] = self._check_model_valid(
            self.models_dir / self.RVM_FILE, 12000)
        for key, (onnx_name, charset_name, _) in self.CRNN_MODELS.items():
            available[key] = (self._check_model_valid(self.models_dir / onnx_name, 20000)
                              and (CHARSET_DIR / charset_name).exists())
        return available

    # ── 人脸检测 ──────────────────────────────────────────────

    def load_face_detector(self) -> bool:
        if "face_detector" in self._nets:
            return True
        fc = MODEL_URLS["face_detector"]
        proto = str(self._get_model_path(fc["local_prototxt"]))
        model = str(self._get_model_path(fc["local_model"]))
        if not (os.path.exists(proto) and os.path.exists(model)):
            self._load_errors["face_detector"] = "模型文件不存在"
            return False
        try:
            net = cv2.dnn.readNetFromCaffe(proto, model)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._nets["face_detector"] = net
            return True
        except Exception as e:
            self._load_errors["face_detector"] = str(e)
            return False

    def detect_faces(self, frame: np.ndarray,
                     conf_threshold: float = 0.5) -> List[Tuple[int, int, int, int, float]]:
        net = self._nets.get("face_detector")
        if net is None:
            return []
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0),
                                     swapRB=False, crop=False)
        net.setInput(blob)
        detections = net.forward()
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > conf_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                x1, y1, x2, y2 = box.astype(int)
                x1, y1 = max(0, x1), max(0, y1)
                x2, y2 = min(w, x2), min(h, y2)
                faces.append((x1, y1, x2 - x1, y2 - y1, float(confidence)))
        return faces

    # ── YOLO 物体检测 ─────────────────────────────────────────

    def load_yolo(self) -> bool:
        if "yolo" in self._nets:
            return True
        yc = MODEL_URLS["yolov4_tiny"]
        cfg = str(self._get_model_path(yc["local_cfg"]))
        weights = str(self._get_model_path(yc["local_weights"]))
        if not (os.path.exists(cfg) and os.path.exists(weights)):
            self._load_errors["yolo"] = "模型文件不存在"
            return False
        names_path = self._get_model_path(yc["local_names"])
        if names_path.exists():
            with open(names_path, "r") as f:
                self._coco_classes = [line.strip() for line in f.readlines()]
        try:
            net = cv2.dnn.readNetFromDarknet(cfg, weights)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._nets["yolo"] = net
            np.random.seed(42)
            self._coco_colors = np.random.randint(0, 255, size=(len(self._coco_classes), 3))
            return True
        except Exception as e:
            self._load_errors["yolo"] = str(e)
            return False

    def detect_objects(self, frame: np.ndarray,
                       conf_threshold: float = 0.5,
                       nms_threshold: float = 0.4) -> List[Dict]:
        net = self._nets.get("yolo")
        if net is None:
            return []
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        net.setInput(blob)
        layer_names = net.getLayerNames()
        output_layers = [layer_names[i - 1] for i in net.getUnconnectedOutLayers().flatten()]
        outputs = net.forward(output_layers)
        boxes, confidences, class_ids = [], [], []
        for output in outputs:
            for detection in output:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > conf_threshold:
                    center_x = int(detection[0] * w)
                    center_y = int(detection[1] * h)
                    bw = int(detection[2] * w)
                    bh = int(detection[3] * h)
                    x = int(center_x - bw / 2)
                    y = int(center_y - bh / 2)
                    boxes.append([x, y, bw, bh])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)
        indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                results.append({
                    "box": boxes[i], "confidence": confidences[i],
                    "class_id": class_ids[i],
                    "class_name": self._coco_classes[class_ids[i]]
                    if class_ids[i] < len(self._coco_classes) else "unknown",
                })
        return results

    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        result = frame.copy()
        for det in detections:
            x, y, w, h = det["box"]
            cid = det["class_id"]
            color = tuple(int(c) for c in self._coco_colors[cid % len(self._coco_colors)])
            cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)
            label = f"{det['class_name']}: {det['confidence']:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(result, (x, y - label_size[1] - 10),
                          (x + label_size[0], y), color, -1)
            cv2.putText(result, label, (x, y - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return result

    # ── 风格迁移 ──────────────────────────────────────────────

    def load_style_transfer(self, model_name: str) -> bool:
        key = f"style_{model_name}"
        if key in self._nets:
            return True
        model_file = model_name.split("/")[-1] if "/" in model_name else model_name
        model_path = self._get_model_path(model_file)
        if not model_path.exists():
            self._load_errors[key] = f"模型文件不存在: {model_file}"
            return False
        file_size = model_path.stat().st_size
        if file_size < 1_000_000:
            self._load_errors[key] = (
                f"模型文件可能不完整: {model_file}\n"
                f"文件大小: {file_size / 1024:.1f} KB（正常应 > 1 MB）\n"
                f"请重新下载完整的 .t7 模型文件")
            return False
        try:
            net = cv2.dnn.readNetFromTorch(str(model_path))
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._nets[key] = net
            self._load_errors.pop(key, None)
            return True
        except cv2.error as e:
            self._load_errors[key] = f"加载失败: {e}"
            return False
        except Exception as e:
            self._load_errors[key] = f"未知错误: {e}"
            return False

    def apply_style_transfer(self, frame: np.ndarray, model_name: str,
                             strength: float = 1.0) -> np.ndarray:
        key = f"style_{model_name}"
        net = self._nets.get(key)
        if net is None:
            return frame
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (w, h),
                                     (103.939, 116.779, 123.680),
                                     swapRB=False, crop=False)
        net.setInput(blob)
        output = net.forward()
        output = output.reshape(3, output.shape[2], output.shape[3])
        output[0] += 103.939
        output[1] += 116.779
        output[2] += 123.680
        output = output.transpose(1, 2, 0)
        styled = np.clip(output, 0, 255).astype(np.uint8)
        if strength < 1.0:
            styled = cv2.addWeighted(styled, max(0, strength), frame, 1.0 - max(0, strength), 0)
        return styled

    def apply_style_reference(self, frame: np.ndarray,
                              reference: np.ndarray,
                              strength: float = 0.7) -> np.ndarray:
        src_lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float64)
        ref_lab = cv2.cvtColor(reference, cv2.COLOR_BGR2LAB).astype(np.float64)
        result = np.zeros_like(src_lab)
        for ch in range(3):
            src_mean, src_std = src_lab[:, :, ch].mean(), max(src_lab[:, :, ch].std(), 1e-6)
            ref_mean, ref_std = ref_lab[:, :, ch].mean(), ref_lab[:, :, ch].std()
            result[:, :, ch] = (src_lab[:, :, ch] - src_mean) * (ref_std / src_std) + ref_mean
        result = np.clip(result, 0, 255).astype(np.uint8)
        styled = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)
        if strength < 1.0:
            styled = cv2.addWeighted(styled, max(0, strength), frame, 1.0 - max(0, strength), 0)
        return styled

    # ── EAST 文字检测 ─────────────────────────────────────────

    def load_east(self) -> bool:
        if "east" in self._nets:
            return True
        et = MODEL_URLS["east_text"]
        model_path = str(self._get_model_path(et["local"]))
        if not os.path.exists(model_path):
            self._load_errors["east"] = "模型文件不存在"
            return False
        try:
            net = cv2.dnn.readNet(model_path)
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._nets["east"] = net
            return True
        except Exception as e:
            self._load_errors["east"] = str(e)
            return False

    def detect_text(self, frame: np.ndarray,
                    conf_threshold: float = 0.5,
                    input_size: Optional[Tuple[int, int]] = None) -> List[np.ndarray]:
        """
        EAST 文字检测，返回若干个 4 点框。

        input_size 是喂给网络的 (宽, 高)，两边都必须是 32 的倍数。默认 320×320
        方形；字幕条那种又宽又扁的输入用方形会把字压变形，调用方应按实际宽高比
        自己算一个尺寸传进来。
        """
        net = self._nets.get("east")
        if net is None:
            return []
        orig_h, orig_w = frame.shape[:2]
        if input_size:
            new_w = max(32, int(input_size[0]) // 32 * 32)
            new_h = max(32, int(input_size[1]) // 32 * 32)
        else:
            new_w, new_h = 320, 320
        ratio_w, ratio_h = orig_w / float(new_w), orig_h / float(new_h)
        blob = cv2.dnn.blobFromImage(frame, 1.0, (new_w, new_h),
                                     (123.68, 116.78, 103.94), swapRB=True, crop=False)
        net.setInput(blob)
        scores, geometry = net.forward([
            "feature_fusion/Conv_7/Sigmoid", "feature_fusion/concat_3"])
        rects, confidences = self._decode_east(scores, geometry, conf_threshold)
        if len(rects) == 0:
            return []
        indices = cv2.dnn.NMSBoxesRotated(rects, confidences, conf_threshold, 0.4)
        results = []
        if len(indices) > 0:
            for i in indices.flatten():
                rect = rects[i]
                rect = ((rect[0][0] * ratio_w, rect[0][1] * ratio_h),
                        (rect[1][0] * ratio_w, rect[1][1] * ratio_h), rect[2])
                box = cv2.boxPoints(rect)
                box = np.asarray(box, dtype=np.intp)
                results.append(box)
        return results

    @staticmethod
    def _decode_east(scores, geometry, conf_threshold):
        num_rows, num_cols = scores.shape[2:4]
        rects, confidences = [], []
        for y in range(num_rows):
            scores_data = scores[0, 0, y]
            x0, x1, x2, x3 = geometry[0, 0, y], geometry[0, 1, y], geometry[0, 2, y], geometry[0, 3, y]
            angles_data = geometry[0, 4, y]
            for x in range(num_cols):
                if scores_data[x] < conf_threshold:
                    continue
                offset_x, offset_y = x * 4.0, y * 4.0
                angle = angles_data[x]
                cos_a, sin_a = np.cos(angle), np.sin(angle)
                h = x0[x] + x2[x]
                w = x1[x] + x3[x]
                end_x = offset_x + cos_a * x1[x] + sin_a * x2[x]
                end_y = offset_y - sin_a * x1[x] + cos_a * x2[x]
                rects.append(((end_x - w / 2, end_y - h / 2), (w, h), -angle * 180.0 / np.pi))
                confidences.append(float(scores_data[x]))
        return rects, confidences

    # ══════════════════════════════════════════════════════════
    #  RobustVideoMatting — 真正的人像分割
    # ══════════════════════════════════════════════════════════

    def load_rvm(self) -> bool:
        """加载 RVM 人像抠图模型 (ONNX Runtime)"""
        if self._rvm is not None:
            return True
        key = "rvm"
        if self._rvm_failed:
            return False

        if not HAS_ORT:
            self._load_errors[key] = (
                "需要安装 onnxruntime:\n"
                "  pip install onnxruntime-directml   (Windows GPU, 推荐)\n"
                "  pip install onnxruntime            (CPU)")
            self._rvm_failed = True
            return False

        path = self._get_model_path(self.RVM_FILE)
        if not self._check_model_valid(path, 12000):
            self._load_errors[key] = (
                f"缺少或不完整: {self.RVM_FILE}\n"
                f"请在「工具 → 模型管理」里下载 RobustVideoMatting (约 15MB)\n"
                f"目录: {self.models_dir.absolute()}")
            self._rvm_failed = True
            return False

        try:
            self._rvm = ort.InferenceSession(str(path), providers=self._preferred_providers())
            self._rvm_output_names = [o.name for o in self._rvm.get_outputs()]
            self.reset_rvm_state()
            LOGGER.info(f"[人像分割] RVM 就绪 ({self._rvm.get_providers()[0]})")
            self._load_errors.pop(key, None)
            return True
        except Exception as e:
            self._load_errors[key] = f"加载失败: {e}"
            LOGGER.error(f"[人像分割] RVM 加载失败: {e}\n{traceback.format_exc()}")
            self._rvm = None
            self._rvm_failed = True
            return False

    def is_rvm_ready(self) -> bool:
        return self._rvm is not None

    def reset_rvm_state(self) -> None:
        """
        清空 RVM 的循环状态。每次开始新视频前必须调用，否则上一个视频的
        人物轮廓会渗进新视频的头几帧。

        首帧按官方约定喂 [1,1,1,1] 的零张量，模型内部会自己扩展成正确形状。
        """
        self._rvm_state = [np.zeros((1, 1, 1, 1), np.float32) for _ in range(4)]

    def matte_person(self, frame: np.ndarray,
                     downsample_ratio: float = 0.0) -> Optional[np.ndarray]:
        """
        返回与输入同尺寸的前景 alpha (float32, 0~1)。模型没就绪时返回 None。

        downsample_ratio 是 RVM 内部的推理缩放比例：越小越快、边缘越粗。
        传 0 表示按分辨率自动取，让内部长边落在 RVM_MAX_SIDE 附近。
        """
        if self._rvm is None:
            return None
        h, w = frame.shape[:2]
        # 模型内部要做 4 次 2 倍下采样，边长不是 4 的倍数会对不齐，先补边
        pad_w, pad_h = (-w) % 4, (-h) % 4
        src = frame if not (pad_w or pad_h) else cv2.copyMakeBorder(
            frame, 0, pad_h, 0, pad_w, cv2.BORDER_REPLICATE)

        rgb = cv2.cvtColor(src, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None]
        if downsample_ratio > 0:
            ratio = float(min(1.0, downsample_ratio))
        else:
            ratio = min(1.0, self.RVM_MAX_SIDE / float(max(src.shape[:2])))

        feed = {"src": tensor,
                "downsample_ratio": np.asarray([ratio], np.float32)}
        for i, state in enumerate(self._rvm_state, 1):
            feed[f"r{i}i"] = state

        try:
            outputs = self._rvm.run(None, feed)
        except Exception as e:
            LOGGER.error(f"[人像分割] RVM 推理失败，本次改用启发式蒙版: {e}")
            self._rvm = None
            self._rvm_failed = True
            self._load_errors["rvm"] = f"推理失败: {e}"
            return None

        named = dict(zip(self._rvm_output_names, outputs))
        self._rvm_state = [named[f"r{i}o"] for i in range(1, 5)]
        alpha = named["pha"][0, 0]
        if pad_w or pad_h:
            alpha = alpha[:h, :w]
        return np.clip(alpha, 0.0, 1.0)

    # ══════════════════════════════════════════════════════════
    #  CRNN — 文字识别 (配合 EAST 做字幕 OCR)
    # ══════════════════════════════════════════════════════════

    def load_crnn(self, model_key: str = "crnn_cn") -> bool:
        """加载 CRNN 识别模型和它配套的字符表"""
        cache_key = f"crnn_{model_key}"
        if cache_key in self._nets:
            return True
        spec = self.CRNN_MODELS.get(model_key)
        if spec is None:
            self._load_errors[cache_key] = f"未知的识别模型: {model_key}"
            return False
        onnx_name, charset_name, _ = spec

        model_path = self._get_model_path(onnx_name)
        if not model_path.exists():
            self._load_errors[cache_key] = (
                f"缺少模型: {onnx_name}\n"
                f"请在「工具 → 模型管理」里下载\n"
                f"目录: {self.models_dir.absolute()}")
            return False

        charset_path = CHARSET_DIR / charset_name
        if not charset_path.exists():
            self._load_errors[cache_key] = (
                f"缺少字符表: {charset_path}\n"
                "该文件随项目一起分发，请确认 charsets/ 目录完整")
            return False

        try:
            # 字符表每行一个字符，空行必须丢掉 —— 否则整个表的下标会错位，
            # 识别出来的会是一串完全无关的字
            charset = "".join(
                line for line in charset_path.read_text(encoding="utf-8").splitlines()
                if line != "")
            net = cv2.dnn.readNet(str(model_path))
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self._nets[cache_key] = net
            self._crnn_charsets[model_key] = charset
            LOGGER.info(f"[字幕 OCR] {onnx_name} 就绪，字符表 {len(charset)} 个字")
            self._load_errors.pop(cache_key, None)
            return True
        except Exception as e:
            self._load_errors[cache_key] = f"加载失败: {e}"
            LOGGER.error(f"[字幕 OCR] CRNN 加载失败: {e}\n{traceback.format_exc()}")
            return False

    def is_crnn_ready(self, model_key: str = "crnn_cn") -> bool:
        return (f"crnn_{model_key}" in self._nets
                and bool(self._crnn_charsets.get(model_key)))

    @staticmethod
    def _order_quad(quad: np.ndarray) -> np.ndarray:
        """
        把 4 个角点排成 [左下, 左上, 右上, 右下]，对上 CRNN 的目标顶点顺序。

        cv2.boxPoints 的出点顺序随旋转角变化，直接拿去做透视变换会得到上下或
        左右翻转的裁片。字幕基本是水平的，所以按 y 分上下两组再各自按 x 排即可。
        """
        pts = np.asarray(quad, np.float32).reshape(4, 2)
        by_y = pts[np.argsort(pts[:, 1])]
        top = by_y[:2][np.argsort(by_y[:2, 0])]
        bottom = by_y[2:][np.argsort(by_y[2:, 0])]
        return np.asarray([bottom[0], top[0], top[1], bottom[1]], np.float32)

    def recognize_text(self, frame: np.ndarray, quad: np.ndarray,
                       model_key: str = "crnn_cn") -> str:
        """识别一个文字框里的内容，识别不出来返回空串"""
        net = self._nets.get(f"crnn_{model_key}")
        charset = self._crnn_charsets.get(model_key)
        if net is None or not charset:
            return ""
        in_w, in_h = self.CRNN_INPUT_SIZE
        target = np.asarray([[0, in_h - 1], [0, 0], [in_w - 1, 0], [in_w - 1, in_h - 1]],
                            np.float32)
        try:
            matrix = cv2.getPerspectiveTransform(self._order_quad(quad), target)
            crop = cv2.warpPerspective(frame, matrix, (in_w, in_h))
            if not self.CRNN_MODELS[model_key][2]:
                crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            blob = cv2.dnn.blobFromImage(crop, size=(in_w, in_h),
                                         mean=127.5, scalefactor=1 / 127.5)
            net.setInput(blob)
            return self._ctc_greedy_decode(net.forward(), charset)
        except Exception as e:
            LOGGER.warn(f"[字幕 OCR] 单框识别失败: {e}")
            return ""

    @staticmethod
    def _ctc_greedy_decode(blob: np.ndarray, charset: str) -> str:
        """
        CTC 贪心解码：每个时间步取概率最大的类别，然后合并相邻重复、去掉空白。

        类别 0 是 CTC 的空白符，真实字符从 1 开始，所以查表要减 1。
        """
        logits = blob.reshape(blob.shape[0], -1)
        best = logits.argmax(axis=1)
        chars: List[str] = []
        previous = -1
        for index in best:
            index = int(index)
            if index != 0 and index != previous:
                position = index - 1
                if 0 <= position < len(charset):
                    chars.append(charset[position])
            previous = index
        return "".join(chars)

     # ══════════════════════════════════════════════════════════
    #  ★★★ 去马赛克 / 超分辨率 — 完全重写 ★★★
    # ══════════════════════════════════════════════════════════

    def load_demosaic_model(self, model_name: str = "real_esrgan_x4") -> bool:
        """
        加载去马赛克/超分辨率模型
        
        支持的模型:
        - real_esrgan_x4: Real-ESRGAN 通用 (需要 onnxruntime)
        - real_esrgan_anime: Real-ESRGAN 动漫 (需要 onnxruntime)
        - espcn_x4: ESPCN 轻量级 (cv2.dnn 即可)
        - traditional: 传统方法 (无需任何模型)
        """
        # 传统方法不需要加载
        if model_name == "traditional":
            return True
        if model_name == "deepmosaics":
            return self.load_deepmosaics()

        key = f"demosaic_{model_name}"

        # 已加载则跳过
        if key in self._ort_model_paths or key in self._nets:
            return True

        model_map = {
            "real_esrgan_x4": "realesrgan-x4plus.onnx",
            "real_esrgan_anime": "realesrgan-animevideov3.onnx",
            "espcn_x4": "ESPCN_x4.pb",
        }

        filename = model_map.get(model_name)
        if not filename:
            self._load_errors[key] = f"未知模型: {model_name}"
            return False

        model_path = self._get_model_path(filename)
        if not model_path.exists():
            self._load_errors[key] = (
                f"模型文件不存在: {filename}\n"
                f"请到「下载DNN模型」中下载\n"
                f"目录: {self.models_dir.absolute()}"
            )
            return False

        if not self._check_model_valid(model_path, min_size_kb=50):
            self._load_errors[key] = f"模型文件损坏或不完整: {filename}"
            return False

        try:
            if filename.endswith('.onnx'):
                # ★ Real-ESRGAN 必须用 onnxruntime，cv2.dnn 不支持
                if not HAS_ORT:
                    self._load_errors[key] = (
                        "需要安装 onnxruntime:\n"
                        "  pip install onnxruntime-directml   (Windows GPU, 推荐)\n"
                        "  pip install onnxruntime            (CPU)\n"
                        "或选择 'traditional' 传统方法"
                    )
                    return False
                if not HAS_ONNX:
                    self._load_errors[key] = (
                        "需要安装 onnx:\n"
                        "  pip install onnx\n"
                        "用于适配模型输入尺寸"
                    )
                    return False

                # 真正的 session 在 _get_esrgan_session 里按分块尺寸惰性创建
                self._ort_model_paths[key] = model_path
                LOGGER.info(f"[去马赛克] 模型就绪: {filename} "
                            f"(可用后端: {', '.join(ort.get_available_providers())})")
                self._load_errors.pop(key, None)
                return True

            elif filename.endswith('.pb'):
                # ESPCN 可以用 cv2.dnn
                net = cv2.dnn.readNetFromTensorflow(str(model_path))
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self._nets[key] = net
                self._load_errors.pop(key, None)
                LOGGER.info(f"[去马赛克] 模型就绪: {filename} (cv2.dnn / CPU)")
                return True

            self._load_errors[key] = f"不支持的模型格式: {filename}"
            return False

        except Exception as e:
            self._load_errors[key] = f"加载模型失败: {e}\n{traceback.format_exc()}"
            return False

    def is_demosaic_model_ready(self, model_name: str) -> bool:
        """模型是否真的可以推理了（不只是文件存在）"""
        if model_name == "traditional":
            return True
        if model_name == "deepmosaics":
            return self._dm_detector is not None and self._dm_generator is not None
        key = f"demosaic_{model_name}"
        return key in self._ort_model_paths or key in self._nets

    def resolve_demosaic_model(self, model_name: str) -> str:
        """
        把「用户选的模型」换算成「当前真能跑的模型」。

        加载失败时统一降级到 traditional。之前这里没有兜底：
        _init_dnn_for_task 提示了「改用传统增强方法」，但 apply_demosaic 仍然
        无条件走 DeepMosaics 分支，而 apply_deepmosaics 在 session 为 None 时
        直接原样返回，结果就是整段视频没有任何处理效果。
        """
        if self.is_demosaic_model_ready(model_name):
            return model_name
        if model_name not in self._demosaic_fallback_warned:
            self._demosaic_fallback_warned.add(model_name)
            LOGGER.warn(f"[去马赛克] {model_name} 不可用，已回退到传统方法。"
                        f"{self.get_load_error(f'demosaic_{model_name}') or ''}".strip())
        return "traditional"

    def apply_demosaic(self, frame: np.ndarray,
                       model_name: str = "real_esrgan_x4",
                       region: Tuple[int, int, int, int] = (0, 0, 0, 0),
                       full_frame: bool = True,
                       tile_size: int = 128) -> np.ndarray:
        """
        去马赛克 / 超分辨率重建 — 主入口
        
        处理流程:
        1. 把请求的模型换算成实际可用的模型 (不可用则降级为传统方法)
        2. 确定处理区域 (全画面 or 局部)
        3. 选择推理方法 (DeepMosaics / ESRGAN / ESPCN / 传统)
        4. 分块推理 (防止 OOM)，拼接结果
        """
        h, w = frame.shape[:2]
        model_name = self.resolve_demosaic_model(model_name)

        # DeepMosaics 自带区域检测，不走分块超分那套流程
        if model_name == "deepmosaics":
            return self.apply_deepmosaics(frame)

        # 确定处理区域
        if not full_frame and region[2] > 0 and region[3] > 0:
            rx, ry, rw, rh = region
            rx, ry = max(0, rx), max(0, ry)
            rw = min(w - rx, rw)
            rh = min(h - ry, rh)
            if rw <= 0 or rh <= 0:
                return frame
            roi = frame[ry:ry + rh, rx:rx + rw].copy()
            enhanced_roi = self._enhance_image(roi, model_name, tile_size)
            result = frame.copy()
            result[ry:ry + rh, rx:rx + rw] = enhanced_roi
            return result
        else:
            return self._enhance_image(frame, model_name, tile_size)

    ESRGAN_SCALE = 4
    ESRGAN_OVERLAP = 16

    @staticmethod
    def _build_static_onnx(model_path: Path, size: int) -> bytes:
        """
        把 Real-ESRGAN 的输入尺寸重写为 size×size。

        这些 ONNX 是以固定 128×128 导出的，图里 1799 条 value_info 记录了
        由 128 推导出的中间层形状。只改输入维度会让 Concat 节点形状校验失败，
        必须连同 value_info 一起清掉，让 onnxruntime 重新推导。
        DirectML 后端对静态形状比动态形状快约一倍，所以这里固定而非置为动态。
        """
        model = onnx_mod.load(str(model_path))
        del model.graph.value_info[:]
        for idx, dim in enumerate(model.graph.input[0].type.tensor_type.shape.dim):
            if idx in (2, 3):
                dim.ClearField('dim_param')
                dim.dim_value = size
        for idx, dim in enumerate(model.graph.output[0].type.tensor_type.shape.dim):
            if idx in (2, 3):
                dim.ClearField('dim_param')
                dim.dim_value = size * DNNEngine.ESRGAN_SCALE
        return model.SerializeToString()

    @staticmethod
    def _preferred_providers() -> List[str]:
        available = ort.get_available_providers()
        return [p for p in ('DmlExecutionProvider', 'CUDAExecutionProvider',
                            'CPUExecutionProvider') if p in available] \
            or ['CPUExecutionProvider']

    def _get_esrgan_session(self, key: str, tile_size: int):
        """按 (模型, 分块尺寸) 缓存 session，尺寸变化时才重新编译计算图"""
        cache_key = (key, tile_size)
        if cache_key in self._ort_sessions:
            return self._ort_sessions[cache_key]

        model_path = self._ort_model_paths[key]
        providers = self._preferred_providers()
        session = ort.InferenceSession(
            self._build_static_onnx(model_path, tile_size), providers=providers)
        LOGGER.info(f"[去马赛克] session 就绪: {model_path.name} @ {tile_size}px "
                    f"({session.get_providers()[0]})")
        self._ort_sessions[cache_key] = session
        return session

    def _enhance_image(self, img: np.ndarray,
                       model_name: str,
                       tile_size: int) -> np.ndarray:
        """
        对图像进行增强处理，自动选择最佳方法
        输出尺寸与输入相同
        """
        key = f"demosaic_{model_name}"

        # 方法1: ONNX Runtime (Real-ESRGAN)
        if key in self._ort_model_paths:
            tile_size = max(64, min(512, int(tile_size) // 8 * 8))
            session = self._get_esrgan_session(key, tile_size)
            return self._enhance_with_esrgan(img, session, tile_size)

        # 方法2: cv2.dnn (ESPCN)
        if key in self._nets:
            return self._enhance_with_espcn(img, self._nets[key])

        # 方法3: 传统方法
        return self._enhance_traditional(img)

    def _enhance_with_esrgan(self, img: np.ndarray,
                              session: 'ort.InferenceSession',
                              tile_size: int = 128) -> np.ndarray:
        """
        使用 Real-ESRGAN (ONNX Runtime) 进行超分辨率
        分块处理以防止内存溢出，输出缩放回原尺寸
        """
        h, w = img.shape[:2]

        # 补边到至少一个完整分块，使所有分块尺寸一致
        pad_b = max(0, tile_size - h)
        pad_r = max(0, tile_size - w)
        if pad_b or pad_r:
            img = cv2.copyMakeBorder(img, 0, pad_b, 0, pad_r, cv2.BORDER_REFLECT_101)

        enhanced = self._tiled_esrgan_inference(img, session, tile_size)

        scale = self.ESRGAN_SCALE
        if pad_b or pad_r:
            enhanced = enhanced[:(h * scale), :(w * scale)]

        if enhanced.shape[0] != h or enhanced.shape[1] != w:
            enhanced = cv2.resize(enhanced, (w, h), interpolation=cv2.INTER_LANCZOS4)

        return enhanced

    def _single_esrgan_inference(self, img: np.ndarray,
                                  session: 'ort.InferenceSession',
                                  pad_to: int) -> np.ndarray:
        """单块 ESRGAN 推理，输入不足 pad_to×pad_to 时镜像补边，输出按原比例裁回"""
        h, w = img.shape[:2]
        if h < pad_to or w < pad_to:
            img = cv2.copyMakeBorder(img, 0, max(0, pad_to - h), 0, max(0, pad_to - w),
                                     cv2.BORDER_REFLECT_101)

        # 预处理: BGR → RGB, uint8 → float32 [0,1], HWC → NCHW
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_float = img_rgb.astype(np.float32) / 255.0
        input_tensor = np.expand_dims(np.transpose(img_float, (2, 0, 1)), 0)

        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        result = session.run([output_name], {input_name: input_tensor})[0]

        # 后处理: NCHW → HWC, float32 → uint8, RGB → BGR
        output = np.transpose(result.squeeze(0), (1, 2, 0))
        output = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        output_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

        scale = self.ESRGAN_SCALE
        return output_bgr[:(h * scale), :(w * scale)]

    @staticmethod
    def _blend_weight_map(size: int, border: int) -> np.ndarray:
        """中心权重高、边缘线性衰减的权重图，用于消除分块接缝"""
        ramp = np.ones(size, dtype=np.float32)
        n = min(border, size // 2)
        if n > 0:
            edge = (np.arange(1, n + 1, dtype=np.float32)) / border
            ramp[:n] = edge
            ramp[-n:] = edge[::-1]
        return (ramp[:, None] * ramp[None, :])[:, :, None]

    def _tiled_esrgan_inference(self, img: np.ndarray,
                                 session: 'ort.InferenceSession',
                                 tile_size: int = 128) -> np.ndarray:
        """
        分块 ESRGAN 推理
        使用重叠区域 + 线性混合避免接缝
        """
        h, w = img.shape[:2]
        scale = self.ESRGAN_SCALE
        overlap = self.ESRGAN_OVERLAP
        out_h, out_w = h * scale, w * scale
        out_tile = tile_size * scale

        output = np.zeros((out_h, out_w, 3), dtype=np.float32)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float32)
        wmap = self._blend_weight_map(out_tile, overlap * scale // 2)

        step = tile_size - overlap
        origins = sorted({(min(y, h - tile_size), min(x, w - tile_size))
                          for y in range(0, h, step)
                          for x in range(0, w, step)})

        for i, (ty, tx) in enumerate(origins):
            tile = img[ty:ty + tile_size, tx:tx + tile_size]
            try:
                enhanced_tile = self._single_esrgan_inference(tile, session, tile_size)
            except Exception as e:
                # 首块就失败说明是配置/驱动问题而非偶发，直接抛出而不是静默降级成插值
                if i == 0:
                    raise RuntimeError(
                        f"Real-ESRGAN 推理失败 (分块 {tile_size}px): {e}\n"
                        f"可尝试: 减小分块大小 / 改用 traditional 方法"
                    ) from e
                LOGGER.warn(f"[去马赛克] 分块推理失败 ({tx},{ty})，该块降级为插值: {e}")
                enhanced_tile = cv2.resize(tile, (out_tile, out_tile),
                                           interpolation=cv2.INTER_CUBIC)

            oy, ox = ty * scale, tx * scale
            output[oy:oy + out_tile, ox:ox + out_tile] += enhanced_tile * wmap
            weight[oy:oy + out_tile, ox:ox + out_tile] += wmap

        np.maximum(weight, 1e-6, out=weight)
        return np.clip(output / weight, 0, 255).astype(np.uint8)

    def _enhance_with_espcn(self, img: np.ndarray,
                             net: cv2.dnn.Net) -> np.ndarray:
        """使用 ESPCN 进行超分辨率 (轻量级)"""
        h, w = img.shape[:2]

        # ESPCN 在 YCbCr 空间的 Y 通道上工作
        img_ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        y_channel = img_ycrcb[:, :, 0].astype(np.float32) / 255.0

        # 构建输入 blob
        input_blob = np.expand_dims(np.expand_dims(y_channel, 0), 0)  # 1x1xHxW
        net.setInput(input_blob)

        try:
            output = net.forward()
            sr_y = output.squeeze()
            sr_y = np.clip(sr_y * 255.0, 0, 255).astype(np.uint8)

            # 放大 CrCb 通道
            sr_h, sr_w = sr_y.shape[:2]
            cr_up = cv2.resize(img_ycrcb[:, :, 1], (sr_w, sr_h), interpolation=cv2.INTER_CUBIC)
            cb_up = cv2.resize(img_ycrcb[:, :, 2], (sr_w, sr_h), interpolation=cv2.INTER_CUBIC)

            sr_ycrcb = cv2.merge([sr_y, cr_up, cb_up])
            result = cv2.cvtColor(sr_ycrcb, cv2.COLOR_YCrCb2BGR)

            # 缩放回原尺寸
            if result.shape[0] != h or result.shape[1] != w:
                result = cv2.resize(result, (w, h), interpolation=cv2.INTER_LANCZOS4)

            return result
        except Exception as e:
            LOGGER.warn(f"[ESPCN] 推理失败，该帧降级为传统方法: {e}")
            return self._enhance_traditional(img)

    # ══════════════════════════════════════════════════════════
    #  DeepMosaics — 检测 + 生成式重建
    # ══════════════════════════════════════════════════════════

    def load_deepmosaics(self) -> bool:
        """加载 BiSeNet 检测器与 BVDNet 生成器（由 export_deepmosaics_onnx.py 导出）"""
        if self._dm_detector is not None and self._dm_generator is not None:
            return True
        key = "demosaic_deepmosaics"

        if not HAS_ORT:
            self._load_errors[key] = (
                "需要安装 onnxruntime:\n"
                "  pip install onnxruntime-directml   (Windows GPU, 推荐)"
            )
            return False

        missing = [f for f in (self.DM_DETECTOR_FILE, self.DM_GENERATOR_FILE)
                   if not self._get_model_path(f).exists()]
        if missing:
            self._load_errors[key] = (
                f"缺少模型: {', '.join(missing)}\n"
                f"请先用 DeepMosaics 权重导出 ONNX:\n"
                f"  python export_deepmosaics_onnx.py\n"
                f"目录: {self.models_dir.absolute()}"
            )
            return False

        try:
            providers = self._preferred_providers()
            self._dm_detector = ort.InferenceSession(
                str(self._get_model_path(self.DM_DETECTOR_FILE)), providers=providers)
            self._dm_generator = ort.InferenceSession(
                str(self._get_model_path(self.DM_GENERATOR_FILE)), providers=providers)
            self.reset_deepmosaics_state()
            LOGGER.info(f"[去马赛克] DeepMosaics 就绪 ({self._dm_detector.get_providers()[0]})")
            self._load_errors.pop(key, None)
            return True
        except Exception as e:
            self._load_errors[key] = f"加载失败: {e}\n{traceback.format_exc()}"
            self._dm_detector = self._dm_generator = None
            return False

    def reset_deepmosaics_state(self) -> None:
        """清空时序状态，每次开始新任务前调用，避免跨视频串帧"""
        self._dm_history.clear()
        self._dm_previous = None

    def detect_mosaic_mask(self, frame: np.ndarray, threshold: int = 48) -> np.ndarray:
        """用 BiSeNet 定位马赛克区域，返回与输入同尺寸的二值掩膜"""
        if self._dm_detector is None:
            return np.zeros(frame.shape[:2], np.uint8)

        h, w = frame.shape[:2]
        # 检测器按 BGR 顺序、[0,1] 归一化训练，且导出为固定 360×360
        resized = cv2.resize(frame, (self.DM_DETECT_SIZE, self.DM_DETECT_SIZE),
                             interpolation=cv2.INTER_LINEAR)
        tensor = np.transpose(resized.astype(np.float32) / 255.0, (2, 0, 1))[None]
        raw = self._dm_detector.run(None, {"image": tensor})[0]

        mask = np.clip(raw[0, 0] * 255.0, 0, 255).astype(np.uint8)
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LANCZOS4)

        # 二值化后先模糊再二值化，等效于把掩膜向外扩张一圈，覆盖马赛克的边缘过渡
        span = max(3, int(min(h, w) / 20))
        mask = cv2.threshold(mask, threshold, 255, cv2.THRESH_BINARY)[1]
        mask = cv2.blur(mask, (span, span))
        return cv2.threshold(mask, max(1, threshold // 5), 255, cv2.THRESH_BINARY)[1]

    @staticmethod
    def _dm_to_tensor(img: np.ndarray) -> np.ndarray:
        """BGR uint8 → RGB [-1,1] 的 CHW"""
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
        return np.transpose(rgb / 127.5 - 1.0, (2, 0, 1))

    @staticmethod
    def _dm_from_tensor(chw: np.ndarray) -> np.ndarray:
        """RGB [-1,1] 的 CHW → BGR uint8"""
        hwc = np.transpose(chw, (1, 2, 0))
        rgb = np.clip((hwc + 1.0) * 127.5, 0, 255).astype(np.uint8)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    def _dm_crop_box(self, mask: np.ndarray, expand: float
                     ) -> Optional[Tuple[int, int, int, int]]:
        """按掩膜的外接矩形取一个带余量的正方形裁剪框，并夹到画面内"""
        x, y, w, h = cv2.boundingRect(mask)
        if w <= 0 or h <= 0:
            return None
        side = int(max(w, h) * expand)
        mh, mw = mask.shape[:2]
        side = min(side, mh, mw)
        cx, cy = x + w // 2, y + h // 2
        x0 = min(max(cx - side // 2, 0), mw - side)
        y0 = min(max(cy - side // 2, 0), mh - side)
        return x0, y0, side, side

    def apply_deepmosaics(self, frame: np.ndarray,
                          threshold: int = 48,
                          min_size: int = 40,
                          expand: float = 1.35,
                          feather: float = 0.25) -> np.ndarray:
        """
        DeepMosaics 去马赛克主入口。

        与 Real-ESRGAN 不同，这里先定位马赛克区域，再由生成网络重建内容。
        BVDNet 是时序模型，输入是以当前帧为中心的 5 帧窗口。逐帧处理的架构拿不到
        未来帧，因此用历史帧填充过去的一半、当前帧重复填充未来的一半——
        窗口中心仍是当前帧，这一点必须保证，因为网络把该位置作为残差基准。
        """
        if self._dm_detector is None or self._dm_generator is None:
            return frame

        self._dm_history.append(frame)

        mask = self.detect_mosaic_mask(frame, threshold)
        if not mask.any():
            self._dm_previous = None
            return frame

        box = self._dm_crop_box(mask, expand)
        if box is None:
            return frame
        x0, y0, bw, bh = box
        if max(bw, bh) < min_size:
            return frame

        size = self.DM_GEN_SIZE
        history = list(self._dm_history)

        def crop_at(img: np.ndarray) -> np.ndarray:
            patch = img[y0:y0 + bh, x0:x0 + bw]
            return cv2.resize(patch, (size, size), interpolation=cv2.INTER_CUBIC)

        stream = np.empty((1, 3, self.DM_GEN_T, size, size), np.float32)
        for i in range(self.DM_GEN_T):
            # 前 N 帧取历史，中心及之后都用当前帧
            back = (self.DM_GEN_N - i) * self.DM_GEN_STRIDE
            src = history[-1 - back] if 0 < back < len(history) else history[-1]
            stream[0, :, i] = self._dm_to_tensor(crop_at(src))

        if self._dm_previous is None or self._dm_previous.shape[-2:] != (size, size):
            self._dm_previous = stream[0, :, self.DM_GEN_N][None].copy()

        try:
            out = self._dm_generator.run(
                None, {"stream": stream, "previous": self._dm_previous})[0]
        except Exception as e:
            LOGGER.warn(f"[去马赛克] DeepMosaics 推理失败，该帧保持原样: {e}")
            return frame
        self._dm_previous = out

        fake = cv2.resize(self._dm_from_tensor(out[0]), (bw, bh),
                          interpolation=cv2.INTER_CUBIC)

        # 只替换掩膜内部，边缘做羽化过渡，避免出现生硬的方块拼接痕迹
        alpha = mask[y0:y0 + bh, x0:x0 + bw].astype(np.float32) / 255.0
        blur = max(3, int(max(bw, bh) * feather) | 1)
        alpha = cv2.GaussianBlur(alpha, (blur, blur), 0)[:, :, None]

        result = frame.copy()
        patch = result[y0:y0 + bh, x0:x0 + bw].astype(np.float32)
        result[y0:y0 + bh, x0:x0 + bw] = np.clip(
            patch * (1 - alpha) + fake.astype(np.float32) * alpha, 0, 255).astype(np.uint8)
        return result

    @staticmethod
    def _enhance_traditional(img: np.ndarray) -> np.ndarray:
        """
        传统去马赛克方法 (不需要 DNN 模型)
        
        多阶段处理流水线:
        1. 双边滤波 (平滑马赛克块边界，保留结构边缘)
        2. 超分辨率插值 (放大后缩小，利用插值平滑)
        3. 非局部均值去噪 (去除块状伪影)
        4. 自适应锐化 (恢复细节)
        5. 细节增强 (通过 unsharp masking)
        """
        h, w = img.shape[:2]

        # ── 阶段1: 双边滤波去除块边界 ──
        # 大的 sigmaColor 保持边缘，大的 sigmaSpace 平滑远处像素
        smooth = cv2.bilateralFilter(img, d=9, sigmaColor=75, sigmaSpace=75)

        # ── 阶段2: 超采样重建 ──
        # 放大 4x → 双三次插值自动在马赛克块之间创建过渡
        upscale_factor = 4
        big = cv2.resize(smooth,
                         (w * upscale_factor, h * upscale_factor),
                         interpolation=cv2.INTER_CUBIC)

        # 在高分辨率下再次双边滤波
        big = cv2.bilateralFilter(big, d=7, sigmaColor=50, sigmaSpace=50)

        # 缩小回原尺寸 (Lanczos 保持清晰度)
        result = cv2.resize(big, (w, h), interpolation=cv2.INTER_LANCZOS4)

        # ── 阶段3: 非局部均值去噪 ──
        # 专门针对块状伪影效果很好
        result = cv2.fastNlMeansDenoisingColored(
            result,
            None,
            h=6,           # 亮度去噪强度
            hColor=6,      # 色彩去噪强度
            templateWindowSize=7,
            searchWindowSize=21
        )

        # ── 阶段4: Unsharp Masking 锐化 ──
        gaussian = cv2.GaussianBlur(result, (0, 0), sigmaX=2.0)
        # result = original + amount * (original - blurred)
        amount = 1.5
        sharpened = cv2.addWeighted(result, 1.0 + amount, gaussian, -amount, 0)
        result = np.clip(sharpened, 0, 255).astype(np.uint8)

        # ── 阶段5: 轻微的细节增强 ──
        # 在 LAB 空间增强 L 通道的局部对比度
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        result = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return result


# ════════════════════════════════════════════════════════════════
#  滤镜与特效引擎
# ════════════════════════════════════════════════════════════════

class FilterEngine:
    """图像/视频滤镜处理"""

    @staticmethod
    def adjust_brightness_contrast(frame: np.ndarray, brightness: int = 0,
                                   contrast: float = 1.0) -> np.ndarray:
        result = frame.astype(np.float32) * contrast + brightness
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
    def adjust_saturation(frame: np.ndarray, saturation: float = 1.0) -> np.ndarray:
        if saturation == 1.0:
            return frame
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation, 0, 255)
        return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    @staticmethod
    def adjust_gamma(frame: np.ndarray, gamma: float = 1.0) -> np.ndarray:
        if gamma == 1.0:
            return frame
        table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in range(256)]).astype("uint8")
        return cv2.LUT(frame, table)

    @staticmethod
    def histogram_equalize(frame: np.ndarray) -> np.ndarray:
        if len(frame.shape) == 2:
            return cv2.equalizeHist(frame)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        lab[:, :, 0] = clahe.apply(lab[:, :, 0])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    @staticmethod
    def apply_blur(frame: np.ndarray, blur_type: str = "gaussian", ksize: int = 5) -> np.ndarray:
        ksize = max(3, ksize | 1)
        if blur_type == "gaussian":
            return cv2.GaussianBlur(frame, (ksize, ksize), 0)
        elif blur_type == "median":
            return cv2.medianBlur(frame, ksize)
        elif blur_type == "bilateral":
            return cv2.bilateralFilter(frame, ksize, 75, 75)
        return frame

    @staticmethod
    def apply_sharpen(frame: np.ndarray, strength: float = 1.0) -> np.ndarray:
        if strength <= 0:
            return frame
        kernel = np.array([[0, -1, 0], [-1, 5 + strength, -1], [0, -1, 0]], dtype=np.float32)
        kernel /= (1 + strength)
        return cv2.filter2D(frame, -1, kernel)

    @staticmethod
    def denoise(frame: np.ndarray, strength: int = 10) -> np.ndarray:
        if strength <= 0:
            return frame
        return cv2.fastNlMeansDenoisingColored(frame, None, strength, strength, 7, 21)

    @staticmethod
    def pencil_sketch(frame: np.ndarray, color: bool = True) -> np.ndarray:
        gray, color_sketch = cv2.pencilSketch(frame, sigma_s=60, sigma_r=0.07, shade_factor=0.05)
        return color_sketch if color else cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def cartoon_effect(frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)
        edges = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                       cv2.THRESH_BINARY, 9, 9)
        color = cv2.bilateralFilter(frame, 9, 300, 300)
        return cv2.bitwise_and(color, color, mask=edges)

    @staticmethod
    def emboss_effect(frame: np.ndarray) -> np.ndarray:
        kernel = np.array([[-2, -1, 0], [-1, 1, 1], [0, 1, 2]], dtype=np.float32)
        return np.clip(cv2.filter2D(frame, -1, kernel) + 128, 0, 255).astype(np.uint8)

    @staticmethod
    def edge_detect(frame: np.ndarray, method: str = "canny",
                    low: int = 50, high: int = 150) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        if method == "canny":
            edges = cv2.Canny(gray, low, high)
        elif method == "sobel":
            sx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            edges = np.clip(np.sqrt(sx ** 2 + sy ** 2), 0, 255).astype(np.uint8)
        elif method == "laplacian":
            edges = np.clip(np.abs(cv2.Laplacian(gray, cv2.CV_64F)), 0, 255).astype(np.uint8)
        else:
            edges = gray
        return cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

    @staticmethod
    def apply_color_tone(frame: np.ndarray, tone: str = "warm") -> np.ndarray:
        result = frame.copy().astype(np.float32)
        if tone == "warm":
            result[:, :, 2] = np.clip(result[:, :, 2] * 1.2 + 10, 0, 255)
            result[:, :, 0] = np.clip(result[:, :, 0] * 0.9, 0, 255)
        elif tone == "cool":
            result[:, :, 0] = np.clip(result[:, :, 0] * 1.2 + 10, 0, 255)
            result[:, :, 2] = np.clip(result[:, :, 2] * 0.9, 0, 255)
        elif tone == "sepia":
            sepia_kernel = np.array([[0.272, 0.534, 0.131], [0.349, 0.686, 0.168], [0.393, 0.769, 0.189]])
            result = np.clip(cv2.transform(frame, sepia_kernel), 0, 255)
        elif tone == "vintage":
            result[:, :, 0] = np.clip(result[:, :, 0] * 0.8, 0, 255)
            result[:, :, 1] = np.clip(result[:, :, 1] * 0.9, 0, 255)
            result[:, :, 2] = np.clip(result[:, :, 2] * 1.1 + 20, 0, 255)
            h, w = frame.shape[:2]
            Y, X = np.ogrid[:h, :w]
            mask = 1 - np.sqrt((X - w / 2) ** 2 + (Y - h / 2) ** 2) / np.sqrt((w / 2) ** 2 + (h / 2) ** 2) * 0.4
            for c in range(3):
                result[:, :, c] *= mask
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
    def apply_mosaic(frame: np.ndarray, x: int, y: int, w: int, h: int,
                     block_size: int = 15) -> np.ndarray:
        result = frame.copy()
        fh, fw = frame.shape[:2]
        x, y = max(0, x), max(0, y)
        w, h = min(fw - x, w), min(fh - y, h)
        if w <= 0 or h <= 0:
            return result
        roi = result[y:y + h, x:x + w]
        small = cv2.resize(roi, (max(1, w // block_size), max(1, h // block_size)),
                           interpolation=cv2.INTER_LINEAR)
        result[y:y + h, x:x + w] = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)
        return result

    @staticmethod
    def apply_vignette(frame: np.ndarray, strength: float = 0.5) -> np.ndarray:
        h, w = frame.shape[:2]
        Y, X = np.ogrid[:h, :w]
        mask = np.clip(1 - np.sqrt((X - w / 2) ** 2 + (Y - h / 2) ** 2) /
                       np.sqrt((w / 2) ** 2 + (h / 2) ** 2) * strength, 0, 1)
        result = frame.astype(np.float32)
        for c in range(frame.shape[2] if len(frame.shape) == 3 else 1):
            if len(frame.shape) == 3:
                result[:, :, c] *= mask
            else:
                result *= mask
        return np.clip(result, 0, 255).astype(np.uint8)

    @staticmethod
    def pixelate_full(frame: np.ndarray, pixel_size: int = 10) -> np.ndarray:
        h, w = frame.shape[:2]
        small = cv2.resize(frame, (max(1, w // pixel_size), max(1, h // pixel_size)),
                           interpolation=cv2.INTER_LINEAR)
        return cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)


# ════════════════════════════════════════════════════════════════
#  文字渲染与 alpha 合成 (水印 / 字幕共用)
# ════════════════════════════════════════════════════════════════

def hex_to_bgr(value: str, default: Tuple[int, int, int] = (255, 255, 255)
               ) -> Tuple[int, int, int]:
    """'#RRGGBB' → (B, G, R)。解析不了就返回默认色"""
    text = (value or "").strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    if len(text) != 6:
        return default
    try:
        r, g, b = (int(text[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default
    return b, g, r


def bgr_to_hex(bgr: Tuple[int, int, int]) -> str:
    b, g, r = (int(max(0, min(255, c))) for c in bgr)
    return f"#{r:02X}{g:02X}{b:02X}"


class TextRenderer:
    """
    把一段（可能含中文的）文字渲染成带描边的 BGRA 贴图。

    cv2.putText 只有 Hershey 矢量字体，非 ASCII 一律画成 '?'，所以中文必须
    走 PIL 加载 TTF。没装 Pillow 时退回 cv2.putText，此时中文会丢字——
    这种情况会记一条日志，但不阻断处理。
    """

    _font_cache: "OrderedDict[Tuple[str, int], Any]" = OrderedDict()
    _FONT_CACHE_MAX = 16
    _fallback_warned = False

    @classmethod
    def _load_font(cls, font_path: str, size: int):
        key = (font_path, size)
        cached = cls._font_cache.get(key)
        if cached is not None:
            cls._font_cache.move_to_end(key)
            return cached
        try:
            font = ImageFont.truetype(font_path, size) if font_path \
                else ImageFont.load_default()
        except Exception as e:
            LOGGER.warn(f"字体加载失败，改用 PIL 默认字体: {font_path} ({e})")
            try:
                font = ImageFont.load_default()
            except Exception:
                return None
        cls._font_cache[key] = font
        cls._font_cache.move_to_end(key)
        while len(cls._font_cache) > cls._FONT_CACHE_MAX:
            cls._font_cache.popitem(last=False)
        return font

    @classmethod
    def render(cls, text: str,
               font_path: str = "",
               font_size: int = 42,
               color: Tuple[int, int, int] = (255, 255, 255),
               outline_color: Tuple[int, int, int] = (0, 0, 0),
               outline_width: int = 0,
               line_spacing: float = 1.25,
               align: str = "center") -> Optional[np.ndarray]:
        """返回 BGRA 贴图 (紧贴文字外框)，text 为空或渲染失败时返回 None"""
        text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            return None
        font_size = max(6, int(font_size))
        outline_width = max(0, int(outline_width))
        if HAS_PIL:
            stamp = cls._render_pil(text, font_path, font_size, color,
                                    outline_color, outline_width, line_spacing, align)
            if stamp is not None:
                return stamp
        return cls._render_cv2(text, font_size, color, outline_color,
                               outline_width, line_spacing)

    @classmethod
    def _render_pil(cls, text, font_path, font_size, color,
                    outline_color, outline_width, line_spacing, align):
        font = cls._load_font(font_path or default_cjk_font(), font_size)
        if font is None:
            return None
        try:
            spacing = max(0, int(font_size * (line_spacing - 1.0)))
            # 先在 1x1 画布上量尺寸，再按量出来的大小开真正的画布
            probe = ImageDraw.Draw(PILImage.new("RGBA", (1, 1)))
            box = probe.multiline_textbbox((0, 0), text, font=font, spacing=spacing,
                                           align=align, stroke_width=outline_width)
            pad = outline_width + 2
            width = max(1, int(box[2] - box[0]) + pad * 2)
            height = max(1, int(box[3] - box[1]) + pad * 2)
            canvas = PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(canvas)
            b, g, r = color
            ob, og, orr = outline_color
            draw.multiline_text((pad - box[0], pad - box[1]), text, font=font,
                                fill=(r, g, b, 255), spacing=spacing, align=align,
                                stroke_width=outline_width,
                                stroke_fill=(orr, og, ob, 255))
            rgba = np.asarray(canvas, dtype=np.uint8)
            return cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        except Exception as e:
            LOGGER.warn(f"PIL 文字渲染失败，回退 cv2.putText: {e}")
            return None

    @classmethod
    def _render_cv2(cls, text, font_size, color, outline_color,
                    outline_width, line_spacing):
        if not cls._fallback_warned:
            cls._fallback_warned = True
            LOGGER.warn("未安装 Pillow，文字改用 cv2.putText 渲染，中文将无法显示 "
                        "(pip install Pillow)")
        face = cv2.FONT_HERSHEY_SIMPLEX
        # Hershey 字体的 1.0 倍缩放大约 22px 高，据此换算成想要的字号
        scale = font_size / 22.0
        thickness = max(1, int(round(font_size / 16.0)))
        lines = text.split("\n")
        sizes = [cv2.getTextSize(ln, face, scale, thickness)[0] for ln in lines]
        step = int(max(s[1] for s in sizes) * line_spacing) + 4
        pad = outline_width + thickness + 2
        width = max(s[0] for s in sizes) + pad * 2
        height = step * len(lines) + pad * 2
        canvas = np.zeros((height, width, 4), np.uint8)
        for i, line in enumerate(lines):
            org = (pad, pad + step * i + sizes[i][1])
            if outline_width > 0:
                cv2.putText(canvas, line, org, face, scale,
                            (*outline_color, 255), thickness + outline_width * 2,
                            cv2.LINE_AA)
            cv2.putText(canvas, line, org, face, scale, (*color, 255),
                        thickness, cv2.LINE_AA)
        return canvas


def rotate_bgra(stamp: np.ndarray, degrees: float) -> np.ndarray:
    """绕中心旋转 BGRA 贴图，画布自动放大到能装下旋转后的内容，空白处 alpha=0"""
    if abs(degrees) < 0.01:
        return stamp
    h, w = stamp.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), degrees, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(h * sin + w * cos)
    new_h = int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2.0 - w / 2.0
    matrix[1, 2] += new_h / 2.0 - h / 2.0
    return cv2.warpAffine(stamp, matrix, (new_w, new_h),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(0, 0, 0, 0))


def alpha_paste(dst: np.ndarray, stamp: np.ndarray, x: int, y: int,
                opacity: float = 1.0) -> np.ndarray:
    """
    把 BGRA 贴图按 alpha 混合到 BGR 图上（原地修改 dst 并返回它）。
    贴图超出边界的部分会被裁掉，允许 x/y 为负。
    """
    if stamp is None or stamp.size == 0 or opacity <= 0:
        return dst
    dh, dw = dst.shape[:2]
    sh, sw = stamp.shape[:2]
    sx0, sy0 = max(0, -x), max(0, -y)
    dx0, dy0 = max(0, x), max(0, y)
    copy_w = min(sw - sx0, dw - dx0)
    copy_h = min(sh - sy0, dh - dy0)
    if copy_w <= 0 or copy_h <= 0:
        return dst

    src = stamp[sy0:sy0 + copy_h, sx0:sx0 + copy_w]
    roi = dst[dy0:dy0 + copy_h, dx0:dx0 + copy_w]
    alpha = src[:, :, 3].astype(np.float32) * (min(1.0, max(0.0, opacity)) / 255.0)
    alpha = alpha[:, :, None]
    blended = src[:, :, :3].astype(np.float32) * alpha + roi.astype(np.float32) * (1.0 - alpha)
    roi[:] = np.clip(blended, 0, 255).astype(np.uint8)
    return dst


# ════════════════════════════════════════════════════════════════
#  水印：添加与去除
# ════════════════════════════════════════════════════════════════

class WatermarkRenderer:
    """
    水印叠加。贴图只在第一帧（或画面尺寸变化时）渲染一次并缓存，
    之后每帧只做一次 alpha 混合，所以逐帧开销基本可以忽略。
    """

    def __init__(self, params: ProcessingParams):
        self.p = params
        self.error = ""
        self._stamp: Optional[np.ndarray] = None
        self._pos: Tuple[int, int] = (0, 0)
        self._tiled: Optional[np.ndarray] = None
        self._built_for: Optional[Tuple[int, int]] = None

    @staticmethod
    def signature(p: ProcessingParams) -> tuple:
        """参数指纹。用来判断缓存的贴图还能不能用（预览时参数会频繁变）"""
        return (p.watermark_type, p.watermark_text, p.watermark_image_path,
                p.watermark_font_path, p.watermark_font_size, p.watermark_color,
                p.watermark_outline_color, p.watermark_outline_width,
                p.watermark_scale, p.watermark_position, p.watermark_margin,
                p.watermark_custom_x, p.watermark_custom_y, p.watermark_rotation,
                p.watermark_tile, p.watermark_tile_gap)

    def _build_stamp(self, frame_w: int) -> Optional[np.ndarray]:
        p = self.p
        if p.watermark_type == "image":
            if not p.watermark_image_path:
                self.error = "未选择水印图片"
                return None
            img = imread_unicode(p.watermark_image_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                self.error = f"无法读取水印图片: {p.watermark_image_path}"
                return None
            if img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
            elif img.shape[2] == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
            target_w = max(8, int(frame_w * max(0.01, min(1.0, p.watermark_scale))))
            scale = target_w / img.shape[1]
            stamp = cv2.resize(img, (target_w, max(1, int(img.shape[0] * scale))),
                               interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        else:
            if not (p.watermark_text or "").strip():
                self.error = "水印文字为空"
                return None
            stamp = TextRenderer.render(
                p.watermark_text,
                font_path=p.watermark_font_path,
                font_size=p.watermark_font_size,
                color=hex_to_bgr(p.watermark_color),
                outline_color=hex_to_bgr(p.watermark_outline_color, (0, 0, 0)),
                outline_width=p.watermark_outline_width)
            if stamp is None:
                self.error = "水印文字渲染失败"
                return None
        return rotate_bgra(stamp, p.watermark_rotation)

    def _anchor(self, frame_w: int, frame_h: int,
                sw: int, sh: int) -> Tuple[int, int]:
        p = self.p
        m = max(0, p.watermark_margin)
        if p.watermark_position == "custom":
            return p.watermark_custom_x, p.watermark_custom_y
        vertical, _, horizontal = p.watermark_position.partition("-")
        if p.watermark_position == "center":
            vertical, horizontal = "middle", "center"
        x = {"left": m, "center": (frame_w - sw) // 2, "right": frame_w - sw - m}.get(
            horizontal, frame_w - sw - m)
        y = {"top": m, "middle": (frame_h - sh) // 2, "bottom": frame_h - sh - m}.get(
            vertical, frame_h - sh - m)
        return x, y

    def _build_tiled(self, stamp: np.ndarray,
                     frame_w: int, frame_h: int) -> np.ndarray:
        """把贴图铺满一整帧，之后每帧只需一次混合而不是 N 次"""
        gap = max(0, self.p.watermark_tile_gap)
        sh, sw = stamp.shape[:2]
        step_x, step_y = sw + gap, sh + gap
        canvas = np.zeros((frame_h, frame_w, 4), np.uint8)
        # 从负偏移起铺，保证四个边角也被覆盖到
        for y in range(-sh // 2, frame_h, step_y):
            for x in range(-sw // 2, frame_w, step_x):
                sx0, sy0 = max(0, -x), max(0, -y)
                dx0, dy0 = max(0, x), max(0, y)
                cw = min(sw - sx0, frame_w - dx0)
                ch = min(sh - sy0, frame_h - dy0)
                if cw > 0 and ch > 0:
                    canvas[dy0:dy0 + ch, dx0:dx0 + cw] = stamp[sy0:sy0 + ch, sx0:sx0 + cw]
        return canvas

    def apply(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        if self._built_for != (w, h):
            self._built_for = (w, h)
            self._stamp = self._build_stamp(w)
            self._tiled = None
            if self._stamp is not None:
                if self.p.watermark_tile:
                    self._tiled = self._build_tiled(self._stamp, w, h)
                else:
                    self._pos = self._anchor(w, h, self._stamp.shape[1],
                                             self._stamp.shape[0])
        if self._stamp is None:
            return frame
        result = frame.copy()
        if self._tiled is not None:
            return alpha_paste(result, self._tiled, 0, 0, self.p.watermark_opacity)
        return alpha_paste(result, self._stamp, self._pos[0], self._pos[1],
                           self.p.watermark_opacity)


class WatermarkRemover:
    """
    区域水印去除。

    半透明水印叠加是不可逆的，所以这里做的是「合理重建」而不是「还原」：
    inpaint 用周围像素把水印笔画补掉。智能蒙版模式先用形态学 top-hat/black-hat
    在区域内挑出比背景更亮或更暗的笔画，只重建那部分，比整块重绘能多留住细节。
    """

    @staticmethod
    def parse_regions(text: str, frame_w: int, frame_h: int
                      ) -> List[Tuple[int, int, int, int]]:
        """解析 'x,y,w,h; x,y,w,h' 或每行一个的区域列表，越界的自动夹到画面内"""
        regions: List[Tuple[int, int, int, int]] = []
        for chunk in re.split(r"[;\n]+", text or ""):
            nums = re.findall(r"-?\d+", chunk)
            if len(nums) < 4:
                continue
            x, y, w, h = (int(n) for n in nums[:4])
            x0, y0 = max(0, min(x, frame_w - 1)), max(0, min(y, frame_h - 1))
            x1, y1 = max(0, min(x + w, frame_w)), max(0, min(y + h, frame_h))
            if x1 - x0 > 1 and y1 - y0 > 1:
                regions.append((x0, y0, x1 - x0, y1 - y0))
        return regions

    @staticmethod
    def _smart_mask(roi: np.ndarray, sensitivity: int, grow: int) -> np.ndarray:
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        # 结构元素取区域短边的 1/4，比水印笔画粗、比背景渐变细
        span = max(3, (min(roi.shape[:2]) // 4) | 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (span, span))
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, kernel)
        thresh = max(1, int(sensitivity))
        mask = ((tophat > thresh) | (blackhat > thresh)).astype(np.uint8) * 255
        if grow > 0:
            mask = cv2.dilate(mask, cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE, (grow * 2 + 1, grow * 2 + 1)))
        # 一个像素都没挑出来说明灵敏度太高，退回整块重绘而不是什么都不做
        if cv2.countNonZero(mask) == 0:
            return np.full(gray.shape, 255, np.uint8)
        return mask

    @classmethod
    def apply(cls, frame: np.ndarray, params: ProcessingParams) -> np.ndarray:
        h, w = frame.shape[:2]
        regions = cls.parse_regions(params.wm_remove_regions, w, h)
        if not regions:
            return frame

        method = params.wm_remove_method
        result = frame.copy()

        if method in ("blur", "pixelate"):
            for (x, y, rw, rh) in regions:
                roi = result[y:y + rh, x:x + rw]
                if method == "blur":
                    k = max(3, (min(rw, rh) // 2) | 1)
                    result[y:y + rh, x:x + rw] = cv2.GaussianBlur(roi, (k, k), 0)
                else:
                    block = max(2, min(rw, rh) // 6)
                    small = cv2.resize(roi, (max(1, rw // block), max(1, rh // block)),
                                       interpolation=cv2.INTER_LINEAR)
                    result[y:y + rh, x:x + rw] = cv2.resize(
                        small, (rw, rh), interpolation=cv2.INTER_NEAREST)
            return result

        # inpaint 需要一张整帧蒙版；区域外保持 0，算法就只会重建区域内
        mask = np.zeros((h, w), np.uint8)
        for (x, y, rw, rh) in regions:
            if params.wm_remove_smart_mask:
                mask[y:y + rh, x:x + rw] = cls._smart_mask(
                    frame[y:y + rh, x:x + rw],
                    params.wm_remove_sensitivity, params.wm_remove_grow)
            else:
                mask[y:y + rh, x:x + rw] = 255
        flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
        radius = max(1, int(params.wm_remove_radius))
        return cv2.inpaint(result, mask, radius, flag)


# ════════════════════════════════════════════════════════════════
#  LUT 颜色分级
# ════════════════════════════════════════════════════════════════

class ColorLUT:
    """
    颜色查找表。支持三种来源：

    - `.cube`：Adobe/DaVinci 的标准文本格式，3D 和 1D 都能读
    - LUT 贴图 (png/jpg)：Hald 方阵 (如 512x512 = 64³) 和横条 (如 256x16 = 16³)
    - 内置预设：按曲线现算一张 33³ 的表，不需要任何外部文件

    3D 表存成 (N, N, N, 3) 的 float32，下标顺序是 [b, g, r]、值是 RGB —— 与
    .cube 里「红色变化最快」的行序一致，读文件时可以直接 reshape。
    """

    _cache: "OrderedDict[tuple, 'ColorLUT']" = OrderedDict()
    _CACHE_MAX = 6

    def __init__(self, table: np.ndarray, kind: str = "3d", name: str = ""):
        self.kind = kind
        self.name = name
        if kind == "3d":
            self.table = table
            self.size = table.shape[0]
            self._lut1d = None
        else:
            self.table = None
            self.size = 256
            self._lut1d = table          # (256, 3) uint8, BGR 顺序

    # ── 构造 ──────────────────────────────────────────────────

    @classmethod
    def load(cls, params: ProcessingParams) -> Tuple[Optional["ColorLUT"], str]:
        """按参数取 LUT，带缓存。返回 (lut, 错误信息)"""
        try:
            if params.lut_source == "file":
                path = (params.lut_path or "").strip()
                if not path:
                    return None, "未选择 LUT 文件"
                if not os.path.exists(path):
                    return None, f"LUT 文件不存在: {path}"
                key = ("file", os.path.abspath(path), os.path.getmtime(path))
            else:
                key = ("preset", params.lut_preset)

            cached = cls._cache.get(key)
            if cached is not None:
                cls._cache.move_to_end(key)
                return cached, ""

            if key[0] == "file":
                ext = os.path.splitext(params.lut_path)[1].lower()
                if ext == ".cube":
                    lut = cls.from_cube(params.lut_path)
                elif ext in IMAGE_EXTENSIONS:
                    lut = cls.from_image(params.lut_path)
                else:
                    return None, f"不支持的 LUT 格式: {ext or '(无扩展名)'}，请用 .cube 或 LUT 贴图"
            else:
                lut = cls.from_preset(params.lut_preset)

            cls._cache[key] = lut
            cls._cache.move_to_end(key)
            while len(cls._cache) > cls._CACHE_MAX:
                cls._cache.popitem(last=False)
            return lut, ""
        except Exception as e:
            LOGGER.error(f"LUT 加载失败: {e}")
            return None, f"LUT 加载失败: {e}"

    @classmethod
    def from_cube(cls, path: str) -> "ColorLUT":
        size_3d = size_1d = None
        domain_min, domain_max = [0.0] * 3, [1.0] * 3
        rows: List[Tuple[float, float, float]] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                upper = line.upper()
                if upper.startswith("LUT_3D_SIZE"):
                    size_3d = int(float(line.split()[-1]))
                    continue
                if upper.startswith("LUT_1D_SIZE"):
                    size_1d = int(float(line.split()[-1]))
                    continue
                if upper.startswith("DOMAIN_MIN"):
                    domain_min = [float(v) for v in line.split()[1:4]]
                    continue
                if upper.startswith("DOMAIN_MAX"):
                    domain_max = [float(v) for v in line.split()[1:4]]
                    continue
                if upper.startswith(("TITLE", "LUT_IN", "LUT_OUT")):
                    continue
                parts = line.split()
                if len(parts) < 3:
                    continue
                try:
                    rows.append((float(parts[0]), float(parts[1]), float(parts[2])))
                except ValueError:
                    continue

        if domain_min != [0.0] * 3 or domain_max != [1.0] * 3:
            LOGGER.warn(f"{os.path.basename(path)} 使用了非 0~1 的 DOMAIN，"
                        "本实现按 0~1 处理，色彩可能有偏差")

        data = np.asarray(rows, dtype=np.float32)
        if size_3d:
            expected = size_3d ** 3
            if len(rows) != expected:
                raise ValueError(f"LUT_3D_SIZE={size_3d} 需要 {expected} 行数据，"
                                 f"实际只有 {len(rows)} 行")
            table = np.clip(data.reshape(size_3d, size_3d, size_3d, 3), 0.0, 1.0)
            return cls(table, "3d", os.path.basename(path))
        if size_1d:
            if len(rows) != size_1d:
                raise ValueError(f"LUT_1D_SIZE={size_1d} 需要 {size_1d} 行数据，"
                                 f"实际只有 {len(rows)} 行")
            return cls(cls._resample_1d(data), "1d", os.path.basename(path))
        raise ValueError("文件里没有 LUT_3D_SIZE / LUT_1D_SIZE，不是有效的 .cube")

    @staticmethod
    def _resample_1d(data: np.ndarray) -> np.ndarray:
        """把任意长度的 1D LUT 重采样成 256 项的 BGR 查表"""
        xs = np.linspace(0.0, 255.0, data.shape[0])
        lut = np.empty((256, 3), np.uint8)
        for channel in range(3):                       # data 是 RGB 顺序
            values = np.interp(np.arange(256, dtype=np.float32), xs, data[:, channel])
            lut[:, 2 - channel] = np.clip(values * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return lut

    @classmethod
    def from_image(cls, path: str) -> "ColorLUT":
        img = imread_unicode(path, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"无法读取 LUT 贴图: {path}")
        h, w = img.shape[:2]
        if h == w:
            # Hald 方阵：边长 = N^1.5，横向排 w//N 个 N×N 小块
            size = int(round((w * h) ** (1.0 / 3.0)))
            if size < 2 or size ** 3 != w * h or w % size != 0:
                raise ValueError(f"{w}x{h} 不是有效的 Hald LUT 尺寸 (常见为 512x512 / 64x64)")
        elif w == h * h:
            size = h                                   # 横条布局，如 256x16
        else:
            raise ValueError(f"无法识别的 LUT 贴图布局: {w}x{h}"
                             "（支持 Hald 方阵和 N²xN 横条）")

        tiles_per_row = w // size
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        table = np.empty((size, size, size, 3), np.float32)
        for blue in range(size):
            ty, tx = divmod(blue, tiles_per_row)
            tile = rgb[ty * size:(ty + 1) * size, tx * size:(tx + 1) * size]
            table[blue] = tile                         # tile[g, r] 正好对上 [g, r]
        return cls(np.clip(table, 0.0, 1.0), "3d", os.path.basename(path))

    @classmethod
    def from_preset(cls, name: str) -> "ColorLUT":
        size = 33
        axis = np.linspace(0.0, 1.0, size, dtype=np.float32)
        blue, green, red = np.meshgrid(axis, axis, axis, indexing="ij")
        rgb = np.stack([red, green, blue], axis=-1)
        table = np.clip(cls._preset_curve(name, rgb), 0.0, 1.0).astype(np.float32)
        return cls(table, "3d", name)

    @staticmethod
    def _preset_curve(name: str, rgb: np.ndarray) -> np.ndarray:
        """对归一化 RGB 施加预设曲线。输入输出形状都是 (..., 3)"""
        luma = (rgb * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1, keepdims=True)

        def smoothstep(x, amount):
            return x * (1.0 - amount) + (x * x * (3.0 - 2.0 * x)) * amount

        if name == "warm_sun":
            out = rgb * np.array([1.10, 1.02, 0.90], np.float32)
            return np.power(np.clip(out, 0, 1), 0.95)
        if name == "cool_blue":
            out = rgb * np.array([0.92, 0.99, 1.12], np.float32)
            return smoothstep(np.clip(out, 0, 1), 0.25)
        if name == "faded_film":
            # 抬黑位、压白位 = 降对比，再往中间调加一点绿，模拟褪色胶片
            out = rgb * 0.78 + 0.13
            return out + np.array([-0.01, 0.02, 0.0], np.float32) * (1.0 - np.abs(luma - 0.5) * 2)
        if name == "black_gold":
            desaturated = luma + (rgb - luma) * 0.22
            return smoothstep(np.clip(desaturated, 0, 1), 0.35) + \
                np.array([0.05, 0.025, -0.03], np.float32) * np.power(luma, 2)
        if name == "mono_contrast":
            return np.repeat(smoothstep(luma, 0.85), 3, axis=-1)
        if name == "vivid":
            saturated = luma + (rgb - luma) * 1.35
            return smoothstep(np.clip(saturated, 0, 1), 0.2)
        # cinematic: 阴影推向青蓝、高光推向橙黄，再加一点 S 曲线
        shadows = np.array([-0.02, 0.015, 0.055], np.float32) * (1.0 - luma)
        highlights = np.array([0.07, 0.025, -0.045], np.float32) * np.power(luma, 1.6)
        return smoothstep(np.clip(rgb + shadows + highlights, 0, 1), 0.3)

    # ── 应用 ──────────────────────────────────────────────────

    def apply(self, frame: np.ndarray, strength: float = 1.0,
              fast: bool = False) -> np.ndarray:
        if self.kind == "1d":
            channels = list(cv2.split(frame))
            for i in range(3):
                channels[i] = cv2.LUT(channels[i], self._lut1d[:, i])
            graded = cv2.merge(channels)
        else:
            graded = self._apply_3d(frame, fast)
        strength = max(0.0, min(1.0, strength))
        if strength >= 0.999:
            return graded
        if strength <= 0.001:
            return frame
        return cv2.addWeighted(graded, strength, frame, 1.0 - strength, 0)

    def _apply_3d(self, frame: np.ndarray, fast: bool) -> np.ndarray:
        size = self.size
        table = self.table
        scale = (size - 1) / 255.0
        out = np.empty_like(frame)
        # 三线性插值要同时持有 8 个 (h, w, 3) float32 中间量，1080p 一次算完
        # 峰值内存能到几百 MB，4K 更夸张，所以按行分块把峰值压在几十 MB
        rows = max(1, int(3_000_000 // max(1, frame.shape[1] * 12)))
        for y0 in range(0, frame.shape[0], rows):
            chunk = frame[y0:y0 + rows]
            bf = chunk[:, :, 0].astype(np.float32) * scale
            gf = chunk[:, :, 1].astype(np.float32) * scale
            rf = chunk[:, :, 2].astype(np.float32) * scale
            if fast or size < 2:
                rgb = table[np.rint(bf).astype(np.int32),
                            np.rint(gf).astype(np.int32),
                            np.rint(rf).astype(np.int32)]
            else:
                rgb = self._trilinear(table, bf, gf, rf, size)
            # 表里存的是 RGB，写回帧要翻回 BGR
            out[y0:y0 + rows] = np.clip(rgb[:, :, ::-1] * 255.0 + 0.5, 0, 255).astype(np.uint8)
        return out

    @staticmethod
    def _trilinear(table: np.ndarray, bf: np.ndarray, gf: np.ndarray,
                   rf: np.ndarray, size: int) -> np.ndarray:
        top = size - 2
        b0 = np.clip(np.floor(bf), 0, top).astype(np.int32)
        g0 = np.clip(np.floor(gf), 0, top).astype(np.int32)
        r0 = np.clip(np.floor(rf), 0, top).astype(np.int32)
        b1, g1, r1 = b0 + 1, g0 + 1, r0 + 1
        db = (bf - b0)[:, :, None]
        dg = (gf - g0)[:, :, None]
        dr = (rf - r0)[:, :, None]

        def lerp_r(bi, gi):
            low = table[bi, gi, r0]
            return low + (table[bi, gi, r1] - low) * dr

        c00, c01 = lerp_r(b0, g0), lerp_r(b0, g1)
        c10, c11 = lerp_r(b1, g0), lerp_r(b1, g1)
        c0 = c00 + (c01 - c00) * dg
        c1 = c10 + (c11 - c10) * dg
        return c0 + (c1 - c0) * db


# ════════════════════════════════════════════════════════════════
#  字幕：解析、渲染、导出
# ════════════════════════════════════════════════════════════════

@dataclass
class SubtitleCue:
    """一条字幕：起止时间 (秒) 加文本，文本里的 \\n 表示换行"""
    start: float
    end: float
    text: str


class SubtitleFile:
    """SRT / ASS 字幕的读写。ASS 只取时间和文本，样式覆盖标签直接剥掉"""

    _SRT_TIME = re.compile(
        r"(\d+):([0-5]?\d):([0-5]?\d)[,.](\d{1,3})\s*-->\s*"
        r"(\d+):([0-5]?\d):([0-5]?\d)[,.](\d{1,3})")
    _ASS_TAGS = re.compile(r"\{[^}]*\}")

    @staticmethod
    def _read_text(path: str) -> str:
        """字幕文件编码五花八门，按最可能的顺序试，latin-1 兜底保证不抛异常"""
        raw = Path(path).read_bytes()
        for encoding in ("utf-8-sig", "utf-8", "gb18030", "big5", "cp1252"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("latin-1", errors="replace")

    @classmethod
    def load(cls, path: str) -> List[SubtitleCue]:
        text = cls._read_text(path)
        ext = os.path.splitext(path)[1].lower()
        cues = cls._parse_ass(text) if ext in (".ass", ".ssa") else cls._parse_srt(text)
        if not cues and ext not in (".ass", ".ssa"):
            cues = cls._parse_ass(text)      # 扩展名不靠谱时再试一次
        cues.sort(key=lambda c: c.start)
        return cues

    @classmethod
    def _parse_srt(cls, text: str) -> List[SubtitleCue]:
        """
        SRT 的结构是「序号 / 时间行 / 若干行正文 / 空行」，所以正文在遇到空行
        时就结束了 —— 不能一路读到下一条时间行，那样会把空行和下一条的序号
        一起吞进正文里。
        """
        cues: List[SubtitleCue] = []
        pending: Optional[Tuple[float, float]] = None
        lines: List[str] = []

        def flush():
            nonlocal pending, lines
            if pending and lines:
                body = lines
                # 有些文件不留空行分隔，此时上一条正文的末尾会粘上下一条的序号。
                # 只在正文多于一行时剥掉纯数字尾行，免得误伤真的只写了个数字的字幕
                if len(body) > 1 and body[-1].strip().isdigit():
                    body = body[:-1]
                cues.append(SubtitleCue(pending[0], pending[1], "\n".join(body).strip()))
            pending, lines = None, []

        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            match = cls._SRT_TIME.search(raw)
            if match:
                flush()
                nums = [int(g) for g in match.groups()]
                start = nums[0] * 3600 + nums[1] * 60 + nums[2] + nums[3] / 1000.0
                end = nums[4] * 3600 + nums[5] * 60 + nums[6] + nums[7] / 1000.0
                pending = (start, end)
                continue
            if pending is None:
                continue
            if not raw.strip():
                # 时间行和正文之间偶尔夹空行，那种情况别急着结束这一条
                if lines:
                    flush()
                continue
            lines.append(raw.rstrip())
        flush()
        return [c for c in cues if c.text and c.end > c.start]

    @classmethod
    def _parse_ass(cls, text: str) -> List[SubtitleCue]:
        cues: List[SubtitleCue] = []
        # 字段顺序由 [Events] 里的 Format 行决定，不能写死下标
        idx_start, idx_end, idx_text, field_count = 1, 2, 9, 10
        for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw.strip()
            if line.lower().startswith("format:") and "start" in line.lower():
                names = [n.strip().lower() for n in line.split(":", 1)[1].split(",")]
                field_count = len(names)
                for key, default in (("start", 1), ("end", 2), ("text", field_count - 1)):
                    if key in names:
                        value = names.index(key)
                    else:
                        value = default
                    if key == "start":
                        idx_start = value
                    elif key == "end":
                        idx_end = value
                    else:
                        idx_text = value
                continue
            if not line.lower().startswith("dialogue:"):
                continue
            # Text 是最后一个字段且可以包含逗号，所以限制 split 次数
            parts = line.split(":", 1)[1].split(",", field_count - 1)
            if len(parts) <= max(idx_start, idx_end, idx_text):
                continue
            start = cls._parse_ass_time(parts[idx_start])
            end = cls._parse_ass_time(parts[idx_end])
            if start is None or end is None or end <= start:
                continue
            body = cls._ASS_TAGS.sub("", parts[idx_text])
            body = body.replace("\\N", "\n").replace("\\n", "\n").replace("\\h", " ")
            body = body.strip()
            if body:
                cues.append(SubtitleCue(start, end, body))
        return cues

    @staticmethod
    def _parse_ass_time(value: str) -> Optional[float]:
        parts = value.strip().split(":")
        if len(parts) != 3:
            return None
        try:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        except ValueError:
            return None

    @staticmethod
    def format_timestamp(seconds: float) -> str:
        seconds = max(0.0, seconds)
        millis = int(round(seconds * 1000))
        hours, millis = divmod(millis, 3600_000)
        minutes, millis = divmod(millis, 60_000)
        secs, millis = divmod(millis, 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @classmethod
    def save_srt(cls, cues: List[SubtitleCue], path: str) -> None:
        blocks = []
        for index, cue in enumerate(cues, 1):
            blocks.append(f"{index}\n"
                          f"{cls.format_timestamp(cue.start)} --> "
                          f"{cls.format_timestamp(cue.end)}\n"
                          f"{cue.text}\n")
        Path(path).write_text("\n".join(blocks), encoding="utf-8")

    @staticmethod
    def cue_at(cues: List[SubtitleCue], moment: float) -> Optional[SubtitleCue]:
        """找当前时刻该显示哪条字幕。cues 已按开始时间排序，用二分定位"""
        if not cues:
            return None
        import bisect
        pos = bisect.bisect_right([c.start for c in cues], moment)
        # 时间轴重叠时靠后的条目优先，所以从候选里往前找第一条还没结束的
        for i in range(pos - 1, max(-1, pos - 4), -1):
            if i >= 0 and cues[i].start <= moment < cues[i].end:
                return cues[i]
        return None


class SubtitleBurner:
    """把字幕画到帧上。同一句台词会持续几十帧，所以渲染结果按文本缓存"""

    def __init__(self, params: ProcessingParams, cues: List[SubtitleCue]):
        self.p = params
        self.cues = cues
        self._cache: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
        self._CACHE_MAX = 48

    def _stamp_for(self, text: str, frame_h: int) -> Optional[np.ndarray]:
        p = self.p
        size = p.subtitle_font_size if p.subtitle_font_size > 0 \
            else max(14, int(frame_h * 0.045))
        key = (text, size, p.subtitle_color, p.subtitle_outline_color,
               p.subtitle_outline_width, p.subtitle_font_path)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        stamp = TextRenderer.render(
            text, font_path=p.subtitle_font_path, font_size=size,
            color=hex_to_bgr(p.subtitle_color),
            outline_color=hex_to_bgr(p.subtitle_outline_color, (0, 0, 0)),
            outline_width=p.subtitle_outline_width)
        if stamp is None:
            return None
        self._cache[key] = stamp
        self._cache.move_to_end(key)
        while len(self._cache) > self._CACHE_MAX:
            self._cache.popitem(last=False)
        return stamp

    def apply(self, frame: np.ndarray, moment: float) -> np.ndarray:
        cue = SubtitleFile.cue_at(self.cues, moment - self.p.subtitle_time_offset)
        if cue is None:
            return frame
        h, w = frame.shape[:2]
        stamp = self._stamp_for(cue.text, h)
        if stamp is None:
            return frame
        sh, sw = stamp.shape[:2]
        x = (w - sw) // 2
        y = max(0, h - sh - max(0, self.p.subtitle_bottom_margin))
        result = frame.copy()
        box_opacity = max(0.0, min(1.0, self.p.subtitle_box_opacity))
        if box_opacity > 0:
            pad = max(4, sh // 8)
            y0, y1 = max(0, y - pad), min(h, y + sh + pad)
            x0, x1 = max(0, x - pad), min(w, x + sw + pad)
            roi = result[y0:y1, x0:x1]
            roi[:] = (roi.astype(np.float32) * (1.0 - box_opacity)).astype(np.uint8)
        return alpha_paste(result, stamp, x, y, 1.0)


# ════════════════════════════════════════════════════════════════
#  视频处理引擎
# ════════════════════════════════════════════════════════════════

class FrameSink:
    """
    统一的帧写出接口。

    选 H.264/H.265 时把 BGR 原始帧写进 ffmpeg 的 stdin，由 libx264/libx265 编码。
    只有这条路能支持 CRF / 目标码率控制和音轨复用 —— cv2.VideoWriter 只认 fourcc，
    这三件事一件都做不到。其余编码器（或 FFmpeg 不可用时）退回 cv2.VideoWriter。
    """

    FFMPEG_CODECS = {"h264": "libx264", "h265": "libx265"}
    FOURCC = {"mp4v": "mp4v", "xvid": "XVID"}

    def __init__(self, output_path: str, fps: float, width: int, height: int,
                 params: Optional[ProcessingParams] = None,
                 audio_source: Optional[str] = None,
                 audio_trim: Optional[Tuple[float, float]] = None):
        self.output_path = output_path
        self.fps = max(0.01, float(fps))
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self.backend = "none"
        self.error = ""
        self.frames_written = 0
        self._proc: Optional[subprocess.Popen] = None
        self._writer: Optional[cv2.VideoWriter] = None
        self._stderr_tail: deque = deque(maxlen=40)
        self._stderr_thread: Optional[threading.Thread] = None

        codec = ((params.video_codec if params else "auto") or "auto").lower()
        if codec in self.FFMPEG_CODECS:
            if ffmpeg_available():
                if self._open_ffmpeg(params, audio_source, audio_trim):
                    return
                LOGGER.warn(f"FFmpeg 编码启动失败，退回 cv2.VideoWriter: {self.error}")
            else:
                LOGGER.warn(f"选择了 {codec.upper()} 但未检测到 FFmpeg，"
                            f"退回 cv2.VideoWriter (mp4v)")
            codec = "auto"
        self._open_cv2(codec)

    # ── FFmpeg 后端 ─────────────────────────────────────────────

    def _build_ffmpeg_cmd(self, params: ProcessingParams,
                          audio_source: Optional[str],
                          audio_trim: Optional[Tuple[float, float]]) -> List[str]:
        encoder = self.FFMPEG_CODECS[params.video_codec.lower()]
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
               "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{self.width}x{self.height}", "-r", f"{self.fps:.6f}", "-i", "-"]

        use_audio = bool(audio_source) and params.keep_audio
        if use_audio:
            # 输入侧裁剪：视频帧从 start_time 开始写，音频也得从同一位置取
            if audio_trim:
                start, duration = audio_trim
                if start > 0:
                    cmd += ["-ss", f"{start:.3f}"]
                if duration > 0:
                    cmd += ["-t", f"{duration:.3f}"]
            cmd += ["-i", audio_source]

        cmd += ["-map", "0:v:0"]
        if use_audio:
            # 尾部的 ? 表示「源没有音轨就跳过」，否则整条命令会直接失败
            cmd += ["-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            cmd += ["-an"]

        cmd += ["-c:v", encoder,
                "-preset", params.encode_preset if params.encode_preset in FFMPEG_PRESETS else "medium"]
        if params.rate_mode == "bitrate":
            br = max(100, int(params.bitrate_kbps))
            cmd += ["-b:v", f"{br}k", "-maxrate", f"{br * 2}k", "-bufsize", f"{br * 4}k"]
        else:
            cmd += ["-crf", str(int(min(51, max(0, params.crf))))]

        # yuv420p 要求宽高都是偶数，奇数分辨率补一行/一列而不是缩放，避免画面变形
        cmd += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p"]
        if encoder == "libx265":
            cmd += ["-tag:v", "hvc1"]  # 不打这个 tag，Apple 系播放器认不出 HEVC
        if os.path.splitext(self.output_path)[1].lower() in (".mp4", ".mov", ".m4v"):
            cmd += ["-movflags", "+faststart"]
        cmd.append(self.output_path)
        return cmd

    def _open_ffmpeg(self, params: ProcessingParams,
                     audio_source: Optional[str],
                     audio_trim: Optional[Tuple[float, float]]) -> bool:
        cmd = self._build_ffmpeg_cmd(params, audio_source, audio_trim)
        LOGGER.debug("FFmpeg: " + " ".join(cmd))
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE, **SUBPROCESS_FLAGS)
        except Exception as e:
            self.error = str(e)
            self._proc = None
            return False

        # stderr 必须持续排空，管道写满会让 ffmpeg 卡死在写日志上
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

        self.backend = f"ffmpeg/{self.FFMPEG_CODECS[params.video_codec.lower()]}"
        mode = (f"{params.bitrate_kbps}kbps" if params.rate_mode == "bitrate"
                else f"CRF {params.crf}")
        LOGGER.info(f"编码器: {self.backend} | {mode} | preset={params.encode_preset} | "
                    f"{self.width}x{self.height}@{self.fps:.2f} | "
                    f"音频: {'保留' if audio_source and params.keep_audio else '丢弃'}")
        return True

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                text = line.decode("utf-8", "replace").rstrip()
                if text:
                    self._stderr_tail.append(text)
        except (OSError, ValueError):
            pass

    def _stderr_text(self) -> str:
        return "\n".join(self._stderr_tail)

    # ── cv2 后端 ────────────────────────────────────────────────

    def _open_cv2(self, codec: str) -> None:
        ext = os.path.splitext(self.output_path)[1].lower()
        if codec in self.FOURCC:
            tag = self.FOURCC[codec]
        elif ext == ".avi":
            tag = "XVID"
        else:
            tag = "mp4v"
        fourcc = cv2.VideoWriter_fourcc(*tag)
        writer = cv2.VideoWriter(self.output_path, fourcc, self.fps,
                                 (self.width, self.height))
        if not writer.isOpened():
            self.error = f"无法创建输出文件 (fourcc={tag}): {self.output_path}"
            return
        self._writer = writer
        self.backend = f"cv2/{tag}"
        LOGGER.info(f"编码器: {self.backend} | {self.width}x{self.height}@{self.fps:.2f}")

    # ── 公共接口 ────────────────────────────────────────────────

    @property
    def is_open(self) -> bool:
        return self._proc is not None or self._writer is not None

    def write(self, frame: np.ndarray) -> bool:
        if frame.ndim == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            frame = cv2.resize(frame, (self.width, self.height))

        if self._proc is not None:
            if not frame.flags["C_CONTIGUOUS"]:
                frame = np.ascontiguousarray(frame)
            try:
                self._proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError) as e:
                self.error = (f"FFmpeg 编码进程提前退出: {e}\n{self._stderr_text()}").strip()
                LOGGER.error(self.error)
                return False
            self.frames_written += 1
            return True

        if self._writer is not None:
            self._writer.write(frame)
            self.frames_written += 1
            return True

        self.error = "输出未打开"
        return False

    def close(self) -> bool:
        """收尾并返回是否成功。FFmpeg 后端必须等进程退出，否则文件尾部索引写不完整"""
        ok = not self.error
        if self._proc is not None:
            proc, self._proc = self._proc, None
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                ret = proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                proc.kill()
                ret = -1
                self.error = "FFmpeg 收尾超时，已强制结束"
            if ret != 0:
                ok = False
                if not self.error:
                    self.error = f"FFmpeg 退出码 {ret}\n{self._stderr_text()}".strip()
                LOGGER.error(self.error)
            if self._stderr_thread is not None:
                self._stderr_thread.join(timeout=5)
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        return ok


class VideoEngine:
    """核心视频处理引擎"""

    def __init__(self):
        self.dnn = DNNEngine()
        self.filter = FilterEngine()
        self._cancel = False
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        self._style_reference_img: Optional[np.ndarray] = None
        # 当前正在处理的帧对应的时间戳 (秒)。字幕烧录要靠它决定显示哪一句，
        # 逐帧函数拿不到 cap，所以由读帧的循环负责更新。
        self._frame_time = 0.0
        self._watermark: Optional[WatermarkRenderer] = None
        self._watermark_signature: Optional[tuple] = None
        self._lut: Optional[ColorLUT] = None
        self._subtitles: Optional[SubtitleBurner] = None
        self._bg_replacement: Optional[np.ndarray] = None
        self._rvm_fallback_logged = False

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        self._progress_callback = callback

    def cancel(self):
        self._cancel = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel

    def _report_progress(self, progress: float, message: str = ""):
        if self._progress_callback:
            self._progress_callback(progress, message)

    @staticmethod
    def get_video_info(path: str) -> Optional[VideoInfo]:
        if not os.path.exists(path):
            return None
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            return None
        info = VideoInfo()
        info.path = path
        info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        info.fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        info.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        info.duration = info.frame_count / info.fps if info.fps > 0 else 0
        fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        info.codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
        info.file_size = os.path.getsize(path)
        cap.release()
        return info

    @staticmethod
    def _audio_plan(params: ProcessingParams
                    ) -> Tuple[Optional[str], Optional[Tuple[float, float]]]:
        """
        决定要不要把源视频的音轨复用到输出里，以及音频要裁掉哪一段。

        帧率调整会等比拉长/压缩时长（所有帧都写出去，只是以新 fps 播放），
        音频没法跟着变，所以那种情况下直接丢弃音轨而不是产出音画不同步的文件。
        """
        if not params.keep_audio or params.task == ProcessingTask.FPS_CHANGE:
            return None, None
        if not params.input_path or not os.path.exists(params.input_path):
            return None, None
        start = max(0.0, params.start_time)
        duration = params.end_time - start if params.end_time > 0 else 0.0
        return params.input_path, (start, max(0.0, duration))

    def process_video(self, params: ProcessingParams) -> bool:
        """通用视频处理流水线"""
        self._cancel = False

        if params.style_reference_path and os.path.exists(params.style_reference_path):
            self._style_reference_img = cv2.imread(params.style_reference_path)
        else:
            self._style_reference_img = None

        # ═══ 修正输出路径 ═══
        params.output_path = self._fix_output_path(params)

        # ═══ 外部资源 (水印贴图 / LUT / 字幕轨 / 背景图) ═══
        active_tasks = list(params.pipeline_tasks) if params.task == ProcessingTask.PIPELINE \
            else [params.task]
        ready, asset_error = self._prepare_assets(params, active_tasks)
        if not ready:
            self._report_progress(-1, asset_error)
            LOGGER.error(f"资源准备失败: {asset_error}")
            return False

        # ═══ 分析任务特殊处理 ═══
        if params.task in ANALYSIS_TASKS:
            self._report_progress(0, f"分析结果将保存到: {params.output_path}")
            cap = cv2.VideoCapture(params.input_path)
            if not cap.isOpened():
                self._report_progress(-1, "无法打开输入视频")
                return False
            info = self.get_video_info(params.input_path)
            result = self._analyze_video(cap, params, info)
            # ★ cap 已在 _analyze_video 中 release
            return result

        # ═══ 字幕 OCR：产出的是 SRT 文本，不走视频编码器 ═══
        if params.task == ProcessingTask.SUBTITLE_OCR:
            cap = cv2.VideoCapture(params.input_path)
            if not cap.isOpened():
                self._report_progress(-1, "无法打开输入视频")
                return False
            if not self._init_dnn_for_task(params):
                cap.release()
                return False
            self._report_progress(0, f"字幕将导出到: {params.output_path}")
            # cap 由 _ocr_subtitles 负责 release
            return self._ocr_subtitles(cap, params, self.get_video_info(params.input_path))

        cap = cv2.VideoCapture(params.input_path)
        if not cap.isOpened():
            self._report_progress(-1, "无法打开输入视频")
            return False

        info = self.get_video_info(params.input_path)
        fps = info.fps if info else 30.0
        total_frames = info.frame_count if info else 0

        start_frame = int(params.start_time * fps) if params.start_time > 0 else 0
        end_frame = int(params.end_time * fps) if params.end_time > 0 else total_frames

        out_w, out_h = self._get_output_size(params, info)
        out_fps = params.target_fps if params.task == ProcessingTask.FPS_CHANGE else fps

        # 特殊任务分流
        if params.task == ProcessingTask.TO_GIF:
            return self._convert_to_gif(cap, params, info)
        if params.task == ProcessingTask.EXTRACT_FRAMES:
            return self._extract_frames(cap, params, info)
        if params.task == ProcessingTask.CONCAT:
            cap.release()
            return self._concat_videos(params)

        # 创建输出
        audio_source, audio_trim = self._audio_plan(params)
        sink = FrameSink(params.output_path, out_fps, out_w, out_h, params,
                         audio_source=audio_source, audio_trim=audio_trim)
        if not sink.is_open:
            cap.release()
            self._report_progress(-1, sink.error or f"无法创建输出文件: {params.output_path}")
            return False

        # 初始化 DNN
        if not self._init_dnn_for_task(params):
            cap.release()
            sink.close()
            return False

        if params.task == ProcessingTask.PIPELINE:
            for pt in params.pipeline_tasks:
                sub_params = ProcessingParams(task=pt)
                sub_params.style_model_name = params.style_model_name
                sub_params.demosaic_model = params.demosaic_model
                if not self._init_dnn_for_task(sub_params):
                    cap.release()
                    sink.close()
                    return False

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        processed = 0
        total_to_process = end_frame - start_frame
        write_failed = False

        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if current_frame > end_frame:
                break

            # 字幕烧录靠这个时间戳取当前该显示哪一句。用源视频的 fps 而不是
            # 输出 fps，这样即使在做帧率转换，字幕也还是对齐原始时间轴的。
            self._frame_time = (current_frame - 1) / fps if fps > 0 else 0.0

            if params.task == ProcessingTask.PIPELINE:
                processed_frame = self._process_frame_pipeline(frame, params)
            else:
                processed_frame = self._process_frame(frame, params)

            if not sink.write(processed_frame):
                write_failed = True
                break
            processed += 1

            if total_to_process > 0:
                progress = processed / total_to_process
                self._report_progress(progress,
                    f"处理中: {processed}/{total_to_process} 帧 ({progress * 100:.1f}%)")

        cap.release()
        closed_ok = sink.close()

        if self._cancel:
            self._report_progress(-1, "已取消")
            self._remove_quietly(params.output_path)
            return False

        if write_failed or not closed_ok:
            self._report_progress(-1, f"编码失败: {sink.error}")
            self._remove_quietly(params.output_path)
            return False

        LOGGER.info(f"处理完成: {params.output_path} ({processed} 帧, {sink.backend})")
        self._report_progress(1.0, "处理完成!")
        return True

    @staticmethod
    def _remove_quietly(path: str) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError as e:
            LOGGER.warn(f"删除未完成的输出失败: {path} ({e})")

    @staticmethod
    def _fix_output_path(params: ProcessingParams) -> str:
        path = params.output_path
        if not path:
            path = os.path.join(os.getcwd(), "output")

        base_no_ext, current_ext = os.path.splitext(path)
        current_ext_lower = current_ext.lower()

        if params.task in ANALYSIS_TASKS:
            if current_ext_lower in VIDEO_EXTENSIONS or current_ext_lower in ('', '.gif'):
                return base_no_ext + '.png'
            elif current_ext_lower not in ('.png', '.jpg', '.jpeg', '.bmp', '.tiff'):
                return base_no_ext + '.png'
            return path
        elif params.task == ProcessingTask.SUBTITLE_OCR:
            return path if current_ext_lower == '.srt' else base_no_ext + '.srt'
        elif params.task == ProcessingTask.EXTRACT_FRAMES:
            if current_ext_lower in VIDEO_EXTENSIONS or current_ext_lower in ('.gif', '.png', '.jpg'):
                return base_no_ext + '_frames'
            return path
        elif params.task == ProcessingTask.TO_GIF:
            if current_ext_lower != '.gif':
                return base_no_ext + '.gif'
            return path
        else:
            if current_ext_lower in ('.png', '.jpg', '.jpeg', '.bmp', '.gif'):
                return base_no_ext + '.mp4'
            elif current_ext_lower == '':
                return base_no_ext + '.mp4'
            return path

    def _get_output_size(self, params: ProcessingParams,
                         info: Optional[VideoInfo]) -> Tuple[int, int]:
        w = info.width if info else 640
        h = info.height if info else 480

        if params.task == ProcessingTask.RESIZE:
            if params.target_width > 0 and params.target_height > 0:
                return params.target_width, params.target_height
            elif params.target_width > 0 and params.keep_aspect:
                return params.target_width, int(h * params.target_width / w)
            elif params.target_height > 0 and params.keep_aspect:
                return int(w * params.target_height / h), params.target_height

        if params.task == ProcessingTask.ROTATE and params.rotation in (90, 270):
            return h, w

        return w, h

    def _prepare_assets(self, params: ProcessingParams,
                        tasks: Optional[List[ProcessingTask]] = None) -> Tuple[bool, str]:
        """
        准备逐帧处理要用到的外部资源：水印贴图、LUT、字幕轨、背景替换图。

        这些都是「一次加载、每帧复用」的东西，放在循环外做掉，同时也把
        「文件找不到」这类错误提前暴露出来，而不是跑到一半才发现。
        返回 (是否可以继续, 错误信息)。
        """
        active = set(tasks or [params.task])
        # 先全部清空。否则上一次任务留下的字幕轨/水印会渗到这一次里，
        # 预览时尤其明显（切换功能后旧字幕还挂在画面上）
        self._watermark = None
        self._watermark_signature = None
        self._lut = None
        self._subtitles = None
        self._bg_replacement = None

        if ProcessingTask.WATERMARK_ADD in active:
            renderer = WatermarkRenderer(params)
            # 先按一个标称宽度渲染一次做校验：文字空了、图片读不出来这类问题
            # 要在开跑之前就报出来，而不是白跑一遍发现没加上水印
            if renderer._build_stamp(1920) is None:
                return False, f"水印无法生成: {renderer.error}"
            self._watermark = renderer
            self._watermark_signature = WatermarkRenderer.signature(params)

        if ProcessingTask.LUT_GRADE in active:
            self._lut, error = ColorLUT.load(params)
            if self._lut is None:
                return False, error or "LUT 加载失败"

        if ProcessingTask.SUBTITLE_BURN in active:
            path = (params.subtitle_path or "").strip()
            if not path:
                return False, "请先选择字幕文件 (.srt / .ass)"
            if not os.path.exists(path):
                return False, f"字幕文件不存在: {path}"
            try:
                cues = SubtitleFile.load(path)
            except Exception as e:
                return False, f"字幕解析失败: {e}"
            if not cues:
                return False, f"字幕文件里没有解析出任何条目: {os.path.basename(path)}"
            self._subtitles = SubtitleBurner(params, cues)
            LOGGER.info(f"[字幕烧录] {os.path.basename(path)} 共 {len(cues)} 条，"
                        f"覆盖到 {SubtitleFile.format_timestamp(cues[-1].end)}")

        if ProcessingTask.BG_BLUR in active and params.bg_mode == "image":
            path = (params.bg_image_path or "").strip()
            if not path or not os.path.exists(path):
                return False, "背景替换模式选了「图片」，但没有指定有效的图片"
            self._bg_replacement = imread_unicode(path, cv2.IMREAD_COLOR)
            if self._bg_replacement is None:
                return False, f"无法读取背景图片: {path}"

        return True, ""

    def _init_dnn_for_task(self, params: ProcessingParams) -> bool:
        task = params.task
        if task == ProcessingTask.BG_BLUR:
            return self._init_segmentation(params)
        if task == ProcessingTask.SUBTITLE_OCR:
            if not self.dnn.load_east():
                self._report_progress(-1, "EAST 文字检测模型未找到: "
                                          f"{self.dnn.get_load_error('east')}")
                return False
            if not self.dnn.load_crnn(params.ocr_model):
                err = self.dnn.get_load_error(f"crnn_{params.ocr_model}")
                self._report_progress(-1, f"文字识别模型加载失败:\n{err}")
                return False
            return True
        if task in (ProcessingTask.FACE_DETECT, ProcessingTask.FACE_MOSAIC):
            if not self.dnn.load_face_detector():
                err = self.dnn.get_load_error("face_detector")
                self._report_progress(-1, f"人脸检测模型未找到: {err}")
                return False
        elif task == ProcessingTask.OBJECT_DETECT:
            if not self.dnn.load_yolo():
                err = self.dnn.get_load_error("yolo")
                self._report_progress(-1, f"YOLO 模型未找到: {err}")
                return False
        elif task == ProcessingTask.STYLE_TRANSFER:
            if not self.dnn.load_style_transfer(params.style_model_name):
                key = f"style_{params.style_model_name}"
                err = self.dnn.get_load_error(key)
                self._report_progress(-1, f"风格迁移模型加载失败:\n{err}")
                return False
        elif task == ProcessingTask.TEXT_DETECT:
            if not self.dnn.load_east():
                err = self.dnn.get_load_error("east")
                self._report_progress(-1, f"EAST 文字检测模型未找到: {err}")
                return False
        elif task == ProcessingTask.DEMOSAIC:
            # 时序状态必须在任务开始时清空，否则会带入上一次处理的残留帧
            self.dnn.reset_deepmosaics_state()
            self.dnn._demosaic_fallback_warned.discard(params.demosaic_model)
            if not self.dnn.load_demosaic_model(params.demosaic_model):
                err = self.dnn.get_load_error(f"demosaic_{params.demosaic_model}")
                # 不 return False —— apply_demosaic 会通过 resolve_demosaic_model
                # 自动降级到传统方法，这里只负责把原因告诉用户
                self._report_progress(0, f"去马赛克模型加载失败，改用传统增强方法\n{err}")
                LOGGER.warn(f"去马赛克模型 {params.demosaic_model} 加载失败: {err}")
        return True

    def _init_segmentation(self, params: ProcessingParams) -> bool:
        """
        背景虚化的模型准备。

        首选 RVM 做真正的人像分割；模型缺失或 onnxruntime 没装时退回旧的
        人脸框椭圆蒙版，只提示不中断 —— 后者效果差但不需要任何额外依赖。
        """
        if params.seg_method == "rvm":
            self.dnn.reset_rvm_state()
            if self.dnn.load_rvm():
                return True
            err = self.dnn.get_load_error("rvm")
            self._report_progress(0, f"RVM 人像分割不可用，改用人脸框启发式蒙版\n{err}")
            # 每改一次参数就会重新预览一次，回退原因只在第一次写进日志
            if not self._rvm_fallback_logged:
                self._rvm_fallback_logged = True
                LOGGER.warn(f"RVM 不可用，回退人脸框启发式: {err}")
        if not self.dnn.load_face_detector():
            err = self.dnn.get_load_error("face_detector")
            self._report_progress(-1, f"人脸检测模型也未找到，背景虚化无法进行: {err}")
            return False
        return True

    def _process_frame(self, frame: np.ndarray, params: ProcessingParams) -> np.ndarray:
        task = params.task

        if task == ProcessingTask.TRIM:
            return frame
        if task == ProcessingTask.RESIZE:
            w, h = self._get_output_size(params, None)
            if w > 0 and h > 0:
                return cv2.resize(frame, (w, h), interpolation=params.interpolation)
            return frame
        if task == ProcessingTask.ROTATE:
            result = frame
            if params.rotation == 90:
                result = cv2.rotate(result, cv2.ROTATE_90_CLOCKWISE)
            elif params.rotation == 180:
                result = cv2.rotate(result, cv2.ROTATE_180)
            elif params.rotation == 270:
                result = cv2.rotate(result, cv2.ROTATE_90_COUNTERCLOCKWISE)
            if params.flip_h:
                result = cv2.flip(result, 1)
            if params.flip_v:
                result = cv2.flip(result, 0)
            return result
        if task == ProcessingTask.FPS_CHANGE:
            return frame
        if task == ProcessingTask.BRIGHTNESS_CONTRAST:
            result = self.filter.adjust_brightness_contrast(frame, params.brightness, params.contrast)
            result = self.filter.adjust_saturation(result, params.saturation)
            return self.filter.adjust_gamma(result, params.gamma)
        if task == ProcessingTask.COLOR_SPACE:
            if params.color_space == "GRAY":
                return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
            elif params.color_space == "HSV":
                return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), cv2.COLOR_HSV2BGR)
            elif params.color_space == "LAB":
                return cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGR2LAB), cv2.COLOR_LAB2BGR)
            return frame
        if task == ProcessingTask.HISTOGRAM_EQ:
            return self.filter.histogram_equalize(frame)
        if task == ProcessingTask.SHARPEN_BLUR:
            result = frame
            if params.blur_type != "none":
                result = self.filter.apply_blur(result, params.blur_type, params.blur_ksize)
            if params.sharpen_strength > 0:
                result = self.filter.apply_sharpen(result, params.sharpen_strength)
            if params.denoise_strength > 0:
                result = self.filter.denoise(result, params.denoise_strength)
            return result
        if task == ProcessingTask.SKETCH:
            return self.filter.pencil_sketch(frame)
        if task == ProcessingTask.CARTOON:
            return self.filter.cartoon_effect(frame)
        if task == ProcessingTask.EMBOSS:
            return self.filter.emboss_effect(frame)
        if task == ProcessingTask.EDGE_DETECT:
            return self.filter.edge_detect(frame, params.edge_type, params.canny_low, params.canny_high)
        if task == ProcessingTask.COLOR_TONE:
            return self.filter.apply_color_tone(frame, params.tone_type)
        if task == ProcessingTask.MOSAIC:
            x, y, w, h = params.mosaic_region
            if w > 0 and h > 0:
                return self.filter.apply_mosaic(frame, x, y, w, h, params.mosaic_size)
            return self.filter.pixelate_full(frame, params.mosaic_size)
        if task == ProcessingTask.VIGNETTE:
            return self.filter.apply_vignette(frame)

        # ── DNN AI ──
        if task == ProcessingTask.FACE_DETECT:
            faces = self.dnn.detect_faces(frame, params.dnn_confidence)
            result = frame.copy()
            for (x, y, w, h, conf) in faces:
                cv2.rectangle(result, (x, y), (x + w, y + h), (0, 255, 0), 2)
                cv2.putText(result, f"{conf:.2f}", (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            return result
        if task == ProcessingTask.OBJECT_DETECT:
            return self.dnn.draw_detections(frame,
                self.dnn.detect_objects(frame, params.dnn_confidence, params.dnn_nms_threshold))
        if task == ProcessingTask.STYLE_TRANSFER:
            return self.dnn.apply_style_transfer(frame, params.style_model_name, params.style_strength)
        if task == ProcessingTask.STYLE_REFERENCE:
            if self._style_reference_img is not None:
                return self.dnn.apply_style_reference(frame, self._style_reference_img, params.style_strength)
            return frame
        if task == ProcessingTask.FACE_MOSAIC:
            faces = self.dnn.detect_faces(frame, params.dnn_confidence)
            result = frame.copy()
            for (x, y, w, h, conf) in faces:
                result = self.filter.apply_mosaic(result, x, y, w, h, params.mosaic_size)
            return result
        if task == ProcessingTask.BG_BLUR:
            return self._background_blur(frame, params)
        if task == ProcessingTask.TEXT_DETECT:
            text_boxes = self.dnn.detect_text(frame, params.dnn_confidence)
            result = frame.copy()
            for box in text_boxes:
                cv2.polylines(result, [box], True, (0, 255, 0), 2)
            return result

        # ★ 去马赛克
        if task == ProcessingTask.DEMOSAIC:
            return self.dnn.apply_demosaic(
                frame,
                model_name=params.demosaic_model,
                region=params.demosaic_region,
                full_frame=params.demosaic_full,
                tile_size=params.demosaic_tile_size,
            )

        # ★ 水印 / 调色 / 字幕
        if task == ProcessingTask.WATERMARK_ADD:
            if self._watermark is None:
                self._watermark = WatermarkRenderer(params)
                self._watermark_signature = WatermarkRenderer.signature(params)
            return self._watermark.apply(frame)
        if task == ProcessingTask.WATERMARK_REMOVE:
            return WatermarkRemover.apply(frame, params)
        if task == ProcessingTask.LUT_GRADE:
            if self._lut is None:
                self._lut, _ = ColorLUT.load(params)
            if self._lut is None:
                return frame
            return self._lut.apply(frame, params.lut_strength, params.lut_fast)
        if task == ProcessingTask.SUBTITLE_BURN:
            if self._subtitles is None:
                return frame
            return self._subtitles.apply(frame, self._frame_time)
        if task == ProcessingTask.SUBTITLE_OCR:
            # OCR 本身产出 SRT 文件，这里画的是给预览看的检测框，方便调字幕带范围
            return self._draw_ocr_debug(frame, params)

        return frame

    # ── 字幕 OCR ──────────────────────────────────────────────

    @staticmethod
    def _ocr_band(frame_h: int, params: ProcessingParams) -> Tuple[int, int]:
        """字幕搜索带的上下边界 (像素)。整段画面都搜会慢很多，也更容易误检"""
        top = int(frame_h * max(0.0, min(1.0, params.ocr_band_top)))
        bottom = int(frame_h * max(0.0, min(1.0, params.ocr_band_bottom)))
        if bottom - top < 32:
            bottom = min(frame_h, top + 32)
            top = max(0, bottom - 32)
        return top, bottom

    def _recognize_band(self, frame: np.ndarray,
                        params: ProcessingParams) -> Tuple[str, List[np.ndarray]]:
        """
        在字幕带里检测并识别文字。返回 (拼好的整行文本, 检测框列表)。

        EAST 通常把一行字幕切成好几段，而 CRNN 的输入宽度固定 100px，长句
        整体缩进去会糊成一团。所以这里不合并框，逐段识别再按 x 从左到右拼接。
        """
        h, w = frame.shape[:2]
        top, bottom = self._ocr_band(h, params)
        band = frame[top:bottom]
        band_h, band_w = band.shape[:2]

        # 按字幕带的实际宽高比给 EAST 定输入尺寸，用默认的方形会把字压扁
        scale = min(1.0, 960.0 / max(1, band_w))
        boxes = self.dnn.detect_text(
            band, params.dnn_confidence,
            input_size=(max(32, int(band_w * scale)), max(32, int(band_h * scale))))
        if not boxes:
            return "", []

        ordered = sorted(boxes, key=lambda b: float(np.min(b[:, 0])))
        pieces: List[str] = []
        absolute: List[np.ndarray] = []
        for box in ordered:
            # 检测框贴得比较紧，向外放一点再识别，避免笔画被切掉
            x, y, bw, bh = cv2.boundingRect(box)
            pad_x, pad_y = max(2, bw // 20), max(2, bh // 6)
            x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
            x1, y1 = min(band_w, x + bw + pad_x), min(band_h, y + bh + pad_y)
            if x1 - x0 < 6 or y1 - y0 < 6:
                continue
            quad = np.asarray([[x0, y1], [x0, y0], [x1, y0], [x1, y1]], np.float32)
            text = self.dnn.recognize_text(band, quad, params.ocr_model)
            if text:
                pieces.append(text)
            shifted = box.copy()
            shifted[:, 1] += top
            absolute.append(shifted)
        return "".join(pieces), absolute

    def _draw_ocr_debug(self, frame: np.ndarray,
                        params: ProcessingParams) -> np.ndarray:
        """预览用：把字幕带范围、检测框和识别结果画出来"""
        result = frame.copy()
        h, w = result.shape[:2]
        top, bottom = self._ocr_band(h, params)
        cv2.rectangle(result, (0, top), (w - 1, bottom - 1), (0, 200, 255), 2)
        if not self.dnn.is_crnn_ready(params.ocr_model):
            return alpha_paste(result, TextRenderer.render(
                "OCR 模型未就绪，请先在「工具 → 模型管理」下载",
                font_size=max(16, h // 28), color=(0, 200, 255),
                outline_color=(0, 0, 0), outline_width=2), 12, 12)

        text, boxes = self._recognize_band(result, params)
        for box in boxes:
            cv2.polylines(result, [box], True, (0, 255, 0), 2)
        stamp = TextRenderer.render(text or "(未识别到文字)",
                                    font_size=max(16, h // 24),
                                    color=(255, 255, 255),
                                    outline_color=(0, 0, 0), outline_width=3)
        return alpha_paste(result, stamp, 12, 12)

    def _ocr_subtitles(self, cap: cv2.VideoCapture, params: ProcessingParams,
                       info: Optional[VideoInfo]) -> bool:
        """
        按固定时间间隔采样识别，把连续几次识别到的同一句话并成一条字幕，
        最后导出 SRT。

        采样而不是逐帧是因为 CRNN 在 CPU 上每帧要跑好几次，逐帧做完一部片子
        不现实；字幕一般会停留 1 秒以上，0.3 秒采样一次足够抓住起止时间。
        """
        fps = info.fps if info and info.fps > 0 else 30.0
        total = info.frame_count if info else 0
        start_frame = int(params.start_time * fps) if params.start_time > 0 else 0
        end_frame = int(params.end_time * fps) if params.end_time > 0 else total
        if end_frame <= start_frame:
            end_frame = total

        step = max(1, int(round(max(0.05, params.ocr_sample_interval) * fps)))
        cues: List[SubtitleCue] = []
        current_text = ""
        current_start = 0.0
        last_moment = 0.0
        sampled = 0

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        position = start_frame
        while not self._cancel and position < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            moment = position / fps
            text = self._recognize_band(frame, params)[0].strip()
            sampled += 1

            if text != current_text:
                if current_text:
                    cues.append(SubtitleCue(current_start,
                                            max(last_moment, current_start) + step / fps,
                                            current_text))
                current_text, current_start = text, moment
            last_moment = moment

            if end_frame > start_frame:
                progress = (position - start_frame) / (end_frame - start_frame)
                self._report_progress(
                    progress * 0.98,
                    f"识别中: {moment:.1f}s / {end_frame / fps:.1f}s "
                    f"(已找到 {len(cues)} 条)")

            position += step
            cap.set(cv2.CAP_PROP_POS_FRAMES, position)

        cap.release()
        if current_text:
            cues.append(SubtitleCue(current_start,
                                    max(last_moment, current_start) + step / fps,
                                    current_text))

        if self._cancel:
            self._report_progress(-1, "已取消")
            return False

        kept = [c for c in cues if c.end - c.start >= params.ocr_min_duration]
        if not kept:
            self._report_progress(-1,
                f"没有识别到有效字幕 (采样 {sampled} 帧)。\n"
                "可以试试：调整字幕带范围、降低置信度阈值，或换用中文识别模型")
            return False

        try:
            SubtitleFile.save_srt(kept, params.output_path)
        except OSError as e:
            self._report_progress(-1, f"写入 SRT 失败: {e}")
            return False

        LOGGER.info(f"[字幕 OCR] 采样 {sampled} 帧，导出 {len(kept)} 条字幕 → "
                    f"{params.output_path} (丢弃 {len(cues) - len(kept)} 条过短条目)")
        self._report_progress(1.0, f"识别完成！导出 {len(kept)} 条字幕\n{params.output_path}")
        return True

    def _process_frame_pipeline(self, frame: np.ndarray,
                                params: ProcessingParams) -> np.ndarray:
        """
        按勾选顺序把各个功能串起来。

        每一步都用一份浅拷贝、只改 task —— 逐帧函数不会修改 params，所以浅拷贝
        足够；而且这样新增参数字段时不用再回来手动补一行，不会漏。
        """
        result = frame.copy()
        for task in params.pipeline_tasks:
            sub_params = copy.copy(params)
            sub_params.task = task
            result = self._process_frame(result, sub_params)
        return result

    def _background_blur(self, frame: np.ndarray, params: ProcessingParams) -> np.ndarray:
        """
        人像与背景分离，然后按 bg_mode 把背景虚化 / 换成纯色 / 换成图片。

        蒙版有两种来源：RVM 的真正人像 alpha，或者旧的「人脸框外扩成椭圆」
        启发式。后者只是个粗糙近似，模型不可用时才会走到。
        """
        alpha = None
        if params.seg_method == "rvm":
            alpha = self.dnn.matte_person(frame, params.seg_downsample)
        if alpha is None:
            alpha = self._face_box_alpha(frame, params)
        if alpha is None:
            return frame

        feather = max(0, int(params.seg_feather))
        if feather > 0:
            ksize = feather * 2 + 1
            alpha = cv2.GaussianBlur(alpha, (ksize, ksize), 0)

        background = self._make_background(frame, params)
        alpha3 = alpha[:, :, None]
        blended = frame.astype(np.float32) * alpha3 + \
            background.astype(np.float32) * (1.0 - alpha3)
        return np.clip(blended, 0, 255).astype(np.uint8)

    def _face_box_alpha(self, frame: np.ndarray,
                        params: ProcessingParams) -> Optional[np.ndarray]:
        """人脸框外扩成椭圆当人像蒙版。很粗糙，只在 RVM 不可用时兜底"""
        faces = self.dnn.detect_faces(frame, params.dnn_confidence)
        if not faces:
            return None
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), np.uint8)
        for (fx, fy, fw, fh, _) in faces:
            cx = fx + fw // 2
            body_w, body_h = int(fw * 2.5), int(fh * 5)
            bx = max(0, cx - body_w // 2)
            by = max(0, fy - int(fh * 0.3))
            bw, bh = min(w - bx, body_w), min(h - by, body_h)
            cv2.ellipse(mask, (bx + bw // 2, by + bh // 2),
                        (bw // 2, bh // 2), 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (51, 51), 0)
        return mask.astype(np.float32) / 255.0

    def _make_background(self, frame: np.ndarray,
                         params: ProcessingParams) -> np.ndarray:
        h, w = frame.shape[:2]
        if params.bg_mode == "color":
            return np.full_like(frame, hex_to_bgr(params.bg_color, (30, 30, 30)))
        if params.bg_mode == "image" and self._bg_replacement is not None:
            source = self._bg_replacement
            # 按较大的比例缩放再中心裁切，避免背景图被拉伸变形
            scale = max(w / source.shape[1], h / source.shape[0])
            resized = cv2.resize(source,
                                 (max(w, int(source.shape[1] * scale) + 1),
                                  max(h, int(source.shape[0] * scale) + 1)),
                                 interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
            y0 = (resized.shape[0] - h) // 2
            x0 = (resized.shape[1] - w) // 2
            return resized[y0:y0 + h, x0:x0 + w]
        ksize = max(3, int(params.bg_blur_strength) | 1)
        return cv2.GaussianBlur(frame, (ksize, ksize), 0)

    # ── 特殊处理任务 ──────────────────────────────────────────

    def _convert_to_gif(self, cap: cv2.VideoCapture,
                        params: ProcessingParams, info: Optional[VideoInfo]) -> bool:
        fps = info.fps if info else 30.0
        total = info.frame_count if info else 0
        start_frame = int(params.start_time * fps) if params.start_time > 0 else 0
        end_frame = int(params.end_time * fps) if params.end_time > 0 else total
        output_path = params.output_path
        if not output_path.lower().endswith('.gif'):
            output_path = os.path.splitext(output_path)[0] + '.gif'

        if self._has_ffmpeg():
            self._report_progress(0.1, "使用 FFmpeg 生成 GIF...")
            scale_w = int((info.width if info else 640) * params.gif_scale)
            if scale_w % 2 != 0:
                scale_w += 1
            cmd = ["ffmpeg", "-y"]
            if params.start_time > 0:
                cmd += ["-ss", str(params.start_time)]
            if params.end_time > 0:
                cmd += ["-to", str(params.end_time)]
            cmd += ["-i", params.input_path, "-vf",
                    f"fps={params.gif_fps},scale={scale_w}:-1:flags=lanczos,"
                    f"split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
                    "-loop", "0", output_path]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=300,
                               **SUBPROCESS_FLAGS)
                self._report_progress(1.0, f"GIF 生成完成! (FFmpeg)\n{output_path}")
                return True
            except Exception as e:
                self._report_progress(0.2, f"FFmpeg 失败 ({e})，切换到备用方案...")

        self._report_progress(0.1, "正在读取视频帧...")
        frames = []
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_interval = max(1, int(fps / params.gif_fps))
        count = 0
        total_to_read = end_frame - start_frame

        while not self._cancel:
            ret, frame = cap.read()
            if not ret or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) > end_frame:
                break
            if count % frame_interval == 0:
                h, w = frame.shape[:2]
                small = cv2.resize(frame, (max(1, int(w * params.gif_scale)),
                                           max(1, int(h * params.gif_scale))))
                frames.append(small)
            count += 1
            if total_to_read > 0 and count % 10 == 0:
                self._report_progress(0.1 + 0.4 * (count / total_to_read),
                    f"读取帧: {len(frames)} 帧 ({count}/{total_to_read})")
        cap.release()

        if not frames:
            self._report_progress(-1, "没有可用的帧")
            return False
        if self._cancel:
            self._report_progress(-1, "已取消")
            return False

        self._report_progress(0.5, f"共 {len(frames)} 帧，正在编码 GIF...")

        if HAS_PIL:
            self._report_progress(0.6, "使用 Pillow 编码 GIF...")
            if GIFEncoder.save_gif_pil(frames, output_path, params.gif_fps):
                file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                self._report_progress(1.0,
                    f"GIF 生成完成! (Pillow)\n{output_path}\n"
                    f"大小: {file_size / 1024 / 1024:.2f} MB, {len(frames)} 帧")
                return True

        self._report_progress(0.7, "使用纯 Python GIF 编码器...")
        if GIFEncoder.save_gif_raw(frames, output_path, params.gif_fps,
                                    max_colors=params.gif_max_colors):
            file_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
            self._report_progress(1.0,
                f"GIF 生成完成! (纯Python)\n{output_path}\n"
                f"大小: {file_size / 1024 / 1024:.2f} MB, {len(frames)} 帧")
            return True
        else:
            self._report_progress(-1, "GIF 编码失败!")
            return False

    def _extract_frames(self, cap: cv2.VideoCapture,
                        params: ProcessingParams, info: Optional[VideoInfo]) -> bool:
        fps = info.fps if info else 30.0
        total = info.frame_count if info else 0
        output_dir = params.output_path
        _, ext = os.path.splitext(output_dir)
        if ext.lower() in VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | {'.gif'}:
            output_dir = os.path.splitext(output_dir)[0] + '_frames'
        os.makedirs(output_dir, exist_ok=True)
        frame_interval = max(1, int(fps * params.extract_interval))
        count = 0
        saved = 0
        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            if count % frame_interval == 0:
                cv2.imwrite(os.path.join(output_dir, f"frame_{saved:06d}.{params.extract_format}"), frame)
                saved += 1
            count += 1
            if total > 0:
                self._report_progress(count / total, f"提取帧: {saved}")
        cap.release()
        self._report_progress(1.0, f"完成! 共提取 {saved} 帧到 {output_dir}")
        return True

    def _concat_videos(self, params: ProcessingParams) -> bool:
        files = params.concat_files
        if not files:
            self._report_progress(-1, "没有选择要拼接的视频")
            return False
        first_info = self.get_video_info(files[0])
        if not first_info:
            self._report_progress(-1, f"无法读取: {files[0]}")
            return False
        # 多个源的音轨拼接逻辑和逐帧管道对不上，拼接一律不带音频
        sink = FrameSink(params.output_path, first_info.fps,
                         first_info.width, first_info.height, params)
        if not sink.is_open:
            self._report_progress(-1, sink.error or "无法创建输出文件")
            return False
        total_frames = sum(
            (self.get_video_info(f).frame_count if self.get_video_info(f) else 0) for f in files)
        processed = 0
        write_failed = False
        for idx, file_path in enumerate(files):
            if self._cancel or write_failed:
                break
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                LOGGER.warn(f"拼接时跳过无法打开的文件: {file_path}")
                continue
            while not self._cancel:
                ret, frame = cap.read()
                if not ret:
                    break
                if not sink.write(frame):
                    write_failed = True
                    break
                processed += 1
                if processed % 30 == 0:
                    self._report_progress(processed / max(1, total_frames),
                        f"视频 {idx + 1}/{len(files)}: {processed} 帧")
            cap.release()
        closed_ok = sink.close()
        if self._cancel:
            self._report_progress(-1, "已取消")
            self._remove_quietly(params.output_path)
            return False
        if write_failed or not closed_ok:
            self._report_progress(-1, f"编码失败: {sink.error}")
            self._remove_quietly(params.output_path)
            return False
        self._report_progress(1.0, f"拼接完成! 共 {processed} 帧")
        return True

    def _analyze_video(self, cap: cv2.VideoCapture,
                       params: ProcessingParams, info: Optional[VideoInfo]) -> bool:
        """分析任务分发 — cap 在内部 release"""
        if params.task == ProcessingTask.BRIGHTNESS_CURVE:
            return self._analyze_brightness(cap, params, info)
        elif params.task == ProcessingTask.COLOR_HISTOGRAM:
            return self._analyze_color_histogram(cap, params, info)
        elif params.task == ProcessingTask.MOTION_HEATMAP:
            return self._analyze_motion(cap, params, info)
        cap.release()
        return False

    def _analyze_brightness(self, cap, params, info):
        total = info.frame_count if info else 0
        values = []
        count = 0
        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            values.append(float(np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))))
            count += 1
            if count % 30 == 0 and total > 0:
                self._report_progress(count / total, f"分析亮度: {count}/{total}")
        cap.release()
        if not values:
            self._report_progress(-1, "没有可分析的帧")
            return False

        values = np.array(values)
        chart_w, chart_h = 1200, 400
        chart = np.ones((chart_h + 60, chart_w + 80, 3), dtype=np.uint8) * 255
        min_v, max_v = values.min(), max(values.max(), values.min() + 1)
        ox, oy = 60, chart_h + 30
        cv2.line(chart, (ox, 30), (ox, oy), (0, 0, 0), 2)
        cv2.line(chart, (ox, oy), (ox + chart_w, oy), (0, 0, 0), 2)
        n = len(values)
        pts = [(ox + int(i / max(1, n - 1) * chart_w),
                oy - int((v - min_v) / (max_v - min_v) * chart_h)) for i, v in enumerate(values)]
        for i in range(len(pts) - 1):
            cv2.line(chart, pts[i], pts[i + 1], (255, 100, 0), 1)

        if HAS_SCIPY and n > 51:
            smooth = savgol_filter(values, min(51, n // 2 * 2 + 1), 3)
        else:
            k = min(21, n // 4 * 2 + 1)
            smooth = np.convolve(values, np.ones(max(3, k)) / max(3, k), mode='same') if k >= 3 else values
        spts = [(ox + int(i / max(1, n - 1) * chart_w),
                 oy - int((v - min_v) / (max_v - min_v) * chart_h)) for i, v in enumerate(smooth)]
        for i in range(len(spts) - 1):
            cv2.line(chart, spts[i], spts[i + 1], (0, 0, 255), 2)

        cv2.putText(chart, "Brightness Curve", (ox + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        cv2.putText(chart, f"Min:{min_v:.1f} Max:{max_v:.1f} Avg:{values.mean():.1f}",
                    (ox + chart_w - 350, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

        # # ★ 确保输出目录存在
        # out_dir = os.path.dirname(params.output_path)
        # if out_dir:
            # os.makedirs(out_dir, exist_ok=True)

        # 兼容中文路径
        try:
            out_dir = os.path.dirname(params.output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            # 尝试直接写入
            success = cv2.imwrite(params.output_path, chart)
            if not success:
                # 回退：用 numpy 编码后写入（兼容中文路径）
                ext = os.path.splitext(params.output_path)[1]
                if not ext:
                    ext = '.png'
                ret, buf = cv2.imencode(ext, chart)
                if ret:
                    with open(params.output_path, 'wb') as f:
                        f.write(buf.tobytes())
                    success = True
        except Exception as e:
            self._report_progress(-1, f"保存失败: {e}")
            success = False
        if success:
            self._report_progress(1.0, f"亮度曲线已保存: {params.output_path}")
        else:
            self._report_progress(-1, f"保存失败: {params.output_path}\n请检查路径和权限")
        return success

    def _analyze_color_histogram(self, cap, params, info):
        total = info.frame_count if info else 0
        hist_b, hist_g, hist_r = np.zeros(256, np.float64), np.zeros(256, np.float64), np.zeros(256, np.float64)
        count = 0
        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            for ch, hist in enumerate([hist_b, hist_g, hist_r]):
                hist += cv2.calcHist([frame], [ch], None, [256], [0, 256]).flatten()
            count += 1
            if count % 30 == 0 and total > 0:
                self._report_progress(count / total, f"分析颜色: {count}/{total}")
        cap.release()
        if count == 0:
            self._report_progress(-1, "没有可分析的帧")
            return False
        for h in [hist_b, hist_g, hist_r]:
            h /= count

        chart_w, chart_h = 1024, 400
        chart = np.ones((chart_h + 60, chart_w + 80, 3), dtype=np.uint8) * 255
        ox, oy = 60, chart_h + 30
        max_val = max(hist_b.max(), hist_g.max(), hist_r.max(), 1)
        for hist, color in [(hist_b, (255, 0, 0)), (hist_g, (0, 180, 0)), (hist_r, (0, 0, 255))]:
            pts = [(ox + int(i / 255 * chart_w), oy - int(hist[i] / max_val * chart_h)) for i in range(256)]
            for i in range(len(pts) - 1):
                cv2.line(chart, pts[i], pts[i + 1], color, 1)
        cv2.putText(chart, "Color Histogram", (ox + 10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        cv2.line(chart, (ox, 30), (ox, oy), (0, 0, 0), 2)
        cv2.line(chart, (ox, oy), (ox + chart_w, oy), (0, 0, 0), 2)

        # out_dir = os.path.dirname(params.output_path)
        # if out_dir:
            # os.makedirs(out_dir, exist_ok=True)
        # 兼容中文路径
        try:
            out_dir = os.path.dirname(params.output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            # 尝试直接写入
            success = cv2.imwrite(params.output_path, chart)
            if not success:
                # 回退：用 numpy 编码后写入（兼容中文路径）
                ext = os.path.splitext(params.output_path)[1]
                if not ext:
                    ext = '.png'
                ret, buf = cv2.imencode(ext, chart)
                if ret:
                    with open(params.output_path, 'wb') as f:
                        f.write(buf.tobytes())
                    success = True
        except Exception as e:
            self._report_progress(-1, f"保存失败: {e}")
            success = False
        if success:
            self._report_progress(1.0, f"颜色直方图已保存: {params.output_path}")
        else:
            self._report_progress(-1, f"保存失败: {params.output_path}")
        return success

    def _analyze_motion(self, cap, params, info):
        total = info.frame_count if info else 0

        ret, prev_frame = cap.read()
        if not ret:
            cap.release()
            self._report_progress(-1, "无法读取第一帧")
            return False

        # ★ 关键修复：用实际帧尺寸，而不是 info 的元数据尺寸
        h, w = prev_frame.shape[:2]
        first_frame = prev_frame.copy()  # ★ 直接保存第一帧，不用后面重新打开

        heatmap = np.zeros((h, w), dtype=np.float64)
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        count = 0

        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            # ★ 确保帧尺寸一致
            if frame.shape[0] != h or frame.shape[1] != w:
                frame = cv2.resize(frame, (w, h))
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            heatmap += cv2.absdiff(prev_gray, gray).astype(np.float64)
            prev_gray = gray
            count += 1
            if count % 30 == 0 and total > 0:
                self._report_progress(count / total, f"分析运动: {count}/{total}")
        cap.release()

        if count == 0:
            self._report_progress(-1, "帧数不足")
            return False

        heatmap /= count
        hm_max = heatmap.max()
        if hm_max > 0:
            heatmap = (heatmap / hm_max * 255).astype(np.uint8)
        else:
            heatmap = heatmap.astype(np.uint8)

        heatmap_color = cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)

        # ★ 直接用之前保存的第一帧，不再重新打开视频
        overlay = cv2.addWeighted(first_frame, 0.5, heatmap_color, 0.5, 0)

        # ★ 安全保存（兼容中文路径）
        out_dir = os.path.dirname(params.output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        success = cv2.imwrite(params.output_path, overlay)
        if not success:
            # 回退：imencode 方式
            ext = os.path.splitext(params.output_path)[1] or '.png'
            ret_enc, buf = cv2.imencode(ext, overlay)
            if ret_enc:
                with open(params.output_path, 'wb') as f:
                    f.write(buf.tobytes())
                success = True

        if success:
            self._report_progress(1.0, f"运动热力图已保存: {params.output_path}")
        else:
            self._report_progress(-1, f"保存失败: {params.output_path}")
        return success

    @staticmethod
    def _has_ffmpeg() -> bool:
        return ffmpeg_available()

    def preview_frame(self, input_path: str, params: ProcessingParams,
                      time_pos: float = 0.0) -> Optional[np.ndarray]:
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(time_pos * fps))
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None

        if params.style_reference_path and os.path.exists(params.style_reference_path):
            self._style_reference_img = cv2.imread(params.style_reference_path)

        self._frame_time = time_pos
        # 预览允许资源缺失（用户可能还没填完路径），失败就按未加载处理，
        # 不弹错误也不中断 —— 真正开始处理时 process_video 会硬性校验
        self._prepare_assets(
            params,
            list(params.pipeline_tasks) if params.task == ProcessingTask.PIPELINE
            else [params.task])
        self._init_dnn_for_task(params)

        if params.task == ProcessingTask.PIPELINE:
            for pt in params.pipeline_tasks:
                sub_p = copy.copy(params)
                sub_p.task = pt
                self._init_dnn_for_task(sub_p)
            return self._process_frame_pipeline(frame, params)

        return self._process_frame(frame, params)


# ════════════════════════════════════════════════════════════════
#  图像转 PhotoImage 工具
# ════════════════════════════════════════════════════════════════

def numpy_bgr_to_photoimage_fast(img_bgr: np.ndarray) -> tk.PhotoImage:
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    if HAS_PIL:
        return ImageTk.PhotoImage(PILImage.fromarray(img_rgb))
    h, w = img_rgb.shape[:2]
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.ppm')
    try:
        with os.fdopen(tmp_fd, 'wb') as f:
            f.write(f"P6\n{w} {h}\n255\n".encode('ascii'))
            f.write(img_rgb.tobytes())
        return tk.PhotoImage(file=tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


# ════════════════════════════════════════════════════════════════
#  GUI 主窗口
# ════════════════════════════════════════════════════════════════

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tip_window:
            return
        x = self.widget.winfo_rootx() + 25
        y = self.widget.winfo_rooty() + 25
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=self.text, background="#FFFFD0", relief="solid",
                 borderwidth=1, font=("Microsoft YaHei", 9)).pack()

    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class VideoPreviewCanvas(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, bg="#1a1a2e", highlightthickness=0, **kwargs)
        self._photo_image = None

    def show_frame(self, frame: np.ndarray):
        if frame is None:
            return
        self.update_idletasks()
        cw, ch = self.winfo_width(), self.winfo_height()
        if cw < 10 or ch < 10:
            self.after(100, lambda: self.show_frame(frame))
            return
        h, w = frame.shape[:2]
        scale = min(cw / w, ch / h, 1.0)
        nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
        display = cv2.resize(frame, (nw, nh))
        try:
            self._photo_image = numpy_bgr_to_photoimage_fast(display)
        except Exception as e:
            self.show_text(f"预览失败: {e}")
            return
        self.delete("all")
        self.create_image((cw - nw) // 2, (ch - nh) // 2, anchor="nw", image=self._photo_image)

    def show_text(self, text: str):
        self.delete("all")
        self.update_idletasks()
        self.create_text(max(1, self.winfo_width() // 2), max(1, self.winfo_height() // 2),
                         text=text, fill="#666666", font=("Microsoft YaHei", 14))


class MainWindow:
    def __init__(self):
        self.root = make_root_window()
        self.root.title(APP_TITLE)
        self.root.geometry("1400x900")
        self.root.minsize(1100, 700)

        self.engine = VideoEngine()
        self.model_manager = ModelManager(self.engine.dnn.models_dir)
        self.current_video_info: Optional[VideoInfo] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.is_processing = False
        self.msg_queue = queue.Queue()

        # 这两个在 _build_function_list 里就会被读到，必须先于建 UI 初始化
        self._current_task: Optional[ProcessingTask] = None
        self.current_params_widgets: List[Any] = []

        # 批处理
        self.batch_jobs: List[BatchJob] = []
        self.batch_window: Optional[tk.Toplevel] = None
        self.batch_tree: Optional[ttk.Treeview] = None
        self.is_batch_running = False
        self._batch_cancel = False
        self._batch_thread: Optional[threading.Thread] = None

        # 日志窗口
        self.log_window: Optional[tk.Toplevel] = None
        self.log_text: Optional[tk.Text] = None
        self._log_seq = 0
        self._last_output_path = ""
        self.var_log_level = tk.StringVar(value="INFO")
        self.var_log_autoscroll = tk.BooleanVar(value=True)

        self._setup_styles()
        self._build_menubar()
        self._build_ui()
        self._setup_shortcuts()
        self._setup_drag_and_drop()
        self._poll_messages()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        LOGGER.info(f"{APP_NAME} v{APP_VERSION} 启动 | OpenCV {cv2.__version__} | "
                    f"FFmpeg {'✅' if ffmpeg_available() else '❌'} | "
                    f"拖拽 {DND_BACKEND or '❌'}")

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        BG, FG, ACCENT = "#f0f2f5", "#333333", "#4a90d9"
        self.root.configure(bg=BG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG, font=("Microsoft YaHei", 10))
        style.configure("TButton", font=("Microsoft YaHei", 10), padding=(8, 4))
        style.configure("Accent.TButton", font=("Microsoft YaHei", 10, "bold"),
                        foreground="white", background=ACCENT)
        style.map("Accent.TButton", background=[("active", "#357abd"), ("pressed", "#357abd")])
        style.configure("TLabelframe", background=BG, foreground=FG, font=("Microsoft YaHei", 10, "bold"))
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("Microsoft YaHei", 10, "bold"))
        style.configure("TNotebook", background=BG)
        style.configure("TNotebook.Tab", font=("Microsoft YaHei", 10), padding=(12, 4))
        style.configure("Horizontal.TProgressbar", troughcolor="#e0e0e0", background=ACCENT)
        style.configure("Header.TLabel", font=("Microsoft YaHei", 12, "bold"), foreground=ACCENT)
        style.configure("Info.TLabel", font=("Microsoft YaHei", 9), foreground="#666666")

    def _build_ui(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=5, pady=(5, 0))
        btn_open = ttk.Button(toolbar, text="📂 打开视频", command=self._open_video)
        btn_open.pack(side="left", padx=2)
        ToolTip(btn_open, "打开单个视频 (Ctrl+O)\n也可以直接把文件拖进窗口")
        btn_batch = ttk.Button(toolbar, text="🗂 批处理队列", command=self._show_batch_queue)
        btn_batch.pack(side="left", padx=2)
        ToolTip(btn_batch, "对多个文件/整个文件夹套用同一套参数 (Ctrl+B)")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        btn_preview = ttk.Button(toolbar, text="👁 预览效果", command=self._preview)
        btn_preview.pack(side="left", padx=2)
        ToolTip(btn_preview, "按当前参数渲染一帧 (F5)")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        self.btn_process = ttk.Button(toolbar, text="▶ 开始处理",
                                      command=self._start_processing, style="Accent.TButton")
        self.btn_process.pack(side="left", padx=2)
        ToolTip(self.btn_process, "开始处理 (F9 / Ctrl+Enter)")
        self.btn_cancel = ttk.Button(toolbar, text="⏹ 取消", command=self._cancel_processing, state="disabled")
        self.btn_cancel.pack(side="left", padx=2)
        ToolTip(self.btn_cancel, "取消当前处理 (Esc)")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        btn_save = ttk.Button(toolbar, text="💾 存预设", command=self._save_preset)
        btn_save.pack(side="left", padx=2)
        ToolTip(btn_save, "把当前所有参数存成 JSON 预设 (Ctrl+S)")
        btn_load = ttk.Button(toolbar, text="📑 读预设", command=self._load_preset)
        btn_load.pack(side="left", padx=2)
        ToolTip(btn_load, "载入之前保存的参数预设 (Ctrl+R)")
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        btn_log = ttk.Button(toolbar, text="📋 日志", command=self._show_log_window)
        btn_log.pack(side="left", padx=2)
        ToolTip(btn_log, "查看处理日志 (Ctrl+L)，同时写入 logs/ 目录")
        ttk.Button(toolbar, text="📥 下载/更新DNN模型", command=self._show_model_manager).pack(side="left", padx=2)
        ttk.Button(toolbar, text="ℹ 关于", command=self._show_about).pack(side="right", padx=2)

        main_paned = ttk.PanedWindow(self.root, orient="horizontal")
        main_paned.pack(fill="both", expand=True, padx=5, pady=5)
        left_frame = ttk.Frame(main_paned, width=250)
        main_paned.add(left_frame, weight=0)
        center_frame = ttk.Frame(main_paned)
        main_paned.add(center_frame, weight=1)
        right_frame = ttk.Frame(main_paned, width=300)
        main_paned.add(right_frame, weight=0)

        self._build_function_list(left_frame)
        self._build_preview_area(center_frame)
        self._build_params_panel(right_frame)
        self._build_statusbar()

    def _build_function_list(self, parent):
        ttk.Label(parent, text="功能列表", style="Header.TLabel").pack(padx=10, pady=(10, 5), anchor="w")
        search_frame = ttk.Frame(parent)
        search_frame.pack(fill="x", padx=10, pady=(0, 5))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filter_functions)
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var,
                                      font=("Microsoft YaHei", 10))
        self.search_entry.pack(fill="x")
        self.search_entry.bind("<Escape>", lambda e: (self.search_var.set(""), "break")[1])
        ToolTip(self.search_entry, "搜索功能 (Ctrl+F)，支持中文名和英文别名，如 gif / mosaic / crop")
        self.search_hint = ttk.Label(search_frame, text="", style="Info.TLabel")
        self.search_hint.pack(fill="x")

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(tree_frame)
        scrollbar.pack(side="right", fill="y")
        self.func_tree = ttk.Treeview(tree_frame, show="tree", yscrollcommand=scrollbar.set, selectmode="browse")
        self.func_tree.pack(fill="both", expand=True)
        scrollbar.config(command=self.func_tree.yview)
        self.func_tree.bind("<<TreeviewSelect>>", self._on_function_select)

        self._function_map = {}
        self._function_names = {}

        categories = OrderedDict({
            "📹 基础处理": [
                ("视频裁剪 (时间段)", ProcessingTask.TRIM),
                ("视频缩放", ProcessingTask.RESIZE),
                ("旋转/翻转", ProcessingTask.ROTATE),
                ("视频拼接", ProcessingTask.CONCAT),
                ("帧率调整", ProcessingTask.FPS_CHANGE),
                ("转 GIF", ProcessingTask.TO_GIF),
                ("提取帧画面", ProcessingTask.EXTRACT_FRAMES),
            ],
            "🎨 画面调整": [
                ("亮度/对比度/饱和度", ProcessingTask.BRIGHTNESS_CONTRAST),
                ("色彩空间转换", ProcessingTask.COLOR_SPACE),
                ("直方图均衡化", ProcessingTask.HISTOGRAM_EQ),
                ("锐化/模糊/降噪", ProcessingTask.SHARPEN_BLUR),
            ],
            "✨ 特效滤镜": [
                ("铅笔素描", ProcessingTask.SKETCH),
                ("卡通化", ProcessingTask.CARTOON),
                ("浮雕效果", ProcessingTask.EMBOSS),
                ("边缘检测", ProcessingTask.EDGE_DETECT),
                ("色调滤镜", ProcessingTask.COLOR_TONE),
                ("马赛克/像素化", ProcessingTask.MOSAIC),
                ("晕影效果", ProcessingTask.VIGNETTE),
            ],
            "🏷 水印 / 调色 / 字幕": [
                ("水印添加 (文字/图片)", ProcessingTask.WATERMARK_ADD),
                ("水印去除 (区域修补)", ProcessingTask.WATERMARK_REMOVE),
                ("LUT 颜色分级", ProcessingTask.LUT_GRADE),
                ("字幕烧录 (SRT/ASS)", ProcessingTask.SUBTITLE_BURN),
            ],
            "🤖 DNN AI 功能": [
                ("人脸检测", ProcessingTask.FACE_DETECT),
                ("物体检测 (YOLO)", ProcessingTask.OBJECT_DETECT),
                ("风格迁移 (模型)", ProcessingTask.STYLE_TRANSFER),
                ("风格迁移 (参考图)", ProcessingTask.STYLE_REFERENCE),
                ("人脸马赛克", ProcessingTask.FACE_MOSAIC),
                ("背景虚化 / 人像分割", ProcessingTask.BG_BLUR),
                ("文字检测 (EAST)", ProcessingTask.TEXT_DETECT),
                ("去马赛克/超分重建", ProcessingTask.DEMOSAIC),  # ★ 新增
                ("字幕 OCR → 导出 SRT", ProcessingTask.SUBTITLE_OCR),
            ],
            "📊 分析工具": [
                ("亮度曲线分析", ProcessingTask.BRIGHTNESS_CURVE),
                ("颜色直方图", ProcessingTask.COLOR_HISTOGRAM),
                ("运动热力图", ProcessingTask.MOTION_HEATMAP),
            ],
            "🔗 高级功能": [
                ("流程组合 (多步串联)", ProcessingTask.PIPELINE),
            ],
        })

        self._function_categories = categories
        self._populate_function_tree()

    def _build_preview_area(self, parent):
        info_frame = ttk.LabelFrame(parent, text="视频信息")
        info_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.info_labels = {}
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill="x", padx=10, pady=5)
        for i, label in enumerate(["文件", "分辨率", "帧率", "时长", "编码", "大小"]):
            row, col = i // 3, (i % 3) * 2
            ttk.Label(info_grid, text=f"{label}:", style="Info.TLabel").grid(
                row=row, column=col, sticky="e", padx=(5, 2), pady=1)
            val = ttk.Label(info_grid, text="--", style="Info.TLabel")
            val.grid(row=row, column=col + 1, sticky="w", padx=(0, 15), pady=1)
            self.info_labels[label] = val

        preview_frame = ttk.LabelFrame(parent, text="预览")
        preview_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.preview_canvas = VideoPreviewCanvas(preview_frame)
        self.preview_canvas.pack(fill="both", expand=True, padx=2, pady=2)

        slider_frame = ttk.Frame(parent)
        slider_frame.pack(fill="x", padx=5, pady=(0, 5))
        ttk.Label(slider_frame, text="预览位置:").pack(side="left")
        self.preview_time_var = tk.DoubleVar(value=0.0)
        self.preview_slider = ttk.Scale(slider_frame, from_=0, to=100,
                                        variable=self.preview_time_var, orient="horizontal",
                                        command=self._on_slider_change)
        self.preview_slider.pack(side="left", fill="x", expand=True, padx=5)
        self.time_label = ttk.Label(slider_frame, text="00:00:00")
        self.time_label.pack(side="right")

        progress_frame = ttk.Frame(parent)
        progress_frame.pack(fill="x", padx=5, pady=(0, 5))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill="x")
        self.progress_label = ttk.Label(progress_frame, text="就绪", style="Info.TLabel")
        self.progress_label.pack(anchor="w")

    def _build_params_panel(self, parent):
        ttk.Label(parent, text="参数设置", style="Header.TLabel").pack(padx=10, pady=(10, 5), anchor="w")

        params_container = ttk.Frame(parent)
        params_container.pack(fill="both", expand=True, padx=5, pady=5)
        self._params_canvas = tk.Canvas(params_container, bg="#f0f2f5", highlightthickness=0)
        scrollbar = ttk.Scrollbar(params_container, orient="vertical", command=self._params_canvas.yview)
        self.params_frame = ttk.Frame(self._params_canvas)
        self.params_frame.bind("<Configure>",
            lambda e: self._params_canvas.configure(scrollregion=self._params_canvas.bbox("all")))
        self._params_canvas_window = self._params_canvas.create_window((0, 0), window=self.params_frame, anchor="nw")
        self._params_canvas.configure(yscrollcommand=scrollbar.set)
        self._params_canvas.bind("<Configure>",
            lambda e: self._params_canvas.itemconfig(self._params_canvas_window, width=e.width))
        self._params_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self._params_canvas.bind_all("<MouseWheel>",
            lambda e: self._params_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self._init_param_vars()
        self._build_output_section()

    def _init_param_vars(self):
        self.var_start_time = tk.StringVar(value="0.0")
        self.var_end_time = tk.StringVar(value="-1")
        self.var_target_w = tk.StringVar(value="1280")
        self.var_target_h = tk.StringVar(value="720")
        self.var_keep_aspect = tk.BooleanVar(value=True)
        self.var_rotation = tk.StringVar(value="0")
        self.var_flip_h = tk.BooleanVar(value=False)
        self.var_flip_v = tk.BooleanVar(value=False)
        self.var_target_fps = tk.StringVar(value="30.0")
        self.var_brightness = tk.IntVar(value=0)
        self.var_contrast = tk.DoubleVar(value=1.0)
        self.var_saturation = tk.DoubleVar(value=1.0)
        self.var_gamma = tk.DoubleVar(value=1.0)
        self.var_color_space = tk.StringVar(value="BGR")
        self.var_blur_type = tk.StringVar(value="none")
        self.var_blur_ksize = tk.IntVar(value=5)
        self.var_sharpen = tk.DoubleVar(value=0.0)
        self.var_denoise = tk.IntVar(value=0)
        self.var_edge_type = tk.StringVar(value="canny")
        self.var_canny_low = tk.IntVar(value=50)
        self.var_canny_high = tk.IntVar(value=150)
        self.var_tone_type = tk.StringVar(value="warm")
        self.var_mosaic_size = tk.IntVar(value=15)
        self.var_dnn_conf = tk.DoubleVar(value=0.5)
        self.var_dnn_nms = tk.DoubleVar(value=0.4)
        self.var_style_model = tk.StringVar(value="")
        self.var_style_reference_path = tk.StringVar(value="")
        self.var_style_strength = tk.DoubleVar(value=1.0)
        self.var_gif_fps = tk.IntVar(value=10)
        self.var_gif_scale = tk.DoubleVar(value=0.5)
        self.var_extract_interval = tk.DoubleVar(value=1.0)
        self.var_extract_format = tk.StringVar(value="jpg")
        self.var_output_path = tk.StringVar(value="")
        self.concat_file_list = []

        # ★ 输出编码
        self.var_video_codec = tk.StringVar(value="auto")
        self.var_rate_mode = tk.StringVar(value="crf")
        self.var_crf = tk.IntVar(value=20)
        self.var_bitrate = tk.StringVar(value="4000")
        self.var_encode_preset = tk.StringVar(value="medium")
        self.var_keep_audio = tk.BooleanVar(value=True)

        # ★ 批处理队列
        self.var_batch_out_dir = tk.StringVar(value="")
        self.var_batch_suffix = tk.StringVar(value="_output")
        self.var_batch_recursive = tk.BooleanVar(value=True)
        self.var_batch_skip_existing = tk.BooleanVar(value=False)

        # ★ 去马赛克参数
        self.var_demosaic_model = tk.StringVar(value="deepmosaics")
        self.var_demosaic_full = tk.BooleanVar(value=True)
        self.var_demosaic_tile = tk.IntVar(value=128)
        self.var_demosaic_rx = tk.IntVar(value=0)
        self.var_demosaic_ry = tk.IntVar(value=0)
        self.var_demosaic_rw = tk.IntVar(value=0)
        self.var_demosaic_rh = tk.IntVar(value=0)

        # ★ 水印添加
        self.var_wm_type = tk.StringVar(value="text")
        self.var_wm_text = tk.StringVar(value="© VideoToolbox")
        self.var_wm_image = tk.StringVar(value="")
        self.var_wm_font = tk.StringVar(value="")
        self.var_wm_font_size = tk.IntVar(value=42)
        self.var_wm_color = tk.StringVar(value="#FFFFFF")
        self.var_wm_outline_color = tk.StringVar(value="#000000")
        self.var_wm_outline_width = tk.IntVar(value=2)
        self.var_wm_opacity = tk.DoubleVar(value=0.75)
        self.var_wm_scale = tk.DoubleVar(value=0.18)
        self.var_wm_position = tk.StringVar(value="bottom-right")
        self.var_wm_margin = tk.IntVar(value=24)
        self.var_wm_cx = tk.IntVar(value=0)
        self.var_wm_cy = tk.IntVar(value=0)
        self.var_wm_rotation = tk.DoubleVar(value=0.0)
        self.var_wm_tile = tk.BooleanVar(value=False)
        self.var_wm_tile_gap = tk.IntVar(value=80)

        # ★ 水印去除
        self.var_wmr_regions = tk.StringVar(value="")
        self.var_wmr_method = tk.StringVar(value="telea")
        self.var_wmr_smart = tk.BooleanVar(value=True)
        self.var_wmr_sensitivity = tk.IntVar(value=22)
        self.var_wmr_radius = tk.IntVar(value=4)
        self.var_wmr_grow = tk.IntVar(value=3)

        # ★ LUT 颜色分级
        self.var_lut_source = tk.StringVar(value="preset")
        self.var_lut_preset = tk.StringVar(value="cinematic")
        self.var_lut_path = tk.StringVar(value="")
        self.var_lut_strength = tk.DoubleVar(value=1.0)
        self.var_lut_fast = tk.BooleanVar(value=False)

        # ★ 字幕烧录
        self.var_sub_path = tk.StringVar(value="")
        # 只注册一次，避免每次重建参数面板都叠一个回调上去
        self.var_sub_path.trace_add("write", lambda *_: self._refresh_subtitle_info())
        self.var_sub_font = tk.StringVar(value="")
        self.var_sub_font_size = tk.IntVar(value=0)
        self.var_sub_color = tk.StringVar(value="#FFFFFF")
        self.var_sub_outline_color = tk.StringVar(value="#000000")
        self.var_sub_outline_width = tk.IntVar(value=3)
        self.var_sub_margin = tk.IntVar(value=40)
        self.var_sub_box_opacity = tk.DoubleVar(value=0.0)
        self.var_sub_offset = tk.DoubleVar(value=0.0)

        # ★ 背景虚化 / 人像分割
        self.var_seg_method = tk.StringVar(value="rvm")
        self.var_seg_downsample = tk.DoubleVar(value=0.0)
        self.var_seg_feather = tk.IntVar(value=3)
        self.var_bg_mode = tk.StringVar(value="blur")
        self.var_bg_blur_strength = tk.IntVar(value=35)
        self.var_bg_color = tk.StringVar(value="#1E1E1E")
        self.var_bg_image = tk.StringVar(value="")

        # ★ 字幕 OCR
        self.var_ocr_model = tk.StringVar(value="crnn_cn")
        self.var_ocr_band_top = tk.DoubleVar(value=0.70)
        self.var_ocr_band_bottom = tk.DoubleVar(value=1.0)
        self.var_ocr_interval = tk.DoubleVar(value=0.3)
        self.var_ocr_min_duration = tk.DoubleVar(value=0.4)

        self.pipeline_vars: Dict[ProcessingTask, tk.BooleanVar] = {}
        for task in VIDEO_OUTPUT_TASKS:
            if task != ProcessingTask.TRIM:
                self.pipeline_vars[task] = tk.BooleanVar(value=False)

    def _build_output_section(self):
        out_frame = ttk.LabelFrame(self.params_frame, text="输出设置")
        out_frame.pack(fill="x", padx=5, pady=5)
        row = ttk.Frame(out_frame)
        row.pack(fill="x", padx=5, pady=3)
        ttk.Label(row, text="输出路径:").pack(side="left")
        ttk.Entry(row, textvariable=self.var_output_path, width=20).pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(row, text="浏览", command=self._browse_output).pack(side="right")
        self.output_hint_label = ttk.Label(out_frame, text="", style="Info.TLabel", wraplength=260)
        self.output_hint_label.pack(fill="x", padx=5, pady=(0, 3))
        self._output_frame = out_frame
        self._build_encode_section()

    def _build_encode_section(self):
        """输出编码设置。只对「产出视频文件」的任务有意义，其余任务会整块隐藏"""
        enc = ttk.LabelFrame(self.params_frame, text="输出编码")
        enc.pack(fill="x", padx=5, pady=5)
        self._encode_frame = enc

        has_ffmpeg = ffmpeg_available()

        ttk.Label(enc, text="编码器:").pack(anchor="w", padx=8, pady=(4, 0))
        codec_box = ttk.Combobox(enc, state="readonly", font=("Microsoft YaHei", 9),
                                 values=[VIDEO_CODEC_CHOICES[k] for k in VIDEO_CODEC_CHOICES])
        codec_box.pack(fill="x", padx=8, pady=2)
        self._codec_keys = list(VIDEO_CODEC_CHOICES.keys())
        codec_box.current(self._codec_keys.index(self.var_video_codec.get()))
        codec_box.bind("<<ComboboxSelected>>",
                       lambda e: self._on_codec_change(self._codec_keys[codec_box.current()]))
        self._codec_box = codec_box

        if not has_ffmpeg:
            ttk.Label(enc, text="⚠️ 未检测到 FFmpeg，H.264/H.265、码率控制、\n"
                                "保留音频都不可用（会自动退回 mp4v）",
                      style="Info.TLabel", wraplength=250, justify="left").pack(
                anchor="w", padx=8, pady=2)

        # ── 码率控制 (仅 H.264/H.265 生效) ──
        self._rate_frame = rate = ttk.Frame(enc)
        rate.pack(fill="x", padx=0, pady=0)

        mode_row = ttk.Frame(rate)
        mode_row.pack(fill="x", padx=8, pady=(4, 0))
        ttk.Radiobutton(mode_row, text="恒定质量 CRF", variable=self.var_rate_mode,
                        value="crf", command=self._on_rate_mode_change).pack(side="left")
        ttk.Radiobutton(mode_row, text="目标码率", variable=self.var_rate_mode,
                        value="bitrate", command=self._on_rate_mode_change).pack(side="left", padx=(8, 0))

        # CRF 和码率两个输入区互斥显示。放进同一个占位容器里 pack/forget，
        # 否则重新 pack 会跑到父容器末尾，把下面的说明文字挤到前面去
        holder = ttk.Frame(rate)
        holder.pack(fill="x", padx=0, pady=0)

        self._crf_frame = crf_frame = ttk.Frame(holder)
        ttk.Label(crf_frame, text="CRF:").pack(side="left")
        ttk.Scale(crf_frame, from_=0, to=51, variable=self.var_crf,
                  orient="horizontal").pack(side="left", fill="x", expand=True, padx=4)
        ttk.Label(crf_frame, textvariable=self.var_crf, width=3).pack(side="right")

        self._bitrate_frame = br_frame = ttk.Frame(holder)
        ttk.Label(br_frame, text="码率 (kbps):").pack(side="left")
        ttk.Entry(br_frame, textvariable=self.var_bitrate, width=8).pack(side="left", padx=4)

        ttk.Label(rate, text="CRF 越小越清晰、文件越大；18~23 基本视觉无损，0=无损",
                  style="Info.TLabel", wraplength=250, justify="left").pack(
            anchor="w", padx=8, pady=(0, 2))

        preset_row = ttk.Frame(rate)
        preset_row.pack(fill="x", padx=8, pady=2)
        ttk.Label(preset_row, text="编码速度:").pack(side="left")
        preset_box = ttk.Combobox(preset_row, state="readonly", width=10,
                                  values=list(FFMPEG_PRESETS),
                                  textvariable=self.var_encode_preset)
        preset_box.pack(side="left", padx=4)
        ttk.Label(rate, text="preset 越慢，同画质下体积越小",
                  style="Info.TLabel", wraplength=250).pack(anchor="w", padx=8)

        self._audio_check = ttk.Checkbutton(
            enc, text="保留原音频 (需 FFmpeg + H.264/H.265)", variable=self.var_keep_audio)
        self._audio_check.pack(anchor="w", padx=8, pady=(4, 6))

        self._on_codec_change(self.var_video_codec.get())

    def _on_codec_change(self, codec_key: str):
        self.var_video_codec.set(codec_key)
        ffmpeg_codec = codec_key in FrameSink.FFMPEG_CODECS and ffmpeg_available()
        if ffmpeg_codec:
            self._rate_frame.pack(fill="x")
            self._audio_check.state(["!disabled"])
        else:
            self._rate_frame.pack_forget()
            self._audio_check.state(["disabled"])
        self._on_rate_mode_change()

    def _on_rate_mode_change(self):
        if self.var_rate_mode.get() == "bitrate":
            self._crf_frame.pack_forget()
            self._bitrate_frame.pack(fill="x", padx=8, pady=2)
        else:
            self._bitrate_frame.pack_forget()
            self._crf_frame.pack(fill="x", padx=8, pady=2)

    def _update_encode_section_visibility(self, task: Optional[ProcessingTask]):
        """转 GIF / 提取帧 / 分析类任务不经过视频编码器，整块隐藏避免误导"""
        produces_video = task is not None and (
            task in VIDEO_OUTPUT_TASKS or task in (ProcessingTask.CONCAT,
                                                   ProcessingTask.TRIM,
                                                   ProcessingTask.PIPELINE))
        if produces_video:
            self._encode_frame.pack(fill="x", padx=5, pady=5)
        else:
            self._encode_frame.pack_forget()

    # ════════════════════════════════════════════════════════════
    #  功能搜索
    # ════════════════════════════════════════════════════════════

    def _filter_functions(self, *args):
        self._populate_function_tree(self.search_var.get())

    def _populate_function_tree(self, query: str = ""):
        """
        按关键词重建功能树。

        匹配范围包括中文功能名、分类名，以及 FUNCTION_KEYWORDS 里登记的
        英文别名（gif / mosaic / crop ...），方便用英文输入法直接搜。
        """
        query = (query or "").strip().lower()
        previous = self._current_task

        self.func_tree.delete(*self.func_tree.get_children())
        self._function_map = {}
        self._function_names = {}

        matched_item_for_previous = None
        total = 0
        for cat_name, functions in self._function_categories.items():
            hits = []
            cat_matches = query and query in cat_name.lower()
            for func_name, task in functions:
                if not query or cat_matches or self._function_matches(query, func_name, task):
                    hits.append((func_name, task))
            if not hits:
                continue
            cat_id = self.func_tree.insert("", "end", text=cat_name, open=True)
            for func_name, task in hits:
                item_id = self.func_tree.insert(cat_id, "end", text=func_name)
                self._function_map[item_id] = task
                self._function_names[item_id] = func_name
                total += 1
                if task == previous:
                    matched_item_for_previous = item_id

        if query:
            self.search_hint.configure(
                text=f"匹配 {total} 项" if total else "没有匹配的功能")
        else:
            self.search_hint.configure(text="")

        # 过滤后如果当前功能还在列表里，保持它高亮，避免参数面板和选中项脱节
        if matched_item_for_previous:
            self.func_tree.selection_set(matched_item_for_previous)
            self.func_tree.see(matched_item_for_previous)

    @staticmethod
    def _function_matches(query: str, func_name: str, task: ProcessingTask) -> bool:
        if query in func_name.lower():
            return True
        return query in FUNCTION_KEYWORDS.get(task, "")

    def _on_function_select(self, event):
        selected = self.func_tree.selection()
        if not selected:
            return
        task = self._function_map.get(selected[0])
        if task is None:
            return
        self._current_task = task
        self._build_task_params(task)
        self._update_encode_section_visibility(task)

        if task in ANALYSIS_TASKS:
            self.output_hint_label.configure(text="📊 分析任务：输出将自动保存为 .png 图片")
            self._auto_fix_output_extension('.png')
        elif task == ProcessingTask.SUBTITLE_OCR:
            self.output_hint_label.configure(text="📝 字幕 OCR：输出将保存为 .srt 字幕文件")
            self._auto_fix_output_extension('.srt')
        elif task == ProcessingTask.EXTRACT_FRAMES:
            self.output_hint_label.configure(text="📁 提取帧：输出路径将作为保存目录")
        elif task == ProcessingTask.TO_GIF:
            self.output_hint_label.configure(text="🎬 转 GIF：自动使用 FFmpeg/PIL/纯Python")
            self._auto_fix_output_extension('.gif')
        elif task == ProcessingTask.PIPELINE:
            self.output_hint_label.configure(text="🔗 流程组合：勾选多个功能串联处理")
        else:
            self.output_hint_label.configure(text="")
            current = self.var_output_path.get()
            if current:
                _, ext = os.path.splitext(current)
                if ext.lower() in ('.png', '.jpg', '.gif', '.bmp', '.srt'):
                    self._auto_fix_output_extension('.mp4')

        if self.current_video_info:
            try:
                self._preview()
            except Exception as e:
                LOGGER.warn(f"切换功能后自动预览失败: {e}")

    def _auto_fix_output_extension(self, target_ext: str):
        current = self.var_output_path.get()
        if current:
            base, ext = os.path.splitext(current)
            if ext.lower() != target_ext.lower():
                self.var_output_path.set(base + target_ext)

    def _build_task_params(self, task: ProcessingTask):
        for w in self.current_params_widgets:
            try:
                w.destroy()
            except Exception:
                pass
        self.current_params_widgets = []

        frame = ttk.LabelFrame(self.params_frame, text="功能参数")
        frame.pack(fill="x", padx=5, pady=5, before=self._output_frame)
        self.current_params_widgets.append(frame)

        builders = {
            ProcessingTask.TRIM: self._build_trim_params,
            ProcessingTask.RESIZE: self._build_resize_params,
            ProcessingTask.ROTATE: self._build_rotate_params,
            ProcessingTask.CONCAT: self._build_concat_params,
            ProcessingTask.FPS_CHANGE: self._build_fps_params,
            ProcessingTask.TO_GIF: self._build_gif_params,
            ProcessingTask.EXTRACT_FRAMES: self._build_extract_params,
            ProcessingTask.BRIGHTNESS_CONTRAST: self._build_brightness_params,
            ProcessingTask.COLOR_SPACE: self._build_colorspace_params,
            ProcessingTask.SHARPEN_BLUR: self._build_blur_params,
            ProcessingTask.EDGE_DETECT: self._build_edge_params,
            ProcessingTask.COLOR_TONE: self._build_tone_params,
            ProcessingTask.MOSAIC: self._build_mosaic_params,
            ProcessingTask.OBJECT_DETECT: self._build_yolo_params,
            ProcessingTask.STYLE_TRANSFER: self._build_style_params,
            ProcessingTask.STYLE_REFERENCE: self._build_style_reference_params,
            ProcessingTask.DEMOSAIC: self._build_demosaic_params,  # ★ 新增
            ProcessingTask.WATERMARK_ADD: self._build_watermark_params,
            ProcessingTask.WATERMARK_REMOVE: self._build_wm_remove_params,
            ProcessingTask.LUT_GRADE: self._build_lut_params,
            ProcessingTask.SUBTITLE_BURN: self._build_subtitle_params,
            ProcessingTask.SUBTITLE_OCR: self._build_ocr_params,
            ProcessingTask.BG_BLUR: self._build_bg_blur_params,
            ProcessingTask.PIPELINE: self._build_pipeline_params,
        }

        if task in builders:
            builders[task](frame)
        elif task in (ProcessingTask.FACE_DETECT, ProcessingTask.FACE_MOSAIC,
                      ProcessingTask.TEXT_DETECT):
            self._build_dnn_basic_params(frame)
        elif task in (ProcessingTask.SKETCH, ProcessingTask.CARTOON, ProcessingTask.EMBOSS,
                      ProcessingTask.HISTOGRAM_EQ, ProcessingTask.VIGNETTE):
            ttk.Label(frame, text="此功能无需额外参数").pack(padx=10, pady=10)
        elif task in ANALYSIS_TASKS:
            ttk.Label(frame, text="📊 分析结果将保存为 PNG 图片", style="Info.TLabel",
                      wraplength=250).pack(padx=10, pady=10)

    # ── 各功能参数面板 ────────────────────────────────────────

    def _build_trim_params(self, parent):
        ttk.Label(parent, text="开始时间 (秒):").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_start_time).pack(fill="x", padx=10, pady=2)
        ttk.Label(parent, text="结束时间 (秒, -1=到结尾):").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_end_time).pack(fill="x", padx=10, pady=2)

    def _build_resize_params(self, parent):
        ttk.Label(parent, text="目标宽度:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_target_w).pack(fill="x", padx=10, pady=2)
        ttk.Label(parent, text="目标高度:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_target_h).pack(fill="x", padx=10, pady=2)
        ttk.Checkbutton(parent, text="保持宽高比", variable=self.var_keep_aspect).pack(anchor="w", padx=10, pady=5)
        pf = ttk.Frame(parent)
        pf.pack(fill="x", padx=10, pady=5)
        ttk.Label(pf, text="预设:").pack(side="left")
        for name, w, h in [("720p", 1280, 720), ("1080p", 1920, 1080), ("4K", 3840, 2160), ("480p", 854, 480)]:
            ttk.Button(pf, text=name,
                       command=lambda ww=w, hh=h: (self.var_target_w.set(str(ww)),
                                                     self.var_target_h.set(str(hh)))).pack(side="left", padx=2)

    def _build_rotate_params(self, parent):
        ttk.Label(parent, text="旋转角度:").pack(anchor="w", padx=10, pady=(5, 0))
        for a in [0, 90, 180, 270]:
            ttk.Radiobutton(parent, text=f"{a}°", variable=self.var_rotation, value=str(a)).pack(anchor="w", padx=20)
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)
        ttk.Checkbutton(parent, text="水平翻转", variable=self.var_flip_h).pack(anchor="w", padx=10)
        ttk.Checkbutton(parent, text="垂直翻转", variable=self.var_flip_v).pack(anchor="w", padx=10, pady=(0, 5))

    def _build_concat_params(self, parent):
        ttk.Label(parent, text="拼接文件列表:").pack(anchor="w", padx=10, pady=(5, 0))
        self.concat_listbox = tk.Listbox(parent, height=6, font=("Microsoft YaHei", 9))
        self.concat_listbox.pack(fill="both", padx=10, pady=5, expand=True)
        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=10, pady=5)
        ttk.Button(bf, text="添加", command=self._add_concat_file).pack(side="left", padx=2)
        ttk.Button(bf, text="移除", command=self._remove_concat_file).pack(side="left", padx=2)
        ttk.Button(bf, text="上移", command=lambda: self._move_concat_file(-1)).pack(side="left", padx=2)
        ttk.Button(bf, text="下移", command=lambda: self._move_concat_file(1)).pack(side="left", padx=2)

    def _build_fps_params(self, parent):
        ttk.Label(parent, text="目标帧率:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_target_fps).pack(fill="x", padx=10, pady=2)
        pf = ttk.Frame(parent)
        pf.pack(fill="x", padx=10, pady=5)
        for fps in [24, 25, 30, 60]:
            ttk.Button(pf, text=f"{fps}fps",
                       command=lambda f=fps: self.var_target_fps.set(str(f))).pack(side="left", padx=2)

    def _build_gif_params(self, parent):
        ttk.Label(parent, text="GIF 帧率:").pack(anchor="w", padx=10, pady=(5, 0))
        f1 = ttk.Frame(parent)
        f1.pack(fill="x", padx=10, pady=2)
        ttk.Scale(f1, from_=5, to=30, variable=self.var_gif_fps, orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(f1, textvariable=self.var_gif_fps, width=4).pack(side="right")
        ttk.Label(parent, text="缩放比例:").pack(anchor="w", padx=10, pady=(5, 0))
        f2 = ttk.Frame(parent)
        f2.pack(fill="x", padx=10, pady=2)
        ttk.Scale(f2, from_=0.1, to=1.0, variable=self.var_gif_scale, orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(f2, textvariable=self.var_gif_scale, width=5).pack(side="right")
        self._build_trim_params(parent)
    def _build_extract_params(self, parent):
        ttk.Label(parent, text="提取间隔 (秒):").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_extract_interval).pack(fill="x", padx=10, pady=2)
        ttk.Label(parent, text="图片格式:").pack(anchor="w", padx=10, pady=(5, 0))
        for fmt in ["jpg", "png", "bmp"]:
            ttk.Radiobutton(parent, text=fmt.upper(), variable=self.var_extract_format,
                            value=fmt).pack(anchor="w", padx=20)

    def _build_brightness_params(self, parent):
        for label_text, var, from_, to_ in [
            ("亮度:", self.var_brightness, -100, 100),
            ("对比度:", self.var_contrast, 0.5, 3.0),
            ("饱和度:", self.var_saturation, 0.0, 3.0),
            ("Gamma:", self.var_gamma, 0.2, 3.0),
        ]:
            ttk.Label(parent, text=label_text).pack(anchor="w", padx=10, pady=(5, 0))
            f = ttk.Frame(parent)
            f.pack(fill="x", padx=10)
            ttk.Scale(f, from_=from_, to=to_, variable=var, orient="horizontal").pack(
                side="left", fill="x", expand=True)
            ttk.Label(f, textvariable=var, width=5).pack(side="right")
        ttk.Button(parent, text="重置", command=lambda: (
            self.var_brightness.set(0), self.var_contrast.set(1.0),
            self.var_saturation.set(1.0), self.var_gamma.set(1.0),
        )).pack(padx=10, pady=5)

    def _build_colorspace_params(self, parent):
        ttk.Label(parent, text="色彩空间:").pack(anchor="w", padx=10, pady=(5, 0))
        for cs in ["BGR", "GRAY", "HSV", "LAB"]:
            ttk.Radiobutton(parent, text=cs, variable=self.var_color_space, value=cs).pack(anchor="w", padx=20)

    def _build_blur_params(self, parent):
        ttk.Label(parent, text="模糊类型:").pack(anchor="w", padx=10, pady=(5, 0))
        for bt, label in [("none", "无"), ("gaussian", "高斯模糊"),
                           ("median", "中值模糊"), ("bilateral", "双边滤波")]:
            ttk.Radiobutton(parent, text=label, variable=self.var_blur_type, value=bt).pack(anchor="w", padx=20)
        ttk.Label(parent, text="模糊核大小:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=3, to=31, variable=self.var_blur_ksize, orient="horizontal").pack(
            fill="x", padx=10, pady=2)
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)
        ttk.Label(parent, text="锐化强度:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=0.0, to=5.0, variable=self.var_sharpen, orient="horizontal").pack(
            fill="x", padx=10, pady=2)
        ttk.Label(parent, text="降噪强度:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=0, to=30, variable=self.var_denoise, orient="horizontal").pack(
            fill="x", padx=10, pady=2)

    def _build_edge_params(self, parent):
        ttk.Label(parent, text="检测方法:").pack(anchor="w", padx=10, pady=(5, 0))
        for et, label in [("canny", "Canny"), ("sobel", "Sobel"), ("laplacian", "Laplacian")]:
            ttk.Radiobutton(parent, text=label, variable=self.var_edge_type, value=et).pack(anchor="w", padx=20)
        ttk.Label(parent, text="Canny 低阈值:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=0, to=255, variable=self.var_canny_low, orient="horizontal").pack(
            fill="x", padx=10, pady=2)
        ttk.Label(parent, text="Canny 高阈值:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=0, to=255, variable=self.var_canny_high, orient="horizontal").pack(
            fill="x", padx=10, pady=2)

    def _build_tone_params(self, parent):
        ttk.Label(parent, text="色调效果:").pack(anchor="w", padx=10, pady=(5, 0))
        for tone, label in [("warm", "暖色调 🔥"), ("cool", "冷色调 ❄"),
                             ("sepia", "怀旧 📜"), ("vintage", "复古 🎞")]:
            ttk.Radiobutton(parent, text=label, variable=self.var_tone_type, value=tone).pack(anchor="w", padx=20)

    def _build_mosaic_params(self, parent):
        ttk.Label(parent, text="马赛克大小:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Scale(parent, from_=5, to=50, variable=self.var_mosaic_size, orient="horizontal").pack(
            fill="x", padx=10, pady=2)
        ttk.Label(parent, text="💡 默认全画面像素化\n如需局部马赛克请使用'人脸马赛克'功能",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=5)

    def _build_dnn_basic_params(self, parent):
        ttk.Label(parent, text="置信度阈值:").pack(anchor="w", padx=10, pady=(5, 0))
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=10)
        ttk.Scale(f, from_=0.1, to=0.99, variable=self.var_dnn_conf, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(f, textvariable=self.var_dnn_conf, width=5).pack(side="right")
        status = self.engine.dnn.get_available_models()
        status_text = "模型状态:\n"
        status_text += f"  人脸检测: {'✅ 可用' if status.get('face_detector') else '❌ 未下载'}\n"
        status_text += f"  EAST文字: {'✅ 可用' if status.get('east_text') else '❌ 未下载'}"
        ttk.Label(parent, text=status_text, style="Info.TLabel", wraplength=250).pack(padx=10, pady=5)

    def _build_yolo_params(self, parent):
        self._build_dnn_basic_params(parent)
        ttk.Label(parent, text="NMS 阈值:").pack(anchor="w", padx=10, pady=(5, 0))
        f = ttk.Frame(parent)
        f.pack(fill="x", padx=10)
        ttk.Scale(f, from_=0.1, to=0.9, variable=self.var_dnn_nms, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(f, textvariable=self.var_dnn_nms, width=5).pack(side="right")
        status = self.engine.dnn.get_available_models()
        ttk.Label(parent, text=f"YOLO: {'✅ 可用' if status.get('yolov4_tiny') else '❌ 未下载'}",
                  style="Info.TLabel").pack(padx=10, pady=5)

    def _build_style_params(self, parent):
        ttk.Label(parent, text="风格模型:").pack(anchor="w", padx=10, pady=(5, 0))
        model_names = [m.split("/")[-1].replace(".t7", "")
                       for m in MODEL_URLS["style_transfer"]["models"]]
        for name in model_names:
            path = self.engine.dnn.models_dir / f"{name}.t7"
            if path.exists():
                size_mb = path.stat().st_size / 1024 / 1024
                status = f"✅ ({size_mb:.1f}MB)" if size_mb >= 1 else f"⚠️ ({size_mb:.1f}MB)"
            else:
                status = "❌"
            ttk.Radiobutton(parent, text=f"{status} {name}", variable=self.var_style_model,
                            value=f"{name}.t7").pack(anchor="w", padx=20)
        if model_names:
            self.var_style_model.set(f"{model_names[0]}.t7")
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)
        ttk.Label(parent, text="风格强度:").pack(anchor="w", padx=10, pady=(5, 0))
        sf = ttk.Frame(parent)
        sf.pack(fill="x", padx=10)
        ttk.Scale(sf, from_=0.0, to=1.0, variable=self.var_style_strength, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(sf, textvariable=self.var_style_strength, width=5).pack(side="right")

    def _build_style_reference_params(self, parent):
        ttk.Label(parent, text="🎨 参考图风格迁移\n使用参考图片的色彩风格应用到视频",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(5, 5))
        ttk.Label(parent, text="参考图片:").pack(anchor="w", padx=10, pady=(5, 0))
        ref_frame = ttk.Frame(parent)
        ref_frame.pack(fill="x", padx=10, pady=2)
        ttk.Entry(ref_frame, textvariable=self.var_style_reference_path, width=18).pack(
            side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(ref_frame, text="浏览", command=self._browse_style_reference).pack(side="right")
        self._ref_preview_label = ttk.Label(parent, text="(未选择参考图)")
        self._ref_preview_label.pack(padx=10, pady=5)
        self._ref_photo = None
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)
        ttk.Label(parent, text="迁移强度:").pack(anchor="w", padx=10, pady=(5, 0))
        sf = ttk.Frame(parent)
        sf.pack(fill="x", padx=10)
        ttk.Scale(sf, from_=0.0, to=1.0, variable=self.var_style_strength, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(sf, textvariable=self.var_style_strength, width=5).pack(side="right")
        ttk.Label(parent, text="💡 此功能不需要 DNN 模型\n基于 LAB 色彩空间的统计量匹配",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=5)

    def _build_demosaic_params(self, parent):
        ttk.Label(parent, text="🔍 去马赛克 / 超分辨率重建",
                  style="Header.TLabel").pack(padx=10, pady=(5, 2))

        ttk.Label(parent, text="利用 AI 或传统方法恢复马赛克区域细节",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(0, 5))

        # ── 模型选择 ──
        ttk.Label(parent, text="处理模型:").pack(anchor="w", padx=10, pady=(5, 0))

        models_info = OrderedDict({
            "deepmosaics": {
                "label": "DeepMosaics (真去马赛克, 推荐)",
                # DeepMosaics 要检测器和生成器两个文件都在才能跑
                "files": [DNNEngine.DM_DETECTOR_FILE, DNNEngine.DM_GENERATOR_FILE],
                "needs_ort": True,
            },
            "real_esrgan_x4": {
                "label": "Real-ESRGAN x4 (超分, 对打码无效)",
                "files": ["realesrgan-x4plus.onnx"],
                "needs_ort": True,
            },
            "real_esrgan_anime": {
                "label": "Real-ESRGAN Anime (动漫专用)",
                "files": ["realesrgan-animevideov3.onnx"],
                "needs_ort": True,
            },
            "espcn_x4": {
                "label": "ESPCN x4 (轻量快速)",
                "files": ["ESPCN_x4.pb"],
                "needs_ort": False,
            },
            "traditional": {
                "label": "传统方法 (无需模型, 效果有限)",
                "files": [],
                "needs_ort": False,
            },
        })

        for key, info in models_info.items():
            files = info["files"]
            if not files:
                status = "✅ 始终可用"
            else:
                paths = [self.engine.dnn.models_dir / f for f in files]
                missing = [p.name for p in paths if not p.exists()]
                if missing:
                    status = f"❌ 缺少 {', '.join(missing)}"
                else:
                    size_mb = sum(p.stat().st_size for p in paths) / 1024 / 1024
                    if info["needs_ort"] and not HAS_ORT:
                        status = f"⚠️ ({size_mb:.1f}MB, 需 onnxruntime)"
                    else:
                        status = f"✅ ({size_mb:.1f}MB)"

            ttk.Radiobutton(parent, text=f"{status} {info['label']}",
                            variable=self.var_demosaic_model, value=key).pack(anchor="w", padx=20)

        ttk.Label(parent, text="💡 选中的模型加载失败时会自动回退到传统方法，"
                              "不会白跑一遍什么都没做（回退原因见处理日志 Ctrl+L）",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=(4, 0))

        # ── onnxruntime 状态提示 ──
        ort_frame = ttk.Frame(parent)
        ort_frame.pack(fill="x", padx=10, pady=5)
        if not HAS_ORT:
            ort_text = ("❌ onnxruntime 未安装\n"
                        "  Real-ESRGAN 需要它才能运行\n"
                        "  GPU版(Windows): pip install onnxruntime-directml\n"
                        "  CPU版: pip install onnxruntime")
        elif not HAS_ONNX:
            ort_text = ("❌ onnx 未安装\n"
                        "  用于适配模型输入尺寸\n"
                        "  安装: pip install onnx")
        else:
            providers = ort.get_available_providers()
            if 'DmlExecutionProvider' in providers:
                backend = "DirectML GPU 加速"
            elif 'CUDAExecutionProvider' in providers:
                backend = "CUDA GPU 加速"
            else:
                backend = "CPU 模式 (很慢, 建议装 onnxruntime-directml)"
            ort_text = f"✅ onnxruntime v{ort.__version__}\n  后端: {backend}"
        ttk.Label(ort_frame, text=ort_text, style="Info.TLabel",
                  wraplength=250, justify="left").pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # ── 处理区域 ──
        ttk.Checkbutton(parent, text="全画面处理", variable=self.var_demosaic_full).pack(
            anchor="w", padx=10, pady=2)
        ttk.Label(parent, text="💡 取消勾选后填写下方坐标, 只处理局部区域",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=2)

        rf = ttk.Frame(parent)
        rf.pack(fill="x", padx=10, pady=2)
        for col, (text, var) in enumerate((("X", self.var_demosaic_rx),
                                           ("Y", self.var_demosaic_ry),
                                           ("宽", self.var_demosaic_rw),
                                           ("高", self.var_demosaic_rh))):
            ttk.Label(rf, text=text).grid(row=0, column=col * 2, padx=(0 if col == 0 else 6, 2))
            ttk.Entry(rf, textvariable=var, width=6).grid(row=0, column=col * 2 + 1)

        # ── 分块大小 ──
        ttk.Label(parent, text="分块大小 (px):").pack(anchor="w", padx=10, pady=(5, 0))
        tf = ttk.Frame(parent)
        tf.pack(fill="x", padx=10, pady=2)
        ttk.Scale(tf, from_=64, to=512, variable=self.var_demosaic_tile,
                  orient="horizontal").pack(side="left", fill="x", expand=True)
        ttk.Label(tf, textvariable=self.var_demosaic_tile, width=5).pack(side="right")
        ttk.Label(parent, text="较大的分块=更好的效果，但需要更多内存",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=2)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # ── 效果说明 ──
        help_text = (
            "📖 模型效果对比:\n\n"
            "🥇 DeepMosaics (真正的去马赛克)\n"
            "  自动定位打码区域并生成式重建\n"
            "  需要: mosaic_position.onnx (45MB)\n"
            "       clean_youknow_video.onnx (204MB)\n"
            "  由 export_deepmosaics_onnx.py 导出\n"
            "  速度: GPU ~16毫秒/帧, CPU ~0.4秒/帧\n"
            "  处理区域由模型自动检测，无需手填坐标\n\n"
            "🥈 Real-ESRGAN x4 (超分, 非去码)\n"
            "  会忠实保留马赛克方块，对打码无效\n"
            "  适合去压缩噪点、提升模糊画面\n"
            "  需要: ONNX模型(~64MB) + onnxruntime\n"
            "  1080p 速度: GPU ~8秒/帧, CPU ~6分钟/帧\n\n"
            "🥉 Real-ESRGAN Anime\n"
            "  动漫/插画专用，色彩更鲜艳\n"
            "  需要: ONNX模型(~17MB) + onnxruntime\n\n"
            "🥉 ESPCN x4\n"
            "  轻量级，速度快\n"
            "  需 opencv-contrib-python\n"
            "  当前 opencv-python 下不可用，会回退\n\n"
            "📦 传统方法\n"
            "  不需要任何模型文件\n"
            "  使用: 双边滤波+超采样+去噪+锐化\n"
            "  效果有限，但总是可用\n\n"
            "⚠️ 重要提醒:\n"
            "  马赛克本质是信息丢失\n"
            "  DeepMosaics 是「猜」出合理的内容，\n"
            "  不是还原真实原图，结果仅供参考。"
        )
        ttk.Label(parent, text=help_text, style="Info.TLabel",
                  wraplength=250, justify="left").pack(padx=10, pady=5)

    # ── 参数面板的通用小部件 ──────────────────────────────────

    @staticmethod
    def _row_slider(parent, label: str, var, from_, to_, width: int = 5):
        ttk.Label(parent, text=label).pack(anchor="w", padx=10, pady=(5, 0))
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10)
        ttk.Scale(row, from_=from_, to=to_, variable=var, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(row, textvariable=var, width=width).pack(side="right")
        return row

    @staticmethod
    def _row_entry(parent, label: str, var, width: int = 10, hint: str = ""):
        ttk.Label(parent, text=label).pack(anchor="w", padx=10, pady=(5, 0))
        entry = ttk.Entry(parent, textvariable=var, width=width)
        entry.pack(fill="x", padx=10, pady=2)
        if hint:
            ttk.Label(parent, text=hint, style="Info.TLabel",
                      wraplength=250, justify="left").pack(anchor="w", padx=10)
        return entry

    def _row_color(self, parent, label: str, var: tk.StringVar):
        """颜色选择行：一个显示当前色的色块按钮 + 可直接改的十六进制输入框"""
        ttk.Label(parent, text=label).pack(anchor="w", padx=10, pady=(5, 0))
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=2)
        swatch = tk.Button(row, width=3, relief="ridge", bd=1)
        swatch.pack(side="left")
        entry = ttk.Entry(row, textvariable=var, width=10)
        entry.pack(side="left", fill="x", expand=True, padx=5)

        def refresh(*_):
            value = var.get().strip()
            try:
                swatch.configure(bg=value if value.startswith("#") else f"#{value}")
            except tk.TclError:
                # 输入框里可能是半截颜色码，等它填完再刷新，别弹错
                pass

        def pick():
            initial = var.get().strip() or "#FFFFFF"
            try:
                chosen = colorchooser.askcolor(color=initial, title=label)[1]
            except tk.TclError:
                chosen = colorchooser.askcolor(title=label)[1]
            if chosen:
                var.set(chosen.upper())

        swatch.configure(command=pick)
        var.trace_add("write", refresh)
        refresh()
        return row

    def _row_file(self, parent, label: str, var: tk.StringVar,
                  title: str, filetypes, hint: str = ""):
        ttk.Label(parent, text=label).pack(anchor="w", padx=10, pady=(5, 0))
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=2)
        ttk.Entry(row, textvariable=var, width=16).pack(
            side="left", fill="x", expand=True, padx=(0, 5))

        def pick():
            path = filedialog.askopenfilename(title=title, filetypes=filetypes)
            if path:
                var.set(path)
                self._refresh_preview_quietly()

        ttk.Button(row, text="浏览", command=pick).pack(side="right")
        if hint:
            ttk.Label(parent, text=hint, style="Info.TLabel",
                      wraplength=250, justify="left").pack(anchor="w", padx=10)
        return row

    def _refresh_preview_quietly(self):
        """改完参数后刷一下预览，失败也不打扰用户（可能只是还没打开视频）"""
        if not self.current_video_info:
            return
        try:
            self._preview()
        except Exception as e:
            LOGGER.debug(f"自动刷新预览失败: {e}")

    FONT_FILETYPES = [("字体文件", "*.ttf *.ttc *.otf"), ("所有文件", "*.*")]

    def _row_font(self, parent, var: tk.StringVar):
        detected = default_cjk_font()
        self._row_file(parent, "字体文件 (留空=自动):", var, "选择字体", self.FONT_FILETYPES,
                       hint=(f"自动检测到: {os.path.basename(detected)}" if detected
                             else "⚠️ 没找到系统中文字体，中文会画不出来，请手动指定"))

    # ── 水印添加 ──────────────────────────────────────────────

    def _build_watermark_params(self, parent):
        ttk.Label(parent, text="🏷 水印添加", style="Header.TLabel").pack(padx=10, pady=(5, 2))
        if not HAS_PIL:
            ttk.Label(parent, text="⚠️ 未安装 Pillow，中文水印无法渲染\n"
                                   "  pip install Pillow",
                      style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=2)

        type_row = ttk.Frame(parent)
        type_row.pack(fill="x", padx=10, pady=(5, 0))
        ttk.Label(type_row, text="类型:").pack(side="left")
        for value, text in (("text", "文字"), ("image", "图片")):
            ttk.Radiobutton(type_row, text=text, variable=self.var_wm_type, value=value,
                            command=self._on_wm_type_change).pack(side="left", padx=(6, 0))

        # 文字和图片两组控件互斥显示，放在同一个占位容器里 pack/forget
        holder = ttk.Frame(parent)
        holder.pack(fill="x")
        self._wm_text_frame = text_frame = ttk.Frame(holder)
        self._wm_image_frame = image_frame = ttk.Frame(holder)

        self._row_entry(text_frame, "水印文字 (\\n 换行):", self.var_wm_text, width=20)
        self._row_font(text_frame, self.var_wm_font)
        self._row_slider(text_frame, "字号:", self.var_wm_font_size, 10, 200)
        self._row_color(text_frame, "文字颜色:", self.var_wm_color)
        self._row_color(text_frame, "描边颜色:", self.var_wm_outline_color)
        self._row_slider(text_frame, "描边粗细:", self.var_wm_outline_width, 0, 10, width=3)

        self._row_file(image_frame, "水印图片:", self.var_wm_image, "选择水印图片",
                       [("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
                       hint="推荐用带透明通道的 PNG，透明区域会被正确保留")
        self._row_slider(image_frame, "宽度占画面比例:", self.var_wm_scale, 0.02, 1.0)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)

        ttk.Label(parent, text="位置:").pack(anchor="w", padx=10, pady=(0, 0))
        pos_box = ttk.Combobox(parent, state="readonly", font=("Microsoft YaHei", 9),
                               values=list(WATERMARK_POSITIONS.values()))
        pos_box.pack(fill="x", padx=10, pady=2)
        pos_keys = list(WATERMARK_POSITIONS.keys())
        current = self.var_wm_position.get()
        pos_box.current(pos_keys.index(current) if current in pos_keys else 8)
        pos_box.bind("<<ComboboxSelected>>", lambda e: (
            self.var_wm_position.set(pos_keys[pos_box.current()]),
            self._on_wm_position_change()))

        self._wm_margin_frame = margin_frame = ttk.Frame(parent)
        self._row_slider(margin_frame, "边距 (px):", self.var_wm_margin, 0, 200)

        self._wm_custom_frame = custom_frame = ttk.Frame(parent)
        xy = ttk.Frame(custom_frame)
        xy.pack(fill="x", padx=10, pady=4)
        for col, (text, var) in enumerate((("X", self.var_wm_cx), ("Y", self.var_wm_cy))):
            ttk.Label(xy, text=text).grid(row=0, column=col * 2, padx=(0 if col == 0 else 10, 3))
            ttk.Entry(xy, textvariable=var, width=7).grid(row=0, column=col * 2 + 1)

        self._row_slider(parent, "不透明度:", self.var_wm_opacity, 0.05, 1.0)
        self._row_slider(parent, "旋转角度:", self.var_wm_rotation, -180, 180)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        ttk.Checkbutton(parent, text="平铺满屏 (防盗录)", variable=self.var_wm_tile,
                        command=self._on_wm_tile_change).pack(anchor="w", padx=10, pady=2)
        self._wm_tile_frame = tile_frame = ttk.Frame(parent)
        self._row_slider(tile_frame, "平铺间隔 (px):", self.var_wm_tile_gap, 0, 400)

        ttk.Label(parent, text="💡 平铺时「位置」和「边距」不生效；配合 30~45° 旋转\n"
                              "和较低的不透明度，观感最接近电商/网课的防盗水印",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=(6, 4))

        self._on_wm_type_change()
        self._on_wm_position_change()
        self._on_wm_tile_change()

    def _on_wm_type_change(self):
        if self.var_wm_type.get() == "image":
            self._wm_text_frame.pack_forget()
            self._wm_image_frame.pack(fill="x")
        else:
            self._wm_image_frame.pack_forget()
            self._wm_text_frame.pack(fill="x")
        self._refresh_preview_quietly()

    def _on_wm_position_change(self):
        if self.var_wm_position.get() == "custom":
            self._wm_margin_frame.pack_forget()
            self._wm_custom_frame.pack(fill="x")
        else:
            self._wm_custom_frame.pack_forget()
            self._wm_margin_frame.pack(fill="x")
        self._refresh_preview_quietly()

    def _on_wm_tile_change(self):
        if self.var_wm_tile.get():
            self._wm_tile_frame.pack(fill="x")
        else:
            self._wm_tile_frame.pack_forget()
        self._refresh_preview_quietly()

    # ── 水印去除 ──────────────────────────────────────────────

    def _build_wm_remove_params(self, parent):
        ttk.Label(parent, text="🧽 水印去除", style="Header.TLabel").pack(padx=10, pady=(5, 2))
        ttk.Label(parent, text="半透明叠加是不可逆的，这里做的是「用周围像素合理补上」"
                              "而不是还原原图，小面积 logo / 台标效果最好。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=(0, 5))

        ttk.Label(parent, text="要处理的区域:").pack(anchor="w", padx=10, pady=(5, 0))
        ttk.Entry(parent, textvariable=self.var_wmr_regions).pack(fill="x", padx=10, pady=2)
        ttk.Label(parent, text="格式 x,y,宽,高 ——多个区域用分号隔开，例如\n"
                              "1600,60,260,90; 40,940,300,80",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        fill_row = ttk.Frame(parent)
        fill_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(fill_row, text="快速填入:").pack(side="left")
        for text, corner in (("右上", "tr"), ("左上", "tl"), ("右下", "br"), ("左下", "bl")):
            ttk.Button(fill_row, text=text, width=4,
                       command=lambda c=corner: self._fill_wm_corner(c)).pack(side="left", padx=1)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)

        ttk.Label(parent, text="处理方式:").pack(anchor="w", padx=10, pady=(0, 0))
        for key, label in WM_REMOVE_METHODS.items():
            ttk.Radiobutton(parent, text=label, variable=self.var_wmr_method,
                            value=key, command=self._refresh_preview_quietly).pack(
                anchor="w", padx=20)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        ttk.Checkbutton(parent, text="智能蒙版 (只修水印笔画)",
                        variable=self.var_wmr_smart,
                        command=self._refresh_preview_quietly).pack(anchor="w", padx=10, pady=2)
        ttk.Label(parent, text="勾选后会在区域内挑出比背景更亮/更暗的笔画，只重建那部分，"
                              "比整块重绘能多留住背景细节；取消勾选则整块重绘。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        self._row_slider(parent, "笔画灵敏度 (小=挑得多):", self.var_wmr_sensitivity, 3, 80, width=3)
        self._row_slider(parent, "蒙版外扩 (px):", self.var_wmr_grow, 0, 12, width=3)
        self._row_slider(parent, "修补半径 (px):", self.var_wmr_radius, 1, 20, width=3)

        ttk.Label(parent, text="💡 区域要比水印本身稍大一圈，把边缘过渡也框进来；"
                              "在预览里拖时间轴逐帧确认效果再开始处理。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=6)

    def _fill_wm_corner(self, corner: str):
        """按当前视频分辨率，往区域框里填一个常见台标位置的估算矩形"""
        info = self.current_video_info
        if not info or info.width <= 0:
            messagebox.showinfo("提示", "请先打开视频，才能按分辨率算出区域坐标")
            return
        w, h = info.width, info.height
        bw, bh = int(w * 0.16), int(h * 0.10)
        margin_x, margin_y = int(w * 0.02), int(h * 0.03)
        x = margin_x if corner in ("tl", "bl") else w - bw - margin_x
        y = margin_y if corner in ("tl", "tr") else h - bh - margin_y
        self.var_wmr_regions.set(f"{x},{y},{bw},{bh}")
        self._refresh_preview_quietly()

    # ── LUT 颜色分级 ──────────────────────────────────────────

    def _build_lut_params(self, parent):
        ttk.Label(parent, text="🎨 LUT 颜色分级", style="Header.TLabel").pack(padx=10, pady=(5, 2))

        source_row = ttk.Frame(parent)
        source_row.pack(fill="x", padx=10, pady=(5, 0))
        ttk.Label(source_row, text="来源:").pack(side="left")
        for value, text in (("preset", "内置预设"), ("file", "LUT 文件")):
            ttk.Radiobutton(source_row, text=text, variable=self.var_lut_source,
                            value=value, command=self._on_lut_source_change).pack(
                side="left", padx=(6, 0))

        holder = ttk.Frame(parent)
        holder.pack(fill="x")
        self._lut_preset_frame = preset_frame = ttk.Frame(holder)
        self._lut_file_frame = file_frame = ttk.Frame(holder)

        for key, label in LUT_PRESETS.items():
            ttk.Radiobutton(preset_frame, text=label, variable=self.var_lut_preset,
                            value=key, command=self._refresh_preview_quietly).pack(
                anchor="w", padx=20, pady=1)

        self._row_file(file_frame, "LUT 文件:", self.var_lut_path, "选择 LUT",
                       [("LUT 文件", "*.cube *.png *.jpg *.jpeg"),
                        ("Cube LUT", "*.cube"),
                        ("LUT 贴图", "*.png *.jpg *.jpeg"),
                        ("所有文件", "*.*")],
                       hint="支持 .cube (3D/1D) 和 LUT 贴图 (Hald 方阵如 512×512，"
                            "或 N²×N 横条如 256×16)")
        if LUT_DIR.exists():
            found = sorted(p.name for p in LUT_DIR.iterdir()
                           if p.suffix.lower() in {".cube"} | IMAGE_EXTENSIONS)
            if found:
                ttk.Label(file_frame, text=f"luts/ 目录里有 {len(found)} 个可用文件",
                          style="Info.TLabel", wraplength=250).pack(anchor="w", padx=10)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        self._row_slider(parent, "强度:", self.var_lut_strength, 0.0, 1.0)
        ttk.Label(parent, text="强度即与原图的混合比例，0=不变、1=完全套用",
                  style="Info.TLabel", wraplength=250).pack(anchor="w", padx=10)
        ttk.Checkbutton(parent, text="快速模式 (最近邻查表)", variable=self.var_lut_fast,
                        command=self._refresh_preview_quietly).pack(anchor="w", padx=10, pady=4)
        ttk.Label(parent, text="默认用三线性插值，色彩过渡更平滑；快速模式约快一倍，"
                              "但渐变区域可能出现色带。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        self._on_lut_source_change()

    def _on_lut_source_change(self):
        if self.var_lut_source.get() == "file":
            self._lut_preset_frame.pack_forget()
            self._lut_file_frame.pack(fill="x")
        else:
            self._lut_file_frame.pack_forget()
            self._lut_preset_frame.pack(fill="x")
        self._refresh_preview_quietly()

    # ── 字幕烧录 ──────────────────────────────────────────────

    def _build_subtitle_params(self, parent):
        ttk.Label(parent, text="💬 字幕烧录", style="Header.TLabel").pack(padx=10, pady=(5, 2))
        ttk.Label(parent, text="把字幕直接画进画面（硬字幕），任何播放器都能看到。",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(0, 5))
        if not HAS_PIL:
            ttk.Label(parent, text="⚠️ 未安装 Pillow，中文字幕无法渲染\n  pip install Pillow",
                      style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=2)

        self._row_file(parent, "字幕文件:", self.var_sub_path, "选择字幕文件",
                       [("字幕文件", "*.srt *.ass *.ssa"), ("SubRip", "*.srt"),
                        ("Advanced SubStation", "*.ass *.ssa"), ("所有文件", "*.*")],
                       hint="也可以把字幕文件直接拖到窗口里")
        self._sub_info_label = ttk.Label(parent, text="", style="Info.TLabel",
                                         wraplength=250, justify="left")
        self._sub_info_label.pack(anchor="w", padx=10, pady=(0, 4))
        self._refresh_subtitle_info()

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        self._row_font(parent, self.var_sub_font)
        self._row_slider(parent, "字号 (0=按画面高度自动):", self.var_sub_font_size, 0, 120)
        self._row_color(parent, "文字颜色:", self.var_sub_color)
        self._row_color(parent, "描边颜色:", self.var_sub_outline_color)
        self._row_slider(parent, "描边粗细:", self.var_sub_outline_width, 0, 10, width=3)
        self._row_slider(parent, "底部边距 (px):", self.var_sub_margin, 0, 300)
        self._row_slider(parent, "背景条不透明度:", self.var_sub_box_opacity, 0.0, 1.0)
        self._row_slider(parent, "时间偏移 (秒):", self.var_sub_offset, -30.0, 30.0)
        ttk.Label(parent, text="时间偏移用于修正字幕整体快了或慢了：正值让字幕延后出现。\n"
                              "描边比背景条更常用，纯色描边在任何画面上都能看清。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=6)

    def _refresh_subtitle_info(self):
        """选好字幕后立刻解析一遍并显示条数，让用户当场知道文件对不对"""
        label = getattr(self, "_sub_info_label", None)
        # 这个方法由 var_sub_path 的 trace 驱动，而参数面板会被反复销毁重建，
        # 所以字幕路径在别的功能下被改动时，标签很可能已经不存在了
        if label is None or not label.winfo_exists():
            return
        path = self.var_sub_path.get().strip()
        if not path:
            self._sub_info_label.configure(text="")
            return
        if not os.path.exists(path):
            self._sub_info_label.configure(text="❌ 文件不存在")
            return
        try:
            cues = SubtitleFile.load(path)
        except Exception as e:
            self._sub_info_label.configure(text=f"❌ 解析失败: {e}")
            return
        if not cues:
            self._sub_info_label.configure(text="❌ 没解析出任何字幕条目")
        else:
            self._sub_info_label.configure(
                text=f"✅ {len(cues)} 条，覆盖到 "
                     f"{SubtitleFile.format_timestamp(cues[-1].end)}\n"
                     f"首句: {cues[0].text.splitlines()[0][:24]}")

    # ── 背景虚化 / 人像分割 ───────────────────────────────────

    def _build_bg_blur_params(self, parent):
        ttk.Label(parent, text="🌫 背景虚化 / 人像分割", style="Header.TLabel").pack(
            padx=10, pady=(5, 2))

        status = self.engine.dnn.get_available_models()
        rvm_ok = status.get("rvm_matting", False)
        ttk.Label(parent, text="分割方式:").pack(anchor="w", padx=10, pady=(5, 0))
        rvm_status = "✅ 可用" if (rvm_ok and HAS_ORT) else (
            "⚠️ 需 onnxruntime" if rvm_ok else "❌ 未下载")
        ttk.Radiobutton(parent, text=f"{rvm_status} RVM 人像分割 (推荐)",
                        variable=self.var_seg_method, value="rvm",
                        command=self._on_seg_method_change).pack(anchor="w", padx=20)
        face_ok = "✅" if status.get("face_detector") else "❌ 未下载"
        ttk.Radiobutton(parent, text=f"{face_ok} 人脸框启发式 (粗糙)",
                        variable=self.var_seg_method, value="face_box",
                        command=self._on_seg_method_change).pack(anchor="w", padx=20)
        ttk.Label(parent, text="RVM 是真正的逐像素人像抠图，带帧间时序状态，边缘和"
                              "头发都能跟住；启发式只是把人脸框放大成椭圆，仅作兜底。\n"
                              "RVM 不可用时会自动回退到启发式，回退原因见处理日志 (Ctrl+L)。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=4)

        self._seg_rvm_frame = rvm_frame = ttk.Frame(parent)
        self._row_slider(rvm_frame, "推理缩放 (0=自动):", self.var_seg_downsample, 0.0, 1.0)
        ttk.Label(rvm_frame, text="越小越快、边缘越粗。1080p 一般 0.25 就够，"
                                  "留 0 让程序按分辨率自己算。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        self._face_conf_frame = conf_frame = ttk.Frame(parent)
        self._row_slider(conf_frame, "人脸置信度阈值:", self.var_dnn_conf, 0.1, 0.99)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        ttk.Label(parent, text="背景处理:").pack(anchor="w", padx=10, pady=(0, 0))
        for key, label in BG_MODES.items():
            ttk.Radiobutton(parent, text=label, variable=self.var_bg_mode, value=key,
                            command=self._on_bg_mode_change).pack(anchor="w", padx=20)

        holder = ttk.Frame(parent)
        holder.pack(fill="x")
        self._bg_blur_frame = blur_frame = ttk.Frame(holder)
        self._bg_color_frame = color_frame = ttk.Frame(holder)
        self._bg_image_frame = image_frame = ttk.Frame(holder)

        self._row_slider(blur_frame, "虚化强度:", self.var_bg_blur_strength, 3, 151)
        self._row_color(color_frame, "背景颜色:", self.var_bg_color)
        ttk.Label(color_frame, text="填 #00FF00 之类的纯色可以当绿幕，方便后续二次合成",
                  style="Info.TLabel", wraplength=250).pack(anchor="w", padx=10)
        self._row_file(image_frame, "背景图片:", self.var_bg_image, "选择背景图片",
                       [("图片文件", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
                       hint="按画面比例居中裁切填满，不会被拉伸变形")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        self._row_slider(parent, "边缘羽化 (px):", self.var_seg_feather, 0, 20, width=3)

        self._on_seg_method_change()
        self._on_bg_mode_change()

    def _on_seg_method_change(self):
        if self.var_seg_method.get() == "rvm":
            self._face_conf_frame.pack_forget()
            self._seg_rvm_frame.pack(fill="x")
        else:
            self._seg_rvm_frame.pack_forget()
            self._face_conf_frame.pack(fill="x")
        self._refresh_preview_quietly()

    def _on_bg_mode_change(self):
        mode = self.var_bg_mode.get()
        for frame in (self._bg_blur_frame, self._bg_color_frame, self._bg_image_frame):
            frame.pack_forget()
        {"color": self._bg_color_frame,
         "image": self._bg_image_frame}.get(mode, self._bg_blur_frame).pack(fill="x")
        self._refresh_preview_quietly()

    # ── 字幕 OCR ──────────────────────────────────────────────

    def _build_ocr_params(self, parent):
        ttk.Label(parent, text="🔎 字幕 OCR → SRT", style="Header.TLabel").pack(
            padx=10, pady=(5, 2))
        ttk.Label(parent, text="用 EAST 找出字幕位置、CRNN 识别文字，结果导出成 .srt。"
                              "输出的是字幕文件，不产生视频。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=(0, 5))

        status = self.engine.dnn.get_available_models()
        ttk.Label(parent, text="识别模型:").pack(anchor="w", padx=10, pady=(5, 0))
        for key, label in OCR_MODELS.items():
            mark = "✅" if status.get(key) else "❌ 未下载"
            ttk.Radiobutton(parent, text=f"{mark} {label}", variable=self.var_ocr_model,
                            value=key, command=self._refresh_preview_quietly).pack(
                anchor="w", padx=20)
        east_mark = "✅" if status.get("east_text") else "❌ 未下载"
        ttk.Label(parent, text=f"文字检测 EAST: {east_mark}  (缺哪个都在「工具 → 模型管理」下载)",
                  style="Info.TLabel", wraplength=250).pack(anchor="w", padx=10, pady=3)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        ttk.Label(parent, text="字幕区域 (画面高度比例):").pack(anchor="w", padx=10, pady=(0, 0))
        self._row_slider(parent, "上边界:", self.var_ocr_band_top, 0.0, 1.0)
        self._row_slider(parent, "下边界:", self.var_ocr_band_bottom, 0.0, 1.0)
        ttk.Label(parent, text="只在这一条横带里找字幕，能大幅提速并减少误检。"
                              "预览里的橙色框就是当前范围，拖时间轴调到刚好框住字幕即可。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=6)
        self._row_slider(parent, "采样间隔 (秒):", self.var_ocr_interval, 0.1, 2.0)
        self._row_slider(parent, "最短保留时长 (秒):", self.var_ocr_min_duration, 0.0, 3.0)
        self._row_slider(parent, "检测置信度:", self.var_dnn_conf, 0.1, 0.99)
        ttk.Label(parent, text="采样间隔越小时间轴越准、耗时越长。字幕一般停留 1 秒以上，"
                              "0.3 秒足够；短于「最短保留时长」的条目会被当作误检丢掉。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(anchor="w", padx=10)

        ttk.Label(parent, text="⚠️ 这是尽力而为的识别，不是商用 OCR：\n"
                              "  · CRNN 中文模型只覆盖 3944 个常用字，生僻字会错\n"
                              "  · 花字、艺术字、半透明字幕识别率明显下降\n"
                              "  · 导出的 SRT 建议再人工校对一遍\n"
                              "  · CPU 上较慢，长视频建议先用「视频裁剪」截一段试跑",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=8)

    def _browse_style_reference(self):
        path = filedialog.askopenfilename(title="选择风格参考图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"), ("所有文件", "*.*")])
        if path:
            self.var_style_reference_path.set(path)
            try:
                ref_img = cv2.imread(path)
                if ref_img is not None:
                    h, w = ref_img.shape[:2]
                    scale = min(200 / w, 150 / h, 1.0)
                    thumb = cv2.resize(ref_img, (int(w * scale), int(h * scale)))
                    self._ref_photo = numpy_bgr_to_photoimage_fast(thumb)
                    self._ref_preview_label.configure(image=self._ref_photo, text="")
                else:
                    self._ref_preview_label.configure(text="(无法读取图片)", image="")
            except Exception as e:
                self._ref_preview_label.configure(text=f"(预览失败: {e})", image="")
    def _build_pipeline_params(self, parent):
        ttk.Label(parent, text="🔗 流程组合\n勾选需要的处理步骤，按列表顺序串联执行",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(5, 10))

        pipeline_categories = OrderedDict({
            "画面调整": [
                (ProcessingTask.BRIGHTNESS_CONTRAST, "亮度/对比度/饱和度"),
                (ProcessingTask.COLOR_SPACE, "色彩空间转换"),
                (ProcessingTask.HISTOGRAM_EQ, "直方图均衡化"),
                (ProcessingTask.SHARPEN_BLUR, "锐化/模糊/降噪"),
            ],
            "特效滤镜": [
                (ProcessingTask.SKETCH, "铅笔素描"),
                (ProcessingTask.CARTOON, "卡通化"),
                (ProcessingTask.EMBOSS, "浮雕效果"),
                (ProcessingTask.EDGE_DETECT, "边缘检测"),
                (ProcessingTask.COLOR_TONE, "色调滤镜"),
                (ProcessingTask.MOSAIC, "马赛克/像素化"),
                (ProcessingTask.VIGNETTE, "晕影效果"),
            ],
            "基础变换": [
                (ProcessingTask.RESIZE, "视频缩放"),
                (ProcessingTask.ROTATE, "旋转/翻转"),
            ],
            "水印 / 调色 / 字幕": [
                (ProcessingTask.LUT_GRADE, "LUT 颜色分级"),
                (ProcessingTask.WATERMARK_REMOVE, "水印去除"),
                (ProcessingTask.SUBTITLE_BURN, "字幕烧录"),
                (ProcessingTask.WATERMARK_ADD, "水印添加"),
            ],
            "DNN AI": [
                (ProcessingTask.FACE_DETECT, "人脸检测标注"),
                (ProcessingTask.OBJECT_DETECT, "物体检测标注"),
                (ProcessingTask.STYLE_TRANSFER, "风格迁移 (模型)"),
                (ProcessingTask.STYLE_REFERENCE, "风格迁移 (参考图)"),
                (ProcessingTask.FACE_MOSAIC, "人脸马赛克"),
                (ProcessingTask.BG_BLUR, "背景虚化"),
                (ProcessingTask.TEXT_DETECT, "文字检测标注"),
                (ProcessingTask.DEMOSAIC, "去马赛克/超分重建"),
            ],
        })

        for cat_name, items in pipeline_categories.items():
            cf = ttk.LabelFrame(parent, text=cat_name)
            cf.pack(fill="x", padx=10, pady=3)
            for task, name in items:
                if task in self.pipeline_vars:
                    ttk.Checkbutton(cf, text=name, variable=self.pipeline_vars[task]).pack(
                        anchor="w", padx=10, pady=1)

        bf = ttk.Frame(parent)
        bf.pack(fill="x", padx=10, pady=5)
        ttk.Button(bf, text="全选", command=lambda: [v.set(True) for v in self.pipeline_vars.values()]).pack(
            side="left", padx=2)
        ttk.Button(bf, text="全不选", command=lambda: [v.set(False) for v in self.pipeline_vars.values()]).pack(
            side="left", padx=2)

        ttk.Label(parent, text="★ 流程组合使用各功能的全局参数\n先分别设置各功能参数再回来勾选",
                  style="Info.TLabel", wraplength=240, justify="left").pack(padx=10, pady=5)

    def _browse_style_reference(self):
        path = filedialog.askopenfilename(title="选择风格参考图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp"), ("所有文件", "*.*")])
        if path:
            self.var_style_reference_path.set(path)
            try:
                ref_img = cv2.imread(path)
                if ref_img is not None:
                    h, w = ref_img.shape[:2]
                    scale = min(200 / w, 150 / h, 1.0)
                    thumb = cv2.resize(ref_img, (int(w * scale), int(h * scale)))
                    self._ref_photo = numpy_bgr_to_photoimage_fast(thumb)
                    self._ref_preview_label.configure(image=self._ref_photo, text="")
                else:
                    self._ref_preview_label.configure(text="(无法读取图片)", image="")
            except Exception as e:
                self._ref_preview_label.configure(text=f"(预览失败: {e})", image="")

    def _build_statusbar(self):
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", padx=5, pady=(0, 5))
        pil_s = "Pillow ✅" if HAS_PIL else "Pillow ❌"
        ffmpeg_s = "FFmpeg ✅" if ffmpeg_available() else "FFmpeg ❌"
        ort_s = f"ORT ✅" if HAS_ORT else "ORT ❌"
        dnd_s = "拖拽 ✅" if DND_BACKEND else "拖拽 ❌"
        self.statusbar = ttk.Label(status_frame,
            text=f"就绪 | OpenCV {cv2.__version__} | {pil_s} | {ffmpeg_s} | {ort_s} | {dnd_s}",
            style="Info.TLabel")
        self.statusbar.pack(side="left")
        available = self.engine.dnn.get_available_models()
        dnn_count = sum(1 for v in available.values() if v)
        ttk.Label(status_frame, text=f"DNN模型: {dnn_count}/{len(available)} 可用",
                  style="Info.TLabel").pack(side="right")

    # ════════════════════════════════════════════════════════════
    #  菜单栏 / 快捷键 / 拖拽
    # ════════════════════════════════════════════════════════════

    SHORTCUTS = [
        ("Ctrl+O", "打开视频"),
        ("Ctrl+Shift+O", "添加文件到批处理队列"),
        ("Ctrl+B", "打开批处理队列窗口"),
        ("Ctrl+S", "保存当前参数为预设"),
        ("Ctrl+R", "载入参数预设"),
        ("Ctrl+F", "定位到功能搜索框"),
        ("Ctrl+L", "打开处理日志窗口"),
        ("Ctrl+M", "打开 DNN 模型管理"),
        ("F5", "预览当前参数效果"),
        ("F9 / Ctrl+Enter", "开始处理"),
        ("Esc", "取消处理"),
        ("F1", "快捷键说明"),
    ]

    def _build_menubar(self):
        menubar = tk.Menu(self.root)

        m_file = tk.Menu(menubar, tearoff=0)
        m_file.add_command(label="打开视频...", accelerator="Ctrl+O", command=self._open_video)
        m_file.add_command(label="添加到批处理队列...", accelerator="Ctrl+Shift+O",
                           command=self._add_batch_files)
        m_file.add_command(label="添加整个文件夹到队列...", command=self._add_batch_folder)
        m_file.add_separator()
        m_file.add_command(label="保存参数预设...", accelerator="Ctrl+S", command=self._save_preset)
        m_file.add_command(label="载入参数预设...", accelerator="Ctrl+R", command=self._load_preset)
        m_file.add_separator()
        m_file.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=m_file)

        m_run = tk.Menu(menubar, tearoff=0)
        m_run.add_command(label="预览效果", accelerator="F5", command=self._preview)
        m_run.add_command(label="开始处理", accelerator="F9", command=self._start_processing)
        m_run.add_command(label="取消处理", accelerator="Esc", command=self._cancel_processing)
        m_run.add_separator()
        m_run.add_command(label="批处理队列...", accelerator="Ctrl+B", command=self._show_batch_queue)
        menubar.add_cascade(label="处理", menu=m_run)

        m_tool = tk.Menu(menubar, tearoff=0)
        m_tool.add_command(label="处理日志...", accelerator="Ctrl+L", command=self._show_log_window)
        m_tool.add_command(label="DNN 模型管理...", accelerator="Ctrl+M",
                           command=self._show_model_manager)
        m_tool.add_separator()
        m_tool.add_command(label="打开日志目录", command=lambda: self._open_path(LOG_DIR))
        m_tool.add_command(label="打开预设目录", command=lambda: self._open_path(PRESET_DIR))
        m_tool.add_command(label="打开模型目录",
                           command=lambda: self._open_path(self.model_manager.models_dir))
        menubar.add_cascade(label="工具", menu=m_tool)

        m_help = tk.Menu(menubar, tearoff=0)
        m_help.add_command(label="快捷键说明", accelerator="F1", command=self._show_shortcuts)
        m_help.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=m_help)

        self.root.configure(menu=menubar)

    def _setup_shortcuts(self):
        def bind(sequence, handler):
            self.root.bind(sequence, lambda e: (handler(), "break")[1])

        bind("<Control-o>", self._open_video)
        bind("<Control-O>", self._add_batch_files)      # Ctrl+Shift+O
        bind("<Control-b>", self._show_batch_queue)
        bind("<Control-s>", self._save_preset)
        bind("<Control-r>", self._load_preset)
        bind("<Control-l>", self._show_log_window)
        bind("<Control-m>", self._show_model_manager)
        bind("<Control-f>", self._focus_search)
        bind("<F5>", self._preview)
        bind("<F9>", self._start_processing)
        bind("<Control-Return>", self._start_processing)
        bind("<F1>", self._show_shortcuts)
        bind("<Escape>", self._cancel_processing)

    def _focus_search(self):
        self.search_entry.focus_set()
        self.search_entry.select_range(0, "end")

    def _setup_drag_and_drop(self):
        """把主窗口和预览区都注册成拖放目标"""
        if DND_BACKEND is None:
            return
        targets = [self.root, self.preview_canvas]
        if DND_BACKEND == "tkinterdnd2":
            for widget in targets:
                try:
                    widget.drop_target_register(DND_FILES)
                    widget.dnd_bind("<<Drop>>", self._on_tkdnd_drop)
                except Exception as e:
                    LOGGER.warn(f"注册拖放目标失败: {e}")
        elif DND_BACKEND == "windnd":
            try:
                windnd.hook_dropfiles(self.root, func=self._on_windnd_drop)
            except Exception as e:
                LOGGER.warn(f"注册拖放目标失败: {e}")

    def _on_tkdnd_drop(self, event):
        # event.data 形如 "{C:/a b.mp4} C:/c.mp4"，只能靠 Tcl 的 splitlist 正确切分
        try:
            paths = list(self.root.tk.splitlist(event.data))
        except Exception:
            paths = [event.data]
        self._handle_dropped_paths(paths)

    def _on_windnd_drop(self, files):
        self._handle_dropped_paths([f.decode("utf-8", "replace") if isinstance(f, bytes) else f
                                    for f in files])

    def _handle_dropped_paths(self, raw_paths: List[str]):
        """
        拖入内容的分派规则：
          目录 / 多个视频 → 进批处理队列
          单个视频       → 直接打开
          字幕文件       → 填进字幕烧录的字幕路径
          .cube / LUT 贴图 → 填进 LUT 路径
          单张图片       → 按当前功能填给水印图 / 背景图 / 风格参考图
        """
        videos: List[str] = []
        images: List[str] = []
        subtitles: List[str] = []
        luts: List[str] = []
        for raw in raw_paths:
            p = raw.strip().strip("{}")
            if not p:
                continue
            if os.path.isdir(p):
                videos.extend(self._scan_videos(p, recursive=True))
            elif os.path.isfile(p):
                ext = os.path.splitext(p)[1].lower()
                if ext in VIDEO_EXTENSIONS:
                    videos.append(p)
                elif ext in SUBTITLE_EXTENSIONS:
                    subtitles.append(p)
                elif ext == ".cube":
                    luts.append(p)
                elif ext in IMAGE_EXTENSIONS:
                    images.append(p)

        if not (videos or images or subtitles or luts):
            self.statusbar.configure(text="拖入的文件里没有可识别的视频/图片/字幕/LUT")
            LOGGER.warn(f"拖入的文件无法识别: {raw_paths}")
            return

        if subtitles and not videos:
            self._apply_dropped_asset(self.var_sub_path, subtitles[0], "字幕",
                                      ProcessingTask.SUBTITLE_BURN)
            return

        if luts and not videos:
            self.var_lut_source.set("file")
            self._apply_dropped_asset(self.var_lut_path, luts[0], "LUT",
                                      ProcessingTask.LUT_GRADE)
            return

        if images and not videos:
            # 同一张图在不同功能下含义不同，按当前选中的功能决定填哪儿
            target, label = {
                ProcessingTask.WATERMARK_ADD: (self.var_wm_image, "水印图片"),
                ProcessingTask.BG_BLUR: (self.var_bg_image, "背景图片"),
                ProcessingTask.LUT_GRADE: (self.var_lut_path, "LUT 贴图"),
            }.get(self._current_task, (self.var_style_reference_path, "风格参考图"))
            if target is self.var_wm_image:
                self.var_wm_type.set("image")
            elif target is self.var_bg_image:
                self.var_bg_mode.set("image")
            elif target is self.var_lut_path:
                self.var_lut_source.set("file")
            self._apply_dropped_asset(target, images[0], label, None)
            return

        if len(videos) == 1:
            self._load_video(videos[0])
        else:
            added = self._enqueue_batch_paths(videos)
            LOGGER.info(f"拖入 {len(videos)} 个视频，已加入批处理队列 {added} 个")
            self._show_batch_queue()

    def _apply_dropped_asset(self, var: tk.StringVar, path: str, label: str,
                             switch_to: Optional[ProcessingTask]):
        """把拖入的辅助文件填进对应参数，必要时顺手切到会用到它的功能上"""
        var.set(path)
        name = os.path.basename(path)
        LOGGER.info(f"已把拖入的文件设为{label}: {path}")
        self.statusbar.configure(text=f"{label}: {name}")
        if switch_to is not None and self._current_task != switch_to:
            if self._select_task_in_tree(switch_to):
                self.statusbar.configure(text=f"{label}: {name}（已切到对应功能）")
                return
        self._refresh_preview_quietly()

    @staticmethod
    def _scan_videos(folder: str, recursive: bool = True) -> List[str]:
        found: List[str] = []
        if recursive:
            for root_dir, _dirs, names in os.walk(folder):
                for n in names:
                    if os.path.splitext(n)[1].lower() in VIDEO_EXTENSIONS:
                        found.append(os.path.join(root_dir, n))
        else:
            try:
                for n in sorted(os.listdir(folder)):
                    full = os.path.join(folder, n)
                    if os.path.isfile(full) and os.path.splitext(n)[1].lower() in VIDEO_EXTENSIONS:
                        found.append(full)
            except OSError as e:
                LOGGER.warn(f"读取目录失败: {folder} ({e})")
        return sorted(found)

    @staticmethod
    def _open_path(path):
        p = Path(path)
        try:
            p.mkdir(parents=True, exist_ok=True)
            if sys.platform == "win32":
                os.startfile(str(p))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(p)], **SUBPROCESS_FLAGS)
            else:
                subprocess.run(["xdg-open", str(p)], **SUBPROCESS_FLAGS)
        except Exception as e:
            messagebox.showerror("错误", f"无法打开目录:\n{p}\n{e}")

    def _show_shortcuts(self):
        width = max(len(k) for k, _ in self.SHORTCUTS)
        lines = "\n".join(f"  {k.ljust(width)}   {d}" for k, d in self.SHORTCUTS)
        dnd = {"tkinterdnd2": "✅ tkinterdnd2", "windnd": "✅ windnd"}.get(
            DND_BACKEND, "❌ 未安装 (pip install tkinterdnd2)")
        messagebox.showinfo("快捷键说明",
                            f"快捷键\n{'─' * 34}\n{lines}\n\n"
                            f"拖拽导入: {dnd}\n"
                            f"  · 拖入单个视频 → 直接打开\n"
                            f"  · 拖入多个视频或文件夹 → 进批处理队列\n"
                            f"  · 拖入图片 → 设为风格迁移参考图")

    def _on_close(self):
        if self.is_processing or self.is_batch_running:
            if not messagebox.askyesno("确认退出", "还有任务正在处理，确定退出吗？"):
                return
            self._batch_cancel = True
            self.engine.cancel()
        LOGGER.info("程序退出")
        LOGGER.close()
        self.root.destroy()

    # ════════════════════════════════════════════════════════════
    #  参数预设 (JSON)
    # ════════════════════════════════════════════════════════════

    # 这些不该跟着预设走：输出路径、待拼接文件都是「这一次」的东西
    PRESET_EXCLUDED_VARS = {"var_output_path", "var_batch_out_dir",
                            "var_log_level", "var_log_autoscroll"}

    def _iter_preset_vars(self):
        """遍历所有 var_* 形式的 tk 变量，预设的存取都基于它"""
        for name, value in sorted(vars(self).items()):
            if (name.startswith("var_") and name not in self.PRESET_EXCLUDED_VARS
                    and isinstance(value, tk.Variable)):
                yield name, value

    def _collect_preset(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "app": APP_NAME,
            "version": APP_VERSION,
            "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "task": self._current_task.name if self._current_task else None,
            "vars": {},
            "pipeline": [t.name for t, v in self.pipeline_vars.items() if v.get()],
        }
        for name, var in self._iter_preset_vars():
            try:
                data["vars"][name] = var.get()
            except tk.TclError:
                # 输入框里留了非法内容（比如宽度栏是空的），跳过而不是让整次保存失败
                LOGGER.warn(f"预设跳过读取失败的参数: {name}")
        return data

    def _apply_preset(self, data: Dict[str, Any]) -> Tuple[int, List[str]]:
        # 先切功能：选中功能会重建参数面板，而某些面板构造时会覆写变量
        # （比如风格迁移会把模型重置为第一个），所以必须在写入变量之前做
        task_name = data.get("task")
        if task_name:
            task = getattr(ProcessingTask, task_name, None)
            if task is not None:
                self._select_task_in_tree(task)
            else:
                LOGGER.warn(f"预设里的功能不存在，已忽略: {task_name}")

        applied, skipped = 0, []
        own_vars = dict(self._iter_preset_vars())
        for name, value in (data.get("vars") or {}).items():
            var = own_vars.get(name)
            if var is None:
                skipped.append(name)
                continue
            try:
                var.set(value)
                applied += 1
            except (tk.TclError, ValueError):
                skipped.append(name)

        saved_pipeline = set(data.get("pipeline") or [])
        for task, var in self.pipeline_vars.items():
            var.set(task.name in saved_pipeline)

        # 编码面板的联动状态不由变量本身驱动，需要手动同步一次
        if hasattr(self, "_codec_box"):
            codec = self.var_video_codec.get()
            if codec in self._codec_keys:
                self._codec_box.current(self._codec_keys.index(codec))
            self._on_codec_change(codec)
        self._update_encode_section_visibility(self._current_task)
        return applied, skipped

    def _select_task_in_tree(self, task: ProcessingTask) -> bool:
        for item_id, mapped in self._function_map.items():
            if mapped == task:
                self.func_tree.selection_set(item_id)
                self.func_tree.see(item_id)
                # selection_set 在目标已被选中时不会触发事件，这里补一次
                self._current_task = task
                self._build_task_params(task)
                return True
        return False

    def _save_preset(self):
        PRESET_DIR.mkdir(parents=True, exist_ok=True)
        default = "preset"
        if self._current_task:
            default = self._current_task.name.lower()
        path = filedialog.asksaveasfilename(
            title="保存参数预设", initialdir=str(PRESET_DIR.absolute()),
            initialfile=f"{default}.json", defaultextension=".json",
            filetypes=[("JSON 预设", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            data = self._collect_preset()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            LOGGER.error(f"保存预设失败: {e}", exc=True)
            messagebox.showerror("错误", f"保存预设失败:\n{e}")
            return
        LOGGER.info(f"预设已保存: {path} ({len(data['vars'])} 项参数)")
        self.statusbar.configure(text=f"预设已保存: {os.path.basename(path)}")

    def _load_preset(self):
        PRESET_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="载入参数预设", initialdir=str(PRESET_DIR.absolute()),
            filetypes=[("JSON 预设", "*.json"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            LOGGER.error(f"读取预设失败: {e}", exc=True)
            messagebox.showerror("错误", f"读取预设失败:\n{e}")
            return
        if not isinstance(data, dict) or "vars" not in data:
            messagebox.showerror("错误", "这不是一个有效的参数预设文件")
            return

        applied, skipped = self._apply_preset(data)
        LOGGER.info(f"预设已载入: {path} (应用 {applied} 项"
                    f"{f', 忽略 {len(skipped)} 项' if skipped else ''})")
        self.statusbar.configure(text=f"预设已载入: {os.path.basename(path)}")
        if skipped:
            messagebox.showwarning(
                "部分参数未应用",
                f"已应用 {applied} 项参数。\n\n"
                f"以下 {len(skipped)} 项无法识别（可能是旧版本预设），已忽略:\n"
                + "\n".join(f"  · {s}" for s in skipped[:15])
                + ("\n  ..." if len(skipped) > 15 else ""))
        if self.current_video_info:
            self._preview()

    # ════════════════════════════════════════════════════════════
    #  批处理队列
    # ════════════════════════════════════════════════════════════

    def _add_batch_files(self):
        paths = filedialog.askopenfilenames(
            title="选择要批量处理的视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.ts"),
                       ("所有文件", "*.*")])
        if not paths:
            return
        added = self._enqueue_batch_paths(list(paths))
        self._show_batch_queue()
        self.statusbar.configure(text=f"批处理队列新增 {added} 个文件")

    def _add_batch_folder(self):
        folder = filedialog.askdirectory(title="选择包含视频的文件夹")
        if not folder:
            return
        videos = self._scan_videos(folder, recursive=self.var_batch_recursive.get())
        if not videos:
            messagebox.showinfo("提示", f"该文件夹里没有找到视频文件:\n{folder}")
            return
        added = self._enqueue_batch_paths(videos)
        if not self.var_batch_out_dir.get():
            self.var_batch_out_dir.set(os.path.join(folder, "output"))
        self._show_batch_queue()
        self.statusbar.configure(text=f"批处理队列新增 {added} 个文件")

    def _enqueue_batch_paths(self, paths: List[str]) -> int:
        existing = {j.input_path for j in self.batch_jobs}
        added = 0
        for p in paths:
            full = os.path.abspath(p)
            if full in existing:
                continue
            existing.add(full)
            self.batch_jobs.append(BatchJob(input_path=full))
            added += 1
        self._refresh_batch_tree()
        return added

    @staticmethod
    def _default_ext_for_task(task: Optional[ProcessingTask], source_ext: str) -> str:
        if task in ANALYSIS_TASKS:
            return ".png"
        if task == ProcessingTask.SUBTITLE_OCR:
            return ".srt"
        if task == ProcessingTask.TO_GIF:
            return ".gif"
        if task == ProcessingTask.EXTRACT_FRAMES:
            return ""          # 输出的是目录
        return source_ext if source_ext.lower() in VIDEO_EXTENSIONS else ".mp4"

    def _batch_output_for(self, job: BatchJob, task: Optional[ProcessingTask]) -> str:
        base, ext = os.path.splitext(os.path.basename(job.input_path))
        out_dir = self.var_batch_out_dir.get().strip()
        if not out_dir:
            out_dir = os.path.join(os.path.dirname(job.input_path), "output")
        suffix = self.var_batch_suffix.get()
        return os.path.join(out_dir, base + suffix + self._default_ext_for_task(task, ext))

    def _show_batch_queue(self):
        if self.batch_window is not None and self.batch_window.winfo_exists():
            self.batch_window.deiconify()
            self.batch_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.batch_window = win
        win.title("批处理队列 — 对多个文件套用同一套参数")
        win.geometry("900x600")
        win.transient(self.root)

        ttk.Label(win, text="🗂 批处理队列", style="Header.TLabel").pack(padx=10, pady=(10, 2))
        ttk.Label(win, text="队列里的每个文件都会套用主窗口当前选中的功能和参数。"
                            "开始批处理时参数会被快照，之后再改主窗口不影响本次运行。",
                  style="Info.TLabel", wraplength=860, justify="left").pack(padx=10, pady=(0, 6))

        # ── 输出设置 ──
        cfg = ttk.LabelFrame(win, text="输出设置")
        cfg.pack(fill="x", padx=10, pady=4)
        row = ttk.Frame(cfg)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Label(row, text="输出目录:").pack(side="left")
        ttk.Entry(row, textvariable=self.var_batch_out_dir).pack(
            side="left", fill="x", expand=True, padx=6)
        ttk.Button(row, text="浏览", command=self._browse_batch_out_dir).pack(side="left")

        row2 = ttk.Frame(cfg)
        row2.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Label(row2, text="文件名后缀:").pack(side="left")
        ttk.Entry(row2, textvariable=self.var_batch_suffix, width=12).pack(side="left", padx=6)
        ttk.Checkbutton(row2, text="添加文件夹时递归子目录",
                        variable=self.var_batch_recursive).pack(side="left", padx=(12, 0))
        ttk.Checkbutton(row2, text="跳过已存在的输出",
                        variable=self.var_batch_skip_existing).pack(side="left", padx=(12, 0))
        ttk.Label(cfg, text="留空输出目录时，输出会放到每个源文件同级的 output/ 子目录",
                  style="Info.TLabel").pack(anchor="w", padx=8, pady=(0, 4))

        # ── 队列列表 ──
        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=4)
        cols = ("idx", "name", "status", "message")
        tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=14)
        for col, text, width, anchor in (("idx", "#", 40, "center"),
                                         ("name", "文件", 300, "w"),
                                         ("status", "状态", 80, "center"),
                                         ("message", "说明", 420, "w")):
            tree.heading(col, text=text)
            tree.column(col, width=width, anchor=anchor)
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.batch_tree = tree

        # ── 队列编辑 ──
        edit = ttk.Frame(win)
        edit.pack(fill="x", padx=10, pady=4)
        ttk.Button(edit, text="➕ 添加文件", command=self._add_batch_files).pack(side="left", padx=2)
        ttk.Button(edit, text="📁 添加文件夹", command=self._add_batch_folder).pack(side="left", padx=2)
        ttk.Button(edit, text="➖ 移除选中", command=self._remove_batch_selected).pack(side="left", padx=2)
        ttk.Button(edit, text="🧹 清空队列", command=self._clear_batch_queue).pack(side="left", padx=2)
        ttk.Button(edit, text="🔄 重置状态", command=self._reset_batch_status).pack(side="left", padx=2)

        # ── 运行 ──
        run = ttk.Frame(win)
        run.pack(fill="x", padx=10, pady=(4, 8))
        self.batch_start_btn = ttk.Button(run, text="▶ 开始批处理", style="Accent.TButton",
                                          command=self._start_batch)
        self.batch_start_btn.pack(side="left", padx=2)
        self.batch_cancel_btn = ttk.Button(run, text="⏹ 取消", state="disabled",
                                           command=self._cancel_batch)
        self.batch_cancel_btn.pack(side="left", padx=2)
        self.batch_progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(run, variable=self.batch_progress_var, maximum=100).pack(
            side="left", fill="x", expand=True, padx=8)
        self.batch_status_label = ttk.Label(win, text="就绪", style="Info.TLabel")
        self.batch_status_label.pack(anchor="w", padx=10, pady=(0, 8))

        win.protocol("WM_DELETE_WINDOW", self._close_batch_window)
        self._refresh_batch_tree()
        self._sync_batch_buttons()

    def _close_batch_window(self):
        if self.batch_window is not None:
            self.batch_window.destroy()
        self.batch_window = None
        self.batch_tree = None

    def _browse_batch_out_dir(self):
        folder = filedialog.askdirectory(title="选择批处理输出目录")
        if folder:
            self.var_batch_out_dir.set(folder)

    def _refresh_batch_tree(self):
        tree = self.batch_tree
        if tree is None or not tree.winfo_exists():
            return
        tree.delete(*tree.get_children())
        for i, job in enumerate(self.batch_jobs, 1):
            tree.insert("", "end", iid=str(i - 1),
                        values=(i, job.name, job.status.value, job.message))

    def _selected_batch_indices(self) -> List[int]:
        if self.batch_tree is None or not self.batch_tree.winfo_exists():
            return []
        return sorted((int(i) for i in self.batch_tree.selection()), reverse=True)

    def _remove_batch_selected(self):
        if self.is_batch_running:
            messagebox.showinfo("提示", "批处理进行中，无法修改队列")
            return
        for idx in self._selected_batch_indices():
            if 0 <= idx < len(self.batch_jobs):
                self.batch_jobs.pop(idx)
        self._refresh_batch_tree()

    def _clear_batch_queue(self):
        if self.is_batch_running:
            messagebox.showinfo("提示", "批处理进行中，无法修改队列")
            return
        self.batch_jobs.clear()
        self._refresh_batch_tree()

    def _reset_batch_status(self):
        if self.is_batch_running:
            return
        for job in self.batch_jobs:
            job.status = BatchStatus.PENDING
            job.message = ""
        self._refresh_batch_tree()

    def _sync_batch_buttons(self):
        if self.batch_window is None or not self.batch_window.winfo_exists():
            return
        self.batch_start_btn.configure(state="disabled" if self.is_batch_running else "normal")
        self.batch_cancel_btn.configure(state="normal" if self.is_batch_running else "disabled")

    def _start_batch(self):
        if self.is_batch_running:
            return
        if self.is_processing:
            messagebox.showwarning("提示", "单个任务正在处理中，请先等它结束")
            return
        if not self.batch_jobs:
            messagebox.showinfo("提示", "队列是空的，先添加文件或文件夹")
            return
        if not self._current_task:
            messagebox.showinfo("提示", "请先在主窗口左侧选择一个功能")
            return
        if self._current_task == ProcessingTask.CONCAT:
            messagebox.showwarning("提示", "视频拼接是把多个文件合成一个，"
                                          "和「逐个文件套用同一参数」的批处理语义冲突，"
                                          "请用主窗口的拼接功能")
            return
        if self._current_task == ProcessingTask.PIPELINE:
            base = self._build_processing_params()
            if not base.pipeline_tasks:
                messagebox.showwarning("提示", "流程组合至少要勾选一个处理步骤")
                return

        # 参数快照：批处理跑起来之后用户还能继续改主窗口，不能让它影响正在跑的任务
        template = copy.deepcopy(self._build_processing_params())
        task = template.task
        pending = []
        for job in self.batch_jobs:
            job.output_path = self._batch_output_for(job, task)
            if job.status in (BatchStatus.DONE, BatchStatus.SKIPPED):
                continue
            job.status = BatchStatus.PENDING
            job.message = ""
            pending.append(job)
        if not pending:
            messagebox.showinfo("提示", "队列里没有待处理的文件（可点「重置状态」重跑）")
            return

        self.is_batch_running = True
        self._batch_cancel = False
        self.batch_progress_var.set(0)
        self._sync_batch_buttons()
        self.btn_process.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.engine.set_progress_callback(lambda p, m: self.msg_queue.put(("progress", p, m)))
        LOGGER.info(f"批处理开始: {len(pending)} 个文件 | 功能={task.name} | "
                    f"编码={template.video_codec}")

        skip_existing = self.var_batch_skip_existing.get()
        self._batch_thread = threading.Thread(
            target=self._run_batch, args=(pending, template, skip_existing), daemon=True)
        self._batch_thread.start()

    def _run_batch(self, jobs: List[BatchJob], template: ProcessingParams,
                   skip_existing: bool):
        """批处理工作线程。所有 GUI 更新都经 msg_queue 回到主线程"""
        total = len(jobs)
        done = failed = skipped = 0
        for i, job in enumerate(jobs):
            if self._batch_cancel:
                for rest in jobs[i:]:
                    self.msg_queue.put(("batch_item", rest, BatchStatus.CANCELLED, ""))
                break

            if skip_existing and job.output_path and os.path.exists(job.output_path):
                skipped += 1
                self.msg_queue.put(("batch_item", job, BatchStatus.SKIPPED, "输出已存在"))
                self.msg_queue.put(("batch_progress", (i + 1) / total,
                                    f"{i + 1}/{total} 跳过 {job.name}"))
                continue

            self.msg_queue.put(("batch_item", job, BatchStatus.RUNNING, ""))
            self.msg_queue.put(("batch_progress", i / total,
                                f"{i + 1}/{total} 正在处理 {job.name}"))
            LOGGER.info(f"[批处理 {i + 1}/{total}] {job.input_path} → {job.output_path}")

            params = copy.deepcopy(template)
            params.input_path = job.input_path
            params.output_path = job.output_path
            out_dir = os.path.dirname(params.output_path)
            try:
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                ok = self.engine.process_video(params)
            except Exception as e:
                LOGGER.error(f"[批处理] {job.name} 出错: {e}", exc=True)
                self.msg_queue.put(("batch_item", job, BatchStatus.FAILED, str(e)[:200]))
                failed += 1
                continue

            if ok:
                done += 1
                self.msg_queue.put(("batch_item", job, BatchStatus.DONE,
                                    os.path.basename(params.output_path)))
            elif self._batch_cancel or self.engine.is_cancelled:
                self.msg_queue.put(("batch_item", job, BatchStatus.CANCELLED, ""))
            else:
                failed += 1
                self.msg_queue.put(("batch_item", job, BatchStatus.FAILED, "处理失败，详见日志"))

        self.msg_queue.put(("batch_done", (done, failed, skipped, total), ""))

    def _cancel_batch(self):
        if not self.is_batch_running:
            return
        self._batch_cancel = True
        self.engine.cancel()
        self.batch_status_label.configure(text="正在取消，等当前文件收尾...")
        LOGGER.warn("批处理已请求取消")

    def _update_batch_item(self, job: BatchJob, status: BatchStatus, message: str):
        job.status = status
        job.message = message
        tree = self.batch_tree
        if tree is None or not tree.winfo_exists():
            return
        # 按对象身份定位，不能用 list.index —— BatchJob 是 dataclass，
        # index 走的是字段相等比较，状态刚被改写会让匹配结果不可靠
        idx = next((i for i, j in enumerate(self.batch_jobs) if j is job), None)
        if idx is None:
            return
        iid = str(idx)
        if tree.exists(iid):
            tree.item(iid, values=(idx + 1, job.name, status.value, message))
            if status == BatchStatus.RUNNING:
                tree.see(iid)

    def _finish_batch(self, stats: Tuple[int, int, int, int]):
        done, failed, skipped, total = stats
        self.is_batch_running = False
        self._batch_cancel = False
        self._sync_batch_buttons()
        if not self.is_processing:
            self.btn_process.configure(state="normal")
            self.btn_cancel.configure(state="disabled")
        summary = f"批处理结束: 成功 {done} / 失败 {failed} / 跳过 {skipped} / 共 {total}"
        LOGGER.info(summary)
        if self.batch_window is not None and self.batch_window.winfo_exists():
            self.batch_progress_var.set(100)
            self.batch_status_label.configure(text=summary)
        self.statusbar.configure(text=summary)
        messagebox.showinfo("批处理完成", summary)

    # ════════════════════════════════════════════════════════════
    #  处理日志窗口
    # ════════════════════════════════════════════════════════════

    LOG_COLORS = {"DEBUG": "#888888", "INFO": "#222222",
                  "WARN": "#b8860b", "ERROR": "#c62828"}

    def _show_log_window(self):
        if self.log_window is not None and self.log_window.winfo_exists():
            self.log_window.deiconify()
            self.log_window.lift()
            return

        win = tk.Toplevel(self.root)
        self.log_window = win
        win.title("处理日志")
        win.geometry("980x560")

        top = ttk.Frame(win)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="最低级别:").pack(side="left")
        level_box = ttk.Combobox(top, state="readonly", width=7, values=list(AppLogger.LEVELS),
                                 textvariable=self.var_log_level)
        level_box.pack(side="left", padx=6)
        level_box.bind("<<ComboboxSelected>>", lambda e: self._reload_log_view())
        ttk.Checkbutton(top, text="自动滚动", variable=self.var_log_autoscroll).pack(
            side="left", padx=(10, 0))
        ttk.Button(top, text="清空显示", command=self._clear_log_view).pack(side="right", padx=2)
        ttk.Button(top, text="另存为...", command=self._save_log_as).pack(side="right", padx=2)
        ttk.Button(top, text="打开日志目录",
                   command=lambda: self._open_path(LOG_DIR)).pack(side="right", padx=2)

        text_frame = ttk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=10, pady=4)
        text = tk.Text(text_frame, wrap="word", font=("Consolas", 9),
                       bg="#fbfbfb", relief="solid", borderwidth=1, state="disabled")
        vsb = ttk.Scrollbar(text_frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        for level, color in self.LOG_COLORS.items():
            text.tag_configure(level, foreground=color)
        self.log_text = text

        path_text = str(LOGGER.log_path) if LOGGER.log_path else "(尚未写入)"
        if LOGGER.file_error:
            path_text = f"⚠️ 落盘失败: {LOGGER.file_error}"
        ttk.Label(win, text=f"日志文件: {path_text}", style="Info.TLabel").pack(
            anchor="w", padx=10, pady=(0, 8))

        win.protocol("WM_DELETE_WINDOW", self._close_log_window)
        self._reload_log_view()

    def _close_log_window(self):
        if self.log_window is not None:
            self.log_window.destroy()
        self.log_window = None
        self.log_text = None

    def _log_view_alive(self) -> bool:
        return self.log_text is not None and self.log_text.winfo_exists()

    def _append_log_records(self, records: List[Tuple[int, str, str, str]]):
        if not self._log_view_alive():
            return
        minimum = self.var_log_level.get()
        text = self.log_text
        text.configure(state="normal")
        for _seq, stamp, level, message in records:
            if not AppLogger.level_at_least(level, minimum):
                continue
            text.insert("end", f"[{stamp}] {level:<5} {message}\n", level)
        text.configure(state="disabled")
        if self.var_log_autoscroll.get():
            text.see("end")

    def _reload_log_view(self):
        if not self._log_view_alive():
            return
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        records = LOGGER.all_records()
        self._log_seq = records[-1][0] if records else self._log_seq
        self._append_log_records(records)

    def _clear_log_view(self):
        if not self._log_view_alive():
            return
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _save_log_as(self):
        path = filedialog.asksaveasfilename(
            title="导出日志", defaultextension=".log",
            initialfile=f"videotoolbox_{time.strftime('%Y%m%d_%H%M%S')}.log",
            filetypes=[("日志文件", "*.log"), ("文本文件", "*.txt"), ("所有文件", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                for _seq, stamp, level, message in LOGGER.all_records():
                    f.write(f"[{stamp}] {level:<5} {message}\n")
        except OSError as e:
            messagebox.showerror("错误", f"导出日志失败:\n{e}")
            return
        self.statusbar.configure(text=f"日志已导出: {os.path.basename(path)}")

    def _pump_log_window(self):
        if not self._log_view_alive():
            return
        records = LOGGER.records_since(self._log_seq)
        if records:
            self._log_seq = records[-1][0]
            self._append_log_records(records)

    # ════════════════════════════════════════════════════════════
    #  操作逻辑
    # ════════════════════════════════════════════════════════════

    def _open_video(self):
        path = filedialog.askopenfilename(title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"), ("所有文件", "*.*")])
        if path:
            self._load_video(path)

    def _load_video(self, path: str) -> bool:
        info = VideoEngine.get_video_info(path)
        if not info:
            LOGGER.error(f"无法读取视频: {path}")
            messagebox.showerror("错误", f"无法读取视频:\n{path}")
            return False
        self.current_video_info = info
        self._update_info_display(info)
        self.preview_slider.configure(to=info.duration)
        name, ext = os.path.splitext(os.path.basename(path))
        out_dir = os.path.dirname(path)
        out_ext = self._default_ext_for_task(self._current_task, ext)
        self.var_output_path.set(os.path.join(out_dir, f"{name}_output{out_ext}"))
        LOGGER.info(f"已打开: {path} | {info.resolution_str} | {info.fps:.2f}fps | "
                    f"{info.duration_str} | {info.codec} | {info.size_str}")
        self.root.after(200, lambda: self._show_preview_at(0.0))
        return True

    def _update_info_display(self, info: VideoInfo):
        self.info_labels["文件"].configure(text=os.path.basename(info.path))
        self.info_labels["分辨率"].configure(text=info.resolution_str)
        self.info_labels["帧率"].configure(text=f"{info.fps:.2f} fps")
        self.info_labels["时长"].configure(text=info.duration_str)
        self.info_labels["编码"].configure(text=info.codec)
        self.info_labels["大小"].configure(text=info.size_str)

    def _show_preview_at(self, time_pos: float):
        if not self.current_video_info:
            return
        params = self._build_processing_params()
        try:
            frame = self.engine.preview_frame(self.current_video_info.path, params, time_pos)
            if frame is not None:
                self.preview_canvas.show_frame(frame)
            else:
                self.preview_canvas.show_text("无法获取预览帧")
        except Exception as e:
            self.preview_canvas.show_text(f"预览出错: {str(e)[:50]}")
            LOGGER.error(f"预览出错: {e}", exc=True)

    def _on_slider_change(self, value):
        t = float(value)
        m, s = divmod(int(t), 60)
        h, m = divmod(m, 60)
        self.time_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def _preview(self):
        if not self.current_video_info:
            messagebox.showinfo("提示", "请先打开视频文件")
            return
        self._show_preview_at(self.preview_time_var.get())

    def _build_processing_params(self) -> ProcessingParams:
        params = ProcessingParams()
        params.task = self._current_task or ProcessingTask.TRIM
        if self.current_video_info:
            params.input_path = self.current_video_info.path
        params.output_path = self.var_output_path.get()

        def safe_float(var, default=0.0):
            try:
                return float(var.get())
            except (ValueError, tk.TclError):
                return default

        def safe_int(var, default=0):
            try:
                return int(var.get())
            except (ValueError, tk.TclError):
                return default

        params.start_time = safe_float(self.var_start_time)
        params.end_time = safe_float(self.var_end_time, -1.0)
        params.target_width = safe_int(self.var_target_w)
        params.target_height = safe_int(self.var_target_h)
        params.keep_aspect = self.var_keep_aspect.get()
        params.rotation = int(self.var_rotation.get())
        params.flip_h = self.var_flip_h.get()
        params.flip_v = self.var_flip_v.get()
        params.target_fps = safe_float(self.var_target_fps, 30.0)
        params.brightness = self.var_brightness.get()
        params.contrast = self.var_contrast.get()
        params.saturation = self.var_saturation.get()
        params.gamma = self.var_gamma.get()
        params.color_space = self.var_color_space.get()
        params.blur_type = self.var_blur_type.get()
        params.blur_ksize = self.var_blur_ksize.get()
        params.sharpen_strength = self.var_sharpen.get()
        params.denoise_strength = self.var_denoise.get()
        params.edge_type = self.var_edge_type.get()
        params.canny_low = self.var_canny_low.get()
        params.canny_high = self.var_canny_high.get()
        params.tone_type = self.var_tone_type.get()
        params.mosaic_size = self.var_mosaic_size.get()
        params.dnn_confidence = self.var_dnn_conf.get()
        params.dnn_nms_threshold = self.var_dnn_nms.get()
        params.style_model_name = self.var_style_model.get()
        params.style_reference_path = self.var_style_reference_path.get()
        params.style_strength = self.var_style_strength.get()
        params.gif_fps = self.var_gif_fps.get()
        params.gif_scale = self.var_gif_scale.get()
        params.extract_interval = self.var_extract_interval.get()
        params.extract_format = self.var_extract_format.get()
        params.concat_files = list(self.concat_file_list)

        # ★ 输出编码
        params.video_codec = self.var_video_codec.get()
        params.rate_mode = self.var_rate_mode.get()
        params.crf = self.var_crf.get()
        params.bitrate_kbps = safe_int(self.var_bitrate, 4000)
        params.encode_preset = self.var_encode_preset.get()
        params.keep_audio = self.var_keep_audio.get()

        # ★ 去马赛克参数
        params.demosaic_model = self.var_demosaic_model.get()
        params.demosaic_full = self.var_demosaic_full.get()
        params.demosaic_tile_size = self.var_demosaic_tile.get()
        params.demosaic_region = (safe_int(self.var_demosaic_rx), safe_int(self.var_demosaic_ry),
                                  safe_int(self.var_demosaic_rw), safe_int(self.var_demosaic_rh))

        # ★ 水印添加
        params.watermark_type = self.var_wm_type.get()
        # 参数面板里没法直接敲回车，用 \n 字面量表示换行
        params.watermark_text = self.var_wm_text.get().replace("\\n", "\n")
        params.watermark_image_path = self.var_wm_image.get()
        params.watermark_font_path = self.var_wm_font.get()
        params.watermark_font_size = safe_int(self.var_wm_font_size, 42)
        params.watermark_color = self.var_wm_color.get()
        params.watermark_outline_color = self.var_wm_outline_color.get()
        params.watermark_outline_width = safe_int(self.var_wm_outline_width, 2)
        params.watermark_opacity = safe_float(self.var_wm_opacity, 0.75)
        params.watermark_scale = safe_float(self.var_wm_scale, 0.18)
        params.watermark_position = self.var_wm_position.get()
        params.watermark_margin = safe_int(self.var_wm_margin, 24)
        params.watermark_custom_x = safe_int(self.var_wm_cx)
        params.watermark_custom_y = safe_int(self.var_wm_cy)
        params.watermark_rotation = safe_float(self.var_wm_rotation, 0.0)
        params.watermark_tile = self.var_wm_tile.get()
        params.watermark_tile_gap = safe_int(self.var_wm_tile_gap, 80)

        # ★ 水印去除
        params.wm_remove_regions = self.var_wmr_regions.get()
        params.wm_remove_method = self.var_wmr_method.get()
        params.wm_remove_smart_mask = self.var_wmr_smart.get()
        params.wm_remove_sensitivity = safe_int(self.var_wmr_sensitivity, 22)
        params.wm_remove_radius = safe_int(self.var_wmr_radius, 4)
        params.wm_remove_grow = safe_int(self.var_wmr_grow, 3)

        # ★ LUT 颜色分级
        params.lut_source = self.var_lut_source.get()
        params.lut_preset = self.var_lut_preset.get()
        params.lut_path = self.var_lut_path.get()
        params.lut_strength = safe_float(self.var_lut_strength, 1.0)
        params.lut_fast = self.var_lut_fast.get()

        # ★ 字幕烧录
        params.subtitle_path = self.var_sub_path.get()
        params.subtitle_font_path = self.var_sub_font.get()
        params.subtitle_font_size = safe_int(self.var_sub_font_size, 0)
        params.subtitle_color = self.var_sub_color.get()
        params.subtitle_outline_color = self.var_sub_outline_color.get()
        params.subtitle_outline_width = safe_int(self.var_sub_outline_width, 3)
        params.subtitle_bottom_margin = safe_int(self.var_sub_margin, 40)
        params.subtitle_box_opacity = safe_float(self.var_sub_box_opacity, 0.0)
        params.subtitle_time_offset = safe_float(self.var_sub_offset, 0.0)

        # ★ 背景虚化 / 人像分割
        params.seg_method = self.var_seg_method.get()
        params.seg_downsample = safe_float(self.var_seg_downsample, 0.0)
        params.seg_feather = safe_int(self.var_seg_feather, 3)
        params.bg_mode = self.var_bg_mode.get()
        params.bg_blur_strength = safe_int(self.var_bg_blur_strength, 35)
        params.bg_color = self.var_bg_color.get()
        params.bg_image_path = self.var_bg_image.get()

        # ★ 字幕 OCR
        params.ocr_model = self.var_ocr_model.get()
        params.ocr_band_top = safe_float(self.var_ocr_band_top, 0.70)
        params.ocr_band_bottom = safe_float(self.var_ocr_band_bottom, 1.0)
        params.ocr_sample_interval = safe_float(self.var_ocr_interval, 0.3)
        params.ocr_min_duration = safe_float(self.var_ocr_min_duration, 0.4)
        if params.ocr_band_bottom <= params.ocr_band_top:
            params.ocr_band_top, params.ocr_band_bottom = \
                params.ocr_band_bottom, params.ocr_band_top

        # 流程组合
        if params.task == ProcessingTask.PIPELINE:
            # 固定的执行顺序。几个位置是有讲究的：
            #   · 水印去除排在最前，趁画面还没被滤镜改动时修补最干净
            #   · LUT 调色在滤镜之后、叠加类之前，免得把水印和字幕一起调色了
            #   · 字幕烧录和水印添加放最后，保证它们永远压在最上层且不被虚化
            ordered = [
                ProcessingTask.WATERMARK_REMOVE,
                ProcessingTask.RESIZE, ProcessingTask.ROTATE,
                ProcessingTask.BRIGHTNESS_CONTRAST, ProcessingTask.COLOR_SPACE,
                ProcessingTask.HISTOGRAM_EQ, ProcessingTask.SHARPEN_BLUR,
                ProcessingTask.SKETCH, ProcessingTask.CARTOON, ProcessingTask.EMBOSS,
                ProcessingTask.EDGE_DETECT, ProcessingTask.COLOR_TONE,
                ProcessingTask.MOSAIC, ProcessingTask.VIGNETTE,
                ProcessingTask.LUT_GRADE,
                ProcessingTask.FACE_DETECT, ProcessingTask.OBJECT_DETECT,
                ProcessingTask.STYLE_TRANSFER, ProcessingTask.STYLE_REFERENCE,
                ProcessingTask.FACE_MOSAIC, ProcessingTask.BG_BLUR,
                ProcessingTask.TEXT_DETECT, ProcessingTask.DEMOSAIC,
                ProcessingTask.SUBTITLE_BURN, ProcessingTask.WATERMARK_ADD,
            ]
            params.pipeline_tasks = [t for t in ordered
                                     if t in self.pipeline_vars and self.pipeline_vars[t].get()]
        return params

    def _start_processing(self):
        if self.is_processing:
            messagebox.showwarning("提示", "正在处理中，请等待...")
            return
        if self.is_batch_running:
            messagebox.showwarning("提示", "批处理进行中，请等它结束或先取消")
            return
        if not self._current_task:
            messagebox.showinfo("提示", "请先从左侧选择一个功能")
            return
        params = self._build_processing_params()
        if not params.input_path and params.task != ProcessingTask.CONCAT:
            messagebox.showwarning("提示", "请先打开视频文件")
            return
        if not params.output_path:
            messagebox.showwarning("提示", "请设置输出路径")
            return
        if params.task == ProcessingTask.PIPELINE and not params.pipeline_tasks:
            messagebox.showwarning("提示", "请至少勾选一个处理步骤")
            return

        out_dir = os.path.dirname(params.output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # 提前算出真实输出路径。完成弹窗不能再从界面反推，否则用户处理期间
        # 改了任何参数，弹窗就会显示一个错的路径
        self._last_output_path = VideoEngine._fix_output_path(copy.deepcopy(params))

        self.is_processing = True
        self.btn_process.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_var.set(0)
        LOGGER.info(f"开始处理: 功能={params.task.name} | 输入={params.input_path} | "
                    f"输出={self._last_output_path} | 编码={params.video_codec}")

        self.engine.set_progress_callback(lambda p, m: self.msg_queue.put(("progress", p, m)))

        def run():
            try:
                success = self.engine.process_video(params)
                self.msg_queue.put(("done", success, ""))
            except Exception as e:
                LOGGER.error(f"处理出错: {e}", exc=True)
                self.msg_queue.put(("error", False, str(e)))

        self.processing_thread = threading.Thread(target=run, daemon=True)
        self.processing_thread.start()

    def _cancel_processing(self):
        if self.is_batch_running:
            self._cancel_batch()
            return
        if self.is_processing:
            LOGGER.warn("用户取消了处理")
            self.engine.cancel()

    def _poll_messages(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                kind = msg[0]
                if kind == "progress":
                    _, progress, message = msg
                    if progress >= 0:
                        self.progress_var.set(progress * 100)
                    self.progress_label.configure(text=message)
                elif kind == "done":
                    _, success, _ = msg
                    self.is_processing = False
                    if not self.is_batch_running:
                        self.btn_process.configure(state="normal")
                        self.btn_cancel.configure(state="disabled")
                    if success:
                        self.progress_var.set(100)
                        actual = self._last_output_path or self.var_output_path.get()
                        messagebox.showinfo("完成", f"处理完成!\n输出: {actual}")
                    else:
                        self.progress_label.configure(text="处理失败或已取消")
                elif kind == "error":
                    _, _, err = msg
                    self.is_processing = False
                    if not self.is_batch_running:
                        self.btn_process.configure(state="normal")
                        self.btn_cancel.configure(state="disabled")
                    messagebox.showerror("错误", f"处理出错:\n{err}")
                elif kind == "batch_item":
                    _, job, status, message = msg
                    self._update_batch_item(job, status, message)
                elif kind == "batch_progress":
                    _, progress, message = msg
                    if self.batch_window is not None and self.batch_window.winfo_exists():
                        self.batch_progress_var.set(progress * 100)
                        self.batch_status_label.configure(text=message)
                    self.statusbar.configure(text=message)
                elif kind == "batch_done":
                    self._finish_batch(msg[1])
        except queue.Empty:
            pass
        self._pump_log_window()
        self.root.after(100, self._poll_messages)

    def _browse_output(self):
        if self._current_task in ANALYSIS_TASKS:
            ft = [("PNG", "*.png"), ("JPEG", "*.jpg"), ("所有文件", "*.*")]
            de = ".png"
        elif self._current_task == ProcessingTask.TO_GIF:
            ft = [("GIF", "*.gif"), ("所有文件", "*.*")]
            de = ".gif"
        else:
            ft = [("MP4", "*.mp4"), ("AVI", "*.avi"), ("MOV", "*.mov"), ("所有文件", "*.*")]
            de = ".mp4"
        path = filedialog.asksaveasfilename(title="选择输出路径", defaultextension=de, filetypes=ft)
        if path:
            self.var_output_path.set(path)

    def _add_concat_file(self):
        paths = filedialog.askopenfilenames(title="添加视频",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv"), ("所有文件", "*.*")])
        if paths:
            for p in paths:
                self.concat_file_list.append(p)
                if hasattr(self, 'concat_listbox'):
                    self.concat_listbox.insert("end", os.path.basename(p))

    def _remove_concat_file(self):
        if not hasattr(self, 'concat_listbox'):
            return
        sel = self.concat_listbox.curselection()
        if sel:
            idx = sel[0]
            self.concat_listbox.delete(idx)
            self.concat_file_list.pop(idx)

    def _move_concat_file(self, direction):
        if not hasattr(self, 'concat_listbox'):
            return
        sel = self.concat_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new_idx = idx + direction
        if 0 <= new_idx < self.concat_listbox.size():
            item = self.concat_listbox.get(idx)
            self.concat_listbox.delete(idx)
            self.concat_listbox.insert(new_idx, item)
            self.concat_listbox.selection_set(new_idx)
            f = self.concat_file_list.pop(idx)
            self.concat_file_list.insert(new_idx, f)

    # ════════════════════════════════════════════════════════════
    #  ★ 智能模型下载管理器 (只下载缺失和损坏的)
    # ════════════════════════════════════════════════════════════

    def _show_model_manager(self):
        """DNN 模型管理窗口 — 智能检测 + 选择性下载"""
        win = tk.Toplevel(self.root)
        win.title("DNN 模型管理 - 下载与更新")
        win.geometry("800x700")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="📥 DNN 模型管理", style="Header.TLabel").pack(padx=10, pady=(10, 5))
        ttk.Label(win, text=f"模型目录: {self.model_manager.models_dir.absolute()}",
                  style="Info.TLabel").pack(padx=10, pady=(0, 5))

        # ── 模型列表 (带复选框) ──
        list_frame = ttk.Frame(win)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("status", "name", "file", "local_size", "min_size", "action")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=18)
        tree.heading("status", text="状态")
        tree.heading("name", text="模型名称")
        tree.heading("file", text="文件名")
        tree.heading("local_size", text="本地大小")
        tree.heading("min_size", text="最小要求")
        tree.heading("action", text="操作")
        tree.column("status", width=50, anchor="center")
        tree.column("name", width=200)
        tree.column("file", width=180)
        tree.column("local_size", width=90, anchor="center")
        tree.column("min_size", width=90, anchor="center")
        tree.column("action", width=80, anchor="center")

        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # 填充数据
        groups = self.model_manager.check_all_models()
        download_vars = {}  # item_id → (BooleanVar, group_key, filename, url)

        for group in groups:
            for fi in group.files:
                status_emoji = {"ok": "✅", "missing": "❌", "corrupted": "⚠️"}.get(fi.status.value, "❓")
                local_str = f"{fi.local_size_kb / 1024:.1f} MB" if fi.local_size_kb > 1024 else \
                            f"{fi.local_size_kb:.0f} KB" if fi.local_size_kb > 0 else "--"
                min_str = f"{fi.min_size_kb / 1024:.1f} MB" if fi.min_size_kb > 1024 else \
                          f"{fi.min_size_kb:.0f} KB" if fi.min_size_kb > 0 else "--"

                if fi.status == ModelFileStatus.MISSING:
                    action = "需下载"
                elif fi.status == ModelFileStatus.CORRUPTED:
                    action = "需重下"
                else:
                    action = "正常"

                item_id = tree.insert("", "end", values=(
                    status_emoji, group.display_name, fi.filename,
                    local_str, min_str, action
                ))

                if fi.status in (ModelFileStatus.MISSING, ModelFileStatus.CORRUPTED):
                    tree.selection_add(item_id)
                    # 获取 alt_urls
                    reg_files = MODEL_REGISTRY.get(group.key, {}).get("files", {})
                    alt_urls = reg_files.get(fi.filename, {}).get("alt_urls", [])
                    download_vars[item_id] = (group.key, fi.filename, fi.url, alt_urls)

        # ── 进度区域 ──
        progress_frame = ttk.LabelFrame(win, text="下载进度")
        progress_frame.pack(fill="x", padx=10, pady=5)
        dl_progress_var = tk.DoubleVar(value=0)
        dl_progress_bar = ttk.Progressbar(progress_frame, variable=dl_progress_var, maximum=100)
        dl_progress_bar.pack(fill="x", padx=10, pady=(5, 2))
        dl_status_label = ttk.Label(progress_frame, text="就绪", style="Info.TLabel", wraplength=700)
        dl_status_label.pack(fill="x", padx=10, pady=(0, 5))

        # ── 按钮区域 ──
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=10, pady=5)

        def open_models_dir():
            p = str(self.model_manager.models_dir.absolute())
            if sys.platform == 'win32':
                os.startfile(p)
            elif sys.platform == 'darwin':
                subprocess.run(['open', p])
            else:
                subprocess.run(['xdg-open', p])

        def download_selected():
            """下载所有选中的 (缺失+损坏) 文件"""
            selected = tree.selection()
            to_download = []
            for item_id in selected:
                if item_id in download_vars:
                    to_download.append(download_vars[item_id])

            if not to_download:
                messagebox.showinfo("提示", "没有需要下载的文件\n所有选中的模型都已完好")
                return

            # 确认
            file_list = "\n".join(f"  • {f[1]}" for f in to_download)
            if not messagebox.askyesno("确认下载",
                f"将下载以下 {len(to_download)} 个文件:\n{file_list}\n\n是否开始?"):
                return

            # 禁用按钮
            for child in btn_frame.winfo_children():
                try:
                    child.configure(state="disabled")
                except Exception:
                    pass

            self.model_manager.reset_cancel()

            def do_download():
                total = len(to_download)
                success_count = 0
                fail_list = []

                for idx, (group_key, filename, url, alt_urls) in enumerate(to_download):
                    if self.model_manager._download_cancel:
                        break

                    dest = self.model_manager.models_dir / filename

                    def progress_cb(pct, msg):
                        overall = (idx + max(0, pct)) / total * 100
                        win.after(0, lambda o=overall, m=msg: (
                            dl_progress_var.set(o), dl_status_label.configure(text=m)))

                    progress_cb(0, f"[{idx + 1}/{total}] 准备下载: {filename}")

                    ok = self.model_manager.download_file(url, dest, progress_cb, alt_urls)
                    if ok:
                        success_count += 1
                    else:
                        fail_list.append(filename)

                # 完成
                def on_done():
                    for child in btn_frame.winfo_children():
                        try:
                            child.configure(state="normal")
                        except Exception:
                            pass

                    if fail_list:
                        dl_status_label.configure(
                            text=f"完成: {success_count}/{total} 成功, "
                                 f"{len(fail_list)} 失败: {', '.join(fail_list)}")
                        messagebox.showwarning("部分失败",
                            f"成功: {success_count}\n"
                            f"失败: {len(fail_list)}\n\n"
                            f"失败文件:\n" + "\n".join(f"  • {f}" for f in fail_list) +
                            f"\n\n请手动下载到:\n{self.model_manager.models_dir.absolute()}")
                    else:
                        dl_status_label.configure(text=f"✅ 全部下载完成! ({success_count} 个文件)")
                        messagebox.showinfo("完成", f"全部 {success_count} 个文件下载成功!")

                    # 刷新列表
                    refresh()

                win.after(0, on_done)

            threading.Thread(target=do_download, daemon=True).start()

        def cancel_download():
            self.model_manager.cancel_download()
            dl_status_label.configure(text="正在取消...")

        def download_all_missing():
            """一键下载所有缺失和损坏的"""
            # 选中所有需要下载的
            tree.selection_set()
            for item_id in download_vars:
                tree.selection_add(item_id)
            download_selected()

        def refresh():
            """刷新状态"""
            tree.delete(*tree.get_children())
            download_vars.clear()
            new_groups = self.model_manager.check_all_models()
            for group in new_groups:
                for fi in group.files:
                    status_emoji = {"ok": "✅", "missing": "❌", "corrupted": "⚠️"}.get(fi.status.value, "❓")
                    local_str = f"{fi.local_size_kb / 1024:.1f} MB" if fi.local_size_kb > 1024 else \
                                f"{fi.local_size_kb:.0f} KB" if fi.local_size_kb > 0 else "--"
                    min_str = f"{fi.min_size_kb / 1024:.1f} MB" if fi.min_size_kb > 1024 else \
                              f"{fi.min_size_kb:.0f} KB" if fi.min_size_kb > 0 else "--"
                    action = {"missing": "需下载", "corrupted": "需重下"}.get(fi.status.value, "正常")
                    item_id = tree.insert("", "end", values=(
                        status_emoji, group.display_name, fi.filename,
                        local_str, min_str, action))
                    if fi.status in (ModelFileStatus.MISSING, ModelFileStatus.CORRUPTED):
                        tree.selection_add(item_id)
                        reg_files = MODEL_REGISTRY.get(group.key, {}).get("files", {})
                        alt_urls = reg_files.get(fi.filename, {}).get("alt_urls", [])
                        download_vars[item_id] = (group.key, fi.filename, fi.url, alt_urls)

        ttk.Button(btn_frame, text="📥 下载选中的缺失/损坏文件",
                   command=download_selected, style="Accent.TButton").pack(side="left", padx=5)
        ttk.Button(btn_frame, text="📥 一键下载全部缺失",
                   command=download_all_missing).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="⏹ 取消下载",
                   command=cancel_download).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="🔄 刷新",
                   command=refresh).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="📁 打开目录",
                   command=open_models_dir).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="关闭",
                   command=win.destroy).pack(side="right", padx=5)

        # 统计
        ok_count = sum(1 for g in groups for f in g.files if f.status == ModelFileStatus.OK)
        miss_count = sum(1 for g in groups for f in g.files if f.status == ModelFileStatus.MISSING)
        bad_count = sum(1 for g in groups for f in g.files if f.status == ModelFileStatus.CORRUPTED)
        total_count = sum(len(g.files) for g in groups)
        ttk.Label(win,
                  text=f"📊 统计: {ok_count} 正常 / {miss_count} 缺失 / {bad_count} 损坏 / {total_count} 总计",
                  style="Info.TLabel").pack(padx=10, pady=(0, 5))

    def _show_about(self):
        dnd = {"tkinterdnd2": "✅ tkinterdnd2", "windnd": "✅ windnd"}.get(
            DND_BACKEND, "❌ pip install tkinterdnd2")
        about_text = f"""{APP_NAME} v{APP_VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python GUI OpenCV 视频处理全家桶

集成 OpenCV DNN 模块，支持:
• 30+ 种视频处理功能
• 人脸/物体检测、风格迁移
• ★ 去马赛克/超分重建 (DeepMosaics / Real-ESRGAN)
• 文字检测、背景虚化
• 智能模型下载管理器
• GIF 导出 (三级回退)
• 流程组合
• 批处理队列 / 参数预设 / 处理日志
• H.264 / H.265 输出 + 码率控制 + 保留音频

环境:
• Python {sys.version.split()[0]}
• OpenCV {cv2.__version__}
• NumPy {np.__version__}
• Pillow {'✅' if HAS_PIL else '❌ pip install Pillow'}
• SciPy {'✅' if HAS_SCIPY else '❌'}
• FFmpeg {'✅' if ffmpeg_available() else '❌ 未安装或不在 PATH'}
• onnxruntime {'✅' if HAS_ORT else '❌'}
• 文件拖拽 {dnd}

日志目录: {LOG_DIR.absolute()}
预设目录: {PRESET_DIR.absolute()}
"""
        messagebox.showinfo("关于", about_text)

    def run(self):
        self.root.mainloop()


# ════════════════════════════════════════════════════════════════
#  程序入口
# ════════════════════════════════════════════════════════════════

def main():
    os.makedirs("models", exist_ok=True)
    if not HAS_PIL:
        print("=" * 50)
        print("提示: 建议安装 Pillow 以获得更好的体验")
        print("  pip install Pillow")
        print("=" * 50)
    if DND_BACKEND is None:
        print("提示: 未安装拖拽支持，拖入文件功能不可用")
        print("  pip install tkinterdnd2")
    try:
        app = MainWindow()
        app.run()
    except Exception as e:
        LOGGER.error(f"程序异常退出: {e}", exc=True)
        raise
    finally:
        LOGGER.close()


if __name__ == "__main__":
    main()