# VideoToolbox

一个基于 **OpenCV + Tkinter** 的 Python 视频处理全家桶，内置 36 种视频/图像处理功能，涵盖基础剪辑、画面调整、特效滤镜、水印/调色/字幕、DNN AI 能力（人脸/物体检测、风格迁移、人像分割、字幕 OCR、视频降噪、去马赛克等）与分析工具，支持多功能串联的流程组合模式。日常推理走 **OpenCV DNN + onnxruntime**；不能转 ONNX 的官方 `.pth`（目前默认 VRT 008 降噪）走独立子窗口，**全程本机**，主程序不 `import torch`。

## 功能清单

### 基础处理
1. 视频裁剪（时间段截取）
2. 视频缩放（分辨率调整）
3. 视频旋转/翻转
4. 视频拼接
5. 帧率调整
6. 视频转 GIF
7. 提取帧画面

### 画面调整
8. 亮度/对比度/饱和度
9. 色彩空间转换（灰度/HSV/LAB）
10. 直方图均衡化
11. 锐化/模糊（传统空域，仍带轻度非局部均值）
12. 视频降噪（主窗口：FFmpeg 快档 / DnCNN / SCUNet / FastDVDnet；`.pth` 走独立入口，见下方专门说明）

### 特效滤镜
13. 铅笔素描
14. 卡通化
15. 浮雕效果
16. 边缘检测（Canny/Sobel/Laplacian）
17. 怀旧/冷暖色调
18. 马赛克/像素化
19. 晕影效果

### 水印 / 调色 / 字幕
20. 水印添加（文字或图片，支持中文、旋转、平铺、九宫格定位，见下方专门说明）
21. 水印去除（区域 inpaint / 模糊 / 像素化，可配合智能蒙版，见下方专门说明）
22. LUT 颜色分级（`.cube` / LUT 贴图 / 7 种内置预设，见下方专门说明）
23. 字幕烧录（SRT / ASS 解析 + 描边渲染，见下方专门说明）

### DNN AI 功能
24. 人脸检测（SSD/Caffe）
25. 物体检测（YOLOv4-tiny）
26. 风格迁移（Neural Style Transfer + 参考图模式）
27. 人脸马赛克（检测 + 模糊）
28. 背景虚化 / 人像分割（RobustVideoMatting，可虚化/换纯色/换图片，见下方专门说明）
29. 文字检测（EAST）
30. 字幕 OCR 提取（EAST 检测 + CRNN 识别 → 导出 SRT，见下方专门说明）
31. 去马赛克/超分重建（Real-ESRGAN / DeepMosaics / ESPCN，见下方专门说明）

### 分析工具
32. 亮度曲线分析
33. 颜色直方图
34. 运动检测/热力图
35. 视频信息查看

### 高级功能
36. 流程组合（多种功能按顺序串联处理）

### 工程化能力
- **批处理队列** — 把多个文件或整个文件夹加进队列，套用同一套参数逐个处理
- **参数预设** — 当前所有参数一键存成 JSON，随时复用（去马赛克/DNN 参数多，尤其省事）
- **输出编码** — H.264 / H.265 输出，CRF 或目标码率控制，可保留原音轨
- **处理日志** — 界面内日志窗口 + 自动落盘到 `logs/`
- **拖拽与快捷键** — 拖入文件即处理，常用操作都有快捷键
- **Torch `.pth` 入口** — `Ctrl+T` 开子窗口，本机另起进程跑官方权重；以后其它 `.pth` 也走这里，不进主窗口 36 项流程

## 环境要求

- Windows 10/11（`opencv_family.bat` 一键安装脚本仅支持 Windows；核心 `main.py` 理论上可跨平台运行）
- Python 3.7+（推荐 3.8+，需自带 `tkinter`）

### 依赖包

完整清单见 [`requirements.txt`](requirements.txt)，直接 `pip install -r requirements.txt` 即可。

