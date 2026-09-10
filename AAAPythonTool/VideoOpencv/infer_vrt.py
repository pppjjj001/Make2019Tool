#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRT / Torch .pth 推理子进程。

本文件只应被单独的 Python 进程启动（窗口里选的解释器），
主程序和 vrt_window.py 都不要 import 它，以免把 torch 拉进 GUI 进程。

协议（stdout，一行一条，前缀 #VT ）:
  #VT PROBE {json}
  #VT STATUS <text>
  #VT LOG <text>
  #VT PROGRESS <0-1>
  #VT FRAME <i> <n>
  #VT DONE <output_path>
  #VT ERROR <text>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any, List, Optional, Sequence, Tuple

# 官方 VRT 还在用旧 meshgrid / checkpoint API；推理时没有梯度，警告可以忽略。
warnings.filterwarnings("ignore", message=r".*meshgrid.*indexing.*")
warnings.filterwarnings("ignore", message=r".*use_reentrant.*")
warnings.filterwarnings("ignore", message=r".*requires_grad=True.*")


VT = "#VT"


def _force_utf8_stdio() -> None:
    """中文 Windows 默认 GBK；窗口按 UTF-8 读管道，这里必须对齐。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def emit(kind: str, payload: str = "") -> None:
    line = f"{VT} {kind}" if not payload else f"{VT} {kind} {payload}"
    print(line, flush=True)


def log(msg: str) -> None:
    emit("LOG", msg)


def die(msg: str, code: int = 1) -> None:
    emit("ERROR", msg)
    sys.exit(code)


# ── 探测：只在本进程 import torch，GUI 进程碰不到 ──────────────

def cmd_probe() -> int:
    info = {"ok": False, "torch": "", "cuda": False, "cuda_name": "", "device": "cpu"}
    try:
        import torch
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
        emit("PROBE", json.dumps(info, ensure_ascii=False))
        return 1
    info["ok"] = True
    info["torch"] = getattr(torch, "__version__", "?")
    info["cuda"] = bool(torch.cuda.is_available())
    if info["cuda"]:
        try:
            info["cuda_name"] = torch.cuda.get_device_name(0)
        except Exception:
            info["cuda_name"] = "CUDA"
        info["device"] = "cuda"
    emit("PROBE", json.dumps(info, ensure_ascii=False))
    return 0


# ── 模型族 ────────────────────────────────────────────────────

VRT_TASKS = {
    "vrt_denoise": "008_VRT_videodenoising_DAVIS",
    "vrt_deblur": "007_VRT_videodeblurring_REDS",
    "vrt_sr": "001_VRT_videosr_bi_REDS_6frames",
}


def guess_task(weights: Path, explicit: str) -> str:
    if explicit and explicit != "auto":
        return explicit
    name = weights.name.lower()
    if any(k in name for k in ("denois", "davis", "008")):
        return "vrt_denoise"
    if any(k in name for k in ("deblur", "005", "006", "007", "gopro", "dvd")):
        return "vrt_deblur"
    if any(k in name for k in ("videosr", "x4", "001", "002", "003", "004")):
        return "vrt_sr"
    if weights.suffix.lower() in (".pt", ".ts") or "script" in name or "jit" in name:
        return "jit"
    return "vrt_denoise"


APP_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = APP_DIR / "third_party" / "VRT"
DEFAULT_WEIGHTS = APP_DIR / "models" / "008_VRT_videodenoising_DAVIS.pth"


def find_vrt_repo(hint: str) -> Optional[Path]:
    candidates: List[Path] = []
    if hint:
        candidates.append(Path(hint))
    here = APP_DIR
    candidates.extend([
        DEFAULT_REPO,
        here / "VRT",
        here / "models" / "VRT",
    ])
    for raw in candidates:
        p = raw.expanduser().resolve()
        if (p / "models" / "network_vrt.py").is_file():
            return p
    return None


def resolve_device(name: str):
    import torch
    name = (name or "auto").lower()
    if name == "cpu":
        return torch.device("cpu")
    if name == "cuda":
        if not torch.cuda.is_available():
            die("指定了 CUDA，但当前解释器的 torch 看不到 GPU")
        return torch.device("cuda")
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def unwrap_state(obj: Any) -> Any:
    if isinstance(obj, dict):
        for key in ("params", "params_ema", "state_dict", "model", "net"):
            if key in obj and isinstance(obj[key], dict):
                return obj[key]
    return obj


def load_checkpoint(path: Path, map_location):
    import torch
    try:
        return torch.load(str(path), map_location=map_location, weights_only=False)
    except TypeError:
        return torch.load(str(path), map_location=map_location)


def _patch_distutils() -> None:
    """官方 network_vrt.py 还在用 distutils，Python 3.12 已经删了。"""
    if "distutils.version" in sys.modules:
        return
    import types

    class LooseVersion:
        def __init__(self, v):
            self.v = str(v)

        def _parts(self):
            out = []
            for p in self.v.replace("+", ".").split("."):
                if p.isdigit():
                    out.append((0, int(p)))
                elif p:
                    out.append((1, p))
            return out

        def __ge__(self, other):
            return self._parts() >= LooseVersion(other.v if isinstance(other, LooseVersion) else other)._parts()

    distutils = types.ModuleType("distutils")
    version = types.ModuleType("distutils.version")
    version.LooseVersion = LooseVersion
    distutils.version = version
    sys.modules["distutils"] = distutils
    sys.modules["distutils.version"] = version


def build_vrt(repo: Path, task_key: str):
    repo_s = str(repo)
    if repo_s not in sys.path:
        sys.path.insert(0, repo_s)
    _patch_distutils()
    try:
        from models.network_vrt import VRT as net
    except Exception as e:
        die(
            f"无法从仓库导入 VRT: {e}\n"
            f"仓库: {repo}\n"
            "需要官方结构 models/network_vrt.py，并在该 Python 里装 einops / timm 等依赖"
        )

    official = VRT_TASKS[task_key]
    if official == "008_VRT_videodenoising_DAVIS":
        model = net(
            upscale=1, img_size=[6, 192, 192], window_size=[6, 8, 8],
            depths=[8, 8, 8, 8, 8, 8, 8, 4, 4, 4, 4],
            indep_reconsts=[9, 10],
            embed_dims=[96, 96, 96, 96, 96, 96, 96, 120, 120, 120, 120],
            num_heads=[6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
            pa_frames=2, deformable_groups=16, nonblind_denoising=True,
        )
        meta = {"scale": 1, "window_size": [6, 8, 8], "nonblind": True}
    elif official.startswith("00") and "deblur" in official:
        model = net(
            upscale=1, img_size=[6, 192, 192], window_size=[6, 8, 8],
            depths=[8, 8, 8, 8, 8, 8, 8, 4, 4, 4, 4],
            indep_reconsts=[9, 10],
            embed_dims=[96, 96, 96, 96, 96, 96, 96, 120, 120, 120, 120],
            num_heads=[6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
            pa_frames=2, deformable_groups=16,
        )
        meta = {"scale": 1, "window_size": [6, 8, 8], "nonblind": False}
    else:
        model = net(
            upscale=4, img_size=[6, 64, 64], window_size=[6, 8, 8],
            depths=[8, 8, 8, 8, 8, 8, 8, 4, 4, 4, 4, 4, 4],
            indep_reconsts=[11, 12],
            embed_dims=[120, 120, 120, 120, 120, 120, 120, 180, 180, 180, 180, 180, 180],
            num_heads=[6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6],
            pa_frames=2, deformable_groups=12,
        )
        meta = {"scale": 4, "window_size": [6, 8, 8], "nonblind": False}
    return model, meta


def load_model(args) -> Tuple[Any, dict]:
    import torch
    from torch import nn

    device = resolve_device(args.device)
    weights = Path(args.weights).expanduser().resolve()
    task = guess_task(weights, args.task)
    log(f"任务={task}  权重={weights.name}  设备={device}")

    if task == "jit":
        emit("STATUS", "loading jit")
        try:
            model = torch.jit.load(str(weights), map_location=device)
        except Exception:
            obj = load_checkpoint(weights, device)
            if isinstance(obj, nn.Module):
                model = obj
            else:
                die("这个文件既不是 TorchScript，也不是完整 nn.Module，jit 模式用不了")
        model.eval()
        model.to(device)
        return model, {"scale": 1, "window_size": [1, 8, 8], "nonblind": False, "kind": "jit"}

    repo = find_vrt_repo(args.repo)
    if repo is None:
        die(
            "找不到官方 VRT 仓库（需要 models/network_vrt.py）。\n"
            "请 git clone https://github.com/JingyunLiang/VRT 后在窗口里填仓库路径。"
        )
    log(f"VRT 仓库: {repo}")
    emit("STATUS", "building vrt")
    model, meta = build_vrt(repo, task)
    emit("STATUS", "loading weights")
    ckpt = load_checkpoint(weights, "cpu")
    state = unwrap_state(ckpt)
    if not isinstance(state, dict):
        die("权重文件不是 state_dict，无法装进 VRT")
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing:
        log(f"缺键 {len(missing)} 个（只列前 5）: {list(missing)[:5]}")
    if unexpected:
        log(f"多余键 {len(unexpected)} 个（只列前 5）: {list(unexpected)[:5]}")
    model.eval()
    model.to(device)
    meta["kind"] = "vrt"
    meta["task"] = task
    return model, meta


# ── 官方 test_clip 的精简版（避免再 import 他们的 dataset）─────

def _tile_indices(length: int, size_patch: int, overlap: int) -> List[int]:
    stride = max(1, size_patch - int(overlap))
    idx = list(range(0, max(1, length - size_patch + 1), stride))
    last = max(0, length - size_patch)
    if not idx or idx[-1] != last:
        idx.append(last)
    return idx


def count_tiles(h: int, w: int, tile: int, overlap: int) -> int:
    size_patch = int(tile)
    if size_patch <= 0:
        return 1
    return len(_tile_indices(h, size_patch, overlap)) * len(_tile_indices(w, size_patch, overlap))


def test_clip(lq, model, scale: int, window_size: Sequence[int],
              tile: int, overlap: int, nonblind: bool, on_tile=None):
    import torch

    size_patch = int(tile)
    if size_patch:
        _, _, _, h0, w0 = lq.size()
        ph = max(0, size_patch - h0)
        pw = max(0, size_patch - w0)
        if ph or pw:
            lq = torch.nn.functional.pad(lq, (0, pw, 0, ph), mode="reflect")
        out = _test_clip_body(lq, model, scale, window_size, size_patch, overlap, nonblind, on_tile)
        return out[:, :, :, :h0 * scale, :w0 * scale]
    return _test_clip_body(lq, model, scale, window_size, 0, overlap, nonblind, on_tile)


def _test_clip_body(lq, model, scale: int, window_size: Sequence[int],
                    size_patch: int, overlap: int, nonblind: bool, on_tile=None):
    import torch

    if size_patch:
        if size_patch % window_size[-1] != 0:
            die(f"空间分块 {size_patch} 必须是 window_size={window_size[-1]} 的倍数")
        overlap_size = int(overlap)
        b, d, c, h, w = lq.size()
        c_out = c - 1 if nonblind else c
        h_idx_list = _tile_indices(h, size_patch, overlap_size)
        w_idx_list = _tile_indices(w, size_patch, overlap_size)
        n_tiles = max(1, len(h_idx_list) * len(w_idx_list))
        E = torch.zeros(b, d, c_out, h * scale, w * scale, device="cpu")
        W = torch.zeros_like(E)
        done = 0
        for h_idx in h_idx_list:
            for w_idx in w_idx_list:
                done += 1
                if on_tile:
                    on_tile(done, n_tiles)
                in_patch = lq[..., h_idx:h_idx + size_patch, w_idx:w_idx + size_patch].contiguous()
                # 官方 VRT 的 forward 里还有 checkpoint + 就地改张量；
                # inference_mode 会把输出锁死，出来再 *= 0 就会炸。用 no_grad。
                with torch.no_grad():
                    out_patch = model(in_patch).detach().cpu().clone()
                out_mask = torch.ones_like(out_patch)
                if h_idx < h_idx_list[-1]:
                    out_patch[..., -overlap_size // 2:, :] *= 0
                    out_mask[..., -overlap_size // 2:, :] *= 0
                if w_idx < w_idx_list[-1]:
                    out_patch[..., :, -overlap_size // 2:] *= 0
                    out_mask[..., :, -overlap_size // 2:] *= 0
                if h_idx > h_idx_list[0]:
                    out_patch[..., :overlap_size // 2, :] *= 0
                    out_mask[..., :overlap_size // 2, :] *= 0
                if w_idx > w_idx_list[0]:
                    out_patch[..., :, :overlap_size // 2] *= 0
                    out_mask[..., :, :overlap_size // 2] *= 0
                E[..., h_idx * scale:(h_idx + size_patch) * scale,
                  w_idx * scale:(w_idx + size_patch) * scale].add_(out_patch)
                W[..., h_idx * scale:(h_idx + size_patch) * scale,
                  w_idx * scale:(w_idx + size_patch) * scale].add_(out_mask)
        return E.div_(W.clamp(min=1e-8))

    _, _, _, h_old, w_old = lq.size()
    h_pad = (window_size[1] - h_old % window_size[1]) % window_size[1]
    w_pad = (window_size[2] - w_old % window_size[2]) % window_size[2]
    if h_pad:
        lq = torch.cat([lq, torch.flip(lq[:, :, :, -h_pad:, :], [3])], 3)
    if w_pad:
        lq = torch.cat([lq, torch.flip(lq[:, :, :, :, -w_pad:], [4])], 4)
    with torch.no_grad():
        output = model(lq).detach().cpu()
    return output[:, :, :, :h_old * scale, :w_old * scale]


def frames_to_tensor(frames_bgr: List[Any], sigma: float, nonblind: bool, device):
    import cv2
    import numpy as np
    import torch

    rgb = [cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames_bgr]
    arr = np.stack(rgb, axis=0).astype(np.float32) / 255.0
    ten = torch.from_numpy(arr).permute(0, 3, 1, 2).unsqueeze(0)
    if nonblind:
        noise = torch.ones(1, ten.size(1), 1, ten.size(3), ten.size(4),
                           dtype=ten.dtype) * (float(sigma) / 255.0)
        ten = torch.cat([ten, noise], dim=2)
    return ten.to(device)


def tensor_to_frames(output) -> List[Any]:
    import numpy as np

    # output: 1,T,3,H,W in 0-1 RGB
    clip = output[0].float().clamp(0, 1).cpu().numpy()
    frames = []
    for i in range(clip.shape[0]):
        img = np.transpose(clip[i][[2, 1, 0], :, :], (1, 2, 0))
        frames.append((img * 255.0).round().astype(np.uint8))
    return frames


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


CONTAINER_EXT = {
    "mp4": ".mp4",
    "mov": ".mov",
    "mkv": ".mkv",
    "avi": ".avi",
}
FFMPEG_CODECS = {"h264": "libx264", "h265": "libx265"}
FOURCC = {"mp4v": "mp4v", "xvid": "XVID"}
FFMPEG_PRESETS = (
    "ultrafast", "superfast", "veryfast", "faster", "fast",
    "medium", "slow", "slower", "veryslow",
)


def apply_output_ext(path: str, fmt: str) -> Path:
    ext = CONTAINER_EXT.get((fmt or "mp4").lower().lstrip("."), ".mp4")
    return Path(path).with_suffix(ext)


def _ffmpeg_bin() -> Optional[str]:
    import shutil
    return shutil.which("ffmpeg")


def _popen_flags() -> dict:
    if sys.platform == "win32":
        import subprocess
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


class ClipWriter:
    """跟主窗口 FrameSink 同一套：H.264/H.265 走 ffmpeg，其余走 OpenCV。"""

    def __init__(self, dest: Path, fps: float, size: Tuple[int, int], args, audio_src: Path):
        import cv2

        self.dest = dest
        self.fps = max(0.01, float(fps))
        self.width, self.height = int(size[0]), int(size[1])
        self._proc = None
        self._writer = None
        self._tmp: Optional[Path] = None
        self._audio_src = audio_src
        self._keep_audio = bool(getattr(args, "keep_audio", True))
        dest.parent.mkdir(parents=True, exist_ok=True)

        codec = (getattr(args, "codec", "auto") or "auto").lower()
        if codec in FFMPEG_CODECS and _ffmpeg_bin():
            if self._open_ffmpeg(args):
                log(f"写出 {dest.name}  ·  ffmpeg/{FFMPEG_CODECS[codec]}")
                return
            log("FFmpeg 编码启动失败，退回 OpenCV")
        self._open_cv2(cv2, codec)

    def _open_ffmpeg(self, args) -> bool:
        import subprocess

        encoder = FFMPEG_CODECS[args.codec.lower()]
        ffmpeg = _ffmpeg_bin()
        cmd = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
            "-s", f"{self.width}x{self.height}", "-r", f"{self.fps:.6f}", "-i", "-",
        ]
        use_audio = self._keep_audio and self._audio_src.is_file()
        if use_audio:
            cmd += ["-i", str(self._audio_src)]
        cmd += ["-map", "0:v:0"]
        if use_audio:
            cmd += ["-map", "1:a:0?", "-c:a", "aac", "-b:a", "192k", "-shortest"]
        else:
            cmd += ["-an"]
        preset = args.encode_preset if args.encode_preset in FFMPEG_PRESETS else "medium"
        cmd += ["-c:v", encoder, "-preset", preset]
        if getattr(args, "rate_mode", "crf") == "bitrate":
            br = max(100, int(args.bitrate))
            cmd += ["-b:v", f"{br}k", "-maxrate", f"{br * 2}k", "-bufsize", f"{br * 4}k"]
        else:
            cmd += ["-crf", str(int(min(51, max(0, float(args.crf)))))]
        cmd += ["-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-pix_fmt", "yuv420p"]
        if encoder == "libx265":
            cmd += ["-tag:v", "hvc1"]
        if self.dest.suffix.lower() in (".mp4", ".mov", ".m4v"):
            cmd += ["-movflags", "+faststart"]
        cmd.append(str(self.dest))
        try:
            self._proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, **_popen_flags(),
            )
        except Exception as e:
            log(f"FFmpeg 拉不起来: {e}")
            self._proc = None
            return False
        return True

    def _open_cv2(self, cv2, codec: str) -> None:
        ext = self.dest.suffix.lower()
        if codec in FOURCC:
            tag = FOURCC[codec]
        elif ext == ".avi":
            tag = "XVID"
        else:
            tag = "mp4v"
        tmp_ext = ".avi" if tag == "XVID" else ".mp4"
        self._tmp = self.dest.with_name(self.dest.stem + ".tmp" + tmp_ext)
        writer = cv2.VideoWriter(
            str(self._tmp), cv2.VideoWriter_fourcc(*tag), self.fps,
            (self.width, self.height),
        )
        if not writer.isOpened():
            die(f"无法创建输出: {self._tmp}")
        self._writer = writer
        log(f"写出 {self._tmp.name}  ·  cv2/{tag}")

    def write(self, frame) -> None:
        import numpy as np

        if frame.ndim == 2:
            import cv2
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        if frame.shape[0] != self.height or frame.shape[1] != self.width:
            import cv2
            frame = cv2.resize(frame, (self.width, self.height))
        if self._proc is not None:
            if not frame.flags["C_CONTIGUOUS"]:
                frame = np.ascontiguousarray(frame)
            try:
                self._proc.stdin.write(frame.tobytes())
            except (BrokenPipeError, OSError) as e:
                die(f"FFmpeg 编码进程提前退出: {e}")
            return
        self._writer.write(frame)

    def close(self) -> Path:
        import subprocess

        if self._proc is not None:
            proc, self._proc = self._proc, None
            try:
                if proc.stdin:
                    proc.stdin.close()
            except OSError:
                pass
            try:
                code = proc.wait(timeout=300)
            except Exception:
                proc.kill()
                die("FFmpeg 收尾超时")
            if code != 0:
                die(f"FFmpeg 退出码 {code}")
            return self.dest

        if self._writer is not None:
            self._writer.release()
            self._writer = None
        tmp = self._tmp
        if tmp is None or not tmp.is_file():
            die("一帧都没写出来")
        if self._keep_audio and remux_audio(self._audio_src, tmp, self.dest):
            _safe_unlink(tmp)
            log("已把原音轨拼回去")
            return self.dest
        _safe_unlink(self.dest)
        tmp.replace(self.dest)
        return self.dest

    def abort(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        if self._tmp:
            _safe_unlink(self._tmp)
        _safe_unlink(self.dest)


def remux_audio(src: Path, silent: Path, dest: Path) -> bool:
    import subprocess

    ffmpeg = _ffmpeg_bin()
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(silent), "-i", str(src),
        "-map", "0:v:0", "-map", "1:a:0?", "-c:v", "copy", "-c:a", "aac",
        "-shortest", str(dest),
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True, **_popen_flags())
        return dest.is_file() and dest.stat().st_size > 500
    except Exception:
        return False


def run_jit_video(model, args, meta: dict) -> None:
    """整模 / TorchScript：按单帧或模型自己声明的输入跑。默认按单帧 RGB。"""
    import cv2
    import numpy as np
    import torch

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        die(f"打不开输入视频: {args.input}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, first = cap.read()
    if not ok:
        die("视频是空的")
    h, w = first.shape[:2]
    scale = int(meta.get("scale") or 1)
    dest = apply_output_ext(args.output, getattr(args, "container", "mp4"))
    writer = ClipWriter(dest, fps, (w * scale, h * scale), args, Path(args.input))
    device = next(model.parameters()).device if hasattr(model, "parameters") else resolve_device(args.device)

    def infer_one(frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        ten = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device)
        with torch.no_grad():
            out = model(ten)
        if isinstance(out, (tuple, list)):
            out = out[0]
        img = out[0].float().clamp(0, 1).detach().cpu().numpy()
        img = np.transpose(img[[2, 1, 0], :, :], (1, 2, 0))
        return (img * 255.0).round().astype(np.uint8)

    idx = 0
    frame = first
    while frame is not None:
        writer.write(infer_one(frame))
        idx += 1
        if total:
            emit("FRAME", f"{idx} {total}")
            emit("PROGRESS", f"{idx / max(total, 1):.4f}")
        ok, nxt = cap.read()
        frame = nxt if ok else None
    cap.release()
    dest = writer.close()
    emit("DONE", str(dest))
    emit("PROGRESS", "1.0")
    log(f"完成: {dest}")


def finalize_output(dest: Path) -> None:
    emit("DONE", str(dest))
    emit("PROGRESS", "1.0")
    log(f"完成: {dest}")


def run_vrt_video(model, args, meta: dict) -> None:
    import cv2

    clip_len = max(2, int(args.temporal))
    overlap = min(max(0, int(args.temporal_overlap)), clip_len - 1)
    stride = clip_len - overlap
    tile = int(args.tile)
    tile_overlap = int(args.tile_overlap)
    sigma = float(args.sigma)
    scale = int(meta["scale"])
    window_size = meta["window_size"]
    nonblind = bool(meta["nonblind"])
    device = next(model.parameters()).device

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        die(f"打不开输入视频: {args.input}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    ok, first = cap.read()
    if not ok:
        die("视频是空的")
    h, w = first.shape[:2]
    dest = apply_output_ext(args.output, getattr(args, "container", "mp4"))
    writer = ClipWriter(dest, fps, (w * scale, h * scale), args, Path(args.input))

    pending = [first]
    written = 0
    eof = False
    n_tiles = count_tiles(h, w, tile, tile_overlap) if tile else 1
    emit("STATUS", "infer")
    log(f"时间窗 {clip_len} / 重叠 {overlap} / 空间分块 {tile or '整帧'}")
    log(f"画面 {w}×{h}，每段 {clip_len} 帧要算 {n_tiles} 块（占着 10G 显存也是在算，不是死机）")
    if n_tiles > 8:
        log("「帧 x/n」要等这一段所有块算完才出现；下面会先报分块进度")

    clip_i = 0
    clips_est = max(1, (max(total - overlap, 1) + stride - 1) // stride) if total else 1

    def pull_more(n: int) -> None:
        nonlocal eof
        while len(pending) < n and not eof:
            good, fr = cap.read()
            if not good:
                eof = True
                return
            pending.append(fr)

    def infer_clip(frames):
        need = clip_len
        work = list(frames)
        if not work:
            return []
        while len(work) < need:
            work.append(work[-1])
        lq = frames_to_tensor(work[:need], sigma, nonblind, device)

        def on_tile(done: int, n: int) -> None:
            emit("STATUS", f"tile {done}/{n}")
            if done == 1:
                log(f"第 {clip_i + 1} 段：开始第 1/{n} 块（含 CUDA 预热，这块最慢）")
            else:
                log(f"分块 {done}/{n}")
            if n:
                frac = (clip_i + done / n) / max(clips_est, 1)
                emit("PROGRESS", f"{min(0.99, frac):.4f}")

        out = test_clip(lq, model, scale, window_size, tile, tile_overlap, nonblind, on_tile)
        return tensor_to_frames(out)[:len(frames)]

    while True:
        pull_more(clip_len)
        if not pending:
            break
        chunk = pending[:clip_len]
        is_last = eof and len(pending) <= clip_len
        outs = infer_clip(chunk)
        clip_i += 1
        take = len(outs) if is_last else min(stride, len(outs))
        if take <= 0:
            break
        for i in range(take):
            writer.write(outs[i])
            written += 1
        pending = pending[take:]
        if total:
            emit("FRAME", f"{written} {total}")
            emit("PROGRESS", f"{min(0.99, written / max(total, 1)):.4f}")
        else:
            emit("FRAME", f"{written} 0")
        if is_last:
            break

    cap.release()
    if written == 0:
        writer.abort()
        die("一帧都没写出来")
    dest = writer.close()
    finalize_output(dest)


def cmd_run(args) -> int:
    emit("STATUS", "checking")
    if not args.input or not Path(args.input).is_file():
        die(f"输入视频不存在: {args.input}")
    if not args.weights:
        args.weights = str(DEFAULT_WEIGHTS)
    if not Path(args.weights).is_file():
        die(f"权重不存在: {args.weights}\n可先运行 python setup_vrt.py")
    if not args.output:
        die("没有给输出路径")
    args.output = str(apply_output_ext(args.output, getattr(args, "container", "mp4")))
    quality = (f"{args.bitrate}kbps" if getattr(args, "rate_mode", "crf") == "bitrate"
               else f"CRF {args.crf}")
    log(f"输出 {Path(args.output).suffix} / {getattr(args, 'codec', 'auto')} / {quality}")
    try:
        import torch  # noqa: F401
    except Exception as e:
        die(f"当前解释器没有 torch: {e}")

    emit("STATUS", "loading")
    model, meta = load_model(args)
    kind = meta.get("kind")
    if kind == "jit":
        run_jit_video(model, args, meta)
    else:
        run_vrt_video(model, args, meta)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="VRT / Torch .pth 子进程推理")
    p.add_argument("--probe", action="store_true", help="只检测 torch，不跑推理")
    p.add_argument("--input", default="")
    p.add_argument("--output", default="")
    p.add_argument("--weights", default="")
    p.add_argument("--repo", default="", help="官方 VRT 仓库根目录")
    p.add_argument("--task", default="auto",
                   choices=["auto", "vrt_denoise", "vrt_deblur", "vrt_sr", "jit"])
    p.add_argument("--sigma", type=float, default=15.0)
    p.add_argument("--tile", type=int, default=256, help="空间分块，0=整帧")
    p.add_argument("--tile-overlap", type=int, default=20)
    p.add_argument("--temporal", type=int, default=12)
    p.add_argument("--temporal-overlap", type=int, default=2)
    p.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    p.add_argument("--codec", default="auto",
                   choices=["auto", "h264", "h265", "mp4v", "xvid"])
    p.add_argument("--format", dest="container", default="mp4",
                   choices=["mp4", "mov", "mkv", "avi"])
    p.add_argument("--rate-mode", default="crf", choices=["crf", "bitrate"])
    p.add_argument("--crf", type=float, default=20.0)
    p.add_argument("--bitrate", type=int, default=4000)
    p.add_argument("--encode-preset", default="medium")
    p.add_argument("--keep-audio", dest="keep_audio", action="store_true")
    p.add_argument("--no-keep-audio", dest="keep_audio", action="store_false")
    p.set_defaults(keep_audio=True)
    return p


def main() -> int:
    _force_utf8_stdio()
    parser = build_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        code = int(e.code) if isinstance(e.code, int) else 1
        if code:
            die("命令行参数无效。任务必须是 auto / vrt_denoise / vrt_deblur / vrt_sr / jit")
        return code
    try:
        if args.probe:
            return cmd_probe()
        return cmd_run(args)
    except SystemExit:
        raise
    except Exception:
        die(traceback.format_exc())
        return 1


if __name__ == "__main__":
    sys.exit(main())
