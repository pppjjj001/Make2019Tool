#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把「最好用的 VRT 降噪」落到本地：官方 network_vrt.py + 008 DAVIS 权重。

不 import torch。主程序 / 子窗口都可以当准备脚本调用。
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = APP_DIR / "third_party" / "VRT"
NET_PATH = REPO_DIR / "models" / "network_vrt.py"
WEIGHT_NAME = "008_VRT_videodenoising_DAVIS.pth"
WEIGHT_PATH = APP_DIR / "models" / WEIGHT_NAME

NET_URLS = [
    "https://raw.githubusercontent.com/JingyunLiang/VRT/master/models/network_vrt.py",
    "https://cdn.jsdelivr.net/gh/JingyunLiang/VRT@master/models/network_vrt.py",
    "https://ghproxy.net/https://raw.githubusercontent.com/JingyunLiang/VRT/master/models/network_vrt.py",
]
WEIGHT_URLS = [
    "https://github.com/JingyunLiang/VRT/releases/download/v0.0/008_VRT_videodenoising_DAVIS.pth",
    "https://ghproxy.net/https://github.com/JingyunLiang/VRT/releases/download/v0.0/008_VRT_videodenoising_DAVIS.pth",
]

# 官方 release 约 104024 KB
WEIGHT_MIN_BYTES = 90 * 1024 * 1024
NET_MIN_BYTES = 20 * 1024


def _log(msg: str) -> None:
    print(msg, flush=True)


def _download(urls: list, dest: Path, min_bytes: int) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size >= min_bytes:
        _log(f"已存在: {dest} ({dest.stat().st_size} bytes)")
        return dest
    last_err = None
    tmp = dest.with_suffix(dest.suffix + ".part")
    for url in urls:
        _log(f"下载 {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VideoToolbox-VRT-setup"})
            with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    fh.flush()
            size = tmp.stat().st_size
            if size < min_bytes:
                raise RuntimeError(f"文件太小 ({size} bytes)，不像下完")
            tmp.replace(dest)
            _log(f"写到 {dest} ({size} bytes)")
            return dest
        except Exception as e:
            last_err = e
            _log(f"失败: {e}")
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    pass
    raise RuntimeError(f"下不下来: {dest.name}\n最后错误: {last_err}")


def _write_repo_stub() -> None:
    models = REPO_DIR / "models"
    models.mkdir(parents=True, exist_ok=True)
    init = models / "__init__.py"
    if not init.exists():
        init.write_text("# official VRT models package\n", encoding="utf-8")
    readme = REPO_DIR / "README.md"
    if not readme.exists():
        readme.write_text(
            "Official VRT network from https://github.com/JingyunLiang/VRT\n"
            "Only `models/network_vrt.py` is required for VideoToolbox inference.\n",
            encoding="utf-8",
        )


def setup() -> dict:
    _write_repo_stub()
    net = _download(NET_URLS, NET_PATH, NET_MIN_BYTES)
    weight = _download(WEIGHT_URLS, WEIGHT_PATH, WEIGHT_MIN_BYTES)
    return {"repo": str(REPO_DIR), "network": str(net), "weights": str(weight)}


def main() -> int:
    try:
        info = setup()
    except Exception as e:
        print(f"ERROR {e}", flush=True)
        return 1
    print("OK repo=" + info["repo"], flush=True)
    print("OK weights=" + info["weights"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