| 包 | 必须性 | 说明 |
|---|---|---|
| `opencv-python` | 必须 | 图像/视频处理核心 |
| `numpy` | 必须 | 数组计算 |
| `onnxruntime-directml` | 必须 | ONNX 推理引擎，Windows 下用 DirectML 做 GPU 加速（比纯 CPU 版快 50+ 倍，无需装 CUDA/cuDNN）。有独立 NVIDIA 显卡也可用 `onnxruntime-gpu` 代替；非 Windows 用 `onnxruntime` |
| `onnx` | 必须 | Real-ESRGAN 分块推理时用于改写模型输入形状 |
| `scipy` | 建议 | 亮度曲线分析的平滑 |
| `Pillow` | 建议 | 提升 GUI 图像预览体验；**水印和字幕要显示中文必须装它**（OpenCV 自带的 `putText` 画不出汉字，缺失时会退化成只能画 ASCII 并在日志里警告） |
| `tkinterdnd2` | 可选 | 文件拖拽导入。缺失时程序照常启动，只是拖不进去（也可改装 `windnd`，仅 Windows） |
| `FFmpeg` | 可选 | **不是 Python 包**，需单独安装并加入 `PATH`。H.264/H.265 编码、码率控制、保留音频、转 GIF 的最优路径都依赖它 |
| `torch` | 可选 | **日常主程序不需要。** 两处才会用到：① `export_deepmosaics_onnx.py` 一次性导出；② `Ctrl+T` 的 Torch `.pth` 子进程。主窗口不 `import torch` |

> `requirements.txt` 第一行的 `# -*- coding: utf-8 -*-` 不要删。pip 读 requirements 文件时如果既没有 BOM 也没有 coding 声明，会按系统默认编码解码（中文 Windows 上是 GBK），文件里的中文注释会让 `pip install -r` 直接报 `UnicodeDecodeError`。

## 快速开始

### 方式一：一键安装脚本（推荐，Windows）

```bat
opencv_family.bat
```

脚本会自动：
- 查找/创建项目私有 Python 虚拟环境（`venv/`），全程不需要管理员权限
- 检测 Python、pip、依赖包、FFmpeg、DNN 模型是否齐全
- 检测不通过时提供菜单：自动修复缺失依赖、单独安装依赖包、下载缺失模型、创建虚拟环境、查看详细帮助
- 检测通过后可直接选择启动主程序

### 方式二：手动安装

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 项目结构

```
VideoOpencv/
├── main.py                       # 主程序（GUI + ONNX/OpenCV 引擎）。只做 .pth 入口，不 import torch
├── vrt_window.py                 # Torch .pth 子窗口（选路径、起停本机子进程、收进度）
├── infer_vrt.py                  # 本机推理子进程：只有这里才会 import torch / 加载 .pth
├── setup_vrt.py                  # 下载官方 network_vrt.py + 008 降噪权重（不 import torch）
├── third_party/VRT/              # 官方 VRT 网络（至少要有 models/network_vrt.py）
├── requirements.txt              # 主程序依赖（不含 torch）
├── opencv_family.bat             # Windows 一键环境检测/安装/启动脚本
├── export_deepmosaics_onnx.py    # 把 DeepMosaics 的 PyTorch 权重导出为 ONNX（一次性工具）
├── models/                       # DNN 模型：ONNX 走 Ctrl+M；008 .pth 走 setup_vrt.py
├── charsets/                     # 字幕 OCR 的 CRNN 字符表（随代码库分发，勿删）
├── luts/                         # 放自己的 .cube / LUT 贴图（可选）
├── presets/                      # 主窗口参数预设；另有 torch_pth.json 记 .pth 窗口路径
├── logs/                         # 处理日志（自动创建，只保留最近 20 份）
├── dmp/                          # DeepMosaics 源码 + .pth 权重（用于导出 ONNX）
├── venv/                         # 项目私有环境（主程序 + 当前这套 CPU torch）
└── venv_torch/                   # 可选：单独的 CUDA torch 环境，窗口里改 Python 路径即可
```

## 批处理 / 预设 / 日志 / 快捷键

### 批处理队列（`Ctrl+B`）

对一批文件套用同一套参数：

1. 主窗口左侧选好功能、右侧调好参数
2. `Ctrl+B` 打开队列窗口，用「添加文件」或「添加文件夹」入队（也可以直接把文件/文件夹拖进主窗口）
3. 设置输出目录和文件名后缀（留空输出目录时，输出放到每个源文件同级的 `output/` 里）
4. 点「开始批处理」

点开始的瞬间参数会被**快照**，之后再改主窗口不影响正在跑的这一批。勾选「跳过已存在的输出」可以断点续跑。视频拼接是「多进一出」，和批处理的「逐个套用」语义冲突，会被拒绝。

### 参数预设（`Ctrl+S` 保存 / `Ctrl+R` 载入）

把当前功能 + 所有参数（含流程组合的勾选项）存成 JSON，默认放在 `presets/`。输出路径不会写进预设，换文件时不用改。载入旧版本预设时，无法识别的字段会被跳过并提示，不会整个失败。

### 处理日志（`Ctrl+L`）

