#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PyGameTools — 手机提包 / APK 反编译 / 资源替换 / 回编译（含 DebugApk）"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import tarfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent
TOOLS_DIR = APP_DIR / "tools"
WORK_DIR = APP_DIR / "work"
OUTPUT_DIR = APP_DIR / "output"
JRE_DIR = TOOLS_DIR / "jre"

APKTOOL_JAR = TOOLS_DIR / "apktool.jar"
SIGNER_JAR = TOOLS_DIR / "uber-apk-signer.jar"
DEBUG_KEYSTORE = TOOLS_DIR / "debug.keystore"
ADB_DIR = TOOLS_DIR / "platform-tools"
ADB_EXE = ADB_DIR / "adb.exe"
PULL_DIR = OUTPUT_DIR / "pulled"

APKTOOL_URL = (
    "https://github.com/iBotPeaches/Apktool/releases/download/"
    "v2.9.3/apktool_2.9.3.jar"
)
SIGNER_URL = (
    "https://github.com/patrickfav/uber-apk-signer/releases/download/"
    "v1.3.0/uber-apk-signer-1.3.0.jar"
)
JRE_URLS = (
    "https://github.com/adoptium/temurin17-binaries/releases/download/"
    "jdk-17.0.20+8/OpenJDK17U-jre_x64_windows_hotspot_17.0.20_8.zip",
    "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/"
    "jre/hotspot/normal/eclipse?project=jdk",
)
PLATFORM_TOOLS_URL = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)
PKG_IN_FOCUS_RE = re.compile(
    r"([a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+)/[a-zA-Z0-9_$.]+"
)

CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ---------------------------------------------------------------------------
# Packer / engine fingerprint (signature only, no unpack)
# ---------------------------------------------------------------------------
# needles 对路径、文件名、清单里的 ASCII/UTF-16 字符串做包含匹配（小写）。
# 能覆盖国内渠道包里大部分「有特色 so / Application」的商业加固；
# 认不出：改过 so 名的私有壳、全新壳、只做混淆不做壳。
DETECT_RULES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "加固",
        "360加固",
        ("libjiagu", "libjgdtc", "libjg.swak", "com.qihoo.util.stubapplication", "com.qihoo.util.stubapp"),
        "classes.dex 多为壳，apktool 改到的通常不是原逻辑。",
    ),
    (
        "加固",
        "腾讯乐固",
        ("libshella", "libshellx-", "libshell-super", "com.tencent.stubshell", "tencent_stub"),
        "乐固壳。清单里的 Application 往往是 TxAppEntry。",
    ),
    (
        "加固",
        "梆梆 / SecNeo",
        (
            "libsecexe",
            "libsecmain",
            "libsecshell",
            "libdexhelper",
            "com.secneo.apkwrapper",
            "com.secshell.secdata",
        ),
        "梆梆或 SecNeo 加固。",
    ),
    (
        "加固",
        "爱加密",
        ("ijiami.dat", "ijiami.ajm", "libexecmain", "ijimaimain", "com.ijiami."),
        "爱加密。不要单独凭 libexec.so 判断（太容易误报）。",
    ),
    (
        "加固",
        "阿里聚安全",
        ("libmobisec", "aliprotect.dat", "com.ali.mobisecenhance"),
        "阿里聚安全 / 移动安全。",
    ),
    (
        "加固",
        "百度加固",
        ("libbaiduprotect", "baiduprotect", "com.baidu.protect"),
        "百度加固。",
    ),
    (
        "加固",
        "娜迦",
        ("libchaosvmp", "libddog.so", "libfdog.so", "libedog.so"),
        "娜迦加固（含 VMP 特征库名）。",
    ),
    (
        "加固",
        "通付盾",
        ("libegis.so", "libnsaferonly", "libnsafer"),
        "通付盾（Payegis）。",
    ),
    (
        "加固",
        "网秦加固",
        ("libnqshield",),
        "网秦 nqshield。",
    ),
    (
        "加固",
        "网易易盾加固",
        ("libnesec", "com.netease.nis.wrapper"),
        "易盾应用加固（不是验证码 SDK）。",
    ),
    (
        "加固",
        "几维安全",
        ("libkwscprotect", "libkwsc.so", "libkws.so"),
        "几维安全加固。",
    ),
    (
        "加固",
        "APKProtect",
        ("libapkprotect",),
        "APKProtect。",
    ),
    (
        "加固",
        "中国移动加固",
        ("libmogosec", "libmogosecurity"),
        "中国移动 / 蘑菇加固。",
    ),
    (
        "加固",
        "珊瑚灵御",
        ("libapssec",),
        "珊瑚灵御。",
    ),
    (
        "加固",
        "顶像加固",
        ("libdx-plaid", "libdxbase.so"),
        "顶像安全。",
    ),
    (
        "加固",
        "华为加固",
        ("libprotectclass", "com.huawei.protection"),
        "华为应用加固。",
    ),
    (
        "加固",
        "小米加固",
        ("libx3g.so",),
        "小米加固常见 so 名。",
    ),
    (
        "加固",
        "瑞星加固",
        ("librsprotect",),
        "瑞星加固。",
    ),
    (
        "加固",
        "盛大加固",
        ("libsndprotect",),
        "盛大加固。",
    ),
    (
        "加固",
        "DexProtector",
        ("dexprotector", "libdexprotector", "dp.dpc"),
        "Licel DexProtector。",
    ),
    (
        "加固",
        "LIAPP",
        ("liappstub", "liappini", "libliapp"),
        "LIAPP。",
    ),
    (
        "热更/渠道",
        "乐变",
        (
            "com.excelliance",
            "lbapplication",
            "assets/lebian",
            "liblebian",
            "lebianflag",
        ),
        "热更/分包外壳，不是 DEX 加固。完整内容多在 Android/data/包名/files。",
    ),
    (
        "反作弊",
        "腾讯游戏安全 (TP)",
        ("libtersafe", "libtp2.so", "libtprt.so"),
        "反作弊/反外挂，一般不是 DEX 壳。",
    ),
    (
        "风控SDK",
        "字节 Metasec",
        ("libmetasec",),
        "风控/设备指纹，不是加固壳。",
    ),
    (
        "引擎",
        "Unity",
        ("libunity.so", "libil2cpp.so", "assets/bin/data"),
        "Unity 游戏。逻辑在 so / il2cpp，不是 Java 壳。",
    ),
    (
        "引擎",
        "Cocos",
        ("libcocos2djs", "libcocos2dcpp", "libcocos2d.so"),
        "Cocos 引擎。",
    ),
    (
        "引擎",
        "Unreal",
        ("libue4.so", "libunreal.so"),
        "Unreal Engine。",
    ),
    (
        "引擎",
        "Flutter",
        ("libflutter.so", "libapp.so"),
        "Flutter。libapp.so 需同时有 libflutter 才较稳，见命中文件。",
    ),
    (
        "资源",
        "YooAsset",
        ("assets/yoo/", "assets/yoo\\"),
        "YooAsset 分包。热更资源常在 files 目录，不是加固壳。",
    ),
    (
        "资源",
        "HybridCLR",
        ("hybridclr", "libhybridclr"),
        "Unity HybridCLR 热更代码。",
    ),
)

UPX_MAGIC = b"UPX!"


@dataclass
class DetectHit:
    kind: str
    name: str
    files: list[str] = field(default_factory=list)
    hint: str = ""


def _ascii_strings(data: bytes, min_len: int = 6) -> str:
    chunks: list[str] = []
    cur: list[str] = []
    for b in data:
        if 32 <= b < 127:
            cur.append(chr(b))
        else:
            if len(cur) >= min_len:
                chunks.append("".join(cur))
            cur = []
    if len(cur) >= min_len:
        chunks.append("".join(cur))
    return "\n".join(chunks)


def _utf16le_strings(data: bytes, min_len: int = 6) -> str:
    chunks: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(data) - 1
    while i < n:
        if data[i + 1] == 0 and 32 <= data[i] < 127:
            cur.append(chr(data[i]))
            i += 2
            continue
        if len(cur) >= min_len:
            chunks.append("".join(cur))
        cur = []
        i += 1
    if len(cur) >= min_len:
        chunks.append("".join(cur))
    return "\n".join(chunks)


def _collect_zip_names(apk: Path) -> tuple[list[str], bytes, list[str]]:
    names: list[str] = []
    manifest = b""
    upx_hits: list[str] = []
    with zipfile.ZipFile(apk) as zf:
        so_checked = 0
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            names.append(name)
            low = name.lower()
            if low.endswith("androidmanifest.xml") and not manifest:
                try:
                    manifest = zf.read(info)
                except Exception:
                    manifest = b""
            if low.endswith(".so") and so_checked < 40:
                so_checked += 1
                try:
                    with zf.open(info, "r") as fp:
                        head = fp.read(256)
                    if UPX_MAGIC in head:
                        upx_hits.append(name)
                except Exception:
                    pass
    return names, manifest, upx_hits


def _collect_dir_names(root: Path) -> tuple[list[str], bytes]:
    names: list[str] = []
    manifest = b""
    for sub in ("lib", "assets", "unknown", "original"):
        folder = root / sub
        if not folder.is_dir():
            continue
        for fp in folder.rglob("*"):
            if not fp.is_file():
                continue
            names.append(fp.relative_to(root).as_posix())
            if len(names) > 12000:
                break
        if len(names) > 12000:
            break
    man = root / "AndroidManifest.xml"
    if man.is_file():
        names.append("AndroidManifest.xml")
        try:
            manifest = man.read_bytes()
        except Exception:
            manifest = b""
    return names, manifest


def _needle_hits(needle: str, names: list[str], blob: str) -> list[str]:
    n = needle.lower()
    found: list[str] = []
    for name in names:
        if n in name.lower():
            found.append(name)
            if len(found) >= 6:
                break
    if not found and n in blob:
        found.append("AndroidManifest / 字符串")
    return found


def detect_packers(apk: Path | None = None, decode_dir: Path | None = None) -> tuple[list[DetectHit], bool]:
    names: list[str] = []
    manifest = b""
    upx_hits: list[str] = []
    if apk and apk.is_file():
        znames, manifest, upx_hits = _collect_zip_names(apk)
        names.extend(znames)
    if decode_dir and decode_dir.is_dir():
        dnames, dman = _collect_dir_names(decode_dir)
        names.extend(dnames)
        if dman:
            manifest = dman
    blob = (
        _ascii_strings(manifest).lower()
        + "\n"
        + _utf16le_strings(manifest).lower()
    )
    hits: list[DetectHit] = []
    has_packer = False
    flutter_libapp = False
    flutter_engine = False
    for kind, name, needles, hint in DETECT_RULES:
        files: list[str] = []
        for needle in needles:
            files.extend(_needle_hits(needle, names, blob))
        # 去重并保序
        uniq: list[str] = []
        seen: set[str] = set()
        for f in files:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        if name == "Flutter":
            flutter_engine = any("libflutter" in x.lower() for x in uniq)
            flutter_libapp = any(x.lower().endswith("libapp.so") for x in uniq)
            if flutter_libapp and not flutter_engine:
                continue
        if not uniq:
            continue
        if kind == "加固":
            has_packer = True
        hits.append(DetectHit(kind=kind, name=name, files=uniq[:8], hint=hint))
    if upx_hits:
        hits.append(
            DetectHit(
                kind="Native压缩",
                name="UPX",
                files=upx_hits[:8],
                hint="so 被 UPX 压缩，不是 DEX 加固。",
            )
        )
    kind_order = {"加固": 0, "热更/渠道": 1, "引擎": 2, "资源": 3, "反作弊": 4, "风控SDK": 5, "Native压缩": 6}
    hits.sort(key=lambda h: (kind_order.get(h.kind, 9), h.name))
    return hits, has_packer


def format_detect_report(hits: list[DetectHit], has_packer: bool) -> str:
    lines = ["---- 壳识别 ----"]
    by_kind: dict[str, list[DetectHit]] = {}
    for h in hits:
        by_kind.setdefault(h.kind, []).append(h)
    if "加固" not in by_kind:
        lines.append("加固: 未发现常见商业加固（可能未加固，或私有壳/改名壳）")
    for kind in ("加固", "热更/渠道", "引擎", "资源", "反作弊", "风控SDK", "Native压缩"):
        items = by_kind.get(kind)
        if not items:
            continue
        for h in items:
            lines.append(f"{kind}: {h.name}")
            show = h.files[:4]
            extra = len(h.files) - len(show)
            detail = ", ".join(show)
            if extra > 0:
                detail += f" 等 {extra} 个"
            lines.append(f"  命中: {detail}")
            if h.hint:
                lines.append(f"  说明: {h.hint}")
    lines.append(
        "范围: 靠 so / 清单 / 资源路径识别国内常见商业壳，覆盖渠道包里的大多数；"
        "认不出改名私有壳和全新壳。识别不是脱壳。"
    )
    if has_packer:
        lines.append("建议: 加固包改 Java/smali 通常无效，优先用未加固测试包。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
def _iter_java_candidates() -> list[Path]:
    found: list[Path] = []
    env = os.environ.get("JAVA_HOME")
    if env:
        found.append(Path(env) / "bin" / "java.exe")
    found.append(JRE_DIR / "bin" / "java.exe")
    extras = [
        Path(r"C:\Program Files\Android\Android Studio\jbr\bin\java.exe"),
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs"
        / "Android"
        / "Android Studio"
        / "jbr"
        / "bin"
        / "java.exe",
    ]
    for base in (
        Path(r"C:\Program Files\Java"),
        Path(r"C:\Program Files\Eclipse Adoptium"),
        Path(r"C:\Program Files\Microsoft"),
        Path(r"C:\Program Files\Eclipse Foundation"),
    ):
        if base.exists():
            extras.extend(base.glob("*/bin/java.exe"))
            extras.extend(base.glob("jdk-*/bin/java.exe"))
    found.extend(extras)
    which = shutil.which("java")
    if which:
        found.append(Path(which))
    return found


def find_java() -> Path | None:
    for p in _iter_java_candidates():
        if p and p.is_file():
            return p
    return None


def find_keytool(java: Path) -> Path | None:
    kt = java.with_name("keytool.exe")
    return kt if kt.is_file() else None


def _urlopen(url: str):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PyGameTools/1.0"
        },
    )
    return urllib.request.urlopen(req, timeout=120)


