"""
把 DeepMosaics 的 PyTorch 权重一次性导出为 ONNX。

导出后主程序只依赖 onnxruntime，可以走 DirectML 用 GPU 推理，运行时不再需要 torch。
所以本脚本只需要跑一次，跑完就可以卸载 torch。

用法:
    python export_deepmosaics_onnx.py --src dmp --dst models
"""

import argparse
import sys
import types
from pathlib import Path

import numpy as np
import torch


def _stub_torchvision() -> None:
    """
    DeepMosaics 的 model_util 顶部有一句 `from torchvision import models`，
    但它的 ResNet 是自己定义的，torchvision 只在 pretrained=True 时才真正用到，
    而离线导出走的是 pretrained=False。为免为一行无用 import 再装一个包，这里补个占位模块。
    """
    if "torchvision" in sys.modules:
        return
    try:
        import torchvision  # noqa: F401
    except ImportError:
        stub = types.ModuleType("torchvision")
        stub.models = types.ModuleType("torchvision.models")
        sys.modules["torchvision"] = stub
        sys.modules["torchvision.models"] = stub.models

# BiSeNet 检测器: 输入按短边 360 缩放
DETECTOR_SIZE = 360
# BVDNet 生成器: 固定 256, 时序窗口 T=5 (N=2)
GEN_SIZE = 256
GEN_N = 2
GEN_T = GEN_N * 2 + 1


def build_detector(weights: Path):
    from models.BiSeNet_model import BiSeNet

    net = BiSeNet(num_classes=1, context_path="resnet18", train_flag=False)
    net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    net.eval()
    return net


def build_generator(weights: Path):
    from models.BVDNet import BVDNet

    net = BVDNet(N=GEN_N, n_blocks=4)
    net.load_state_dict(torch.load(weights, map_location="cpu", weights_only=True))
    net.eval()
    return net


def export(net, args, path: Path, input_names, output_names):
    path.parent.mkdir(parents=True, exist_ok=True)
    with torch.inference_mode():
        reference = net(*args)
    torch.onnx.export(
        net, args, str(path),
        input_names=input_names, output_names=output_names,
        opset_version=17, do_constant_folding=True, dynamo=False,
    )
    return reference


def verify(path: Path, feeds: dict, reference: torch.Tensor) -> float:
    import onnxruntime as ort

    session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    got = session.run(None, feeds)[0]
    return float(np.abs(got - reference.numpy()).max())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default="dmp", help="DeepMosaics 源码与权重所在目录")
    parser.add_argument("--dst", default="models", help="ONNX 输出目录")
    opt = parser.parse_args()

    src, dst = Path(opt.src).resolve(), Path(opt.dst).resolve()
    sys.path.insert(0, str(src))
    _stub_torchvision()

    jobs = []

    det_w = src / "mosaic_position.pth"
    if det_w.exists():
        jobs.append(("detector", det_w, dst / "mosaic_position.onnx"))
    else:
        print(f"[跳过] 找不到 {det_w}")

    gen_w = src / "clean_youknow_video.pth"
    if gen_w.exists():
        jobs.append(("generator", gen_w, dst / "clean_youknow_video.onnx"))
    else:
        print(f"[跳过] 找不到 {gen_w}")

    if not jobs:
        print("没有可导出的权重")
        return 1

    for kind, weights, out_path in jobs:
        print(f"\n=== 导出 {kind}: {weights.name} -> {out_path.name} ===")
        if kind == "detector":
            net = build_detector(weights)
            args = (torch.rand(1, 3, DETECTOR_SIZE, DETECTOR_SIZE),)
            names_in, names_out = ["image"], ["mask"]
        else:
            net = build_generator(weights)
            args = (torch.rand(1, 3, GEN_T, GEN_SIZE, GEN_SIZE) * 2 - 1,
                    torch.rand(1, 3, GEN_SIZE, GEN_SIZE) * 2 - 1)
            names_in, names_out = ["stream", "previous"], ["output"]

        reference = export(net, args, out_path, names_in, names_out)
        size_mb = out_path.stat().st_size / 1024 / 1024
        feeds = {n: a.numpy() for n, a in zip(names_in, args)}
        max_diff = verify(out_path, feeds, reference)
        print(f"  输出 {out_path.name}  {size_mb:.1f}MB  "
              f"onnx 与 torch 最大误差 {max_diff:.2e}")
        if max_diff > 1e-3:
            print("  ⚠️ 误差偏大，导出可能不正确")

    print("\n完成。之后可以卸载 torch: pip uninstall torch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