界面内可按级别过滤查看，同时自动落盘到 `logs/videotoolbox_<时间戳>.log`（只保留最近 20 份）。去马赛克模型回退、FFmpeg 编码参数、批处理每个文件的成败都会记在里面。

### 输出编码

「输出编码」面板对产出视频的功能可用：

| 编码器 | 依赖 | 说明 |
|---|---|---|
| 自动 | 无 | `mp4v` / `.avi` 时用 `XVID`，走 `cv2.VideoWriter` |
| H.264 (libx264) | FFmpeg | 支持 CRF / 目标码率、保留音轨 |
| H.265 / HEVC (libx265) | FFmpeg | 同上，体积更小、编码更慢 |

- **CRF**：恒定质量，18~23 基本视觉无损，0 为无损，值越大越小越糊
- **目标码率**：按 kbps 控制体积，同时设置 `maxrate`/`bufsize`
- **保留原音频**：只在 FFmpeg + H.264/H.265 下可用。裁剪时音频按同样的时间段裁；**帧率调整会改变时长**，那种情况下会自动丢弃音轨，避免产出音画不同步的文件
- 未装 FFmpeg 时选了 H.264/H.265 会自动退回 `mp4v` 并在日志里说明

### 拖拽导入

装了 `tkinterdnd2`（或 `windnd`）后可以直接往窗口里拖：

- 单个视频 → 直接打开
- 多个视频 / 文件夹 → 进批处理队列（文件夹递归扫描）
- `.srt` / `.ass` → 填进字幕烧录的字幕路径，并自动切到「字幕烧录」
- `.cube` → 填进 LUT 路径，并自动切到「LUT 颜色分级」
- 图片 → 按当前选中的功能决定用途：水印添加下当水印图、背景虚化下当背景图、LUT 分级下当 LUT 贴图，其他情况仍作风格迁移参考图

### 快捷键

| 快捷键 | 功能 |
|---|---|
| `Ctrl+O` | 打开视频 |
| `Ctrl+Shift+O` | 添加文件到批处理队列 |
| `Ctrl+B` | 批处理队列窗口 |
| `Ctrl+S` / `Ctrl+R` | 保存 / 载入参数预设 |
| `Ctrl+F` | 定位到功能搜索框 |
| `Ctrl+L` | 处理日志窗口 |
| `Ctrl+M` | DNN 模型管理 |
| `Ctrl+T` | Torch `.pth` 子窗口（默认 VRT 008 降噪） |
| `F5` | 预览当前参数效果 |
| `F9` / `Ctrl+Enter` | 开始处理 |
| `Esc` | 取消处理 |
| `F1` | 快捷键说明 |

功能搜索框支持中文名、分类名、英文别名和拼音（`gif` / `mosaic` / `crop` / `blur` / `watermark` / `lut` / `cube` / `srt` / `ocr` / `shuiyin` / `tiaose` / `zimu` 等），不用切输入法。

## 迁移到其他电脑

换电脑/换盘时，**不要直接拷贝整个项目文件夹**（`venv/` 很大且和当前系统绑定，拷过去大概率用不了），按下面的取舍来拷贝即可。

### 必须拷贝

| 文件/目录 | 大小(约) | 说明 |
|---|---|---|
| `main.py` | <1MB | 主程序 |
| `vrt_window.py` / `infer_vrt.py` / `setup_vrt.py` | <50KB | Torch `.pth` 入口三件套，不拷就打不开 `Ctrl+T` |
| `requirements.txt` | <1KB | 依赖清单，安装脚本会优先用它装依赖 |
| `opencv_family.bat` | <1MB | 一键环境检测/安装/启动脚本 |
| `charsets/` | ~30KB | 字幕 OCR 的 CRNN 字符表，不拷过去 OCR 功能会显示为不可用 |
| `models/` | ~800MB | 已下载的 ONNX + 若有 `008_VRT_videodenoising_DAVIS.pth`（约 102MB） |

### 按需拷贝（可选）

| 文件/目录 | 大小(约) | 什么时候需要 |
|---|---|---|
| `dmp/` | ~150MB | 只有以后还想用 `export_deepmosaics_onnx.py` 重新导出/更新 DeepMosaics 模型时才需要；`models/` 里已经有导出好的 `.onnx` 的话，日常使用不需要这个目录 |
| `export_deepmosaics_onnx.py` | <1MB | 配合上面的 `dmp/` 一起用，同样只在需要重新导出时才需要 |
| `luts/` | 看你放了多少 | 自己收集的 `.cube` / LUT 贴图 |
| `presets/` | <1MB | 主窗口参数预设；`torch_pth.json` 是 .pth 窗口上次填的路径 |
| `third_party/VRT/` | <1MB | 官方 `network_vrt.py`。没有的话新电脑上再跑一次 `python setup_vrt.py` 即可 |

