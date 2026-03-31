#!/usr/bin/env python3
"""
NVVFX Denoise 全黑问题诊断
"""
import subprocess, sys, os, tempfile

NVENCC = "NVEncC64"
# ★ 请改为你的测试文件路径
INPUT = r"C:\Users\pull.pu\Downloads\scene_battle_new_xiyou0_deflickered.mp4"


def run(name, args):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, f"{name}.mp4")
        cmd = [NVENCC, "-i", INPUT] + args + ["-o", out]
        print(f"\n{'='*60}")
        print(f"  测试: {name}")
        print(f"  CMD: {' '.join(cmd)}")
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        size = os.path.getsize(out) if os.path.exists(out) else 0
        ok = r.returncode == 0 and size > 2000
        status = "✅ 正常" if ok else f"❌ 异常 (size={size})"
        print(f"  结果: {status} (code={r.returncode}, size={size})")
        # 检查输出中的警告
        for line in (r.stdout + r.stderr).split("\n"):
            line = line.strip()
            if any(k in line.lower() for k in ["warn", "error", "fail", "nvvfx", "black", "format"]):
                print(f"  LOG: {line}")
        return ok, size


def main():
    print("NVVFX Denoise 全黑问题诊断")
    print(f"输入: {INPUT}")

    # 先用 ffprobe 查看实际像素格式
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-select_streams", "v:0",
             "-show_entries", "stream=pix_fmt,width,height,codec_name,color_space,color_transfer",
             "-of", "csv=p=0", INPUT],
            capture_output=True, text=True, timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=="win32" else 0)
        print(f"\n输入视频信息: {r.stdout.strip()}")
    except:
        pass

    results = {}

    # 测试1: 基准 - 无滤镜
    results["01_基准_无滤镜"] = run("01_baseline", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28"
    ])

    # 测试2: NVVFX 直接使用 (你的当前方式)
    results["02_nvvfx_直接"] = run("02_nvvfx_direct", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试3: 先转 NV12 再 NVVFX
    results["03_nvvfx_input_nv12"] = run("03_nvvfx_nv12", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--input-csp", "nv12",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试4: 指定输出 csp 为 yuv420
    results["04_nvvfx_output_yuv420"] = run("04_nvvfx_yuv420", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--output-csp", "yuv420",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试5: 强制缩放到 NVVFX 标准尺寸再处理
    results["05_nvvfx_resize_first"] = run("05_nvvfx_resize", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--output-res", "1470x630",
        "--vpp-resize", "spline64",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试6: 缩放到标准 16:9 尺寸
    results["06_nvvfx_resize_720p"] = run("06_nvvfx_720p", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--output-res", "1280x720",
        "--vpp-resize", "spline64",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试7: 缩放到 960x540 (标准 16:9)
    results["07_nvvfx_resize_540p"] = run("07_nvvfx_540p", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--output-res", "960x540",
        "--vpp-resize", "spline64",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试8: 先 pad 到 16:9 再 NVVFX
    # 1470x630 的宽高比约 2.33:1, 不是 16:9
    results["08_nvvfx_pad_1080p"] = run("08_nvvfx_pad", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--output-res", "1920x1080",
        "--vpp-resize", "spline64",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试9: NVVFX strength=1
    results["09_nvvfx_str1"] = run("09_nvvfx_str1", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-nvvfx-denoise", "strength=1"
    ])

    # 测试10: 用 avhw 解码器
    results["10_nvvfx_avhw"] = run("10_nvvfx_avhw", [
        "--avhw",
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试11: 用 avsw 解码器
    results["11_nvvfx_avsw"] = run("11_nvvfx_avsw", [
        "--avsw",
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-nvvfx-denoise", "strength=0"
    ])

    # 测试12: NVVFX artifact (对比，之前测试正常)
    results["12_nvvfx_artifact"] = run("12_artifact", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-nvvfx-artifact-reduction", "mode=0"
    ])

    # 测试13: KNN (对比正常)
    results["13_knn_对比"] = run("13_knn", [
        "--codec", "hevc", "--frames", "10", "--preset", "performance", "--cqp", "28",
        "--vpp-knn", "radius=3,strength=0.08,lerp=0.20,th_lerp=0.8"
    ])

    # ═══ 总结 ═══
    print("\n" + "=" * 60)
    print("  诊断总结")
    print("=" * 60)
    for name, (ok, size) in results.items():
        status = "✅" if ok else f"❌ ({size}b)"
        print(f"  {status}  {name}")

    # 分析
    print("\n  【分析】")
    if results["02_nvvfx_直接"][1] < 2000:
        print("  ❌ NVVFX Denoise 直接使用产生全黑视频")

        if results.get("06_nvvfx_resize_720p", (False, 0))[0]:
            print("  → 缩放到 720p 后正常: 可能是非标准分辨率问题")
            print("  → 1470x630 不是标准 16:9，NVVFX 可能需要特定宽高比")
        elif results.get("08_nvvfx_pad_1080p", (False, 0))[0]:
            print("  → 缩放到 1080p 后正常: NVVFX 需要标准分辨率")
        elif results.get("10_nvvfx_avhw", (False, 0))[0]:
            print("  → 使用 --avhw 解码后正常: 解码方式影响")
        elif results.get("11_nvvfx_avsw", (False, 0))[0]:
            print("  → 使用 --avsw 解码后正常: 解码方式影响")
        elif results.get("03_nvvfx_input_nv12", (False, 0))[0]:
            print("  → 指定 NV12 输入后正常: 色彩空间问题")
        else:
            print("  → 所有方式都全黑: 可能是 NVVFX SDK/驱动问题")
            print("  → 建议: 改用 KNN/PMD/NLMeans 降噪")

    if results["12_nvvfx_artifact"][0]:
        print("  ✅ NVVFX Artifact Reduction 正常")
        print("  → Denoise 和 Artifact 使用不同的 NVVFX 模型")

    print()


if __name__ == "__main__":
    main()