#!/usr/bin/env python3
"""
NVVFX Denoise 分辨率要求精确测试
确定 NVVFX Denoise 到底需要什么分辨率
"""

import subprocess, sys, os, tempfile, time

NVENCC = "NVEncC64"
INPUT = r"C:\Users\pull.pu\Downloads\scene_battle_new_xiyou0_deflickered.mp4"


def run(name, args):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"{name}.mp4")
        cmd = [NVENCC, "-i", INPUT] + args + ["-o", out]
        print(f"\n  [{name}]")
        print(f"  CMD: {' '.join(cmd)}")
        start = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        elapsed = time.time() - start
        size = os.path.getsize(out) if os.path.exists(out) else 0
        # 基准：无滤镜 10 帧约 88KB，全黑约 1.7KB
        ok = r.returncode == 0 and size > 5000
        status = "✅ 正常" if ok else f"❌ 全黑/异常 (size={size})"
        print(f"  结果: {status} ({elapsed:.1f}s)")
        # 提取 nvvfx 相关日志
        for line in r.stdout.split("\n"):
            if "nvvfx" in line.lower() or "error" in line.lower() or "warn" in line.lower():
                print(f"  LOG: {line.strip()}")
        return ok, size


def main():
    print("=" * 60)
    print("  NVVFX Denoise 分辨率精确测试")
    print(f"  输入: {INPUT}")
    print("=" * 60)

    base = [
        "--codec", "hevc", "--frames", "10",
        "--preset", "performance", "--cqp", "28",
    ]

    resolutions = [
        # (宽, 高, 描述)
        (1920, 1080, "Full HD 16:9"),
        (1920, 800,  "1920x800 电影宽屏"),
        (1920, 816,  "1920x816 电影宽屏"),
        (1920, 1040, "1920x1040 近1080"),
        (1600, 900,  "1600x900 16:9"),
        (1280, 720,  "720p 16:9"),
        (1470, 630,  "原始分辨率 (无resize)"),
        (1440, 1080, "1440x1080 4:3"),
        (1080, 1080, "1080x1080 正方形"),
        (1920, 1920, "1920x1920 正方形"),
        (1280, 1080, "1280x1080"),
        (960,  540,  "540p 16:9"),
        (640,  480,  "VGA 4:3"),
        (1920, 1088, "1920x1088 (16对齐)"),
        (1024, 768,  "XGA 4:3"),
        (1536, 864,  "1536x864 16:9"),
        (1792, 1008, "1792x1008 16:9"),
        (1856, 1044, "1856x1044 16:9"),
    ]

    results = {}

    for w, h, desc in resolutions:
        name = f"denoise_{w}x{h}"
        if w == 1470 and h == 630:
            # 原始分辨率不需要 resize
            args = base + ["--vpp-nvvfx-denoise", "strength=0"]
        else:
            args = base + [
                "--output-res", f"{w}x{h}",
                "--vpp-resize", "spline64",
                "--vpp-nvvfx-denoise", "strength=0",
            ]
        ok, size = run(f"{desc} ({w}x{h})", args)
        results[(w, h)] = (ok, size, desc)

    # 同时测试 artifact-reduction 作为对比
    print("\n" + "=" * 60)
    print("  对比: NVVFX Artifact Reduction 分辨率测试")
    print("=" * 60)

    ar_resolutions = [
        (1470, 630, "原始分辨率"),
        (1280, 720, "720p"),
        (1920, 1080, "1080p"),
        (960, 540, "540p"),
    ]

    ar_results = {}
    for w, h, desc in ar_resolutions:
        name = f"artifact_{w}x{h}"
        if w == 1470 and h == 630:
            args = base + ["--vpp-nvvfx-artifact-reduction", "mode=0"]
        else:
            args = base + [
                "--output-res", f"{w}x{h}",
                "--vpp-resize", "spline64",
                "--vpp-nvvfx-artifact-reduction", "mode=0",
            ]
        ok, size = run(f"Artifact {desc} ({w}x{h})", args)
        ar_results[(w, h)] = (ok, size, desc)

    # 总结
    print("\n" + "=" * 60)
    print("  结果总结")
    print("=" * 60)

    print("\n  ── NVVFX Denoise ──")
    for (w, h), (ok, size, desc) in sorted(results.items(), key=lambda x: (-x[0][0], -x[0][1])):
        status = "✅" if ok else "❌"
        print(f"  {status} {w:>4}x{h:<4}  {desc:30s}  size={size}")

    print("\n  ── NVVFX Artifact Reduction (对比) ──")
    for (w, h), (ok, size, desc) in sorted(ar_results.items(), key=lambda x: (-x[0][0], -x[0][1])):
        status = "✅" if ok else "❌"
        print(f"  {status} {w:>4}x{h:<4}  {desc:30s}  size={size}")

    # 分析
    ok_resolutions = [(w, h) for (w, h), (ok, _, _) in results.items() if ok]
    fail_resolutions = [(w, h) for (w, h), (ok, _, _) in results.items() if not ok]

    print("\n  ── 分析 ──")
    if ok_resolutions:
        print(f"  ✅ Denoise 正常的分辨率: {ok_resolutions}")
    if fail_resolutions:
        print(f"  ❌ Denoise 全黑的分辨率: {fail_resolutions}")

    # 检查是否只有 1920x1080 正常
    if ok_resolutions == [(1920, 1080)]:
        print("\n  结论: NVVFX Denoise 必须精确 1920x1080 输入!")
        print("  解决方案: 先 resize 到 1920x1080 → denoise → resize 回原尺寸")
    elif all(w >= 1920 and h >= 1080 for w, h in ok_resolutions):
        print("\n  结论: NVVFX Denoise 可能需要最小 1920x1080")
    else:
        min_w = min(w for w, h in ok_resolutions)
        min_h = min(h for w, h in ok_resolutions)
        print(f"\n  结论: NVVFX Denoise 最小可用分辨率约 {min_w}x{min_h}")

    print()


if __name__ == "__main__":
    main()