### 不要拷贝

| 文件/目录 | 原因 |
|---|---|
| `venv/`（约 950MB） | Python 虚拟环境里的路径、依赖是和当前电脑绑定的，直接拷过去大概率启动不了；新电脑上用 `opencv_family.bat` 重新创建即可，几分钟搞定 |
| `logs/` | 处理日志，换机器没有意义，会自动重建 |
| `__pycache__/` | Python 编译缓存，会自动重新生成 |
| `main - 副本.py` 之类的备份/临时文件 | 非必要文件 |

### 新电脑上的步骤

1. 拷贝「必须拷贝」（以及需要的话，「按需拷贝」）里的内容到新目录，保持相对路径结构不变（`models/`、`charsets/`、`dmp/`、`third_party/` 要和 `main.py` 在同一层）
2. 双击运行 `opencv_family.bat`，选择 `[4] 创建/重建私有环境` 或直接让它自动创建
3. 环境检测通过后（`models/` 已经拷过去了，ONNX 会直接显示已齐全），选 `[Y]` 启动即可
4. 若还要用 `Ctrl+T` 的 VRT：在新环境里按下方「Torch .pth 入口」装 `torch` / `einops` / `torchvision`（不要让 pip 擅自升级已有 torch），缺网络文件就跑 `python setup_vrt.py`

## 模型下载地址一览

`models/` 目录下的文件都不随代码库分发，需要单独下载。凡是「自动下载」列打 ✅ 的都可以直接运行 `opencv_family.bat` → `[3] 仅下载缺失 DNN 模型`（或程序内的模型管理窗口 `Ctrl+M`）自动下载；去马赛克和 Real-ESRGAN 模型体积太大、且托管在不稳定的境外站点，需要按下方链接手动获取。

