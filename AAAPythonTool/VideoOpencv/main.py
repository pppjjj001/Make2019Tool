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
import struct
import traceback

try:
    from scipy.signal import savgol_filter
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

try:
    from PIL import Image as PILImage, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


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
}

ANALYSIS_TASKS = {
    ProcessingTask.BRIGHTNESS_CURVE,
    ProcessingTask.COLOR_HISTOGRAM,
    ProcessingTask.MOTION_HEATMAP,
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

    concat_files: List[str] = field(default_factory=list)

    gif_fps: int = 10
    gif_scale: float = 0.5
    gif_max_colors: int = 256

    extract_interval: float = 1.0
    extract_format: str = "jpg"

    pipeline_tasks: List[ProcessingTask] = field(default_factory=list)


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
            print(f"PIL GIF 保存失败: {e}")
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
            print(f"原始 GIF 编码失败: {e}")
            traceback.print_exc()
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
#  DNN 引擎
# ════════════════════════════════════════════════════════════════
# 尝试导入 onnxruntime（去马赛克核心依赖）
try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

class DNNEngine:
    """OpenCV DNN 模块管理器"""

    def __init__(self, models_dir: str = "models"):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(exist_ok=True)
        self._nets: Dict[str, cv2.dnn.Net] = {}
        self._ort_sessions: Dict[str, Any] = {}  # ★ 加上这一行
        self._coco_classes: List[str] = COCO_CLASSES
        self._coco_colors: Optional[np.ndarray] = None
        self._load_errors: Dict[str, str] = {}

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
                    conf_threshold: float = 0.5) -> List[np.ndarray]:
        net = self._nets.get("east")
        if net is None:
            return []
        orig_h, orig_w = frame.shape[:2]
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

        key = f"demosaic_{model_name}"

        # 已加载则跳过
        if key in self._ort_sessions or key in self._nets:
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
                        "  pip install onnxruntime\n"
                        "或选择 'traditional' 传统方法"
                    )
                    return False

                # 创建 onnxruntime session
                providers = ['CPUExecutionProvider']
                # 如果有 GPU 支持
                if 'CUDAExecutionProvider' in ort.get_available_providers():
                    providers.insert(0, 'CUDAExecutionProvider')

                session = ort.InferenceSession(str(model_path), providers=providers)

                # 验证模型可用性
                input_info = session.get_inputs()[0]
                print(f"[去马赛克] 模型加载成功: {filename}")
                print(f"  输入名: {input_info.name}")
                print(f"  输入形状: {input_info.shape}")
                print(f"  输入类型: {input_info.type}")

                self._ort_sessions[key] = session
                self._load_errors.pop(key, None)
                return True

            elif filename.endswith('.pb'):
                # ESPCN 可以用 cv2.dnn
                net = cv2.dnn.readNetFromTensorflow(str(model_path))
                net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
                net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
                self._nets[key] = net
                self._load_errors.pop(key, None)
                return True

        except Exception as e:
            self._load_errors[key] = f"加载模型失败: {e}\n{traceback.format_exc()}"
            return False

    def apply_demosaic(self, frame: np.ndarray,
                       model_name: str = "real_esrgan_x4",
                       region: Tuple[int, int, int, int] = (0, 0, 0, 0),
                       full_frame: bool = True,
                       tile_size: int = 128) -> np.ndarray:
        """
        去马赛克 / 超分辨率重建 — 主入口
        
        处理流程:
        1. 确定处理区域 (全画面 or 局部)
        2. 选择推理方法 (ESRGAN / ESPCN / 传统)
        3. 分块推理 (防止 OOM)
        4. 拼接结果
        """
        h, w = frame.shape[:2]

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

    def _enhance_image(self, img: np.ndarray,
                       model_name: str,
                       tile_size: int) -> np.ndarray:
        """
        对图像进行增强处理，自动选择最佳方法
        输出尺寸与输入相同
        """
        key = f"demosaic_{model_name}"

        # 方法1: ONNX Runtime (Real-ESRGAN)
        if key in self._ort_sessions:
            return self._enhance_with_esrgan(img, self._ort_sessions[key], tile_size)

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
        分块处理以防止内存溢出
        """
        h, w = img.shape[:2]
        scale = 4  # Real-ESRGAN 是 4x 放大

        # ★ 对于视频帧，先缩小再超分可以获得更好的效果
        # 因为超分后会放大4倍，我们需要缩放回原尺寸
        # 策略：直接对原图超分，然后缩放回原尺寸

        # 如果图片很大，使用分块处理
        if h > tile_size or w > tile_size:
            enhanced = self._tiled_esrgan_inference(img, session, tile_size, scale)
        else:
            enhanced = self._single_esrgan_inference(img, session)

        # 缩放回原始尺寸
        if enhanced.shape[0] != h or enhanced.shape[1] != w:
            enhanced = cv2.resize(enhanced, (w, h), interpolation=cv2.INTER_LANCZOS4)

        return enhanced

    def _single_esrgan_inference(self, img: np.ndarray,
                                  session: 'ort.InferenceSession') -> np.ndarray:
        """单次 ESRGAN 推理"""
        # 预处理: BGR → RGB, uint8 → float32 [0,1], HWC → NCHW
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_float = img_rgb.astype(np.float32) / 255.0
        input_tensor = np.transpose(img_float, (2, 0, 1))  # HWC → CHW
        input_tensor = np.expand_dims(input_tensor, 0)       # CHW → NCHW

        # 推理
        input_name = session.get_inputs()[0].name
        output_name = session.get_outputs()[0].name
        result = session.run([output_name], {input_name: input_tensor})[0]

        # 后处理: NCHW → HWC, float32 → uint8, RGB → BGR
        output = result.squeeze(0)                    # NCHW → CHW
        output = np.transpose(output, (1, 2, 0))     # CHW → HWC
        output = np.clip(output * 255.0, 0, 255).astype(np.uint8)
        output_bgr = cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

        return output_bgr

    def _tiled_esrgan_inference(self, img: np.ndarray,
                                 session: 'ort.InferenceSession',
                                 tile_size: int = 128,
                                 scale: int = 4) -> np.ndarray:
        """
        分块 ESRGAN 推理
        使用重叠区域 + 线性混合避免接缝
        """
        h, w = img.shape[:2]
        overlap = 16  # 重叠像素
        out_h, out_w = h * scale, w * scale

        # 输出缓冲
        output = np.zeros((out_h, out_w, 3), dtype=np.float64)
        weight = np.zeros((out_h, out_w, 1), dtype=np.float64)

        # 创建混合权重 (边缘渐变)
        def make_weight_map(th, tw, border=16):
            """创建中心权重高、边缘权重低的权重图"""
            wmap = np.ones((th, tw), dtype=np.float64)
            for i in range(min(border, th // 2)):
                f = (i + 1) / border
                wmap[i, :] *= f
                wmap[th - 1 - i, :] *= f
            for j in range(min(border, tw // 2)):
                f = (j + 1) / border
                wmap[:, j] *= f
                wmap[:, tw - 1 - j] *= f
            return wmap[:, :, np.newaxis]

        step = tile_size - overlap

        for y in range(0, h, step):
            for x in range(0, w, step):
                # 计算块范围
                ty = min(y, max(0, h - tile_size))
                tx = min(x, max(0, w - tile_size))
                th = min(tile_size, h - ty)
                tw = min(tile_size, w - tx)

                tile = img[ty:ty + th, tx:tx + tw].copy()

                try:
                    enhanced_tile = self._single_esrgan_inference(tile,session)
                except Exception as e:
                    print(f"[去马赛克] 分块推理失败 ({tx},{ty}): {e}")
                    # 失败时用双三次插值
                    enhanced_tile = cv2.resize(tile, (tw * scale, th * scale),
                                               interpolation=cv2.INTER_CUBIC)

                # 输出坐标
                out_ty, out_tx = ty * scale, tx * scale
                enh_h, enh_w = enhanced_tile.shape[:2]
                out_th = min(enh_h, out_h - out_ty)
                out_tw = min(enh_w, out_w - out_tx)

                if out_th <= 0 or out_tw <= 0:
                    continue

                # 权重混合
                wmap = make_weight_map(out_th, out_tw, border=overlap * scale // 2)
                output[out_ty:out_ty + out_th, out_tx:out_tx + out_tw] += \
                    enhanced_tile[:out_th, :out_tw].astype(np.float64) * wmap
                weight[out_ty:out_ty + out_th, out_tx:out_tx + out_tw] += wmap

        # 归一化
        weight = np.maximum(weight, 1e-6)
        output = output / weight
        return np.clip(output, 0, 255).astype(np.uint8)

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
            print(f"[ESPCN] 推理失败: {e}")
            return self._enhance_traditional(img)

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
            hForColorComponents=6,  # 色彩去噪强度
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
#  视频处理引擎
# ════════════════════════════════════════════════════════════════

class VideoEngine:
    """核心视频处理引擎"""

    def __init__(self):
        self.dnn = DNNEngine()
        self.filter = FilterEngine()
        self._cancel = False
        self._progress_callback: Optional[Callable[[float, str], None]] = None
        self._style_reference_img: Optional[np.ndarray] = None

    def set_progress_callback(self, callback: Callable[[float, str], None]):
        self._progress_callback = callback

    def cancel(self):
        self._cancel = True

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

    def _create_writer(self, output_path: str, fps: float, width: int,
                       height: int) -> cv2.VideoWriter:
        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".avi":
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
        elif ext == ".mov":
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        else:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        return cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    def process_video(self, params: ProcessingParams) -> bool:
        """通用视频处理流水线"""
        self._cancel = False

        if params.style_reference_path and os.path.exists(params.style_reference_path):
            self._style_reference_img = cv2.imread(params.style_reference_path)
        else:
            self._style_reference_img = None

        # ═══ 修正输出路径 ═══
        params.output_path = self._fix_output_path(params)

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
        writer = self._create_writer(params.output_path, out_fps, out_w, out_h)
        if not writer.isOpened():
            cap.release()
            self._report_progress(-1, f"无法创建输出文件: {params.output_path}")
            return False

        # 初始化 DNN
        if not self._init_dnn_for_task(params):
            cap.release()
            writer.release()
            return False

        if params.task == ProcessingTask.PIPELINE:
            for pt in params.pipeline_tasks:
                sub_params = ProcessingParams(task=pt)
                sub_params.style_model_name = params.style_model_name
                sub_params.demosaic_model = params.demosaic_model
                if not self._init_dnn_for_task(sub_params):
                    cap.release()
                    writer.release()
                    return False

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        processed = 0
        total_to_process = end_frame - start_frame

        while not self._cancel:
            ret, frame = cap.read()
            if not ret:
                break
            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            if current_frame > end_frame:
                break

            if params.task == ProcessingTask.PIPELINE:
                processed_frame = self._process_frame_pipeline(frame, params)
            else:
                processed_frame = self._process_frame(frame, params)

            if processed_frame.shape[1] != out_w or processed_frame.shape[0] != out_h:
                processed_frame = cv2.resize(processed_frame, (out_w, out_h))
            if len(processed_frame.shape) == 2:
                processed_frame = cv2.cvtColor(processed_frame, cv2.COLOR_GRAY2BGR)

            writer.write(processed_frame)
            processed += 1

            if total_to_process > 0:
                progress = processed / total_to_process
                self._report_progress(progress,
                    f"处理中: {processed}/{total_to_process} 帧 ({progress * 100:.1f}%)")

        cap.release()
        writer.release()

        if self._cancel:
            self._report_progress(-1, "已取消")
            if os.path.exists(params.output_path):
                os.remove(params.output_path)
            return False

        self._report_progress(1.0, "处理完成!")
        return True

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

    def _init_dnn_for_task(self, params: ProcessingParams) -> bool:
        task = params.task
        if task in (ProcessingTask.FACE_DETECT, ProcessingTask.FACE_MOSAIC, ProcessingTask.BG_BLUR):
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
            # 尝试加载 DNN 模型，失败则使用传统方法
            model_loaded = self.dnn.load_demosaic_model(params.demosaic_model)
            if not model_loaded:
                self._report_progress(0, "DNN 去马赛克模型未找到，将使用传统增强方法")
                # 不 return False —— 允许回退到传统方法
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

        return frame

    def _process_frame_pipeline(self, frame: np.ndarray,
                                params: ProcessingParams) -> np.ndarray:
        result = frame.copy()
        for task in params.pipeline_tasks:
            sub_params = ProcessingParams(
                task=task,
                input_path=params.input_path,
                target_width=params.target_width,
                target_height=params.target_height,
                keep_aspect=params.keep_aspect,
                interpolation=params.interpolation,
                rotation=params.rotation,
                flip_h=params.flip_h,
                flip_v=params.flip_v,
                brightness=params.brightness,
                contrast=params.contrast,
                saturation=params.saturation,
                gamma=params.gamma,
                color_space=params.color_space,
                blur_type=params.blur_type,
                blur_ksize=params.blur_ksize,
                sharpen_strength=params.sharpen_strength,
                denoise_strength=params.denoise_strength,
                edge_type=params.edge_type,
                canny_low=params.canny_low,
                canny_high=params.canny_high,
                tone_type=params.tone_type,
                mosaic_size=params.mosaic_size,
                mosaic_region=params.mosaic_region,
                dnn_confidence=params.dnn_confidence,
                dnn_nms_threshold=params.dnn_nms_threshold,
                style_model_name=params.style_model_name,
                style_reference_path=params.style_reference_path,
                style_strength=params.style_strength,
                demosaic_model=params.demosaic_model,
                demosaic_region=params.demosaic_region,
                demosaic_full=params.demosaic_full,
                demosaic_tile_size=params.demosaic_tile_size,
            )
            result = self._process_frame(result, sub_params)
        return result

    def _background_blur(self, frame: np.ndarray, params: ProcessingParams) -> np.ndarray:
        faces = self.dnn.detect_faces(frame, params.dnn_confidence)
        if not faces:
            return frame
        h, w = frame.shape[:2]
        mask = np.zeros((h, w), dtype=np.uint8)
        for (fx, fy, fw, fh, _) in faces:
            cx = fx + fw // 2
            body_w = int(fw * 2.5)
            body_h = int(fh * 5)
            bx = max(0, cx - body_w // 2)
            by = max(0, fy - int(fh * 0.3))
            bw = min(w - bx, body_w)
            bh = min(h - by, body_h)
            cv2.ellipse(mask, (bx + bw // 2, by + bh // 2), (bw // 2, bh // 2), 0, 0, 360, 255, -1)
        mask = cv2.GaussianBlur(mask, (51, 51), 0)
        mask_f = mask.astype(np.float32) / 255.0
        blurred = cv2.GaussianBlur(frame, (51, 51), 0)
        result = np.zeros_like(frame, dtype=np.float32)
        for c in range(3):
            result[:, :, c] = frame[:, :, c] * mask_f + blurred[:, :, c] * (1 - mask_f)
        return result.astype(np.uint8)

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
                subprocess.run(cmd, check=True, capture_output=True, timeout=300)
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
        writer = self._create_writer(params.output_path, first_info.fps,
                                     first_info.width, first_info.height)
        if not writer.isOpened():
            self._report_progress(-1, "无法创建输出文件")
            return False
        total_frames = sum(
            (self.get_video_info(f).frame_count if self.get_video_info(f) else 0) for f in files)
        processed = 0
        for idx, file_path in enumerate(files):
            if self._cancel:
                break
            cap = cv2.VideoCapture(file_path)
            while not self._cancel:
                ret, frame = cap.read()
                if not ret:
                    break
                if frame.shape[1] != first_info.width or frame.shape[0] != first_info.height:
                    frame = cv2.resize(frame, (first_info.width, first_info.height))
                writer.write(frame)
                processed += 1
                if processed % 30 == 0:
                    self._report_progress(processed / max(1, total_frames),
                        f"视频 {idx + 1}/{len(files)}: {processed} 帧")
            cap.release()
        writer.release()
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
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

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

        self._init_dnn_for_task(params)

        if params.task == ProcessingTask.PIPELINE:
            for pt in params.pipeline_tasks:
                sub_p = ProcessingParams(task=pt, style_model_name=params.style_model_name,
                                         demosaic_model=params.demosaic_model)
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
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("1400x900")
        self.root.minsize(1100, 700)

        self.engine = VideoEngine()
        self.model_manager = ModelManager(self.engine.dnn.models_dir)
        self.current_video_info: Optional[VideoInfo] = None
        self.processing_thread: Optional[threading.Thread] = None
        self.is_processing = False
        self.msg_queue = queue.Queue()

        self._setup_styles()
        self._build_ui()
        self._poll_messages()

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
        ttk.Button(toolbar, text="📂 打开视频", command=self._open_video).pack(side="left", padx=2)
        ttk.Button(toolbar, text="📂 批量添加", command=self._add_batch_files).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        ttk.Button(toolbar, text="👁 预览效果", command=self._preview).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
        self.btn_process = ttk.Button(toolbar, text="▶ 开始处理",
                                      command=self._start_processing, style="Accent.TButton")
        self.btn_process.pack(side="left", padx=2)
        self.btn_cancel = ttk.Button(toolbar, text="⏹ 取消", command=self._cancel_processing, state="disabled")
        self.btn_cancel.pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)
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
        ttk.Entry(search_frame, textvariable=self.search_var, font=("Microsoft YaHei", 10)).pack(fill="x")

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

        categories = {
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
            "🤖 DNN AI 功能": [
                ("人脸检测", ProcessingTask.FACE_DETECT),
                ("物体检测 (YOLO)", ProcessingTask.OBJECT_DETECT),
                ("风格迁移 (模型)", ProcessingTask.STYLE_TRANSFER),
                ("风格迁移 (参考图)", ProcessingTask.STYLE_REFERENCE),
                ("人脸马赛克", ProcessingTask.FACE_MOSAIC),
                ("背景虚化", ProcessingTask.BG_BLUR),
                ("文字检测 (EAST)", ProcessingTask.TEXT_DETECT),
                ("去马赛克/超分重建", ProcessingTask.DEMOSAIC),  # ★ 新增
            ],
            "📊 分析工具": [
                ("亮度曲线分析", ProcessingTask.BRIGHTNESS_CURVE),
                ("颜色直方图", ProcessingTask.COLOR_HISTOGRAM),
                ("运动热力图", ProcessingTask.MOTION_HEATMAP),
            ],
            "🔗 高级功能": [
                ("流程组合 (多步串联)", ProcessingTask.PIPELINE),
            ],
        }

        for cat_name, functions in categories.items():
            cat_id = self.func_tree.insert("", "end", text=cat_name, open=True)
            for func_name, task in functions:
                item_id = self.func_tree.insert(cat_id, "end", text=func_name)
                self._function_map[item_id] = task
                self._function_names[item_id] = func_name

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
        self.current_params_widgets = []
        self._current_task = None

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

        # ★ 去马赛克参数
        self.var_demosaic_model = tk.StringVar(value="real_esrgan_x4")
        self.var_demosaic_full = tk.BooleanVar(value=True)
        self.var_demosaic_tile = tk.IntVar(value=128)

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

    def _filter_functions(self, *args):
        pass  # 搜索功能可后续实现

    def _on_function_select(self, event):
        selected = self.func_tree.selection()
        if not selected:
            return
        task = self._function_map.get(selected[0])
        if task is None:
            return
        self._current_task = task
        self._build_task_params(task)

        if task in ANALYSIS_TASKS:
            self.output_hint_label.configure(text="📊 分析任务：输出将自动保存为 .png 图片")
            self._auto_fix_output_extension('.png')
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
                if ext.lower() in ('.png', '.jpg', '.gif', '.bmp'):
                    self._auto_fix_output_extension('.mp4')

        if self.current_video_info:
            try:
                self._preview()
            except Exception as e:
                print(f"预览失败: {e}")

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
            ProcessingTask.PIPELINE: self._build_pipeline_params,
        }

        if task in builders:
            builders[task](frame)
        elif task in (ProcessingTask.FACE_DETECT, ProcessingTask.FACE_MOSAIC,
                      ProcessingTask.BG_BLUR, ProcessingTask.TEXT_DETECT):
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

    # ★ 新增: 去马赛克参数面板
    def _build_demosaic_params(self, parent):
        ttk.Label(parent, text="🔍 去马赛克 / 超分辨率重建\n"
                                "利用 AI 或传统方法恢复马赛克区域细节",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(5, 5))

        ttk.Label(parent, text="处理模型:").pack(anchor="w", padx=10, pady=(5, 0))
        models_info = {
            "real_esrgan_x4": ("Real-ESRGAN x4 (通用, 最佳质量)", "realesrgan-x4plus.onnx"),
            "real_esrgan_anime": ("Real-ESRGAN Anime (动漫专用)", "realesrgan-animevideov3.onnx"),
            "espcn_x4": ("ESPCN x4 (轻量快速)", "ESPCN_x4.pb"),
            "traditional": ("传统方法 (无需模型)", None),
        }
        for key, (label, filename) in models_info.items():
            if filename:
                fpath = self.engine.dnn.models_dir / filename
                if fpath.exists():
                    size_mb = fpath.stat().st_size / 1024 / 1024
                    status = f"✅ ({size_mb:.1f}MB)"
                else:
                    status = "❌ 未下载"
            else:
                status = "✅ 始终可用"
            ttk.Radiobutton(parent, text=f"{status} {label}",
                            variable=self.var_demosaic_model, value=key).pack(anchor="w", padx=20)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)

        ttk.Checkbutton(parent, text="全画面处理", variable=self.var_demosaic_full).pack(
            anchor="w", padx=10, pady=2)
        ttk.Label(parent, text="💡 取消勾选可设置局部区域\n目前局部区域需在代码中指定坐标",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=2)

        ttk.Label(parent, text="分块大小 (px):").pack(anchor="w", padx=10, pady=(5, 0))
        tf = ttk.Frame(parent)
        tf.pack(fill="x", padx=10, pady=2)
        ttk.Scale(tf, from_=64, to=512, variable=self.var_demosaic_tile, orient="horizontal").pack(
            side="left", fill="x", expand=True)
        ttk.Label(tf, textvariable=self.var_demosaic_tile, width=5).pack(side="right")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)

        ttk.Label(parent, text="⚠️ 注意事项:\n"
                                "• Real-ESRGAN 需要下载 ONNX 模型 (~64MB)\n"
                                "• 处理速度较慢，建议先短片段测试\n"
                                "• 若无 DNN 模型，自动回退传统方法\n"
                                "• 传统方法使用双三次插值+锐化+去噪\n"
                                "• 效果: ESRGAN > ESPCN > 传统方法\n\n"
                                "去马赛克原理:\n"
                                "马赛克本质是信息丢失，AI 模型通过\n"
                                "学习大量图像来「猜测」丢失的细节。\n"
                                "完全恢复原图是不可能的，但可以显著\n"
                                "提升视觉效果。",
                  style="Info.TLabel", wraplength=250, justify="left").pack(padx=10, pady=5)
    # ★ 替换 MainWindow 类中的 _build_demosaic_params 方法
    def _build_demosaic_params(self, parent):
        ttk.Label(parent, text="🔍 去马赛克 / 超分辨率重建",
                  style="Header.TLabel").pack(padx=10, pady=(5, 2))

        ttk.Label(parent, text="利用 AI 或传统方法恢复马赛克区域细节",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=(0, 5))

        # ── 模型选择 ──
        ttk.Label(parent, text="处理模型:").pack(anchor="w", padx=10, pady=(5, 0))

        models_info = {
            "real_esrgan_x4": {
                "label": "Real-ESRGAN x4 (通用, 最佳质量)",
                "filename": "realesrgan-x4plus.onnx",
                "needs_ort": True,
            },
            "real_esrgan_anime": {
                "label": "Real-ESRGAN Anime (动漫专用)",
                "filename": "realesrgan-animevideov3.onnx",
                "needs_ort": True,
            },
            "espcn_x4": {
                "label": "ESPCN x4 (轻量快速)",
                "filename": "ESPCN_x4.pb",
                "needs_ort": False,
            },
            "traditional": {
                "label": "传统方法 (无需模型, 效果有限)",
                "filename": None,
                "needs_ort": False,
            },
        }

        for key, info in models_info.items():
            filename = info["filename"]
            needs_ort = info["needs_ort"]

            if filename:
                fpath = self.engine.dnn.models_dir / filename
                if fpath.exists():
                    size_mb = fpath.stat().st_size / 1024 / 1024
                    if needs_ort and not HAS_ORT:
                        status = f"⚠️ ({size_mb:.1f}MB, 需 onnxruntime)"
                    else:
                        status = f"✅ ({size_mb:.1f}MB)"
                else:
                    status = "❌ 未下载"
            else:
                status = "✅ 始终可用"

            ttk.Radiobutton(parent, text=f"{status} {info['label']}",
                            variable=self.var_demosaic_model, value=key).pack(anchor="w", padx=20)

        # ── onnxruntime 状态提示 ──
        ort_frame = ttk.Frame(parent)
        ort_frame.pack(fill="x", padx=10, pady=5)
        if HAS_ORT:
            ort_text = f"✅ onnxruntime 已安装 (v{ort.__version__})"
            providers = ort.get_available_providers()
            if 'CUDAExecutionProvider' in providers:
                ort_text += " [GPU加速可用]"
            else:
                ort_text += " [CPU模式]"
        else:
            ort_text = ("❌ onnxruntime 未安装\n"
                       "  Real-ESRGAN 需要它才能运行\n"
                       "  安装: pip install onnxruntime\n"
                       "  GPU版: pip install onnxruntime-gpu")
        ttk.Label(ort_frame, text=ort_text, style="Info.TLabel",
                  wraplength=250, justify="left").pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # ── 处理区域 ──
        ttk.Checkbutton(parent, text="全画面处理", variable=self.var_demosaic_full).pack(
            anchor="w", padx=10, pady=2)
        ttk.Label(parent, text="💡 取消勾选可处理局部区域\n(需在参数中指定坐标)",
                  style="Info.TLabel", wraplength=250).pack(padx=10, pady=2)

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
            "🥇 Real-ESRGAN x4 (推荐)\n"
            "  效果最好，适合真实照片/视频\n"
            "  需要: ONNX模型(~64MB) + onnxruntime\n"
            "  速度: 较慢 (CPU ~2-5秒/帧)\n\n"
            "🥈 Real-ESRGAN Anime\n"
            "  动漫/插画专用，色彩更鲜艳\n"
            "  需要: ONNX模型(~17MB) + onnxruntime\n\n"
            "🥉 ESPCN x4\n"
            "  轻量级，速度快\n"
            "  只需: PB模型(~50KB), 不需 onnxruntime\n"
            "  效果一般，适合实时处理\n\n"
            "📦 传统方法\n"
            "  不需要任何模型文件\n"
            "  使用: 双边滤波+超采样+去噪+锐化\n"
            "  效果有限，但总是可用\n\n"
            "⚠️ 重要提醒:\n"
            "  马赛克本质是信息丢失\n"
            "  AI 只能「猜测」丢失的细节\n"
            "  无法 100% 恢复原图"
        )
        ttk.Label(parent, text=help_text, style="Info.TLabel",
                  wraplength=250, justify="left").pack(padx=10, pady=5)
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
        ffmpeg_s = "FFmpeg ✅" if VideoEngine._has_ffmpeg() else "FFmpeg ❌"
        ort_s = f"ORT ✅" if HAS_ORT else "ORT ❌"
        self.statusbar = ttk.Label(status_frame,
            text=f"就绪 | OpenCV {cv2.__version__} | {pil_s} | {ffmpeg_s} | {ort_s}",
            style="Info.TLabel")
        self.statusbar.pack(side="left")
        available = self.engine.dnn.get_available_models()
        dnn_count = sum(1 for v in available.values() if v)
        ttk.Label(status_frame, text=f"DNN模型: {dnn_count}/{len(available)} 可用",
                  style="Info.TLabel").pack(side="right")

    # ════════════════════════════════════════════════════════════
    #  操作逻辑
    # ════════════════════════════════════════════════════════════

    def _open_video(self):
        path = filedialog.askopenfilename(title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"), ("所有文件", "*.*")])
        if not path:
            return
        info = VideoEngine.get_video_info(path)
        if not info:
            messagebox.showerror("错误", f"无法读取视频:\n{path}")
            return
        self.current_video_info = info
        self._update_info_display(info)
        self.preview_slider.configure(to=info.duration)
        name, ext = os.path.splitext(os.path.basename(path))
        out_dir = os.path.dirname(path)
        if self._current_task in ANALYSIS_TASKS:
            out_ext = '.png'
        elif self._current_task == ProcessingTask.TO_GIF:
            out_ext = '.gif'
        else:
            out_ext = ext if ext else '.mp4'
        self.var_output_path.set(os.path.join(out_dir, f"{name}_output{out_ext}"))
        self.root.after(200, lambda: self._show_preview_at(0.0))

    def _add_batch_files(self):
        paths = filedialog.askopenfilenames(title="选择视频文件",
            filetypes=[("视频文件", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"), ("所有文件", "*.*")])
        if paths:
            for p in paths:
                self.concat_file_list.append(p)
                if hasattr(self, 'concat_listbox'):
                    self.concat_listbox.insert("end", os.path.basename(p))

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
            traceback.print_exc()

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

        # ★ 去马赛克参数
        params.demosaic_model = self.var_demosaic_model.get()
        params.demosaic_full = self.var_demosaic_full.get()
        params.demosaic_tile_size = self.var_demosaic_tile.get()

        # 流程组合
        if params.task == ProcessingTask.PIPELINE:
            ordered = [
                ProcessingTask.RESIZE, ProcessingTask.ROTATE,
                ProcessingTask.BRIGHTNESS_CONTRAST, ProcessingTask.COLOR_SPACE,
                ProcessingTask.HISTOGRAM_EQ, ProcessingTask.SHARPEN_BLUR,
                ProcessingTask.SKETCH, ProcessingTask.CARTOON, ProcessingTask.EMBOSS,
                ProcessingTask.EDGE_DETECT, ProcessingTask.COLOR_TONE,
                ProcessingTask.MOSAIC, ProcessingTask.VIGNETTE,
                ProcessingTask.FACE_DETECT, ProcessingTask.OBJECT_DETECT,
                ProcessingTask.STYLE_TRANSFER, ProcessingTask.STYLE_REFERENCE,
                ProcessingTask.FACE_MOSAIC, ProcessingTask.BG_BLUR,
                ProcessingTask.TEXT_DETECT, ProcessingTask.DEMOSAIC,
            ]
            params.pipeline_tasks = [t for t in ordered
                                     if t in self.pipeline_vars and self.pipeline_vars[t].get()]
        return params

    def _start_processing(self):
        if self.is_processing:
            messagebox.showwarning("提示", "正在处理中，请等待...")
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

        self.is_processing = True
        self.btn_process.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_var.set(0)

        self.engine.set_progress_callback(lambda p, m: self.msg_queue.put(("progress", p, m)))

        def run():
            try:
                success = self.engine.process_video(params)
                self.msg_queue.put(("done", success, ""))
            except Exception as e:
                self.msg_queue.put(("error", False, str(e)))
                traceback.print_exc()

        self.processing_thread = threading.Thread(target=run, daemon=True)
        self.processing_thread.start()

    def _cancel_processing(self):
        self.engine.cancel()

    def _poll_messages(self):
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                if msg[0] == "progress":
                    _, progress, message = msg
                    if progress >= 0:
                        self.progress_var.set(progress * 100)
                    self.progress_label.configure(text=message)
                elif msg[0] == "done":
                    _, success, _ = msg
                    self.is_processing = False
                    self.btn_process.configure(state="normal")
                    self.btn_cancel.configure(state="disabled")
                    if success:
                        self.progress_var.set(100)
                        params_tmp = self._build_processing_params()
                        actual = VideoEngine._fix_output_path(params_tmp)
                        messagebox.showinfo("完成", f"处理完成!\n输出: {actual}")
                    else:
                        self.progress_label.configure(text="处理失败或已取消")
                elif msg[0] == "error":
                    _, _, err = msg
                    self.is_processing = False
                    self.btn_process.configure(state="normal")
                    self.btn_cancel.configure(state="disabled")
                    messagebox.showerror("错误", f"处理出错:\n{err}")
        except queue.Empty:
            pass
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
        about_text = f"""{APP_NAME} v{APP_VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Python GUI OpenCV 视频处理全家桶

集成 OpenCV DNN 模块，支持:
• 30+ 种视频处理功能
• 人脸/物体检测、风格迁移
• ★ 去马赛克/超分重建 (Real-ESRGAN)
• 文字检测、背景虚化
• 智能模型下载管理器
• GIF 导出 (三级回退)
• 流程组合

环境:
• Python {sys.version.split()[0]}
• OpenCV {cv2.__version__}
• NumPy {np.__version__}
• Pillow {'✅' if HAS_PIL else '❌ pip install Pillow'}
• SciPy {'✅' if HAS_SCIPY else '❌'}
• FFmpeg {'✅' if VideoEngine._has_ffmpeg() else '❌'}
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
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()