def download_file(url: str, dest: Path, log, label: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log(f"正在下载 {label} ...")
    last_pct = -1
    try:
        with _urlopen(url) as resp, open(tmp, "wb") as out:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if total > 0:
                    pct = done * 100 // total
                    if pct != last_pct and pct % 10 == 0:
                        log(f"  {label}: {pct}%  ({done // 1024} / {total // 1024} KB)")
                        last_pct = pct
        tmp.replace(dest)
        log(f"下载完成: {dest.name}")
    except Exception:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise


def _extract_jre_zip(zpath: Path, log) -> None:
    log("正在解压便携 JRE ...")
    staging = TOOLS_DIR / "_jre_staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(staging)
    java_exe = next(staging.rglob("bin/java.exe"), None)
    if not java_exe:
        raise RuntimeError("JRE 压缩包中未找到 java.exe")
    root = java_exe.parent.parent
    if JRE_DIR.exists():
        shutil.rmtree(JRE_DIR, ignore_errors=True)
    shutil.move(str(root), str(JRE_DIR))
    shutil.rmtree(staging, ignore_errors=True)
    zpath.unlink(missing_ok=True)
    log(f"便携 JRE 已就绪: {JRE_DIR}")


def generate_debug_keystore(java: Path, log) -> None:
    if DEBUG_KEYSTORE.exists():
        return
    keytool = find_keytool(java)
    if not keytool:
        log("未找到 keytool，将使用 uber-apk-signer 内置 Debug 签名")
        return
    log("正在生成 debug.keystore ...")
    cmd = [
        str(keytool),
        "-genkeypair",
        "-keystore",
        str(DEBUG_KEYSTORE),
        "-storepass",
        "android",
        "-alias",
        "androiddebugkey",
        "-keypass",
        "android",
        "-keyalg",
        "RSA",
        "-keysize",
        "2048",
        "-validity",
        "10000",
        "-dname",
        "CN=Android Debug,O=Android,C=US",
    ]
    run_cmd(cmd, log)
    log("debug.keystore 已生成")


def ensure_tools(log) -> Path:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not APKTOOL_JAR.exists() or APKTOOL_JAR.stat().st_size < 1000:
        download_file(APKTOOL_URL, APKTOOL_JAR, log, "apktool 2.9.3")
    if not SIGNER_JAR.exists() or SIGNER_JAR.stat().st_size < 1000:
        download_file(SIGNER_URL, SIGNER_JAR, log, "uber-apk-signer")

    java = find_java()
    if java is None:
        zpath = TOOLS_DIR / "jre17.zip"
        last_err: Exception | None = None
        for url in JRE_URLS:
            try:
                download_file(url, zpath, log, "便携 JRE 17（约 40MB，仅首次）")
                last_err = None
                break
            except Exception as exc:
                last_err = exc
                log(f"下载失败，尝试备用地址: {exc}")
        if last_err is not None and not zpath.exists():
            raise last_err
        _extract_jre_zip(zpath, log)
        java = find_java()
    if java is None:
        raise RuntimeError("未找到 Java，请安装 JDK 17+ 或检查 tools/jre")

    generate_debug_keystore(java, log)
    log(f"Java: {java}")
    return java


def _iter_adb_candidates() -> list[Path]:
    found: list[Path] = []
    found.append(ADB_EXE)
    for env in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(env)
        if val:
            found.append(Path(val) / "platform-tools" / "adb.exe")
    local = os.environ.get("LOCALAPPDATA", "")
    home = os.environ.get("USERPROFILE", "")
    found.append(Path(local) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
    found.append(Path(home) / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe")
    which = shutil.which("adb")
    if which:
        found.append(Path(which))
    return found


def find_adb() -> Path | None:
    for p in _iter_adb_candidates():
        if p and p.is_file():
            return p
    return None


def _extract_platform_tools(zpath: Path, log) -> None:
    log("正在解压 Android platform-tools ...")
    staging = TOOLS_DIR / "_pt_staging"
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(staging)
    adb_exe = next(staging.rglob("adb.exe"), None)
    if not adb_exe:
        raise RuntimeError("platform-tools 压缩包中未找到 adb.exe")
    root = adb_exe.parent
    if ADB_DIR.exists():
        shutil.rmtree(ADB_DIR, ignore_errors=True)
    shutil.move(str(root), str(ADB_DIR))
    shutil.rmtree(staging, ignore_errors=True)
    zpath.unlink(missing_ok=True)
    log(f"adb 已就绪: {ADB_EXE}")


def ensure_adb(log) -> Path:
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    adb = find_adb()
    if adb:
        log(f"adb: {adb}")
        return adb
    zpath = TOOLS_DIR / "platform-tools.zip"
    download_file(PLATFORM_TOOLS_URL, zpath, log, "Android platform-tools（adb，仅首次）")
    _extract_platform_tools(zpath, log)
    adb = find_adb()
    if adb is None:
        raise RuntimeError("未找到 adb，请检查 tools/platform-tools")
    return adb


# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------
def run_cmd(cmd: list[str], log, cwd: Path | None = None) -> None:
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=str(cwd) if cwd else None,
        creationflags=CREATE_NO_WINDOW,
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            line = raw.decode("gbk", errors="replace")
        text = line.rstrip("\r\n")
        if text:
            log(text)
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"命令失败，退出码 {code}")


def adb_output(
    adb: Path,
    args: list[str],
    device: str | None = None,
    check: bool = True,
) -> str:
    cmd = [str(adb)]
    if device:
        cmd.extend(["-s", device])
    cmd.extend(args)
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    raw = proc.stdout or b""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    text = text.replace("\r\n", "\n")
    if check and proc.returncode != 0:
        raise RuntimeError(text.strip() or f"adb 失败，退出码 {proc.returncode}")
    return text


def adb_run(adb: Path, args: list[str], device: str | None, log) -> None:
    cmd = [str(adb)]
    if device:
        cmd.extend(["-s", device])
    cmd.extend(args)
    run_cmd(cmd, log)


# ---------------------------------------------------------------------------
# Phone APK pull (提包)
# ---------------------------------------------------------------------------
def list_adb_devices(adb: Path) -> list[tuple[str, str]]:
    text = adb_output(adb, ["devices"])
    devices: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("List of"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append((parts[0], parts[1]))
    return devices


def parse_package_list(text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("package:"):
            continue
        body = line[len("package:") :]
        if "=" not in body:
            continue
        path, pkg = body.rsplit("=", 1)
        items.append((pkg.strip(), path.strip()))
    items.sort(key=lambda x: x[0].lower())
    return items


def list_installed_packages(
    adb: Path, device: str, third_party_only: bool = True
) -> list[tuple[str, str]]:
    args = ["shell", "pm", "list", "packages", "-f"]
    if third_party_only:
        args.append("-3")
    text = adb_output(adb, args, device)
    items = parse_package_list(text)
    if items:
        return items
    raise RuntimeError("未读到应用列表。请确认手机已授权 USB 调试。")


def get_apk_paths(adb: Path, device: str, package: str) -> list[str]:
    text = adb_output(adb, ["shell", "pm", "path", package], device)
    paths: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            paths.append(line[len("package:") :].strip())
    if not paths:
        raise RuntimeError(f"找不到 {package} 的安装路径（应用可能已卸载）")
    return paths


def get_foreground_package(adb: Path, device: str) -> str:
    probes = (
        ["shell", "dumpsys", "window", "displays"],
        ["shell", "dumpsys", "activity", "activities"],
        ["shell", "dumpsys", "activity", "top"],
    )
    keys = (
        "mCurrentFocus",
        "mFocusedApp",
        "topResumedActivity",
        "mResumedActivity",
    )
    for args in probes:
        text = adb_output(adb, args, device, check=False)
        for line in text.splitlines():
            if not any(k in line for k in keys):
                continue
            m = PKG_IN_FOCUS_RE.search(line)
            if m:
                return m.group(1)
    raise RuntimeError("无法识别前台应用，请先在手机上打开目标 App，或在列表里手动选择")


def merge_split_apks(apk_files: list[Path], output: Path, log) -> Path:
    if len(apk_files) == 1:
        if apk_files[0].resolve() != output.resolve():
            shutil.copy2(apk_files[0], output)
            log(f"单包应用，已复制: {output.name}")
        return output

    def _order(p: Path) -> tuple[int, str]:
        name = p.name.lower()
        if name == "base.apk" or name.endswith("-base.apk"):
            return (0, name)
        return (1, name)

    ordered = sorted(apk_files, key=_order)
    log(f"正在合并 {len(ordered)} 个分包 -> {output.name}")
    seen: set[str] = set()
    with zipfile.ZipFile(output, "w") as out_z:
        for apk in ordered:
            with zipfile.ZipFile(apk, "r") as in_z:
                for info in in_z.infolist():
                    name = info.filename
                    if not name or name.endswith("/") or name in seen:
                        continue
                    seen.add(name)
                    data = in_z.read(name)
                    dest = zipfile.ZipInfo(filename=name)
                    dest.compress_type = info.compress_type
                    dest.date_time = info.date_time
                    dest.external_attr = info.external_attr
                    out_z.writestr(dest, data)
    log(f"合并完成，共 {len(seen)} 个文件")
    return output


def _obb_dirs(package: str) -> list[str]:
    return [
        f"/sdcard/Android/obb/{package}",
        f"/storage/emulated/0/Android/obb/{package}",
    ]


def pull_obb(adb: Path, device: str, package: str, dest: Path, log) -> bool:
    for remote in _obb_dirs(package):
        listing = adb_output(
            adb, ["shell", "ls", "-1", remote], device, check=False
        )
        low = listing.lower()
        if "no such file" in low or "not found" in low or not listing.strip():
            continue
        if "permission denied" in low:
            log(f"OBB 目录无权限: {remote}")
            continue
        target = dest / "obb"
        target.mkdir(parents=True, exist_ok=True)
        log(f"正在提取 OBB: {remote}")
        adb_run(adb, ["pull", remote, str(target)], device, log)
        return True
    log("未发现 OBB 扩展包（多数游戏没有）")
    return False


def _data_roots(package: str) -> list[str]:
    return [
        f"/sdcard/Android/data/{package}",
        f"/storage/emulated/0/Android/data/{package}",
    ]


DATA_ALWAYS = ("files", "cache")
DATA_NAME_HINTS = (
    "lebian",
    "update",
    "patch",
    "download",
    "hotfix",
    "hotupdate",
    "respatch",
    "ota",
)


def _ls_remote(adb: Path, device: str, remote: str) -> tuple[str, list[str]]:
    text = adb_output(adb, ["shell", "ls", "-1", remote], device, check=False)
    low = text.lower()
    if "permission denied" in low:
        return "denied", []
    if "no such file" in low or "not found" in low:
        return "missing", []
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("ls:") or line in {".", ".."}:
            continue
        names.append(line)
    return "ok", names


def _want_data_subdir(name: str) -> bool:
    low = name.lower()
    if low in DATA_ALWAYS or low == "code_cache":
        return True
    return any(key in low for key in DATA_NAME_HINTS)


def _pull_remote_into(adb: Path, device: str, remote: str, parent: Path, log) -> bool:
    parent.mkdir(parents=True, exist_ok=True)
    log(f"正在提取应用数据: {remote}")
    try:
        adb_run(adb, ["pull", remote, str(parent)], device, log)
        return True
    except RuntimeError as exc:
        log(f"提取失败: {remote} ({exc})")
        return False


def pull_app_data(adb: Path, device: str, package: str, dest: Path, log) -> bool:
    parent = dest / "appdata"
    pulled = False
    denied = False
    for root in _data_roots(package):
        status, names = _ls_remote(adb, device, root)
        if status == "missing":
            continue
        if status == "denied":
            denied = True
            log(f"应用数据目录无权限（Android 11+ 常见）: {root}")
            for sub in DATA_ALWAYS:
                remote = f"{root}/{sub}"
                sub_status, _ = _ls_remote(adb, device, remote)
                if sub_status == "ok":
                    pulled = _pull_remote_into(adb, device, remote, parent, log) or pulled
            if pulled:
                break
            continue
        targets = [n for n in names if _want_data_subdir(n)]
        if not targets:
            targets = [n for n in names if n in DATA_ALWAYS]
        if not targets:
            for sub in DATA_ALWAYS:
                sub_status, _ = _ls_remote(adb, device, f"{root}/{sub}")
                if sub_status == "ok":
                    targets.append(sub)
        if not targets:
            log(f"{root} 下没有 files/cache/热更目录")
            continue
        for name in targets:
            local_hit = parent / name
            if local_hit.exists() and any(local_hit.rglob("*")):
                continue
            pulled = _pull_remote_into(adb, device, f"{root}/{name}", parent, log) or pulled
        if pulled:
            break
    if _pull_private_via_runas(adb, device, package, dest, log):
        pulled = True
    if pulled:
        log(f"应用数据已保存: {parent}")
        return True
    if denied:
        log(
            "未提取到应用数据。Android 11+ 常拦截 /Android/data；"
            "可在手机文件管理器中授权后手动拷贝，或先装 DebugApk 再提。"
        )
    else:
        log("未发现应用数据目录（可能尚未启动过游戏或未下载热更）")
    return False


def _pull_private_via_runas(
    adb: Path, device: str, package: str, dest: Path, log
) -> bool:
    probe = adb_output(adb, ["shell", "run-as", package, "ls"], device, check=False)
    low = probe.lower()
    if "not debuggable" in low:
        log("应用未开启 debuggable，跳过 /data/data 私有目录")
        return False
    if any(s in low for s in ("unknown package", "permission denied", "run-as:")):
        return False
    out_dir = dest / "appdata" / "private"
    out_dir.mkdir(parents=True, exist_ok=True)
    tar_path = dest / "appdata" / "_private.tar"
    cmd = [str(adb)]
    if device:
        cmd.extend(["-s", device])
    cmd.extend(
        [
            "exec-out",
            "run-as",
            package,
            "sh",
            "-c",
            "tar c files cache 2>/dev/null || tar c files 2>/dev/null || tar c cache 2>/dev/null",
        ]
    )
    log("正在通过 run-as 提取私有 files/cache（仅 debuggable）...")
    try:
        with open(tar_path, "wb") as out:
            proc = subprocess.run(
                cmd,
                stdout=out,
                stderr=subprocess.PIPE,
                creationflags=CREATE_NO_WINDOW,
            )
    except Exception as exc:
        tar_path.unlink(missing_ok=True)
        log(f"run-as 提取失败: {exc}")
        return False
    if proc.returncode != 0 or not tar_path.is_file() or tar_path.stat().st_size < 64:
        err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
        tar_path.unlink(missing_ok=True)
        if err:
            log(f"run-as 提取失败: {err}")
        return False
    try:
        with tarfile.open(tar_path, "r") as tf:
            try:
                tf.extractall(out_dir, filter="data")
            except TypeError:
                tf.extractall(out_dir)
    except tarfile.TarError as exc:
        log(f"私有目录压缩包无法解开: {exc}")
        tar_path.unlink(missing_ok=True)
        return False
    tar_path.unlink(missing_ok=True)
    log(f"已提取私有目录: {out_dir}")
    return True


def pull_installed_apk(
    adb: Path,
    device: str,
    package: str,
    merge: bool,
    with_obb: bool,
    with_data: bool,
    log,
) -> Path:
    paths = get_apk_paths(adb, device, package)
    dest = PULL_DIR / package
    dest.mkdir(parents=True, exist_ok=True)
    log(f"安装路径 {len(paths)} 个:")
    pulled: list[Path] = []
    for remote in paths:
        name = Path(remote.replace("\\", "/")).name or "base.apk"
        local = dest / name
        log(f"  {remote}")
        adb_run(adb, ["pull", remote, str(local)], device, log)
        if not local.is_file():
            raise RuntimeError(f"提取失败: {remote}")
        pulled.append(local)
    result = dest / f"{package}.apk"
    if merge:
        merge_split_apks(pulled, result, log)
    elif len(pulled) == 1:
        shutil.copy2(pulled[0], result)
    if with_obb:
        pull_obb(adb, device, package, dest, log)
    if with_data:
        pull_app_data(adb, device, package, dest, log)
    if result.is_file():
        log(f"提包完成: {result}")
        return result
    if pulled:
        log(f"提包完成（未合并）: {dest}")
        return pulled[0]
    raise RuntimeError("没有提取到任何 APK")


# ---------------------------------------------------------------------------
# Merge appdata (files / hot-update) into decompiled APK
# 乐变: Android/data/<pkg>/files  <->  apk 内 assets/
# ---------------------------------------------------------------------------
MERGE_SKIP_DIRS = {
    "cache",
    "code_cache",
    "obb",
    ".thumbnails",
    "lost+found",
    "__macosx",
}
YOO_CACHE_DIR_NAMES = frozenset(
    {"cachebundlefiles", "cacherawfiles", "cachefiles"}
)
# 普通 ZIP/APK 中央目录偏移是 32 位，超过后签名器会报 offset 4294967295
ZIP32_MAX_BYTES = 4 * 1024 * 1024 * 1024 - 1
# Windows zipalign 用 32 位 signed long 做 ftell，超过 2GB 会 could not execute zipalign
ZIPALIGN_WIN_MAX_BYTES = 2 * 1024 * 1024 * 1024
MERGE_SKIP_SUFFIX = {
    ".tmp",
    ".temp",
    ".lock",
    ".crdownload",
    ".download",
    ".apk",
    ".dex",
    ".odex",
    ".vdex",
    ".jar",
    ".so.bak",
}
ABI_DIRS = {"arm64-v8a", "armeabi-v7a", "armeabi", "x86", "x86_64"}


def guess_appdata_dir(apk: Path | None, package: str = "") -> Path | None:
    candidates: list[Path] = []
    if apk:
        candidates.append(apk.parent / "appdata")
        candidates.append(apk.parent)
        if apk.parent.name != "pulled":
            candidates.append(PULL_DIR / apk.parent.name / "appdata")
        candidates.append(PULL_DIR / apk.stem / "appdata")
    if package:
        candidates.append(PULL_DIR / package / "appdata")
    seen: set[Path] = set()
    for raw in candidates:
        try:
            p = raw.resolve()
        except OSError:
            p = raw
        if p in seen:
            continue
        seen.add(p)
        if _looks_like_appdata(p):
            return p
    return None


def _looks_like_appdata(path: Path) -> bool:
    if not path.is_dir():
        return False
    if path.name.lower() == "appdata" and any(path.iterdir()):
        return True
    names = {c.name.lower() for c in path.iterdir() if c.is_dir()}
    return bool(names & {"files", "cache", "private"})


def _is_tiny_stub(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size <= 8
    except OSError:
        return False


def _unwrap_files_root(src: Path) -> Path:
    cur = src
    for _ in range(6):
        if not cur.is_dir():
            return src
        if (cur / "bin" / "Data").exists() or (cur / "yoo").is_dir():
            return cur
        if (cur / "assets" / "bin").exists() or (cur / "assets" / "yoo").is_dir():
            return cur / "assets"
        if (cur / "assets").is_dir() and any((cur / "assets").iterdir()):
            kids = [p.name.lower() for p in cur.iterdir() if p.is_dir()]
            if kids == ["assets"] or set(kids) <= {"assets", "cache"}:
                return cur / "assets"
        android = cur / "Android" / "data"
        if android.is_dir():
            pkgs = [p for p in android.iterdir() if p.is_dir()]
            if len(pkgs) == 1 and (pkgs[0] / "files").is_dir():
                cur = pkgs[0] / "files"
                continue
        children = [p for p in cur.iterdir() if p.is_dir() and p.name.lower() not in MERGE_SKIP_DIRS]
        if len(children) == 1 and children[0].name.lower() in {"files", "0"}:
            cur = children[0]
            continue
        break
    return cur


def _iter_merge_sources(appdata: Path) -> list[tuple[str, Path]]:
    found: list[tuple[str, Path]] = []
    if not appdata.is_dir():
        return found
    # 若用户直接选了 files 目录
    if appdata.name.lower() == "files" or (appdata / "bin" / "Data").exists() or (appdata / "yoo").is_dir():
        found.append(("files", _unwrap_files_root(appdata)))
        return found
    for name in ("files",):
        p = appdata / name
        if p.is_dir():
            found.append((name, _unwrap_files_root(p)))
    private_files = appdata / "private" / "files"
    if private_files.is_dir():
        found.append(("private/files", _unwrap_files_root(private_files)))
    if not found:
        # 热更目录直接当资源根（排除 cache）
        extras = [
            p
            for p in appdata.iterdir()
            if p.is_dir() and p.name.lower() not in MERGE_SKIP_DIRS | {"private"}
        ]
        for p in extras:
            found.append((p.name, _unwrap_files_root(p)))
    return found


def _should_skip_file(path: Path, skip_yoo_cache: bool = False) -> bool:
    if path.suffix.lower() in MERGE_SKIP_SUFFIX:
        return True
    parts = {x.lower() for x in path.parts}
    if parts & MERGE_SKIP_DIRS:
        return True
    if skip_yoo_cache and parts & YOO_CACHE_DIR_NAMES:
        return True
    return False


def _is_yoo_cache_path(path: Path) -> bool:
    return bool({x.lower() for x in path.parts} & YOO_CACHE_DIR_NAMES)


def _dir_size_bytes(root: Path) -> int:
    total = 0
    for f in root.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def slim_yooasset_cache(decode_dir: Path, log) -> dict[str, int]:
    """从反编译工程移出 YooAsset 缓存目录，避免回编译 APK 超过 4GB。"""
    stats = {"dirs": 0, "bytes": 0}
    assets = decode_dir / "assets"
    if not assets.is_dir():
        return stats
    targets: list[Path] = []
    for path in assets.rglob("*"):
        if path.is_dir() and path.name.lower() in YOO_CACHE_DIR_NAMES:
            targets.append(path)
    targets.sort(key=lambda p: len(p.parts))
    kept: list[Path] = []
    for path in targets:
        if any(path == k or k in path.parents for k in kept):
            continue
        kept.append(path)
    for path in kept:
        size = _dir_size_bytes(path)
        rel = path.relative_to(decode_dir)
        shutil.rmtree(path, ignore_errors=True)
        if path.exists():
            log(f"未能删除 YooAsset 缓存: {rel}")
            continue
        stats["dirs"] += 1
        stats["bytes"] += size
        log(
            f"已移出 YooAsset 缓存 {rel}（{size / (1024 ** 3):.2f} GB）。"
            "完整资源请留在手机 Android/data/<包名>/files/yoo/，不要打进 APK。"
        )
    return stats


def assert_apk_within_zip32(path: Path) -> None:
    size = path.stat().st_size
    if size <= ZIP32_MAX_BYTES:
        return
    raise RuntimeError(
        f"未签名 APK 已 {size / (1024 ** 3):.2f} GB，超过 ZIP/APK 4GB 上限，无法签名。"
        "请先移出 assets/yoo/*/CacheBundleFiles 和 CacheRawFiles 后再回编译。"
    )


def _merge_dest(decode_dir: Path, rel: Path) -> Path:
    parts = rel.parts
    if parts and parts[0].lower() == "lib" and len(parts) >= 3 and parts[1] in ABI_DIRS:
        return decode_dir.joinpath(*parts)
    if parts and parts[0].lower() == "assets":
        return decode_dir.joinpath(*parts)
    return decode_dir / "assets" / rel


def merge_appdata_into_decode(
    appdata: Path,
    decode_dir: Path,
    log,
    skip_cache_if_over_4g: bool = True,
) -> dict[str, int]:
    if not decode_dir.is_dir() or not (decode_dir / "AndroidManifest.xml").exists():
        raise RuntimeError("请先反编译 APK，再合并应用数据")
    if not appdata.is_dir():
        raise RuntimeError(f"应用数据目录不存在: {appdata}")
    sources = _iter_merge_sources(appdata)
    if not sources:
        raise RuntimeError(
            f"{appdata} 下没有 files / 热更资源。请先在提包页勾选「应用数据」并提取。"
        )
    planned: list[tuple[Path, Path, bool, int]] = []
    cache_bytes = 0
    other_new_bytes = 0
    stats = {
        "copied": 0,
        "overwritten": 0,
        "skipped": 0,
        "stub_skip": 0,
        "cache_skip": 0,
        "cache_skip_bytes": 0,
        "skipped_cache": 0,
    }
    for label, root in sources:
        log(f"合并来源 [{label}]: {root}")
        for src in root.rglob("*"):
            if not src.is_file() or _should_skip_file(src):
                if src.is_file():
                    stats["skipped"] += 1
                continue
            rel = src.relative_to(root)
            dest = _merge_dest(decode_dir, rel)
            try:
                size = src.stat().st_size
            except OSError:
                size = 0
            is_cache = _is_yoo_cache_path(src)
            if is_cache:
                cache_bytes += size
            elif not dest.exists() or _is_tiny_stub(dest):
                other_new_bytes += size
            planned.append((src, dest, is_cache, size))

    decode_size = _dir_size_bytes(decode_dir)
    projected = decode_size + other_new_bytes + cache_bytes
    skip_cache = bool(
        skip_cache_if_over_4g and cache_bytes > 0 and projected > ZIP32_MAX_BYTES
    )
    log(
        f"体积预估: 工程现有 {decode_size / (1024 ** 3):.2f} GB，"
        f"待合并 {other_new_bytes / (1024 ** 3):.2f} GB，"
        f"YooAsset 缓存 {cache_bytes / (1024 ** 3):.2f} GB，"
        f"合计约 {projected / (1024 ** 3):.2f} GB（APK 上限 4GB）"
    )
    if skip_cache:
        log(
            "已勾选「超过 4GB 时跳过缓存」：本次不把 CacheBundleFiles / CacheRawFiles 打进 APK。"
            "装机后请点「推送缓存到手机」。"
        )
    elif projected > ZIP32_MAX_BYTES:
        log(
            "预估将超过 4GB。未勾选取舍时仍会全部合并，但回编译大概率无法签名。"
        )

    for src, dest, is_cache, size in planned:
        if is_cache and skip_cache:
            stats["cache_skip"] += 1
            stats["cache_skip_bytes"] += size
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if _is_tiny_stub(src) and not _is_tiny_stub(dest):
                stats["stub_skip"] += 1
                continue
            shutil.copy2(src, dest)
            stats["overwritten"] += 1
        else:
            shutil.copy2(src, dest)
            stats["copied"] += 1
    stats["skipped_cache"] = 1 if skip_cache else 0
    log(
        f"合并完成: 新增 {stats['copied']}，覆盖 {stats['overwritten']}，"
        f"跳过占位 {stats['stub_skip']}，跳过缓存 {stats['cache_skip']}，"
        f"跳过其它 {stats['skipped']}"
    )
    log("已写入反编译工程的 assets/（以及 files 里的 lib/<abi>/*.so）。请再点回编译。")
    return stats


def find_local_yoo_dir(appdata: Path) -> Path | None:
    if not appdata.is_dir():
        return None
    for cand in (
        appdata / "files" / "yoo",
        appdata / "yoo",
        appdata / "private" / "files" / "yoo",
    ):
        if cand.is_dir():
            return cand
    for _label, root in _iter_merge_sources(appdata):
        if (root / "yoo").is_dir():
            return root / "yoo"
        if root.name.lower() == "yoo":
            return root
    return None


def iter_local_yoo_cache_dirs(yoo: Path) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in yoo.rglob("*"):
        if path.is_dir() and path.name.lower() in YOO_CACHE_DIR_NAMES:
            found.append((path, path.relative_to(yoo).as_posix()))
    found.sort(key=lambda item: item[1].count("/"))
    return found


def push_yoo_cache_to_device(
    adb: Path,
    device: str,
    package: str,
    appdata: Path,
    log,
) -> Path:
    if not package:
        raise RuntimeError("缺少包名，无法确定手机上的 Android/data/<包名>/files/yoo")
    yoo = find_local_yoo_dir(appdata)
    if yoo is None:
        raise RuntimeError(
            f"{appdata} 下没有 yoo 目录。请先在提包页勾选「应用数据」并提取。"
        )
    caches = iter_local_yoo_cache_dirs(yoo)
    if not caches:
        raise RuntimeError(f"{yoo} 下没有 CacheBundleFiles / CacheRawFiles")
    remote_root = f"/sdcard/Android/data/{package}/files/yoo"
    total = sum(_dir_size_bytes(p) for p, _rel in caches)
    log(
        f"将推送 {len(caches)} 个缓存目录，约 {total / (1024 ** 3):.2f} GB → {remote_root}"
    )
    adb_run(adb, ["shell", "mkdir", "-p", remote_root], device, log)
    for local, rel in caches:
        remote = f"{remote_root}/{rel}"
        parent = remote.rsplit("/", 1)[0]
        adb_run(adb, ["shell", "mkdir", "-p", parent], device, log)
        cache_gb = _dir_size_bytes(local) / (1024 ** 3)
        log(f"正在推送 {rel}（{cache_gb:.2f} GB）")
        adb_run(adb, ["push", str(local), remote], device, log)
    log(f"缓存已推送到手机: {remote_root}")
    return Path(remote_root)


# ---------------------------------------------------------------------------
# Manifest / resource patch
# ---------------------------------------------------------------------------
def _read_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def patch_apktool_yml(decode_dir: Path, package: str, log) -> None:
    yml = decode_dir / "apktool.yml"
    if not yml.exists() or not package:
        return
    text = _read_text(yml)
    if re.search(r"(?m)^\s*renameManifestPackage:", text):
        text = re.sub(
            r"(?m)^(\s*renameManifestPackage:\s*).*$",
            rf"\1{package}",
            text,
        )
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += f"  renameManifestPackage: {package}\n"
    _write_text(yml, text)
    log(f"已设置 renameManifestPackage = {package}")


def patch_manifest_package(manifest: Path, package: str, log) -> None:
    text = _read_text(manifest)
    new_text, n = re.subn(
        r'(<manifest\b[^>]*\bpackage=")[^"]+"',
        rf"\g<1>{package}\"",
        text,
        count=1,
    )
    if n:
        _write_text(manifest, new_text)
        log(f"已修改 AndroidManifest package = {package}")


def set_debuggable(manifest: Path, log) -> None:
    text = _read_text(manifest)
    if re.search(r'android:debuggable\s*=\s*"[^"]*"', text):
        text = re.sub(
            r'android:debuggable\s*=\s*"[^"]*"',
            'android:debuggable="true"',
            text,
        )
    else:
        text = re.sub(
            r"(<application\b)",
            r'\1 android:debuggable="true"',
            text,
            count=1,
        )
    _write_text(manifest, text)
    log("已设置 android:debuggable=true")


def patch_app_name(decode_dir: Path, app_name: str, log) -> None:
    updated = 0
    for xml in decode_dir.glob("res/values*/strings.xml"):
        text = _read_text(xml)
        new_text, n = re.subn(
            r'(<string\s+name="app_name">)[^<]*(</string>)',
            rf"\g<1>{_xml_escape(app_name)}\g<2>",
            text,
        )
        if n:
            _write_text(xml, new_text)
            updated += n
    manifest = decode_dir / "AndroidManifest.xml"
    if manifest.exists():
        text = _read_text(manifest)
        new_text, n = re.subn(
            r'(<application\b[^>]*\bandroid:label=")(?!@)[^"]+"',
            rf"\g<1>{_xml_escape(app_name)}\"",
            text,
            count=1,
        )
        if n:
            _write_text(manifest, new_text)
            updated += n
    if updated:
        log(f"已修改应用名: {app_name}（{updated} 处）")
    else:
        log("未找到 app_name，已写入 assets/game_info.json")


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


META_GAME_KEYS = (
    "GAME_ID",
    "game_id",
    "gameId",
    "TY_GAME_ID",
    "app_id",
    "APP_ID",
)
META_CHANNEL_KEYS = (
    "CHANNEL",
    "CHANNEL_ID",
    "channel",
    "channelId",
    "CHANNEL_NO",
    "app_channel",
)


def patch_manifest_meta(manifest: Path, game_id: str, channel: str, log) -> None:
    text = _read_text(manifest)

    def replace_meta(src: str, keys: tuple[str, ...], value: str) -> str:
        if not value:
            return src
        for key in keys:
            src, n = re.subn(
                rf'(<meta-data\b[^>]*android:name="{re.escape(key)}"[^>]*android:value=")[^"]*"',
                rf"\g<1>{_xml_escape(value)}\"",
                src,
            )
            if n == 0:
                src, n = re.subn(
                    rf'(<meta-data\b[^>]*android:value=")[^"]*("[^>]*android:name="{re.escape(key)}")',
                    rf"\g<1>{_xml_escape(value)}\2",
                    src,
                )
        return src

    new_text = replace_meta(text, META_GAME_KEYS, game_id)
    new_text = replace_meta(new_text, META_CHANNEL_KEYS, channel)
    if new_text != text:
        _write_text(manifest, new_text)
        log("已更新 AndroidManifest meta-data")


def write_game_info(decode_dir: Path, game_id: str, channel: str, package: str, app_name: str, log) -> None:
    assets = decode_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    info = {
        "gameId": game_id,
        "channel": channel,
        "package": package,
        "appName": app_name,
    }
    path = assets / "game_info.json"
    _write_text(path, json.dumps(info, ensure_ascii=False, indent=2))
    log(f"已写入 {path.relative_to(decode_dir)}")


FORCE_GLES_FLAG = "-force-gles"

FORCE_GLES_SMALI = """
.method protected updateUnityCommandLineArguments(Ljava/lang/String;)Ljava/lang/String;
    .locals 2

    const-string v0, "-force-gles"

    if-nez p1, :cond_has_arg

    return-object v0

    :cond_has_arg
    invoke-virtual {p1}, Ljava/lang/String;->length()I

    move-result v1

    if-eqz v1, :cond_empty

    const-string v1, "-force-gles"

    invoke-virtual {p1, v1}, Ljava/lang/String;->contains(Ljava/lang/CharSequence;)Z

    move-result v1

    if-nez v1, :cond_already

    new-instance v1, Ljava/lang/StringBuilder;

    invoke-direct {v1}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v1, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    const-string p1, " "

    invoke-virtual {v1, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v1, v0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v1}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object p1

    return-object p1

    :cond_already
    return-object p1

    :cond_empty
    return-object v0
.end method
""".strip()

UPDATE_CMDLINE_RE = re.compile(
    r"\.method[^\n]*updateUnityCommandLineArguments\(Ljava/lang/String;\)Ljava/lang/String;.*?\.end method",
    re.S,
)

VULKAN_FEATURES = (
    "android.hardware.vulkan.level",
    "android.hardware.vulkan.version",
    "android.hardware.vulkan.compute",
)

BOOT_VULKAN_KEYS = {
    "android-disable-vulkan": "1",
    "force-gles": "1",
}


def force_disable_vulkan(decode_dir: Path, log) -> None:
    n_smali = _patch_unity_force_gles_smali(decode_dir, log)
    _patch_boot_config_no_vulkan(decode_dir, log)
    manifest = decode_dir / "AndroidManifest.xml"
    if manifest.exists():
        _patch_manifest_no_vulkan(manifest, log)
    if n_smali == 0 and not (decode_dir / "assets" / "bin" / "Data" / "boot.config").exists():
        log("未发现 Unity 启动入口，已尽量改 Manifest；若仍走 Vulkan，需要该引擎自己的关闭开关")


def _patch_unity_force_gles_smali(decode_dir: Path, log) -> int:
    count = 0
    for smali in decode_dir.rglob("*.smali"):
        text = _read_text(smali)
        if "updateUnityCommandLineArguments(Ljava/lang/String;)Ljava/lang/String;" not in text:
            continue
        new_text, n = UPDATE_CMDLINE_RE.subn(FORCE_GLES_SMALI, text, count=1)
        if n and new_text != text:
            _write_text(smali, new_text)
            count += 1
            log(f"已注入 -force-gles: {smali.relative_to(decode_dir)}")
    return count


def apply_boot_vulkan_keys(text: str) -> str:
    lines = text.splitlines()
    keys_seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in BOOT_VULKAN_KEYS:
                out.append(f"{key}={BOOT_VULKAN_KEYS[key]}")
                keys_seen.add(key)
                continue
        out.append(line)
    for key, val in BOOT_VULKAN_KEYS.items():
        if key not in keys_seen:
            out.append(f"{key}={val}")
    return "\n".join(out).rstrip() + "\n"


def _patch_boot_config_no_vulkan(decode_dir: Path, log) -> None:
    boot = decode_dir / "assets" / "bin" / "Data" / "boot.config"
    if not boot.exists():
        return
    _write_text(boot, apply_boot_vulkan_keys(_read_text(boot)))
    log("已写入 boot.config：关闭 Vulkan，强制 GLES")


def ensure_gles_boot_config(decode_dir: Path | None, log) -> Path:
    """得到带 GLES 开关的 boot.config；工程里有则就地更新，没有则写临时文件。"""
    if decode_dir:
        boot = decode_dir / "assets" / "bin" / "Data" / "boot.config"
        if boot.is_file():
            _write_text(boot, apply_boot_vulkan_keys(_read_text(boot)))
            log(f"已更新工程 boot.config: {boot.relative_to(decode_dir)}")
            return boot
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT_DIR / "_gles_boot.config"
    _write_text(tmp, apply_boot_vulkan_keys(""))
    log("工程没有 boot.config，将只推送 GLES 开关到手机")
    return tmp


def push_gles_config_to_device(
    adb: Path,
    device: str,
    package: str,
    decode_dir: Path | None,
    log,
) -> str:
    if not package:
        raise RuntimeError("缺少包名，无法确定手机上的 Android/data/<包名>/files")
    local = ensure_gles_boot_config(decode_dir, log)
    remote_dir = f"/sdcard/Android/data/{package}/files/bin/Data"
    remote = f"{remote_dir}/boot.config"
    log(f"将推送 GLES 配置 → {remote}")
    adb_run(adb, ["shell", "mkdir", "-p", remote_dir], device, log)
    adb_run(adb, ["push", str(local), remote], device, log)
    probe = adb_output(adb, ["shell", "run-as", package, "ls"], device, check=False)
    low = probe.lower()
    if "not debuggable" in low or "unknown package" in low or "run-as:" in low:
        log("应用不可 run-as，跳过私有目录清理（需已装 DebugApk）")
    else:
        adb_output(
            adb,
            [
                "shell",
                "run-as",
                package,
                "sh",
                "-c",
                "rm -f shared_prefs/*ulkan* shared_prefs/*raphics* 2>/dev/null; true",
            ],
            device,
            check=False,
        )
        log("已尝试清理 Unity / Vulkan SharedPreferences（run-as）")
    adb_run(adb, ["shell", "am", "force-stop", package], device, log)
    log(f"已强制停止 {package}。请从 RenderDoc 重新启动，不要只点桌面图标。")
    return remote


LOGIN_PREF_NEEDLES = (
    "login",
    "logon",
    "logout",
    "prelogin",
    "tuyoo",
    "tysdk",
    "ty_sdk",
    "gamesdk",
    "token",
    "account",
    "userid",
    "userinfo",
    "username",
    "session",
    "passport",
    "oauth",
    "openid",
    "guest",
    "switchaccount",
    "switch_account",
)
LOGIN_KEEP_NAMES = frozenset({"yoo", "bin", "il2cpp", "lebian", "cache", "code_cache"})


def _is_login_cache_name(name: str) -> bool:
    low = name.lower().strip()
    if not low or low in LOGIN_KEEP_NAMES or "yoo" in low:
        return False
    return any(needle in low for needle in LOGIN_PREF_NEEDLES)


def _run_as_usable(adb: Path, device: str, package: str) -> tuple[bool, str]:
    text = adb_output(adb, ["shell", "run-as", package, "ls"], device, check=False)
    low = text.lower()
    if "not debuggable" in low:
        return False, "应用未开启 debuggable，请先安装 DebugApk"
    if "unknown package" in low or "permission denied" in low or "run-as:" in low:
        return False, (text.strip() or "run-as 不可用")
    return True, text


def _run_as_ls(adb: Path, device: str, package: str, remote_dir: str) -> list[str]:
    text = adb_output(
        adb, ["shell", "run-as", package, "ls", "-1", remote_dir], device, check=False
    )
    low = text.lower()
    if "no such file" in low or "not found" in low or "not a directory" in low:
        return []
    names: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("ls:") or line in {".", ".."}:
            continue
        names.append(line)
    return names


def clear_login_cache_on_device(adb: Path, device: str, package: str, log) -> str:
    if not package:
        raise RuntimeError("缺少包名")
    ok, reason = _run_as_usable(adb, device, package)
    if not ok:
        raise RuntimeError(reason)
    adb_run(adb, ["shell", "am", "force-stop", package], device, log)
    prefs = _run_as_ls(adb, device, package, "shared_prefs")
    root_files = _run_as_ls(adb, device, package, "files")
    pref_hits = [n for n in prefs if _is_login_cache_name(n)]
    file_hits = [n for n in root_files if _is_login_cache_name(n)]
    log(f"shared_prefs 共 {len(prefs)} 个，登录相关 {len(pref_hits)} 个")
    if root_files:
        log(f"files 根目录共 {len(root_files)} 项，登录相关 {len(file_hits)} 个（不会进入 yoo/）")
    removed: list[str] = []
    for name in pref_hits:
        adb_output(
            adb,
            ["shell", "run-as", package, "rm", "-f", f"shared_prefs/{name}"],
            device,
            check=False,
        )
        removed.append(f"shared_prefs/{name}")
        log(f"已删除 {name}")
    for name in file_hits:
        adb_output(
            adb,
            ["shell", "run-as", package, "rm", "-f", f"files/{name}"],
            device,
            check=False,
        )
        removed.append(f"files/{name}")
        log(f"已删除 files/{name}（仅根目录文件，不是目录）")
    yoo_priv = _run_as_ls(adb, device, package, "files/yoo")
    yoo_ext = adb_output(
        adb,
        ["shell", "ls", "-1", f"/sdcard/Android/data/{package}/files/yoo"],
        device,
        check=False,
    )
    if yoo_priv:
        log(f"私有 files/yoo 仍在（{len(yoo_priv)} 项），未删除资源缓存")
    if "no such file" not in yoo_ext.lower() and yoo_ext.strip():
        log("外部 Android/data/.../files/yoo 仍在，未删除资源缓存")
    if not removed:
        log("没有匹配到登录缓存文件（可能本来就没有，或命名不含常见关键字）")
        return f"{package}：未找到登录缓存，yoo 未动"
    return f"{package}：已删 {len(removed)} 个登录文件，yoo 未动"


def _patch_manifest_no_vulkan(manifest: Path, log) -> None:
    text = _read_text(manifest)
    changed = False
    for name in VULKAN_FEATURES:
        pat = rf'(<uses-feature\b[^>]*android:name="{re.escape(name)}"[^>]*)(/?>)'
        m = re.search(pat, text)
        if m:
            tag = m.group(0)
            if 'android:required="false"' not in tag:
                if re.search(r'android:required="[^"]*"', tag):
                    text = text.replace(
                        tag,
                        re.sub(r'android:required="[^"]*"', 'android:required="false"', tag),
                        1,
                    )
                else:
                    text = text.replace(
                        tag,
                        tag.replace(m.group(2), ' android:required="false"' + m.group(2)),
                        1,
                    )
                changed = True
        else:
            insert = (
                f'    <uses-feature android:name="{name}" android:required="false"/>\n'
            )
            text = re.sub(r"(<manifest\b[^>]*>\s*)", r"\1" + insert, text, count=1)
            changed = True
    if 'android:name="unity.command-line"' in text:
        text2 = re.sub(
            r'(<meta-data\b[^>]*android:name="unity.command-line"[^>]*android:value=")[^"]*"',
            rf'\g<1>{FORCE_GLES_FLAG}"',
            text,
        )
        if text2 != text:
            text = text2
            changed = True
    else:
        text = re.sub(
            r"(<application\b[^>]*>)",
            rf'\1\n        <meta-data android:name="unity.command-line" android:value="{FORCE_GLES_FLAG}"/>',
            text,
            count=1,
        )
        changed = True
    if changed:
        _write_text(manifest, text)
        log("已将 Manifest 中 Vulkan 标为非必需，并写入 unity.command-line=-force-gles")


def apply_app_info(
    decode_dir: Path,
    game_id: str,
    channel: str,
    package: str,
    app_name: str,
    debug: bool,
    log,
    disable_vulkan: bool = False,
    disable_lebian_hot: bool = False,
) -> None:
    manifest = decode_dir / "AndroidManifest.xml"
    if not manifest.exists():
        raise RuntimeError("反编译目录中没有 AndroidManifest.xml")
    if package:
        patch_apktool_yml(decode_dir, package, log)
        patch_manifest_package(manifest, package, log)
    if app_name:
        patch_app_name(decode_dir, app_name, log)
    if game_id or channel:
        patch_manifest_meta(manifest, game_id, channel, log)
        write_game_info(decode_dir, game_id, channel, package, app_name, log)
    if debug:
        set_debuggable(manifest, log)
    if disable_vulkan:
        force_disable_vulkan(decode_dir, log)
    if disable_lebian_hot:
        disable_lebian_hotupdate(decode_dir, log)


LEBIAN_HOTUPDATE_OFF = {
    "use_regeng": "false",
    "auto_check_newver_onstart": "false",
    "use_streaming": "false",
    "streaming_auto_start_bwbx": "false",
    "download_after_quit": "false",
}


def _set_lebian_setting(text: str, key: str, value: str) -> tuple[str, bool]:
    pat_kv = re.compile(
        rf'(<setting\b[^>]*\bkey="{re.escape(key)}"[^>]*\bvalue=")[^"]*"',
        re.I,
    )
    # 不能用 rf'...\"'：raw 字符串会把反斜杠写进 XML，变成 value="false\"
    new, n = pat_kv.subn(r"\g<1>" + value + '"', text, count=1)
    if n:
        return new, True
    pat_vk = re.compile(
        rf'(<setting\b[^>]*\bvalue=")[^"]*("[^>]*\bkey="{re.escape(key)}")',
        re.I,
    )
    new, n = pat_vk.subn(rf"\g<1>{value}\2", text, count=1)
    if n:
        return new, True
    if re.search(r"</settings\s*>", text, re.I):
        insert = f'    <setting key="{key}" value="{value}"/>\n'
        text = re.sub(r"</settings\s*>", insert + "</settings>", text, count=1, flags=re.I)
        return text, True
    return text, False


def disable_lebian_hotupdate(decode_dir: Path, log) -> None:
    files: list[Path] = []
    seen: set[Path] = set()
    preferred = decode_dir / "assets" / "lebian" / "globalSettings.xml"
    for path in [preferred, *decode_dir.glob("assets/**/globalSettings.xml")]:
        if not path.is_file():
            continue
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        files.append(path)
    if not files:
        log("未找到乐变 globalSettings.xml，跳过关闭热更（可能不是乐变包）")
        return
    for path in files:
        text = _read_text(path)
        # 旧版本写入过 value="false\"，先清掉再改开关
        text = re.sub(r'(value=")([^"\\]*)\\"', r'\1\2"', text)
        changed: list[str] = []
        for key, val in LEBIAN_HOTUPDATE_OFF.items():
            new_text, ok = _set_lebian_setting(text, key, val)
            if ok and new_text != text:
                changed.append(f"{key}={val}")
            text = new_text
        if changed:
            _write_text(path, text)
            log(f"已关闭乐变热更: {path.relative_to(decode_dir)}（{'，'.join(changed)}）")
        else:
            _write_text(path, text)
            log(f"乐变热更开关已是目标值: {path.relative_to(decode_dir)}")
    log("未改 use_lebian。装机后请清掉 Android/data/<包名>，或换新包名，避免本地 files 盖过包内资源。")


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------
class Workflow:
    def __init__(self, log) -> None:
        self.log = log
        self.java: Path | None = None
        self.apk_path: Path | None = None
        self.decode_dir: Path | None = None
        self.appdata_dir: Path | None = None

    def ensure(self) -> Path:
        if self.java is None or not self.java.is_file():
            self.java = ensure_tools(self.log)
        return self.java

    def set_apk(self, path: Path) -> None:
        self.apk_path = path
        self.decode_dir = WORK_DIR / path.stem
        guessed = guess_appdata_dir(path)
        self.appdata_dir = guessed if guessed else self.appdata_dir

    def decompile(self) -> None:
        java = self.ensure()
        if not self.apk_path or not self.apk_path.is_file():
            raise RuntimeError("请先拖入或选择一个 APK 文件")
        self.decode_dir = WORK_DIR / self.apk_path.stem
        if self.decode_dir.exists():
            self.log(f"清理旧目录: {self.decode_dir}")
            shutil.rmtree(self.decode_dir, ignore_errors=True)
        cmd = [
            str(java),
            "-Duser.language=en",
            "-Dfile.encoding=UTF-8",
            "-jar",
            str(APKTOOL_JAR),
            "d",
            "-f",
            str(self.apk_path),
            "-o",
            str(self.decode_dir),
        ]
        run_cmd(cmd, self.log)
        self.log(f"反编译完成: {self.decode_dir}")
        try:
            hits, packed = detect_packers(self.apk_path, self.decode_dir)
            self.log(format_detect_report(hits, packed).rstrip())
        except Exception as exc:
            self.log(f"壳识别失败: {exc}")

    def build_and_sign(self, app_info: dict, debug: bool, sign_mode: str) -> Path:
        java = self.ensure()
        if not self.decode_dir or not self.decode_dir.exists():
            raise RuntimeError("请先反编译 APK")
        if app_info.get("skip_cache_if_over_4g", True):
            decode_size = _dir_size_bytes(self.decode_dir)
            if decode_size > ZIP32_MAX_BYTES:
                slim = slim_yooasset_cache(self.decode_dir, self.log)
                if slim["dirs"]:
                    self.log(
                        f"工程 {decode_size / (1024 ** 3):.2f} GB，超过 4GB，"
                        f"已按选项移出 {slim['dirs']} 个 YooAsset 缓存目录"
                        f"（{slim['bytes'] / (1024 ** 3):.2f} GB）。"
                    )
        apply_app_info(
            self.decode_dir,
            app_info.get("game_id", ""),
            app_info.get("channel", ""),
            app_info.get("package", ""),
            app_info.get("app_name", ""),
            debug=debug,
            log=self.log,
            disable_vulkan=bool(app_info.get("disable_vulkan")),
            disable_lebian_hot=bool(app_info.get("disable_lebian_hot")),
        )
        stem = self.apk_path.stem if self.apk_path else self.decode_dir.name
        suffix = "_debug" if debug else ""
        unsigned = OUTPUT_DIR / f"{stem}{suffix}_unsigned.apk"
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if unsigned.exists():
            unsigned.unlink()
        cmd = [
            str(java),
            "-Duser.language=en",
            "-Dfile.encoding=UTF-8",
            "-jar",
            str(APKTOOL_JAR),
            "b",
            str(self.decode_dir),
            "-o",
            str(unsigned),
        ]
        run_cmd(cmd, self.log)
        assert_apk_within_zip32(unsigned)
        signed = self._sign(java, unsigned, debug=debug or sign_mode == "测试签名")
        if unsigned.exists() and unsigned != signed:
            unsigned.unlink(missing_ok=True)
        self.log(f"回编译完成: {signed}")
        return signed

    def _sign(self, java: Path, unsigned: Path, debug: bool) -> Path:
        out_dir = OUTPUT_DIR / "_signed_tmp"
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        size = unsigned.stat().st_size
        skip_align = sys.platform == "win32" and size >= ZIPALIGN_WIN_MAX_BYTES
        if skip_align:
            self.log(
                f"未签名 APK {size / (1024 ** 3):.2f} GB，超过 Windows zipalign 的 2GB 限制，"
                "将跳过对齐后直接签名。侧载/调试可装；上架商店才必须对齐。"
            )
        cmd = self._signer_cmd(java, unsigned, out_dir, debug, skip_align=skip_align)
        try:
            run_cmd(cmd, self.log)
        except RuntimeError:
            if skip_align:
                raise
            self.log("zipalign 失败，改跳过对齐后重试签名（侧载/调试通常仍可装）")
            if out_dir.exists():
                shutil.rmtree(out_dir, ignore_errors=True)
            out_dir.mkdir(parents=True, exist_ok=True)
            run_cmd(
                self._signer_cmd(java, unsigned, out_dir, debug, skip_align=True),
                self.log,
            )
        signed_files = list(out_dir.glob("*.apk"))
        if not signed_files:
            raise RuntimeError("签名后未找到 APK")
        stem = unsigned.stem.replace("_unsigned", "")
        final = OUTPUT_DIR / f"{stem}.apk"
        if final.exists():
            final.unlink()
        shutil.move(str(signed_files[0]), str(final))
        shutil.rmtree(out_dir, ignore_errors=True)
        return final

    def _signer_cmd(
        self,
        java: Path,
        unsigned: Path,
        out_dir: Path,
        debug: bool,
        skip_align: bool,
    ) -> list[str]:
        cmd = [
            str(java),
            "-jar",
            str(SIGNER_JAR),
            "-a",
            str(unsigned),
            "-o",
            str(out_dir),
            "--allowResign",
        ]
        if skip_align:
            cmd.append("--skipZipAlign")
        if debug and DEBUG_KEYSTORE.exists():
            cmd += [
                "--ks",
                str(DEBUG_KEYSTORE),
                "--ksAlias",
                "androiddebugkey",
                "--ksPass",
                "android",
                "--ksKeyPass",
                "android",
            ]
        else:
            cmd.append("--debug")
        return cmd


# ---------------------------------------------------------------------------
# Drag & drop
# ---------------------------------------------------------------------------
class DropTarget:
    """Windows WM_DROPFILES hook for Tk widgets."""

    def __init__(self, widget, callback) -> None:
        self.widget = widget
        self.callback = callback
        self._new_proc = None
        self._old_proc = None

    def attach(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import ctypes
            from ctypes import wintypes

            self.widget.update_idletasks()
            hwnd = int(self.widget.winfo_id())
            parent = ctypes.windll.user32.GetParent(hwnd)
            target = parent or hwnd

            WM_DROPFILES = 0x0233
            GWLP_WNDPROC = -4
            DragAcceptFiles = ctypes.windll.shell32.DragAcceptFiles
            DragQueryFileW = ctypes.windll.shell32.DragQueryFileW
            DragFinish = ctypes.windll.shell32.DragFinish
            DragAcceptFiles(target, True)

            LRESULT = ctypes.c_ssize_t
            WndProcType = ctypes.WINFUNCTYPE(
                LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
            )
            GetWindowLong = ctypes.windll.user32.GetWindowLongPtrW
            SetWindowLong = ctypes.windll.user32.SetWindowLongPtrW
            CallWindowProc = ctypes.windll.user32.CallWindowProcW
            self._old_proc = GetWindowLong(target, GWLP_WNDPROC)

            def wndproc(h, msg, wp, lp):
                if msg == WM_DROPFILES:
                    count = DragQueryFileW(wp, 0xFFFFFFFF, None, 0)
                    files = []
                    for i in range(count):
                        nchars = DragQueryFileW(wp, i, None, 0) + 1
                        buf = ctypes.create_unicode_buffer(nchars)
                        DragQueryFileW(wp, i, buf, nchars)
                        files.append(buf.value)
                    DragFinish(wp)
                    self.widget.after(0, lambda fs=files: self.callback(fs))
                    return 0
                return CallWindowProc(self._old_proc, h, msg, wp, lp)

            self._new_proc = WndProcType(wndproc)
            SetWindowLong(target, GWLP_WNDPROC, self._new_proc)
            return True
        except Exception:
            return False


def try_tkinterdnd2(root, widget, callback) -> bool:
    try:
        from tkinterdnd2 import DND_FILES, TkinterDnD
    except ImportError:
        return False
    if not isinstance(root, TkinterDnD.Tk):
        return False

    def _on_drop(event) -> None:
        data = event.data.strip()
        files = root.tk.splitlist(data)
        callback(list(files))

    widget.drop_target_register(DND_FILES)
    widget.dnd_bind("<<Drop>>", _on_drop)
    return True


def create_root():
    try:
        from tkinterdnd2 import TkinterDnD

        return TkinterDnD.Tk(), True
    except ImportError:
        import tkinter as tk

        return tk.Tk(), False


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
class PyGameToolsApp:
    def __init__(self, root, dnd_ready: bool) -> None:
        self.root = root
        self.dnd_ready = dnd_ready
        self.q: queue.Queue[tuple[str, object]] = queue.Queue()
        self.busy = False
        self.wf = Workflow(self._thread_log)
        self._drop_hook = None
        self._adb: Path | None = None
        self._packages: list[tuple[str, str]] = []
        self._devices: list[tuple[str, str]] = []

        self._build_ui()
        self._bind_drop()
        self.root.after(80, self._pump)
        self.root.after(200, self._boot_check)

    def _build_ui(self) -> None:
        self.root.title("PyGameTools — 改包 / 提包")
        self.root.geometry("980x700")
        self.root.minsize(860, 600)
        bg = "#f0f0f0"
        self.root.configure(bg=bg)
        try:
            self.root.option_add("*Font", ("Microsoft YaHei UI", 9))
        except Exception:
            pass

        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        style.configure("TLabel", background=bg)
        style.configure("TFrame", background=bg)
        style.configure("Hint.TLabel", foreground="#333333", background=bg)
        style.configure("Action.TButton", padding=(8, 6))

        self.var_game = tk.StringVar()
        self.var_channel = tk.StringVar()
        self.var_package = tk.StringVar()
        self.var_appname = tk.StringVar()
        self.var_sign = tk.StringVar(value="测试签名")
        self.var_status = tk.StringVar(value="请拖入 APK，或到「提包」页从手机提取")
        self.var_no_vulkan = tk.BooleanVar(value=True)
        self.var_no_lebian_hot = tk.BooleanVar(value=False)
        self.var_skip_cache_4g = tk.BooleanVar(value=True)
        self.var_device = tk.StringVar()
        self.var_search = tk.StringVar()
        self.var_third = tk.BooleanVar(value=True)
        self.var_merge = tk.BooleanVar(value=True)
        self.var_obb = tk.BooleanVar(value=True)
        self.var_data = tk.BooleanVar(value=False)
        self.var_autoload = tk.BooleanVar(value=True)

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=False, padx=8, pady=(8, 0))
        self.tab_mod = ttk.Frame(self.nb, padding=(4, 4, 4, 2))
        self.tab_pull = ttk.Frame(self.nb, padding=(4, 4, 4, 2))
        self.nb.add(self.tab_mod, text="  改包  ")
        self.nb.add(self.tab_pull, text="  提包  ")
        self._build_mod_tab(self.tab_mod)
        self._build_pull_tab(self.tab_pull)

        log_wrap = ttk.Frame(self.root, padding=(12, 8, 12, 6))
        log_wrap.pack(fill="both", expand=True)
        self.txt = tk.Text(
            log_wrap,
            bg="white",
            fg="#111",
            relief="sunken",
            bd=1,
            wrap="word",
            undo=False,
            font=("Consolas", 10),
        )
        scroll = ttk.Scrollbar(log_wrap, command=self.txt.yview)
        self.txt.configure(yscrollcommand=scroll.set)
        self.txt.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.txt.tag_configure("err", foreground="#b00020")
        self.txt.tag_configure("ok", foreground="#0a7a0a")
        self.txt.tag_configure("cmd", foreground="#1a4d8f")
        self.txt.bind("<Double-Button-1>", self._browse_if_idle)
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="选择 APK...", command=self._browse_apk)
        self.menu.add_command(label="打开输出目录", command=self._open_output)
        self.menu.add_command(label="打开提包目录", command=self._open_pull_dir)
        self.txt.bind("<Button-3>", self._popup_menu)

        status = ttk.Frame(self.root)
        status.pack(fill="x", side="bottom")
        ttk.Label(status, textvariable=self.var_status, padding=(8, 3)).pack(anchor="w")

        self._append(
            "PyGameTools 已启动。可拖入 APK，或打开「提包」页从已连接的手机提取已安装应用。\n",
            "ok",
        )

    def _build_mod_tab(self, parent) -> None:
        top = ttk.Frame(parent, padding=(8, 6, 8, 4))
        top.pack(fill="x")
        top.columnconfigure((1, 3, 5, 7), weight=1)

        fields = (
            ("游戏id", self.var_game, 0),
            ("渠道号", self.var_channel, 2),
            ("包名", self.var_package, 4),
            ("应用名", self.var_appname, 6),
        )
        for label, var, col in fields:
            ttk.Label(top, text=label).grid(row=0, column=col, padx=(0, 4), sticky="e")
            ttk.Entry(top, textvariable=var).grid(
                row=0, column=col + 1, padx=(0, 12), sticky="ew"
            )

        btns = ttk.Frame(parent, padding=(8, 4, 8, 4))
        btns.pack(fill="x")
        for i in range(5):
            btns.columnconfigure(i, weight=1)

        ttk.Button(btns, text="反编译apk", style="Action.TButton", command=self.on_decompile).grid(
            row=0, column=0, padx=4, sticky="ew"
        )
        ttk.Button(
            btns,
            text="打开目录，替换游戏资源",
            style="Action.TButton",
            command=self.on_open_dir,
        ).grid(row=0, column=1, padx=4, sticky="ew")

        sign_box = ttk.Frame(btns)
        sign_box.grid(row=0, column=2, padx=4, sticky="ew")
        sign_box.columnconfigure(0, weight=1)
        self.cmb_sign = ttk.Combobox(
            sign_box,
            textvariable=self.var_sign,
            values=("测试签名",),
            state="readonly",
            justify="center",
        )
        self.cmb_sign.pack(fill="x", ipady=4)

        ttk.Button(btns, text="回编译apk", style="Action.TButton", command=self.on_rebuild).grid(
            row=0, column=3, padx=4, sticky="ew"
        )
        ttk.Button(
            btns,
            text="回编译DebugApk",
            style="Action.TButton",
            command=self.on_rebuild_debug,
        ).grid(row=0, column=4, padx=4, sticky="ew")

        opts = ttk.Frame(parent, padding=(10, 0, 10, 2))
        opts.pack(fill="x")
        ttk.Button(opts, text="识别壳", command=self.on_detect).pack(side="left", padx=(0, 12))
        ttk.Button(opts, text="合并应用数据", command=self.on_merge_appdata).pack(
            side="left", padx=(0, 12)
        )
        ttk.Button(opts, text="推送缓存到手机", command=self.on_push_yoo_cache).pack(
            side="left", padx=(0, 12)
        )
        ttk.Button(opts, text="推送 GLES 配置", command=self.on_push_gles_config).pack(
            side="left", padx=(0, 12)
        )
        ttk.Button(opts, text="清理登录缓存", command=self.on_clear_login_cache).pack(
            side="left", padx=(0, 12)
        )

        flags = ttk.Frame(parent, padding=(10, 0, 10, 2))
        flags.pack(fill="x")
        ttk.Checkbutton(
            flags,
            text="强制关闭 Vulkan（仅 Unity：回编译时改为 OpenGL ES / -force-gles）",
            variable=self.var_no_vulkan,
        ).pack(anchor="w")
        ttk.Checkbutton(
            flags,
            text="关闭乐变热更（回编译时关闭查新版本 / 边玩边下，需先合并应用数据）",
            variable=self.var_no_lebian_hot,
        ).pack(anchor="w")
        ttk.Checkbutton(
            flags,
            text="合并超过 4GB 时跳过 YooAsset 缓存（装机后可点「推送缓存到手机」）",
            variable=self.var_skip_cache_4g,
        ).pack(anchor="w")

        ttk.Label(
            parent,
            style="Hint.TLabel",
            text=(
                "使用说明：1.将apk拖入下方日志区或从「提包」页提取（会自动识别常见壳）；"
                "2.点击反编译apk；3.有热更数据则点「合并应用数据」填回 assets，或手动打开目录替换；"
                "4.可选填写应用信息后回编译。勾选超过 4GB 跳过缓存后，装机再点「推送缓存到手机」。"
                "第二次启动又走 Vulkan 时，点「推送 GLES 配置」。"
                "RenderDoc 第二次卡登录可点「清理登录缓存」（不动 yoo 资源）。"
            ),
            padding=(10, 2, 10, 6),
        ).pack(fill="x")

    def _build_pull_tab(self, parent) -> None:
        row1 = ttk.Frame(parent, padding=(8, 6, 8, 2))
        row1.pack(fill="x")
        ttk.Label(row1, text="设备").pack(side="left")
        self.cmb_device = ttk.Combobox(
            row1, textvariable=self.var_device, state="readonly", width=36
        )
        self.cmb_device.pack(side="left", padx=(6, 8))
        ttk.Button(row1, text="刷新设备", command=self.on_refresh_devices).pack(
            side="left", padx=2
        )
        ttk.Button(row1, text="无线连接", command=self.on_wireless).pack(side="left", padx=2)
        ttk.Checkbutton(row1, text="仅第三方应用", variable=self.var_third).pack(
            side="left", padx=(16, 4)
        )

        row2 = ttk.Frame(parent, padding=(8, 4, 8, 2))
        row2.pack(fill="x")
        ttk.Label(row2, text="搜索").pack(side="left")
        ent = ttk.Entry(row2, textvariable=self.var_search)
        ent.pack(side="left", fill="x", expand=True, padx=(6, 8))
        ent.bind("<KeyRelease>", lambda _e: self._filter_packages())
        ttk.Button(row2, text="刷新应用列表", command=self.on_refresh_packages).pack(
            side="left", padx=2
        )
        ttk.Button(row2, text="定位前台应用", command=self.on_focus_foreground).pack(
            side="left", padx=2
        )

        tree_wrap = ttk.Frame(parent, padding=(8, 4, 8, 2))
        tree_wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("pkg", "path"),
            show="headings",
            height=10,
            selectmode="browse",
        )
        self.tree.heading("pkg", text="包名")
        self.tree.heading("path", text="安装路径")
        self.tree.column("pkg", width=280, stretch=True)
        self.tree.column("path", width=480, stretch=True)
        yscroll = ttk.Scrollbar(tree_wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self.on_pull_selected())

        opts = ttk.Frame(parent, padding=(8, 2, 8, 2))
        opts.pack(fill="x")
        ttk.Checkbutton(opts, text="合并分包为单个 APK", variable=self.var_merge).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(opts, text="同时提取 OBB", variable=self.var_obb).pack(
            side="left", padx=(0, 12)
        )
        ttk.Checkbutton(
            opts,
            text="同时提取应用数据（files / 热更缓存）",
            variable=self.var_data,
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(
            opts, text="提取后自动选入「改包」", variable=self.var_autoload
        ).pack(side="left")

        actions = ttk.Frame(parent, padding=(8, 4, 8, 4))
        actions.pack(fill="x")
        for i in range(3):
            actions.columnconfigure(i, weight=1)
        ttk.Button(
            actions, text="提取选中应用", style="Action.TButton", command=self.on_pull_selected
        ).grid(row=0, column=0, padx=4, sticky="ew")
        ttk.Button(
            actions,
            text="提取前台应用",
            style="Action.TButton",
            command=self.on_pull_foreground,
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ttk.Button(
            actions, text="打开提包目录", style="Action.TButton", command=self._open_pull_dir
        ).grid(row=0, column=2, padx=4, sticky="ew")

        ttk.Label(
            parent,
            style="Hint.TLabel",
            text=(
                "手机：设置 → 关于手机，连点版本号打开开发者选项；开启 USB 调试并授权本电脑。"
                "小米/OPPO/vivo/华为还需打开「USB 调试（安全设置）」。无需 Root。"
                "AAB 安装的应用会有 base.apk + split_*.apk，勾选合并即可得到完整包。"
                "热更资源在 Android/data/包名/files，勾选「应用数据」一并拉取（目录可能很大）。"
            ),
            padding=(8, 2, 8, 4),
            wraplength=920,
        ).pack(fill="x")

    def _bind_drop(self) -> None:
        if try_tkinterdnd2(self.root, self.txt, self._on_drop_files):
            return
        hook = DropTarget(self.txt, self._on_drop_files)
        if hook.attach():
            self._drop_hook = hook

    def _popup_menu(self, event) -> None:
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _open_output(self) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(OUTPUT_DIR))

    def _open_pull_dir(self) -> None:
        PULL_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(PULL_DIR))

    def _selected_device(self) -> str:
        raw = self.var_device.get().strip()
        if not raw:
            raise RuntimeError("没有已连接的设备，请先点「刷新设备」")
        serial = raw.split()[0]
        for s, state in self._devices:
            if s == serial and state != "device":
                raise RuntimeError(f"设备 {serial} 状态为 {state}，请在手机上点「允许 USB 调试」")
        return serial

    def _selected_package(self) -> str:
        sel = self.tree.selection()
        if not sel:
            raise RuntimeError("请先在列表中选择一个应用")
        pkg = self.tree.item(sel[0], "values")[0]
        if not pkg:
            raise RuntimeError("无法读取选中的包名")
        return str(pkg)

    def _fill_devices(self, devices: list[tuple[str, str]]) -> None:
        self._devices = devices
        labels = []
        ready = []
        for serial, state in devices:
            if state == "device":
                labels.append(serial)
                ready.append(serial)
            else:
                labels.append(f"{serial}  ({state})")
        self.cmb_device["values"] = labels
        if ready:
            cur = self.var_device.get().split()[0] if self.var_device.get() else ""
            self.var_device.set(cur if cur in ready else ready[0])
        elif labels:
            self.var_device.set(labels[0])
        else:
            self.var_device.set("")
            self._append("未检测到设备。用数据线连接手机，打开 USB 调试后点「刷新设备」。\n", "err")

    def _fill_packages(self, items: list[tuple[str, str]]) -> None:
        self._packages = items
        self._filter_packages()
        self._append(f"已加载 {len(items)} 个应用。可搜索包名，双击即可提取。\n", "ok")

    def _filter_packages(self) -> None:
        needle = self.var_search.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        for pkg, path in self._packages:
            if needle and needle not in pkg.lower() and needle not in path.lower():
                continue
            self.tree.insert("", "end", values=(pkg, path))

    def _select_package_in_tree(self, package: str) -> None:
        self.var_search.set(package)
        self._filter_packages()
        for iid in self.tree.get_children():
            if self.tree.item(iid, "values")[0] == package:
                self.tree.selection_set(iid)
                self.tree.see(iid)
                return

    def on_refresh_devices(self) -> None:
        self._run_job("刷新设备", self._job_refresh_devices)

    def on_refresh_packages(self) -> None:
        try:
            device = self._selected_device()
        except RuntimeError as exc:
            messagebox.showinfo("PyGameTools", str(exc))
            return
        third = bool(self.var_third.get())
        self._run_job("刷新应用列表", lambda: self._job_refresh_packages(device, third))

    def on_focus_foreground(self) -> None:
        try:
            device = self._selected_device()
        except RuntimeError as exc:
            messagebox.showinfo("PyGameTools", str(exc))
            return
        self._run_job("定位前台应用", lambda: self._job_focus_foreground(device))

    def on_pull_selected(self) -> None:
        try:
            pkg = self._selected_package()
            device = self._selected_device()
        except RuntimeError as exc:
            messagebox.showinfo("PyGameTools", str(exc))
            return
        self._run_job("提包", lambda: self._job_pull(device, pkg, *self._pull_opts()))

    def on_pull_foreground(self) -> None:
        try:
            device = self._selected_device()
        except RuntimeError as exc:
            messagebox.showinfo("PyGameTools", str(exc))
            return
        self._run_job("提取前台应用", lambda: self._job_pull_foreground(device, *self._pull_opts()))

    def _pull_opts(self) -> tuple[bool, bool, bool, bool]:
        return (
            bool(self.var_merge.get()),
            bool(self.var_obb.get()),
            bool(self.var_data.get()),
            bool(self.var_autoload.get()),
        )

    def on_wireless(self) -> None:
        win = tk.Toplevel(self.root)
        win.title("无线 ADB")
        win.transient(self.root)
        win.geometry("420x170")
        win.resizable(False, False)
        ttk.Label(
            win,
            text="手机与电脑同一 Wi-Fi。开发者选项 → 无线调试，填入「IP:端口」。",
            wraplength=390,
        ).pack(padx=14, pady=(12, 6), anchor="w")
        var_addr = tk.StringVar(value="192.168.1.100:5555")
        ttk.Entry(win, textvariable=var_addr).pack(fill="x", padx=14, pady=4)

        def go() -> None:
            addr = var_addr.get().strip()
            win.destroy()
            if addr:
                self._run_job("无线连接", lambda: self._job_connect(addr))

        ttk.Button(win, text="连接", command=go).pack(pady=10)

    def _job_connect(self, addr: str) -> None:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        out = adb_output(adb, ["connect", addr], check=False)
        self._thread_log(out.strip() or f"adb connect {addr}")
        low = out.lower()
        if "connected" not in low and "already" not in low:
            raise RuntimeError(out.strip() or "无线连接失败")
        devices = list_adb_devices(adb)
        self.q.put(("devices", devices))

    def _job_refresh_devices(self) -> None:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        adb_output(adb, ["start-server"], check=False)
        devices = list_adb_devices(adb)
        self.q.put(("devices", devices))
        if devices:
            return f"{len(devices)} 台"

    def _job_refresh_packages(self, device: str, third: bool) -> None:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        items = list_installed_packages(adb, device, third_party_only=third)
        self.q.put(("packages", items))

    def _job_focus_foreground(self, device: str) -> str:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        pkg = get_foreground_package(adb, device)
        self.q.put(("focus", pkg))
        return pkg

    def _job_pull(
        self,
        device: str,
        package: str,
        merge: bool,
        with_obb: bool,
        with_data: bool,
        autoload: bool,
    ) -> Path:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        result = pull_installed_apk(
            adb,
            device,
            package,
            merge=merge,
            with_obb=with_obb,
            with_data=with_data,
            log=self._thread_log,
        )
        if autoload:
            self.q.put(("autoload", str(result)))
        return result

    def _job_pull_foreground(
        self,
        device: str,
        merge: bool,
        with_obb: bool,
        with_data: bool,
        autoload: bool,
    ) -> Path:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        pkg = get_foreground_package(adb, device)
        self._thread_log(f"前台应用: {pkg}")
        self.q.put(("focus", pkg))
        return self._job_pull(device, pkg, merge, with_obb, with_data, autoload)

    def _browse_if_idle(self, _event=None) -> None:
        if self.busy or self.wf.apk_path:
            return
        self._browse_apk()

    def _browse_apk(self) -> None:
        path = filedialog.askopenfilename(
            title="选择 APK",
            filetypes=[("APK 文件", "*.apk"), ("所有文件", "*.*")],
        )
        if path:
            self._set_apk(Path(path))

    def _on_drop_files(self, files: list[str]) -> None:
        for f in files:
            p = Path(f.strip("{}"))
            if p.suffix.lower() == ".apk" and p.is_file():
                self._set_apk(p)
                return
        messagebox.showwarning("PyGameTools", "请拖入 .apk 文件")

    def _set_apk(self, path: Path) -> None:
        self.wf.set_apk(path)
        self.var_status.set(str(path))
        self._append(f"已选择 APK: {path}\n", "ok")
        threading.Thread(target=self._auto_detect, args=(path,), daemon=True).start()

    def _auto_detect(self, path: Path) -> None:
        try:
            decode = self.wf.decode_dir if self.wf.decode_dir and self.wf.decode_dir.exists() else None
            hits, packed = detect_packers(path, decode)
            text = format_detect_report(hits, packed)
            self.q.put(("err" if packed else "ok", text if text.endswith("\n") else text + "\n"))
        except Exception as exc:
            self.q.put(("err", f"壳识别失败: {exc}\n"))

    def on_detect(self) -> None:
        if not self.wf.apk_path and not (self.wf.decode_dir and self.wf.decode_dir.exists()):
            self._browse_apk()
        if not self.wf.apk_path and not (self.wf.decode_dir and self.wf.decode_dir.exists()):
            return
        self._run_job("壳识别", self._job_detect)

    def _job_detect(self) -> str:
        hits, packed = detect_packers(self.wf.apk_path, self.wf.decode_dir)
        text = format_detect_report(hits, packed).rstrip()
        self._thread_log(text)
        kinds = [h.name for h in hits]
        return "、".join(kinds) if kinds else "未发现常见商业加固"

    def _resolve_appdata(self) -> Path | None:
        if self.wf.appdata_dir and _looks_like_appdata(self.wf.appdata_dir):
            return self.wf.appdata_dir
        pkg = self.var_package.get().strip()
        guessed = guess_appdata_dir(self.wf.apk_path, pkg)
        if guessed:
            self.wf.appdata_dir = guessed
            return guessed
        path = filedialog.askdirectory(
            title="选择应用数据目录（appdata 或 files）",
            initialdir=str(PULL_DIR if PULL_DIR.exists() else APP_DIR),
        )
        if not path:
            return None
        chosen = Path(path)
        self.wf.appdata_dir = chosen
        return chosen

    def on_merge_appdata(self) -> None:
        decode = self.wf.decode_dir
        if decode is None or not decode.exists() or not (decode / "AndroidManifest.xml").exists():
            if not self.wf.apk_path:
                self._browse_apk()
            if not self.wf.apk_path:
                return
            if not messagebox.askyesno("PyGameTools", "尚未反编译。先反编译再合并应用数据？"):
                return
            appdata = self._resolve_appdata()
            if appdata is None:
                return
            self._run_job("反编译并合并应用数据", lambda: self._job_decompile_and_merge(appdata))
            return
        appdata = self._resolve_appdata()
        if appdata is None:
            return
        self._run_job("合并应用数据", lambda: self._job_merge_appdata(appdata))

    def _job_merge_appdata(self, appdata: Path) -> str:
        if not self.wf.decode_dir:
            raise RuntimeError("请先反编译 APK")
        stats = merge_appdata_into_decode(
            appdata,
            self.wf.decode_dir,
            self._thread_log,
            skip_cache_if_over_4g=bool(self.var_skip_cache_4g.get()),
        )
        extra = ""
        if stats.get("skipped_cache"):
            extra = (
                f"，已跳过缓存 {stats['cache_skip_bytes'] / (1024 ** 3):.2f} GB"
                "（装机后点「推送缓存到手机」）"
            )
        return (
            f"新增 {stats['copied']}，覆盖 {stats['overwritten']}{extra}"
            f" → {self.wf.decode_dir / 'assets'}"
        )

    def _job_decompile_and_merge(self, appdata: Path) -> str:
        self.wf.decompile()
        return self._job_merge_appdata(appdata)

    def _app_info(self) -> dict:
        return {
            "game_id": self.var_game.get().strip(),
            "channel": self.var_channel.get().strip(),
            "package": self.var_package.get().strip(),
            "app_name": self.var_appname.get().strip(),
            "disable_vulkan": bool(self.var_no_vulkan.get()),
            "disable_lebian_hot": bool(self.var_no_lebian_hot.get()),
            "skip_cache_if_over_4g": bool(self.var_skip_cache_4g.get()),
        }

    def _push_package_name(self) -> str:
        pkg = self.var_package.get().strip()
        if pkg:
            return pkg
        if self.wf.apk_path:
            parent = self.wf.apk_path.parent.name
            if parent and parent not in {"pulled", "output", "work"}:
                return parent
            return self.wf.apk_path.stem.replace("_debug", "").replace("_unsigned", "")
        if self.wf.decode_dir:
            return self.wf.decode_dir.name
        return ""

    def _job_ensure_device(self) -> str:
        try:
            return self._selected_device()
        except RuntimeError:
            pass
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        devices = list_adb_devices(adb)
        self.q.put(("devices", devices))
        ready = [serial for serial, state in devices if state == "device"]
        if not ready:
            raise RuntimeError("没有已连接的设备，请先到「提包」页刷新设备并授权 USB 调试")
        return ready[0]

    def on_push_yoo_cache(self) -> None:
        appdata = self._resolve_appdata()
        if appdata is None:
            return
        pkg = self._push_package_name()
        if not pkg:
            messagebox.showinfo(
                "PyGameTools",
                "请填写改包页「包名」，或先选好从该包名目录提出来的 APK。",
            )
            return
        if not messagebox.askyesno(
            "PyGameTools",
            f"将把本地 YooAsset 缓存推到手机：\n"
            f"/sdcard/Android/data/{pkg}/files/yoo\n\n"
            "请先装好 APK 并至少启动一次（以便生成目录）。继续？",
        ):
            return
        self._run_job(
            "推送 Yoo 缓存",
            lambda: self._job_push_yoo_cache(appdata, pkg),
        )

    def _job_push_yoo_cache(self, appdata: Path, package: str) -> str:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        device = self._job_ensure_device()
        remote = push_yoo_cache_to_device(adb, device, package, appdata, self._thread_log)
        return str(remote)

    def on_push_gles_config(self) -> None:
        pkg = self._push_package_name()
        if not pkg:
            messagebox.showinfo(
                "PyGameTools",
                "请填写改包页「包名」，或先选好从该包名目录提出来的 APK。",
            )
            return
        if not messagebox.askyesno(
            "PyGameTools",
            f"将把关闭 Vulkan / 强制 GLES 的 boot.config 推到：\n"
            f"/sdcard/Android/data/{pkg}/files/bin/Data/boot.config\n\n"
            "用于盖住第二次启动时乐变/Unity 读到的旧配置。会 force-stop 应用。"
            "请先装好 APK。继续？",
        ):
            return
        self._run_job("推送 GLES 配置", lambda: self._job_push_gles_config(pkg))

    def _job_push_gles_config(self, package: str) -> str:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        device = self._job_ensure_device()
        decode = self.wf.decode_dir if self.wf.decode_dir and self.wf.decode_dir.exists() else None
        return push_gles_config_to_device(adb, device, package, decode, self._thread_log)

    def on_clear_login_cache(self) -> None:
        pkg = self._push_package_name()
        if not pkg:
            messagebox.showinfo(
                "PyGameTools",
                "请填写改包页「包名」，或先选好从该包名目录提出来的 APK。",
            )
            return
        if not messagebox.askyesno(
            "PyGameTools",
            f"将清理 {pkg} 的登录缓存（shared_prefs 里带 login/token/账号等关键字的文件）。\n\n"
            "不会删除 files/yoo 和 Android/data 下的热更资源。\n"
            "需要已装 DebugApk。会 force-stop 应用。继续？",
        ):
            return
        self._run_job("清理登录缓存", lambda: self._job_clear_login_cache(pkg))

    def _job_clear_login_cache(self, package: str) -> str:
        adb = ensure_adb(self._thread_log)
        self._adb = adb
        device = self._job_ensure_device()
        return clear_login_cache_on_device(adb, device, package, self._thread_log)

    def on_decompile(self) -> None:
        if not self.wf.apk_path:
            self._browse_apk()
        if not self.wf.apk_path:
            return
        self._run_job("反编译", self.wf.decompile)

    def on_open_dir(self) -> None:
        target = self.wf.decode_dir
        if target is None or not target.exists():
            messagebox.showinfo("PyGameTools", "请先反编译 APK")
            return
        os.startfile(str(target))  # noqa: S606
        self._append(f"已打开目录: {target}\n")
        self._append("可在此替换 res / assets / lib/*.so 等游戏资源。\n")

    def on_rebuild(self) -> None:
        self._run_job(
            "回编译",
            lambda: self.wf.build_and_sign(
                self._app_info(), debug=False, sign_mode=self.var_sign.get()
            ),
        )

    def on_rebuild_debug(self) -> None:
        self._run_job(
            "回编译 DebugApk",
            lambda: self.wf.build_and_sign(
                self._app_info(), debug=True, sign_mode="测试签名"
            ),
        )

    def _run_job(self, title: str, fn) -> None:
        if self.busy:
            messagebox.showinfo("PyGameTools", "正在执行任务，请稍候")
            return
        self.busy = True
        self._append(f"\n======== {title} ========\n", "cmd")

        def worker() -> None:
            try:
                result = fn()
                if isinstance(result, Path):
                    self.q.put(("ok", f"{title}成功: {result}\n"))
                    self.q.put(("offer", str(result)))
                elif result:
                    self.q.put(("ok", f"{title}成功: {result}\n"))
                else:
                    self.q.put(("ok", f"{title}成功\n"))
            except Exception as exc:
                self.q.put(("err", f"{title}失败: {exc}\n"))
            finally:
                self.q.put(("done", ""))

        threading.Thread(target=worker, daemon=True).start()

    def _thread_log(self, msg: str) -> None:
        tag = ""
        low = msg.lower()
        if msg.startswith("$ "):
            tag = "cmd"
        elif "error" in low or "失败" in msg or "exception" in low:
            tag = "err"
        elif "完成" in msg or "success" in low:
            tag = "ok"
        self.q.put((tag, msg + "\n"))

    def _append(self, text: str, tag: str = "") -> None:
        self.txt.insert("end", text, (tag,) if tag else ())
        self.txt.see("end")

    def _pump(self) -> None:
        try:
            while True:
                tag, text = self.q.get_nowait()
                if tag == "done":
                    self.busy = False
                    continue
                if tag == "offer":
                    if messagebox.askyesno("PyGameTools", f"已生成:\n{text}\n\n打开所在目录？"):
                        os.startfile(str(Path(str(text)).parent))
                    continue
                if tag == "devices":
                    self._fill_devices(text)  # type: ignore[arg-type]
                    continue
                if tag == "packages":
                    self._fill_packages(text)  # type: ignore[arg-type]
                    continue
                if tag == "focus":
                    self._select_package_in_tree(str(text))
                    continue
                if tag == "autoload":
                    path = Path(str(text))
                    if path.is_file():
                        self._set_apk(path)
                        self.nb.select(self.tab_mod)
                        self.var_package.set(path.parent.name)
                    continue
                self._append(str(text), str(tag))
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _boot_check(self) -> None:
        def worker() -> None:
            try:
                java = find_java()
                if java:
                    self.q.put(("ok", f"检测到 Java: {java}\n"))
                else:
                    self.q.put(
                        (
                            "",
                            "未检测到 Java。首次反编译时会自动下载便携 JRE 和 apktool，请保持网络畅通。\n",
                        )
                    )
                if APKTOOL_JAR.exists():
                    self.q.put(("ok", f"已找到 apktool: {APKTOOL_JAR}\n"))
                else:
                    self.q.put(("", "尚未下载 apktool，将在首次任务时自动获取。\n"))
                adb = find_adb()
                if adb:
                    self.q.put(("ok", f"检测到 adb: {adb}\n"))
                else:
                    self.q.put(
                        (
                            "",
                            "未检测到 adb。首次「提包」时会自动下载 platform-tools，请保持网络畅通。\n",
                        )
                    )
            except Exception as exc:
                self.q.put(("err", f"环境检查失败: {exc}\n"))

        threading.Thread(target=worker, daemon=True).start()


def _pip_install(pkg: str, log) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-q", pkg]
    try:
        run_cmd(cmd, log)
        return True
    except Exception as exc:
        log(f"pip 安装 {pkg} 失败（可忽略，仍可用右键选 APK）: {exc}")
        return False


def setup_cli() -> int:
    def log(msg: str) -> None:
        print(msg, flush=True)

    try:
        log("==== PyGameTools 环境安装 ====")
        try:
            import tkinter  # noqa: F401
            log("tkinter: OK")
        except Exception as exc:
            log(f"tkinter 不可用: {exc}")
            log("请安装官方 Windows 版 Python 3.10+（不要用精简/嵌入版）")
            return 1
        try:
            import tkinterdnd2  # noqa: F401
            log("tkinterdnd2: 已安装")
        except Exception:
            log("正在安装 tkinterdnd2 ...")
            _pip_install("tkinterdnd2", log)
        java = ensure_tools(log)
        try:
            ensure_adb(log)
        except Exception as exc:
            log(f"adb 可选安装失败（提包时会再试）: {exc}")
        checks = [
            ("apktool.jar", APKTOOL_JAR),
            ("uber-apk-signer.jar", SIGNER_JAR),
            ("便携 JRE", JRE_DIR / "bin" / "java.exe"),
            ("debug.keystore", DEBUG_KEYSTORE),
            ("adb", ADB_EXE if ADB_EXE.exists() else Path(shutil.which("adb") or "")),
        ]
        log("---- 环境核对 ----")
        failed = False
        for name, path in checks:
            if path.exists():
                log(f"  [OK] {name}: {path}")
            else:
                log(f"  [缺失] {name}: {path}")
                if name not in {"debug.keystore", "adb"}:
                    failed = True
        log(f"  [OK] Java: {java}")
        if failed:
            log("安装未完成")
            return 1
        log("安装完成。换电脑时拷贝整个 PyGameTools 文件夹，再运行 一键安装.bat")
        return 0
    except Exception as exc:
        print(f"SETUP FAILED: {exc}", file=sys.stderr)
        return 1


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] in {"--setup", "setup"}:
        raise SystemExit(setup_cli())
    root, dnd = create_root()
    PyGameToolsApp(root, dnd)
    root.mainloop()


if __name__ == "__main__":
    main()