| 分类 | 文件 | 大小 | 下载地址 | 自动下载 |
|---|---|---|---|---|
| 人脸检测 | `deploy.prototxt` | ~28KB | <https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt> | ✅ |
| 人脸检测 | `res10_300x300_ssd_iter_140000.caffemodel` | ~10MB | <https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel> | ✅ |
| 物体检测 | `yolov4-tiny.cfg` | ~3KB | <https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg> | ✅ |
| 物体检测 | `yolov4-tiny.weights` | ~24MB | <https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights> | ✅ |
| 物体检测 | `coco.names` | ~1KB | <https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names> | ✅ |
| 风格迁移 | `mosaic.t7` / `candy.t7` / `rain_princess.t7` / `udnie.t7` | 各 ~10-15MB | <https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/instance_norm/> + 文件名 | ✅ |
| 风格迁移 | `the_wave.t7` / `starry_night.t7` / `la_muse.t7` / `composition_vii.t7` | 各 ~10-25MB | <https://cs.stanford.edu/people/jcjohns/fast-neural-style/models/eccv16/> + 文件名 | ✅ |
| 文字检测 | `frozen_east_text_detection.pb` | ~96MB | <https://raw.githubusercontent.com/oyyd/frozen_east_text_detection.pb/master/frozen_east_text_detection.pb> | ✅ |
| 人像分割 | `rvm_mobilenetv3_fp32.onnx` | ~15MB | <https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx> | ✅ |
| 字幕 OCR（中文） | `text_recognition_CRNN_CN_2021nov.onnx` | ~69MB | <https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_CN_2021nov.onnx> | ✅ |
| 字幕 OCR（英文） | `text_recognition_CRNN_EN_2021sep.onnx` | ~32MB | <https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx> | ✅ |
| 单帧降噪 | `dncnn_color.onnx` | ~2.6MB | <https://github.com/ikeno-web/npuscale/releases/download/v1.2/dncnn_color.onnx> | ✅ |
| 单帧降噪 | `scunet_color_real_psnr.onnx` + `.onnx.data` | ~3.6MB + ~70MB | <https://huggingface.co/Heliosoph/scunet-onnx/resolve/main/scunet_color_real_psnr.onnx>（配套 `.onnx.data` 必须放同一目录） | ✅ |
| 时域降噪 | `fastdvdnet_s15.onnx` / `s25` / `s50` | 各 ~9.5MB | <https://github.com/ikeno-web/npuscale/releases/download/v1.3/fastdvdnet_s25.onnx>（把文件名里的 `s25` 换成 `s15` / `s50`） | ✅ |
| VRT 视频降噪 | `008_VRT_videodenoising_DAVIS.pth` | ~102MB | <https://github.com/JingyunLiang/VRT/releases/download/v0.0/008_VRT_videodenoising_DAVIS.pth>（窗口「补全官方文件」或 `python setup_vrt.py`） | ❌ 走 setup_vrt |
| VRT 网络代码 | `third_party/VRT/models/network_vrt.py` | ~70KB | 官方 [JingyunLiang/VRT](https://github.com/JingyunLiang/VRT)，同样由 `setup_vrt.py` 拉取 | ❌ 走 setup_vrt |
| 超分（轻量） | `ESPCN_x4.pb` | ~100KB | <https://raw.githubusercontent.com/fannymonori/TF-ESPCN/master/export/ESPCN_x4.pb> | ✅ |
| 超分（Real-ESRGAN） | `realesrgan-x4plus.onnx` | ~64MB | <https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-x4plus.onnx>（备用：<https://huggingface.co/ai-forever/Real-ESRGAN/resolve/main/RealESRGAN_x4.onnx>） | ❌ 手动 |
| 超分（Real-ESRGAN 动漫） | `realesrgan-x4plus-anime.onnx` | 数MB~20MB | <https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-x4plus-anime.onnx> | ❌ 手动 |
| 去马赛克（DeepMosaics） | `mosaic_position.onnx` + `clean_youknow_video.onnx` | ~48MB + ~213MB | 由 `dmp/` 里的 `.pth` 权重本地导出得到，权重来自 <https://github.com/foooooooooooooooooooooooooootw/DeepMosaicsPlus/releases/latest/download/DeepMosaicsPlus.zip>（源码仓库：<https://github.com/foooooooooooooooooooooooooootw/DeepMosaicsPlus>；原始项目：<https://github.com/HypoX64/DeepMosaics>） | ❌ 手动 |

> 提示：如果 GitHub 在你的网络环境下访问不稳定，可以给 GitHub 链接加一个加速代理前缀重试，例如 `https://ghfast.top/` + 原始 GitHub 链接（`raw.githubusercontent.com`、`github.com/.../releases/...` 均适用）。

> - **人像分割**走 `onnxruntime`（不走 `cv2.dnn`，因为 RVM 有帧间循环状态），模型下好了但没装 `onnxruntime` 时会提示并回退。
> - **字幕 OCR** 除了 `.onnx` 还需要 `charsets/` 里配套的字符表（`charset_3944_CN.txt` / `charset_36_EN.txt`），这两个文件随代码库分发，删掉的话模型会被判定为不可用。
> - **SCUNet** 是「小图文件 + 外置权重」一对，两个都下齐才能用。
> - **视频降噪**的 FastDVDnet / DnCNN / SCUNet 都走 `onnxruntime`（DirectML 可用）。VRT `.pth` 不走这条，见下方「Torch .pth 入口」。

## 视频降噪功能说明

主窗口「视频降噪」里分档选，全部本机、不经过 `.pth`：

| 档 | 方法 | 依赖 | 适合 |
|---|---|---|---|
| **快档** | FFmpeg `hqdn3d` / `atadenoise` / `nlmeans` | 系统 `ffmpeg` | 轻颗粒、要速度、要保真 |
| **质量档** | FastDVDnet（5 帧时域） | `fastdvdnet_s15/s25/s50.onnx` + onnxruntime | 实拍、手机夜景、传感器噪声 |
| **质量档** | SCUNet / DnCNN（单帧） | 对应 ONNX | 动画、录屏、预览；或 FastDVD 缺失时的回退 |
| **兜底** | OpenCV 非局部均值 | 无 | 模型和 FFmpeg 都没有时仍能用 |

- **实拍 / 动画**开关：动画、定格、硬切不要走 FastDVDnet，时域融合会把线稿糊掉，这时会强制改用单帧模型。
- **σ=15/25/50**：FastDVDnet 是三套分开训练的权重；快档里同一组数字只是用来加减滤镜力度。
- **混合强度**：把降噪结果按比例混回原图，宁可欠一点也不要抹成塑料皮。
- **色度多降一点**：FFmpeg 档对 U/V 下手更重，专门灭色斑。
- 快档是整段丢给 FFmpeg 的滤镜图（`atadenoise` 这种必须看前后帧，不能逐帧在 Python 里跑）。质量档在工具里逐帧/滑窗推理，4K 会自动分块以免撑爆显存。
- 缺模型或没装 `onnxruntime` 时会按 `FastDVDnet → DnCNN → OpenCV` 降级，原因写在处理日志（`Ctrl+L`）里。
- 「锐化/模糊」里那条旧的降噪滑条还在，只是单帧 `fastNlMeans`，和新功能不是一回事。
- 还要官方 Transformer 降噪（VRT 008）时，不要在这个列表里找，走下面的独立入口。

## Torch .pth 入口（本机子进程）

不能转 ONNX、必须 `torch.load(.pth)` 的模型，**一律走这里**，以后加别的 `.pth` 也是这个入口，不写进 `main.py` 的 36 项流程。

全部在本机：子窗口和推理进程都是这台电脑上的 Python，不上传。所谓「子进程」只是再开一个本地解释器，避免主窗口 `import torch` 后变卡、变胖、崩了整棵 GUI。

### 三层怎么拆

| 层 | 文件 | 干什么 | 会不会 `import torch` |
|---|---|---|---|
| 入口 | `main.py` | 菜单 **工具 → VRT / Torch .pth 降噪**（`Ctrl+T`），或「视频降噪」参数页按钮 | 否，只懒加载窗口 |
| 窗口 | `vrt_window.py` | 选 Python / 仓库 / `.pth`、开始、取消、进度 | 否 |
| 推理 | `infer_vrt.py` | 读视频、加载权重、写结果；进度行以 `#VT` 开头回窗口 | **是**，只在这个进程里 |

准备脚本 `setup_vrt.py` 只下载文件，也不 `import torch`。

### 默认接好的方案：VRT 008 视频降噪

当前入口默认就是官方 [JingyunLiang/VRT](https://github.com/JingyunLiang/VRT) 的 **008 DAVIS 视频降噪**（非盲，σ 0–50），本机已按这个对齐：

| 项 | 默认位置 |
|---|---|
| 任务 | `vrt_denoise` |
| 官方网络 | `third_party/VRT/models/network_vrt.py` |
| 权重 | `models/008_VRT_videodenoising_DAVIS.pth`（约 102MB） |
| Python | 项目 `venv`（窗口可改） |
| 路径记忆 | `presets/torch_pth.json` |

怎么用：主窗口打开视频 → `Ctrl+T` → 点「开始（子进程）」。缺网络或权重时点窗口里的「补全官方文件」，或：

```bash
python setup_vrt.py
```

参数：`σ` 对应官方 non-blind 噪声图；空间分块默认 256（`0` = 整帧，显存不够降到 128）；时间窗默认 12。CPU 上会很慢，适合短片；日常长片仍用主窗口 FastDVDnet。

窗口里其它任务（同一套入口，换权重即可）：

| 任务 | 说明 | 还要什么 |
|---|---|---|
| `vrt_denoise` | 默认。008 降噪 | 上面两样默认文件 |
| `vrt_deblur` | VRT 去模糊 | 对应官方 `.pth`（005/006/007） |
| `vrt_sr` | VRT 超分 ×4 | 对应官方 `.pth`（001 等） |
| `jit` | TorchScript / 整模 `.pt` | 文件本身就是可跑的模块 |
| `auto` | 按文件名猜上面几种 | — |

不是任意 `.pth` 丢进去就能跑：权重必须配得上网络代码。VRT 用官方 `network_vrt.py`；`jit` 要整模或 TorchScript。其它论文结构以后仍走这个窗口，在 `infer_vrt.py` 里加一种任务即可。

### 这个入口额外要装的包

**不要**写进主程序的 `requirements.txt`，也不要用裸 `pip install timm`（新版会顺带把 `torch` 升到 2.13）。和现有 `torch 2.9.1+cpu` 对齐的装法：

```bash
venv\Scripts\python.exe -m pip install einops "timm==0.6.13" --no-deps
venv\Scripts\python.exe -m pip install "torchvision==0.24.1" --index-url https://download.pytorch.org/whl/cpu --no-deps
```

| 包 | 实际用途 |
|---|---|
| `torch` | 加载 `.pth`、推理 |
| `einops` | 官方 `network_vrt.py` 里的张量重排 |
| `torchvision` | 官方网络的 `deform_conv2d`（硬依赖，版本要跟 torch 对齐） |
| `timm` | 官方文件已把 DropPath 抄进去了，现成环境里装着即可，不是推理硬依赖 |

有 NVIDIA 显卡想加速：另建 `venv_torch`，装 CUDA 版 `torch` + 配套 `torchvision`，再在子窗口把 Python 指过去。主程序继续用原来的 `venv`。

## 水印 / 调色 / 字幕功能说明

### 水印添加

- **文字水印**：可选任意 `.ttf`/`.otf` 字体（不选则自动找系统里的中文字体），支持描边、不透明度、多行（在文字框里写 `\n` 换行）
- **图片水印**：带透明通道的 PNG 会按 alpha 正确合成；按画面宽度的百分比缩放，不用管原图多大
- **定位**：九宫格（四角/四边中点/居中）+ 边距，或者切到「自定义」直接填像素坐标
- **旋转 / 平铺**：任意角度旋转；开平铺后整个画面铺满水印（配 30~45° 旋转 + 低不透明度就是常见的防盗版满屏水印）

水印图和字体都只渲染一次然后缓存复用，逐帧只做 alpha 混合，所以开水印对处理速度影响很小。

### 水印去除

填入一个或多个矩形区域（格式 `x,y,w,h`，多个区域用 `;` 分隔），支持三种处理方式：

| 方式 | 说明 |
|---|---|
| `telea` / `ns` inpaint | 用周围像素推算出被遮住的内容，适合半透明台标、小 logo |
| 模糊 | 直接把区域糊掉，最快，痕迹明显 |
| 像素化 | 打马赛克，同上 |

- 打开视频后点「快速填入」可以直接把四个角常见的台标位置填进去，省得自己数坐标
- **智能蒙版**只对区域里真正像水印的亮/暗像素做修补，而不是整块矩形都动，背景变化大时痕迹更小；灵敏度调高会圈进更多像素
- 区域坐标同时支持像素和 0~1 的比例值，所以一套参数可以套用到不同分辨率的视频上

### LUT 颜色分级

三种 LUT 来源：

1. **内置预设** — 电影感（青橙调）、暖阳、冷调、褪色胶片、黑金、高对比黑白、鲜艳增强
2. **`.cube` 文件** — 标准 3D LUT（也认 1D LUT），达芬奇/PS 里导出的都能用，放进 `luts/` 或直接拖进窗口
3. **LUT 贴图** — Hald 方图和横条图两种排布都自动识别

- **强度**滑块可以把效果按比例混回原图，不用重新导 LUT
- **快速模式**用最近邻取样代替三线性插值，快一些但过渡处可能有色带；预览时可以开，出片建议关

### 字幕烧录

- 支持 **SRT** 和 **ASS**（ASS 的样式标签会被剥掉只取文字），自动识别 UTF-8 / UTF-8-BOM / GBK 等编码
- 选好文件后参数面板会**立刻显示解析出多少条、覆盖到什么时间、首句内容**，文件不对当场就能看出来
- 字体、字号、颜色、描边粗细、底部边距都可调；可以给字幕加一层半透明黑底（`box_opacity`）提升可读性
- **时间偏移**用来修正字幕整体快了或慢了的情况，单位秒，可为负

### 背景虚化 / 人像分割

| 分割方式 | 依赖 | 效果 |
|---|---|---|
| **RVM 人像分割**（推荐） | `rvm_mobilenetv3_fp32.onnx` + `onnxruntime` | 真正的逐像素抠图，带帧间时序状态，头发和边缘都能跟住 |
| 人脸框启发式 | 人脸检测模型 | 把人脸框放大成一个椭圆当蒙版，姿态复杂时边缘明显不准，仅作兜底 |

背景可以选**虚化**（模糊强度可调）、**替换为纯色**或**替换为图片**（图片会按画面比例裁剪填充）。RVM 不可用时会自动回退到启发式并在日志里说明原因，不会直接失败。

`downsample` 比例控制 RVM 推理时的缩放，越小越快但边缘越粗；`feather` 用来羽化蒙版边缘，让前后景过渡自然一些。

### 字幕 OCR 提取

从**硬字幕**（已经烧进画面里的字幕）里把文字提取出来，导出成 `.srt`：

1. 用 EAST 在指定的**纵向区间**里找文字框（默认画面下方 70%~100%，缩小范围能明显提速并减少误检）
2. 对每个框用 CRNN 识别文字，同一帧的多个框按从左到右拼成一行
3. 按**采样间隔**逐帧取样，内容相同的相邻采样点合并成一条字幕，短于**最短时长**的条目当误检丢掉

输出路径会自动改成 `.srt` 扩展名。中文模型认数字+字母+3944 个常用汉字，英文模型只认数字+26 个字母但快得多。识别准确率取决于原片字幕的清晰度和字体，**结果基本都需要人工校对**，建议当成"省去手打"的工具而不是全自动方案。

由于这个功能产出的是字幕文件而不是视频，它不能加入流程组合。

## 去马赛克功能说明

"去马赛克/超分重建" 提供 4 种可选方法，效果和速度差异很大：

| 方法 | 模型文件 | 效果 | 速度 | 说明 |
|---|---|---|---|---|
| **DeepMosaics**（推荐） | `mosaic_position.onnx` + `clean_youknow_video.onnx` | ⭐⭐⭐⭐⭐ 真正的去马赛克 | 中等 | 检测马赛克区域后用生成式模型重建内容，带时序平滑，效果最好。**两个文件都齐全**才能用 |
| Real-ESRGAN x4 | `realesrgan-x4plus.onnx` | 仅超分/降噪，**对马赛克本身无效** | 快（GPU） | 只放大/增强画质，不会移除马赛克 |
| ESPCN x4 | `ESPCN_x4.pb` | 轻量超分 | 很快 | 走 `cv2.dnn`，效果一般 |
| 传统方法 | 无需模型 | ⭐⭐ 效果有限 | 很快 | 基于插值/滤波，始终可用，作为兜底方案 |

> 选中的模型加载失败时（文件缺失、`onnxruntime` 没装等）会**自动回退到传统方法**，不会白跑一遍什么都不做，回退原因可在处理日志（`Ctrl+L`）里查。

### 去马赛克模型获取

上述 ONNX 模型体积较大（合计约 300MB+），且原始托管在 HuggingFace/GitHub，未随代码库分发，也不会被安装脚本自动下载（下载地址见上方"模型下载地址一览"）。获取方式（任选其一）：

1. **直接放置**：按上表链接下载 `realesrgan-x4plus.onnx` / `realesrgan-x4plus-anime.onnx`，放入 `models/` 目录即可。
2. **本地导出（DeepMosaics）**：先下载 [DeepMosaicsPlus.zip](https://github.com/foooooooooooooooooooooooooootw/DeepMosaicsPlus/releases/latest/download/DeepMosaicsPlus.zip) 并解压到 `dmp/`（里面包含 `mosaic_position.pth` 和 `clean_youknow_video.pth` 权重），然后本地导出为 ONNX：

   ```bash
   pip install torch          # 仅导出时需要，装 CPU 版即可
   python export_deepmosaics_onnx.py --src dmp --dst models
   pip uninstall torch        # 导出完成后可卸载，主程序不再需要它
   ```

导出脚本会自动加载 `dmp/mosaic_position.pth`（BiSeNet 检测器）和 `dmp/clean_youknow_video.pth`（BVDNet 生成器），转换为 ONNX 并与原始 PyTorch 输出比对误差，确保导出正确。

### GPU 加速说明

`onnxruntime` 会自动检测并优先使用以下推理后端：

1. **DirectML**（Windows，装 `onnxruntime-directml`）— 无需 CUDA/cuDNN，任意 DX12 显卡（含集显）均可加速
2. **CUDA**（装 `onnxruntime-gpu`，需配 NVIDIA 显卡 + CUDA/cuDNN）
3. **CPU** — 兜底方案，速度明显慢于前两者（去马赛克/超分类任务尤其明显）

程序界面和 `opencv_family.bat` 检测报告都会显示当前实际使用的后端，方便确认加速是否生效。`Ctrl+T` 的 VRT / `.pth` 不走 onnxruntime，加速看的是那个子进程里的 `torch`（CPU 或 CUDA）。

## 注意事项

- 所有处理均在本地进行，不上传任何数据。`Ctrl+T` 的子进程也是本机 Python，不是远程。
- 主程序日常不依赖 `torch`。不要在 `main.py` 里 `import torch`；`.pth` 只从 `infer_vrt.py` 加载。
- DNN 相关功能（人脸/物体检测、风格迁移、人像分割、文字检测/识别、ONNX 降噪等）依赖对应模型文件，未下载时会在界面提示并可一键下载（除去马赛克、Real-ESRGAN、VRT `.pth` 外，见上文）。
- 转 GIF、H.264/H.265 编码、码率控制、保留音频依赖系统已安装 `ffmpeg` 并加入 `PATH`。
- 「文字检测 (EAST)」只框出文字位置不识别内容；要拿到文字请用「字幕 OCR 提取」。
- 水印和字幕**要显示中文必须装 `Pillow`**，没装时只能画 ASCII 字符。
- 「字幕 OCR 提取」的识别结果受原片字幕清晰度影响较大，**导出后请人工校对**。
- 给 `timm` / `torchvision` 做 `pip install` 时看清是否会升级已有 `torch`，对不上版本官方 VRT 会装不进权重。
