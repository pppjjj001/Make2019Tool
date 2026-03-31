#!/usr/bin/env python3
"""
NVEncC 功能检测工具
检测 NVEncC 支持的 VPP 滤镜、编码器、参数格式
"""

import subprocess
import sys
import re
import json
import shutil
from pathlib import Path


def get_creation_flags():
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def run_cmd(cmd, timeout=15):
    """运行命令并返回输出"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=get_creation_flags()
        )
        return result.returncode, result.stdout + result.stderr
    except FileNotFoundError:
        return -1, f"找不到程序: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -2, "执行超时"
    except Exception as e:
        return -3, str(e)


class NVEncCDetector:
    """NVEncC 功能检测器"""

    def __init__(self, nvencc_path="NVEncC64"):
        self.nvencc = nvencc_path
        self.version = ""
        self.help_text = ""
        self.results = {}

    def detect_all(self):
        """运行全部检测"""
        print("=" * 70)
        print("  NVEncC 功能检测工具")
        print("=" * 70)

        self._check_binary()
        self._check_version()
        self._check_gpu()
        self._check_encoders()
        self._check_vpp_filters()
        self._check_vpp_filter_params()
        self._test_dummy_encode()

        self._print_summary()

    def _check_binary(self):
        """检查 NVEncC 是否存在"""
        print("\n[1/7] 检查 NVEncC 可执行文件...")

        # 尝试 which
        found = shutil.which(self.nvencc)
        if found:
            print(f"  ✅ 找到: {found}")
            self.results["binary"] = True
            return

        # 直接测试
        code, output = run_cmd([self.nvencc, "--version"])
        if code == -1:
            print(f"  ❌ 找不到 {self.nvencc}")
            print(f"     请确保 NVEncC64.exe 在 PATH 中或指定完整路径")
            self.results["binary"] = False
        else:
            print(f"  ✅ 可执行")
            self.results["binary"] = True

    def _check_version(self):
        """检查版本"""
        print("\n[2/7] 检查版本信息...")
        code, output = run_cmd([self.nvencc, "--version"])
        if code == 0 or code == 1:  # 有些版本 --version 返回 1
            lines = output.strip().split("\n")
            for line in lines[:5]:
                print(f"  {line.strip()}")
                if "nvencc" in line.lower():
                    self.version = line.strip()
            self.results["version"] = True
        else:
            print(f"  ⚠ 无法获取版本: {output[:200]}")
            self.results["version"] = False

    def _check_gpu(self):
        """检查 GPU 信息"""
        print("\n[3/7] 检查 GPU...")
        code, output = run_cmd([self.nvencc, "--check-device"])
        if code == 0:
            for line in output.strip().split("\n"):
                line = line.strip()
                if line:
                    print(f"  {line}")
            self.results["gpu"] = True
        else:
            print(f"  ⚠ GPU 检测失败")
            print(f"  输出: {output[:300]}")
            self.results["gpu"] = False

    def _check_encoders(self):
        """检查支持的编码器"""
        print("\n[4/7] 检查编码器支持...")

        for codec in ["h264", "hevc", "av1"]:
            code, output = run_cmd([self.nvencc, "--check-features", codec])
            if code == 0 and "not available" not in output.lower():
                print(f"  ✅ {codec.upper()}: 支持")
                self.results[f"enc_{codec}"] = True
            else:
                print(f"  ❌ {codec.upper()}: 不支持")
                self.results[f"enc_{codec}"] = False

    def _check_vpp_filters(self):
        """检查 VPP 滤镜支持"""
        print("\n[5/7] 检查 VPP 滤镜...")

        # 获取帮助文本
        code, output = run_cmd([self.nvencc, "--help"], timeout=30)
        if code in (0, 1):
            self.help_text = output
        else:
            print(f"  ⚠ 无法获取帮助信息")
            self.help_text = ""

        filters_to_check = {
            # 滤镜名: (帮助文本中的关键词, 说明)
            "vpp-knn":                    ("--vpp-knn",                    "KNN 降噪"),
            "vpp-nlmeans":                ("--vpp-nlmeans",                "Non-Local Means 降噪"),
            "vpp-pmd":                    ("--vpp-pmd",                    "PMD 降噪"),
            "vpp-nvvfx-denoise":          ("--vpp-nvvfx-denoise",          "NVIDIA VFX AI 降噪 (≤1080p)"),
            "vpp-nvvfx-artifact-reduction":("--vpp-nvvfx-artifact-reduction","NVIDIA VFX 去伪影 (≤1080p)"),
            "vpp-decimate":               ("--vpp-decimate",               "Decimate 去重复帧"),
            "vpp-mpdecimate":             ("--vpp-mpdecimate",             "MPDecimate 去重复帧"),
            "vpp-resize":                 ("--vpp-resize",                 "缩放/超分"),
            "vpp-unsharp":                ("--vpp-unsharp",                "锐化"),
            "vpp-edgelevel":              ("--vpp-edgelevel",              "边缘增强"),
            "vpp-afs":                    ("--vpp-afs",                    "自动场移位(反交错)"),
            "vpp-nnedi":                  ("--vpp-nnedi",                  "NNEDI 反交错"),
            "vpp-deband":                 ("--vpp-deband",                 "去色带"),
            "vpp-tweak":                  ("--vpp-tweak",                  "色彩调整"),
            "vpp-curves":                 ("--vpp-curves",                 "曲线调整"),
            "vpp-pad":                    ("--vpp-pad",                    "填充边框"),
            "vpp-overlay":                ("--vpp-overlay",                "叠加"),
            "vpp-fruc":                   ("--vpp-fruc",                   "光流补帧 (Frame Rate Up Conversion)"),
        }

        for filter_name, (keyword, desc) in filters_to_check.items():
            found = keyword.lower() in self.help_text.lower()
            status = "✅" if found else "❌"
            print(f"  {status} {keyword:42s} {desc}")
            self.results[f"filter_{filter_name}"] = found

    def _check_vpp_filter_params(self):
        """检查各滤镜的具体参数格式"""
        print("\n[6/7] 检查滤镜参数格式...")
        print("  (从帮助文本解析参数说明)\n")

        # === KNN ===
        self._extract_filter_help("--vpp-knn", "KNN 降噪")

        # === NVVFX Denoise ===
        self._extract_filter_help("--vpp-nvvfx-denoise", "NVVFX AI 降噪")

        # === NVVFX Artifact Reduction ===
        self._extract_filter_help("--vpp-nvvfx-artifact-reduction", "NVVFX 去伪影")

        # === Decimate ===
        self._extract_filter_help("--vpp-decimate", "Decimate")

        # === MPDecimate ===
        self._extract_filter_help("--vpp-mpdecimate", "MPDecimate")

        # === FRUC (光流补帧) ===
        self._extract_filter_help("--vpp-fruc", "FRUC 光流补帧")

        # === AFS ===
        self._extract_filter_help("--vpp-afs", "AFS 反交错")

        # === Resize 算法 ===
        self._extract_filter_help("--vpp-resize", "Resize 算法")

    def _extract_filter_help(self, keyword, desc):
        """从帮助文本提取滤镜说明"""
        print(f"  ── {desc} ({keyword}) ──")

        if keyword.lower() not in self.help_text.lower():
            print(f"     ❌ 帮助中未找到此滤镜\n")
            return

        # 找到 keyword 所在行及后续缩进行
        lines = self.help_text.split("\n")
        found = False
        collected = []

        for i, line in enumerate(lines):
            if keyword.lower() in line.lower() and not found:
                found = True
                collected.append(line.rstrip())
                continue

            if found:
                # 缩进行属于同一个滤镜说明
                stripped = line.rstrip()
                if stripped and (stripped.startswith(" ") or stripped.startswith("\t")):
                    collected.append(stripped)
                    if len(collected) > 25:  # 限制行数
                        collected.append("     ... (更多内容省略)")
                        break
                elif stripped == "":
                    # 空行可能是段内间隔
                    if len(collected) > 1:
                        break
                else:
                    break

        if collected:
            for line in collected:
                print(f"     {line}")
        else:
            print(f"     (找到关键词但无法提取详细参数)")

        print()

    def _test_dummy_encode(self):
        """用极短的测试来验证各滤镜是否能正常工作"""
        print("\n[7/7] 实际运行测试 (生成1帧测试)...")

        import tempfile
        import os

        # 创建一个极小的测试视频（用 NVEncC 的 --raw 模式或直接用现有文件）
        # 这里我们测试 --check-* 命令来避免需要实际输入文件

        tests = [
            {
                "name": "KNN 降噪参数验证",
                "filter": "--vpp-knn",
                "params_list": [
                    # (参数字符串, 说明)
                    ("radius=3,strength=0.08,lerp_threshold=0.1,th_weight=0.02",
                     "标准参数"),
                    ("radius=3,strength=0.08,lerp=0.1,th_weight=0.02",
                     "lerp 简写"),
                    ("strength=0.08",
                     "仅 strength"),
                ],
            },
            {
                "name": "Decimate 参数验证",
                "filter": "--vpp-decimate",
                "params_list": [
                    ("cycle=5,thredup=1.1,thresc=15.0",
                     "cycle=5 (标准)"),
                    ("cycle=2,thredup=1.1,thresc=15.0",
                     "cycle=2 (最小)"),
                    ("cycle=1,thredup=1.1,thresc=15.0",
                     "cycle=1 (❌ 应该报错)"),
                    ("cycle=10",
                     "cycle=10 仅 cycle"),
                    ("blockx=32,blocky=32,cycle=5",
                     "带 block 参数"),
                ],
            },
            {
                "name": "MPDecimate 参数验证",
                "filter": "--vpp-mpdecimate",
                "params_list": [
                    ("hi=768,lo=320,frac=0.33",
                     "标准参数"),
                    ("",
                     "默认参数(无参数)"),
                ],
            },
            {
                "name": "NVVFX Denoise 参数验证",
                "filter": "--vpp-nvvfx-denoise",
                "params_list": [
                    ("strength=0",
                     "strength=0 (自动)"),
                    ("strength=50",
                     "strength=50"),
                ],
            },
        ]

        # 我们不能直接测试滤镜（需要输入文件），
        # 但可以用 --check-vpp 如果有的话，或者解析帮助

        print("\n  注: 以下为参数格式分析（基于帮助文本和已知规则）")
        print("  要进行实际测试，需要一个视频文件。\n")

        for test in tests:
            print(f"  ── {test['name']} ──")
            filter_name = test["filter"]
            filter_found = filter_name.lower() in self.help_text.lower()

            if not filter_found:
                print(f"     ❌ 滤镜 {filter_name} 不可用，跳过\n")
                continue

            for params, desc in test["params_list"]:
                # 基于已知规则分析
                issues = self._analyze_params(filter_name, params)
                if issues:
                    print(f"     ⚠ {filter_name} {params}")
                    print(f"       {desc}")
                    for issue in issues:
                        print(f"       → {issue}")
                else:
                    print(f"     ✅ {filter_name} {params}")
                    print(f"       {desc}")

            print()

    def _analyze_params(self, filter_name, params):
        """基于已知规则分析参数是否正确"""
        issues = []

        if filter_name == "--vpp-decimate":
            # cycle 必须 >= 2
            m = re.search(r'cycle=(\d+)', params)
            if m:
                cycle = int(m.group(1))
                if cycle < 2:
                    issues.append(f"cycle={cycle} 无效，必须 >= 2")
            else:
                issues.append("缺少 cycle 参数")

        elif filter_name == "--vpp-knn":
            # 检查参数名是否正确
            valid_params = {"radius", "strength", "lerp_threshold",
                            "lerp", "th_weight", "th_lerp", "channel"}
            for part in params.split(","):
                if "=" in part:
                    key = part.split("=")[0].strip()
                    if key not in valid_params:
                        issues.append(
                            f"参数 '{key}' 可能无效，"
                            f"有效参数: {', '.join(sorted(valid_params))}"
                        )

        elif filter_name == "--vpp-nvvfx-denoise":
            # strength 范围 0-100（或 0.0-1.0 取决于版本）
            m = re.search(r'strength=(\d+)', params)
            if m:
                val = int(m.group(1))
                if val < 0:
                    issues.append(f"strength={val} 无效，不能小于 0")

        return issues

    def _print_summary(self):
        """打印总结"""
        print("\n" + "=" * 70)
        print("  检测总结")
        print("=" * 70)

        # 基础环境
        print("\n  【基础环境】")
        items = [
            ("binary", "NVEncC 可执行文件"),
            ("version", "版本信息"),
            ("gpu", "GPU 检测"),
        ]
        for key, desc in items:
            status = "✅" if self.results.get(key) else "❌"
            print(f"    {status} {desc}")

        # 编码器
        print("\n  【编码器】")
        for codec in ["h264", "hevc", "av1"]:
            status = "✅" if self.results.get(f"enc_{codec}") else "❌"
            print(f"    {status} {codec.upper()}")

        # 常用滤镜
        print("\n  【VPP 滤镜】")
        important_filters = [
            ("filter_vpp-knn", "KNN 降噪 (无分辨率限制)"),
            ("filter_vpp-nlmeans", "Non-Local Means 降噪 (无分辨率限制)"),
            ("filter_vpp-pmd", "PMD 降噪 (无分辨率限制)"),
            ("filter_vpp-nvvfx-denoise", "NVIDIA VFX AI 降噪 (≤1080p)"),
            ("filter_vpp-nvvfx-artifact-reduction", "NVIDIA VFX 去伪影 (≤1080p)"),
            ("filter_vpp-decimate", "Decimate 去重复帧 (cycle≥2)"),
            ("filter_vpp-mpdecimate", "MPDecimate 去重复帧"),
            ("filter_vpp-fruc", "FRUC 光流补帧"),
            ("filter_vpp-resize", "Resize 缩放"),
            ("filter_vpp-afs", "AFS 反交错"),
            ("filter_vpp-deband", "去色带"),
        ]
        for key, desc in important_filters:
            status = "✅" if self.results.get(key) else "❌"
            print(f"    {status} {desc}")

        # 建议
        print("\n  【关键建议】")

        if self.results.get("filter_vpp-decimate"):
            print("    ⚠ vpp-decimate 的 cycle 参数必须 >= 2，不能设为 1")
            print("      示例: --vpp-decimate cycle=5,thredup=1.1,thresc=15.0")

        if self.results.get("filter_vpp-nvvfx-denoise"):
            print("    ⚠ vpp-nvvfx-denoise 要求输入分辨率 ≤ 1920x1080")
            print("      超过此分辨率需要先缩小再处理")

        if self.results.get("filter_vpp-nvvfx-artifact-reduction"):
            print("    ⚠ vpp-nvvfx-artifact-reduction 要求输入分辨率 ≤ 1920x1080")

        if not self.results.get("filter_vpp-fruc"):
            print("    ℹ vpp-fruc (光流补帧) 不可用，")
            print("      可能需要更新 NVEncC 或 GPU 不支持")

        print("\n" + "=" * 70)

        # 导出 JSON
        try:
            json_path = "nvencc_detect_result.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2, ensure_ascii=False)
            print(f"\n  检测结果已保存到: {json_path}")
        except Exception as e:
            print(f"\n  保存结果失败: {e}")


def test_with_real_file(nvencc_path="NVEncC64", test_file=None):
    """使用实际视频文件测试各滤镜"""
    import tempfile
    import os

    if test_file is None:
        print("\n需要提供测试视频文件路径")
        print("用法: test_with_real_file('NVEncC64', 'test.mp4')")
        return

    if not os.path.exists(test_file):
        print(f"文件不存在: {test_file}")
        return

    print("\n" + "=" * 70)
    print(f"  实际滤镜测试 (使用: {test_file})")
    print("=" * 70)

    # 只编码前 5 帧
    base_cmd = [
        nvencc_path,
        "-i", test_file,
        "--codec", "hevc",
        "--frames", "5",
        "--preset", "performance",
        "--cqp", "51",  # 最低质量，快速测试
    ]

    tests = [
        {
            "name": "纯编码 (无滤镜)",
            "args": [],
        },
        {
            "name": "KNN 降噪 (strength=0.08)",
            "args": ["--vpp-knn", "radius=3,strength=0.08,lerp_threshold=0.1,th_weight=0.02"],
        },
        {
            "name": "KNN 降噪 (仅 strength)",
            "args": ["--vpp-knn", "strength=0.08"],
        },
        {
            "name": "PMD 降噪",
            "args": ["--vpp-pmd", "apply_count=2,strength=100,threshold=100"],
        },
        {
            "name": "NVVFX AI 降噪 (strength=0)",
            "args": ["--vpp-nvvfx-denoise", "strength=0"],
        },
        {
            "name": "NVVFX 去伪影 (mode=1)",
            "args": ["--vpp-nvvfx-artifact-reduction", "mode=1"],
        },
        {
            "name": "Decimate (cycle=5)",
            "args": ["--vpp-decimate", "cycle=5,thredup=1.1,thresc=15.0"],
        },
        {
            "name": "Decimate (cycle=2)",
            "args": ["--vpp-decimate", "cycle=2"],
        },
        {
            "name": "❌ Decimate (cycle=1，应报错)",
            "args": ["--vpp-decimate", "cycle=1"],
        },
        {
            "name": "MPDecimate (默认)",
            "args": ["--vpp-mpdecimate", ""],
        },
        {
            "name": "Resize (spline64 → 960x540)",
            "args": ["--output-res", "960x540", "--vpp-resize", "spline64"],
        },
        {
            "name": "FRUC 光流补帧",
            "args": ["--vpp-fruc", "fps=60"],
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, test in enumerate(tests):
            out_file = os.path.join(tmpdir, f"test_{i:02d}.mp4")
            cmd = base_cmd + test["args"] + ["-o", out_file]

            # 移除空字符串参数
            cmd = [c for c in cmd if c]

            print(f"\n  [{i+1}/{len(tests)}] {test['name']}")
            print(f"  CMD: {' '.join(cmd)}")

            code, output = run_cmd(cmd, timeout=60)

            if code == 0:
                size = os.path.getsize(out_file) if os.path.exists(out_file) else 0
                print(f"  ✅ 成功 (输出 {size} bytes)")
            else:
                # 提取错误信息
                error_lines = [
                    l.strip() for l in output.split("\n")
                    if l.strip() and ("error" in l.lower() or
                                      "unsupported" in l.lower() or
                                      "invalid" in l.lower() or
                                      "must be" in l.lower() or
                                      "failed" in l.lower())
                ]
                if error_lines:
                    print(f"  ❌ 失败 (code={code})")
                    for el in error_lines[:5]:
                        print(f"     {el}")
                else:
                    print(f"  ❌ 失败 (code={code})")
                    # 输出最后几行
                    last_lines = [l for l in output.strip().split("\n") if l.strip()]
                    for el in last_lines[-5:]:
                        print(f"     {el}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NVEncC 功能检测工具")
    parser.add_argument(
        "--nvencc", default="NVEncC64",
        help="NVEncC 路径 (默认: NVEncC64)"
    )
    parser.add_argument(
        "--test-file", default=None,
        help="测试视频文件路径 (可选，用于实际滤镜测试)"
    )
    args = parser.parse_args()

    detector = NVEncCDetector(args.nvencc)
    detector.detect_all()

    if args.test_file:
        test_with_real_file(args.nvencc, args.test_file)
    else:
        print("\n  提示: 使用 --test-file <视频> 可进行实际滤镜测试")
        print("  例: python nvencc_detector.py --test-file test.mp4")

    print()


if __name__ == "__main__":
    main()