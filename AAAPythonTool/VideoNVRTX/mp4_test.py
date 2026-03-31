#!/usr/bin/env python3
"""
NVEncC 实际滤镜测试 - 用真实视频文件验证每个滤镜
"""

import subprocess
import sys
import os
import tempfile
import time


def get_creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def run_test(nvencc, input_file, test_name, extra_args, tmpdir):
    """运行单个滤镜测试"""
    out_file = os.path.join(tmpdir, f"test_{test_name.replace(' ', '_')}.mp4")

    cmd = [
        nvencc,
        "-i", input_file,
        "--codec", "hevc",
        "--frames", "3",          # 只编码3帧
        "--preset", "performance",
        "--cqp", "51",            # 最低质量，快速
    ]
    cmd.extend(extra_args)
    cmd.extend(["-o", out_file])

    # 过滤空字符串
    cmd = [c for c in cmd if c]

    print(f"\n  [{test_name}]")
    print(f"  CMD: {' '.join(cmd)}")

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            creationflags=get_creation_flags()
        )
        elapsed = time.time() - start

        if result.returncode == 0 and os.path.exists(out_file):
            size = os.path.getsize(out_file)
            print(f"  ✅ 成功 ({elapsed:.1f}s, {size} bytes)")
            return True, ""
        else:
            output = result.stdout + result.stderr
            # 提取关键错误行
            error_lines = []
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                low = line.lower()
                if any(kw in low for kw in [
                    "error", "unsupported", "invalid", "must be",
                    "failed", "not found", "cannot", "unable"
                ]):
                    error_lines.append(line)

            if not error_lines:
                # 取最后几行
                all_lines = [l.strip() for l in output.split("\n") if l.strip()]
                error_lines = all_lines[-5:]

            print(f"  ❌ 失败 (code={result.returncode}, {elapsed:.1f}s)")
            for el in error_lines[:8]:
                print(f"     {el}")
            return False, "\n".join(error_lines)

    except subprocess.TimeoutExpired:
        print(f"  ⏰ 超时")
        return False, "timeout"
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return False, str(e)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NVEncC 滤镜实际测试")
    parser.add_argument("input_file", help="测试视频文件")
    parser.add_argument("--nvencc", default="NVEncC64", help="NVEncC 路径")
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"文件不存在: {args.input_file}")
        sys.exit(1)

    print("=" * 70)
    print("  NVEncC 滤镜实际测试")
    print(f"  输入文件: {args.input_file}")
    print(f"  NVEncC:   {args.nvencc}")
    print("=" * 70)

    tests = [
        # (名称, 额外参数)
        ("00_纯编码_无滤镜", []),

        # === KNN 降噪 ===
        ("01_KNN_正确参数", [
            "--vpp-knn", "radius=3,strength=0.08,lerp=0.2,th_lerp=0.8"
        ]),
        ("02_KNN_仅strength", [
            "--vpp-knn", "strength=0.08"
        ]),
        ("03_KNN_错误参数名_lerp_threshold", [
            "--vpp-knn", "radius=3,strength=0.08,lerp_threshold=0.1,th_weight=0.02"
        ]),
        ("04_KNN_弱降噪", [
            "--vpp-knn", "radius=3,strength=0.04,lerp=0.2,th_lerp=0.8"
        ]),
        ("05_KNN_强降噪", [
            "--vpp-knn", "radius=3,strength=0.15,lerp=0.15,th_lerp=0.9"
        ]),

        # === PMD 降噪 ===
        ("06_PMD_默认", [
            "--vpp-pmd", "apply_count=2,strength=100,threshold=100"
        ]),
        ("07_PMD_弱", [
            "--vpp-pmd", "apply_count=2,strength=60,threshold=60"
        ]),
        ("08_PMD_强", [
            "--vpp-pmd", "apply_count=3,strength=150,threshold=120"
        ]),

        # === NLMeans 降噪 ===
        ("09_NLMeans_默认", [
            "--vpp-nlmeans", "sigma=5,h=5,patch=5,search=11"
        ]),
        ("10_NLMeans_弱", [
            "--vpp-nlmeans", "sigma=3,h=3,patch=5,search=11"
        ]),

        # === NVVFX 降噪 ===
        ("11_NVVFX_denoise_strength0", [
            "--vpp-nvvfx-denoise", "strength=0"
        ]),
        ("12_NVVFX_denoise_strength1", [
            "--vpp-nvvfx-denoise", "strength=1"
        ]),

        # === NVVFX 去伪影 ===
        ("13_NVVFX_artifact_mode0", [
            "--vpp-nvvfx-artifact-reduction", "mode=0"
        ]),
        ("14_NVVFX_artifact_mode1", [
            "--vpp-nvvfx-artifact-reduction", "mode=1"
        ]),

        # === Decimate ===
        ("15_Decimate_cycle5", [
            "--vpp-decimate", "cycle=5,thredup=1.1,thresc=15.0"
        ]),
        ("16_Decimate_cycle2", [
            "--vpp-decimate", "cycle=2"
        ]),
        ("17_Decimate_cycle10", [
            "--vpp-decimate", "cycle=10"
        ]),
        ("18_Decimate_cycle1_应报错", [
            "--vpp-decimate", "cycle=1"
        ]),

        # === MPDecimate ===
        ("19_MPDecimate_默认", [
            "--vpp-mpdecimate", ""
        ]),
        ("20_MPDecimate_带参数", [
            "--vpp-mpdecimate", "hi=768,lo=320,frac=0.33"
        ]),

        # === Resize ===
        ("21_Resize_spline64_960x540", [
            "--output-res", "960x540", "--vpp-resize", "spline64"
        ]),
        ("22_Resize_nvvfx_superres_2x", [
            "--output-res", "3840x2160",
            "--vpp-resize", "nvvfx-superres"
        ]),
        ("23_Resize_ngx_vsr_2x", [
            "--output-res", "3840x2160",
            "--vpp-resize", "ngx-vsr"
        ]),

        # === FRUC 补帧 ===
        ("24_FRUC_double", [
            "--vpp-fruc", "double"
        ]),
        ("25_FRUC_fps60", [
            "--vpp-fruc", "fps=60"
        ]),
        ("26_FRUC_fps120", [
            "--vpp-fruc", "fps=120"
        ]),

        # === 组合测试 ===
        ("27_组合_KNN加Resize2x", [
            "--vpp-knn", "strength=0.08",
            "--output-res", "3840x2160",
            "--vpp-resize", "spline64"
        ]),
        ("28_组合_NVVFX降噪加去伪影", [
            "--vpp-nvvfx-denoise", "strength=0",
            "--vpp-nvvfx-artifact-reduction", "mode=0"
        ]),
        ("29_组合_KNN加Decimate", [
            "--vpp-knn", "strength=0.08",
            "--vpp-decimate", "cycle=5"
        ]),
        ("30_组合_KNN加FRUC", [
            "--vpp-knn", "strength=0.08",
            "--vpp-fruc", "fps=60"
        ]),
    ]

    results = {}

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, extra_args in tests:
            success, error = run_test(args.nvencc, args.input_file, name, extra_args, tmpdir)
            results[name] = {"success": success, "error": error}

    # === 总结 ===
    print("\n" + "=" * 70)
    print("  测试总结")
    print("=" * 70)

    passed = 0
    failed = 0
    expected_fail = 0

    for name, result in results.items():
        if result["success"]:
            print(f"  ✅ {name}")
            passed += 1
        else:
            if "应报错" in name:
                print(f"  ✅ {name} (预期失败)")
                expected_fail += 1
            else:
                print(f"  ❌ {name}")
                failed += 1

    print(f"\n  通过: {passed} | 预期失败: {expected_fail} | 意外失败: {failed}")
    print("=" * 70)

    # === 生成正确参数建议 ===
    print("\n  【参数建议】")

    # KNN
    if results.get("01_KNN_正确参数", {}).get("success"):
        print("  ✅ KNN 正确参数: radius=3,strength=0.08,lerp=0.2,th_lerp=0.8")
    if results.get("03_KNN_错误参数名_lerp_threshold", {}).get("success"):
        print("  ℹ  KNN 旧参数名 lerp_threshold/th_weight 也能用")
    else:
        print("  ⚠  KNN 旧参数名 lerp_threshold/th_weight 不能用！")
        print("     必须使用: lerp 和 th_lerp")

    # NVVFX
    if results.get("11_NVVFX_denoise_strength0", {}).get("success"):
        print("  ✅ NVVFX Denoise: strength=0 (conservative) 或 strength=1 (aggressive)")
    else:
        print("  ⚠  NVVFX Denoise 不可用 (可能分辨率超限或缺少 VFX SDK)")

    # FRUC
    if results.get("24_FRUC_double", {}).get("success"):
        print("  ✅ FRUC 补帧可用")
    else:
        print("  ⚠  FRUC 补帧不可用")

    # Resize
    if results.get("22_Resize_nvvfx_superres_2x", {}).get("success"):
        print("  ✅ NVVFX SuperRes 超分可用")
    else:
        print("  ⚠  NVVFX SuperRes 不可用")

    if results.get("23_Resize_ngx_vsr_2x", {}).get("success"):
        print("  ✅ NGX VSR 超分可用")
    else:
        print("  ⚠  NGX VSR 不可用")

    print()


if __name__ == "__main__":
    main()