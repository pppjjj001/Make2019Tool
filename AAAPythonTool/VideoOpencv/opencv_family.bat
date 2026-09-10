@echo off
setlocal EnableDelayedExpansion

:: ════════════════════════════════════════════════════════════════
::  VideoToolbox - 私有环境检测与安装工具 v2.5
:: ════════════════════════════════════════════════════════════════
::
::  v2.5 变更 (去马赛克功能重构后同步):
::    1. onnxruntime (CPU) -> onnxruntime-directml (Windows GPU 加速)
::       实测 DirectML 比 CPU 快 50+ 倍，且不需要单独装 CUDA/cuDNN
::    2. 新增 onnx 依赖检测 (Real-ESRGAN 分块推理需要它改写模型形状)
::    3. 新增去马赛克模型检测: realesrgan-x4plus.onnx /
::       mosaic_position.onnx + clean_youknow_video.onnx (DeepMosaics)
::       这两类模型体积大且托管在 HuggingFace/GitHub, 网络不稳定时
::       无法用 curl 直接下载, 因此只检测不自动拉取, 改为提示手动获取
::    4. pip 主镜像由清华改为阿里云 (清华源 /simple/torch/ 索引页
::       在实测环境下出现 SSL EOF 断连, 阿里云更稳定且速度相近)
::       所有 pip 安装均加入备用镜像自动重试
::    5. torch 不再列为必须依赖 —— 仅 export_deepmosaics_onnx.py
::       (一次性把 DeepMosaics 的 .pth 转成 ONNX) 需要它, 主程序
::       运行期完全不依赖 torch
::
::  v2.4 变更:
::    1. 新增 onnxruntime (CPU) 作为必须依赖项
::    2. 检测/自动修复/手动安装 均包含 onnxruntime
::
::  v2.3 修复:
::    根本原因: for /f 中 cmd /c 对带路径的 python.exe 解析失败
::    解决方案: 
::      1. 所有 for /f 执行 python 改用临时 bat 中转
::      2. GetModuleVersion 改用 errorlevel + 临时输出文件
::      3. 避免一切 for /f 内嵌 "!var!" 的情况
::
:: ════════════════════════════════════════════════════════════════

title VideoToolbox - 环境检测 v2.5

:: ── 配置 ──
set "SCRIPT_NAME=main.py"
set "REQUIREMENTS_FILE=requirements.txt"
set "MODELS_DIR=models"
set "CHARSET_DIR=charsets"
set "DM_EXPORT_DIR=dmp"
set "DM_EXPORT_SCRIPT=export_deepmosaics_onnx.py"

:: pip 主镜像 (阿里云) + 备用镜像 (清华), 主镜像失败自动重试备用
set "PIP_MIRROR=https://mirrors.aliyun.com/pypi/simple"
set "PIP_TRUSTED=mirrors.aliyun.com"
set "PIP_MIRROR2=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_TRUSTED2=pypi.tuna.tsinghua.edu.cn"

:: ── 私有环境搜索列表 ──
set "VENV_SEARCH=venv .venv env python_env"

:: ── 状态变量 ──
set "VENV_DIR="
set "VENV_PYTHON="
set "VENV_ACTIVATED=0"
set /a TOTAL=0
set /a PASS=0
set /a FAIL=0
set /a WARN=0
set "FAIL_LIST="

:: ── 临时文件 ──
set "_PROBE=%TEMP%\_vtb_probe.py"
set "_RESULT=%TEMP%\_vtb_result.txt"
set "_RUNNER=%TEMP%\_vtb_run.bat"

:: ════════════════════════════════════════════════════════════════
::  主流程
:: ════════════════════════════════════════════════════════════════

call :Banner
echo.
echo   [1/5] 查找私有 Python 环境...
echo.
call :FindVenv

echo.
echo   [2/5] 验证 Python / pip ...
echo.
call :CheckPythonPip

echo.
echo   [3/5] 检测 Python 依赖包...
echo.
call :CheckPackages

echo.
echo   [4/5] 检测 FFmpeg ...
echo.
call :CheckFFmpeg

echo.
echo   [5/5] 检测模型与主程序...
echo.
call :CheckModelsAndScript

:: ── 清理临时文件 ──
call :Cleanup

:: ── 汇总 ──
echo.
echo   ==================================================
call :Report

if !FAIL! EQU 0 goto :AllPassed
goto :HasFailures


:AllPassed
echo.
echo   [OK] 环境检测全部通过！
if !WARN! GTR 0 (
    echo   [^^!^^!] !WARN! 个警告项, 不影响基础运行
)
echo.
echo   [Y] 启动程序   [N] 退出
echo.
set /p "RUN=  请选择 (Y/N): "
if /i "!RUN!"=="Y" call :Launch
echo.
echo   按任意键退出...
pause >nul
goto :EOF


:HasFailures
echo.
echo   [XX] !FAIL! 个必要项缺失, 无法运行
echo.
echo   [1] 自动修复 (仅安装缺失依赖)
echo   [2] 仅安装 Python 依赖包
echo   [3] 仅下载缺失 DNN 模型
echo   [4] 创建/重建私有环境
echo   [5] 详细帮助
echo   [6] 退出
echo.
set /p "CH=  请选择 (1-6): "
if "!CH!"=="1" call :AutoFix
if "!CH!"=="2" call :InstallPackages
if "!CH!"=="3" call :DownloadModels
if "!CH!"=="4" call :CreateVenvFlow
if "!CH!"=="5" call :ShowHelp
echo.
echo   按任意键退出...
pause >nul
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  安全执行 Python 并获取输出
:: ════════════════════════════════════════════════════════════════

:RunPythonGetOutput
> "!_RUNNER!" (
    echo @echo off
    echo "!VENV_PYTHON!" "!_PROBE!" ^> "!_RESULT!" 2^>nul
)
call "!_RUNNER!"
goto :EOF


:GetModuleVersion
set "%~2="
> "!_PROBE!" (
    echo try:
    echo     import %~1
    echo     v = getattr(%~1, '__version__', 'installed'^)
    echo     print(v^)
    echo except ImportError:
    echo     pass
)
> "!_RUNNER!" (
    echo @"!VENV_PYTHON!" "!_PROBE!" ^> "!_RESULT!" 2^>nul
)
call "!_RUNNER!"
if exist "!_RESULT!" (
    for /f "usebackq delims=" %%V in ("!_RESULT!") do (
        set "%~2=%%V"
    )
    del "!_RESULT!" 2>nul
)
goto :EOF


:CheckModuleImport
> "!_PROBE!" (
    echo import %~1
)
> "!_RUNNER!" (
    echo @"!VENV_PYTHON!" "!_PROBE!" ^>nul 2^>nul
)
call "!_RUNNER!"
goto :EOF


:GetPythonOutput
set "%~1="
> "!_RUNNER!" (
    echo @"!VENV_PYTHON!" "!_PROBE!" ^> "!_RESULT!" 2^>nul
)
call "!_RUNNER!"
if exist "!_RESULT!" (
    for /f "usebackq delims=" %%V in ("!_RESULT!") do (
        if "!%~1!"=="" set "%~1=%%V"
    )
    del "!_RESULT!" 2>nul
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  pip 安装 (主镜像失败自动重试备用镜像)
::  用法: call :PipInstall "显示名" 包名或参数...
:: ════════════════════════════════════════════════════════════════

:PipInstall
set "_pi_desc=%~1"
set "_pi_args="
shift
:_PipInstallCollect
if "%~1"=="" goto :_PipInstallRun
set "_pi_args=!_pi_args! %1"
shift
goto :_PipInstallCollect

:_PipInstallRun
echo     [安装] !_pi_desc! ...
"!VENV_PYTHON!" -m pip install !_pi_args! -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
if !errorlevel! EQU 0 goto :EOF
echo     [^^!^^!] 主镜像 (阿里云) 失败, 切换备用镜像 (清华) 重试...
"!VENV_PYTHON!" -m pip install !_pi_args! -i %PIP_MIRROR2% --trusted-host %PIP_TRUSTED2% --prefer-binary --no-warn-script-location
if !errorlevel! NEQ 0 (
    echo     [XX] !_pi_desc! 安装失败 (两个镜像均不可用)
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  [1] 查找并激活私有环境
:: ════════════════════════════════════════════════════════════════

:FindVenv

for %%V in (%VENV_SEARCH%) do (
    if "!VENV_DIR!"=="" (
        if exist "%%V\Scripts\python.exe" (
            set "VENV_DIR=%%V"
            set "VENV_PYTHON=%%V\Scripts\python.exe"
        )
    )
)

if not "!VENV_DIR!"=="" (
    echo     [OK] 找到私有环境: !VENV_DIR!\
    echo          Python: !VENV_PYTHON!

    if exist "!VENV_DIR!\pyvenv.cfg" (
        for /f "tokens=1,* delims==" %%A in ('type "!VENV_DIR!\pyvenv.cfg" 2^>nul ^| findstr /i "version"') do (
            echo          %%A = %%B
        )
    )

    echo.
    echo     [..] 激活私有环境...
    call "!VENV_DIR!\Scripts\activate.bat" 2>nul
    set "VENV_ACTIVATED=1"
    echo     [OK] 私有环境已激活

    > "!_PROBE!" (
        echo import sys
        echo print(sys.executable^)
    )
    call :GetPythonOutput _ACTUAL_PY
    if not "!_ACTUAL_PY!"=="" (
        echo          实际解释器: !_ACTUAL_PY!
    )

    echo.
    echo     [说明] 私有环境不需要管理员权限
    echo            所有 pip install 均安装到 !VENV_DIR!\Lib\site-packages\

    goto :EOF
)

echo     [^^!^^!] 当前目录未找到私有环境
echo          已搜索: %VENV_SEARCH%
echo.
echo     是否立即创建私有环境？
echo.
echo     [Y] 创建   [N] 尝试系统Python
echo.
set /p "CV=     请选择 (Y/N): "
if /i "!CV!"=="Y" (
    call :CreateVenvFlow
    goto :EOF
)

echo.
echo     [..] 尝试查找系统 Python...
call :FindSystemPython
goto :EOF


:FindSystemPython
set "_found=0"
for %%P in (python python3 py) do (
    if !_found! EQU 0 (
        where %%P >nul 2>&1
        if !errorlevel! EQU 0 (
            set "VENV_PYTHON=%%P"
            set "_found=1"
            echo     [^^!^^!] 使用系统 Python: %%P
            echo          建议: 创建私有环境隔离依赖
        )
    )
)
if !_found! EQU 0 (
    echo     [XX] 系统也未找到 Python
    echo          请安装 Python 3.7+: https://www.python.org/downloads/
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  创建虚拟环境
:: ════════════════════════════════════════════════════════════════

:CreateVenvFlow
echo.
echo   === 创建私有 Python 环境 ===
echo.

set "SYS_PY="
for %%P in (python python3 py) do (
    if "!SYS_PY!"=="" (
        %%P --version >nul 2>&1
        if !errorlevel! EQU 0 set "SYS_PY=%%P"
    )
)

if "!SYS_PY!"=="" (
    echo     [XX] 未找到系统 Python
    goto :EOF
)

for /f "tokens=2 delims= " %%V in ('!SYS_PY! --version 2^>^&1') do (
    echo     系统 Python: %%V
)

echo.
echo     环境目录名 (回车 = venv):
set "NEW_VENV=venv"
set /p "VINPUT=     > "
if not "!VINPUT!"=="" set "NEW_VENV=!VINPUT!"

if exist "!NEW_VENV!" (
    echo.
    echo     [^^!^^!] 目录 !NEW_VENV! 已存在
    echo     [1] 删除重建   [2] 跳过
    set /p "RB=     请选择: "
    if "!RB!"=="1" (
        rmdir /s /q "!NEW_VENV!" 2>nul
    ) else (
        goto :EOF
    )
)

echo.
echo     [..] 执行: !SYS_PY! -m venv !NEW_VENV!
!SYS_PY! -m venv "!NEW_VENV!"

if !errorlevel! NEQ 0 (
    echo     [XX] 创建失败
    goto :EOF
)

set "VENV_DIR=!NEW_VENV!"
set "VENV_PYTHON=!NEW_VENV!\Scripts\python.exe"
echo     [OK] 创建成功: !NEW_VENV!\

call "!NEW_VENV!\Scripts\activate.bat" 2>nul
set "VENV_ACTIVATED=1"
echo     [OK] 已激活

echo.
echo     是否立即安装依赖包？ (Y/N)
set /p "INST=     > "
if /i "!INST!"=="Y" call :InstallPackages
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  [2] 检测 Python / pip
:: ════════════════════════════════════════════════════════════════

:CheckPythonPip

set /a TOTAL+=1

if "!VENV_PYTHON!"=="" (
    call :ItemFail "Python" "未找到"
    set "FAIL_LIST=!FAIL_LIST!Python "
    goto :EOF
)

> "!_PROBE!" (
    echo import sys
    echo vi = sys.version_info
    echo print(f'{vi.major}.{vi.minor}.{vi.micro}'^)
)
call :GetPythonOutput PY_VER
if "!PY_VER!"=="" set "PY_VER=unknown"

set "PY_MAJ=0"
set "PY_MIN=0"
for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
    set "PY_MAJ=%%A"
    set "PY_MIN=%%B"
)

set "VER_OK=0"
if !PY_MAJ! GTR 3 set "VER_OK=1"
if !PY_MAJ! EQU 3 if !PY_MIN! GEQ 7 set "VER_OK=1"

if !VER_OK! EQU 1 (
    if not "!VENV_DIR!"=="" (
        call :ItemPass "Python" "!PY_VER! [私有: !VENV_DIR!\]"
    ) else (
        call :ItemPass "Python" "!PY_VER! [系统]"
    )
) else (
    call :ItemFail "Python" "!PY_VER! 过低, 需 >= 3.7"
    set "FAIL_LIST=!FAIL_LIST!Python版本 "
)

:: tkinter
set /a TOTAL+=1
call :CheckModuleImport tkinter
if !errorlevel! EQU 0 (
    call :ItemPass "tkinter" "GUI 库可用"
) else (
    call :ItemFail "tkinter" "缺失 (重装Python勾选tcl/tk)"
    set "FAIL_LIST=!FAIL_LIST!tkinter "
)

:: pip
set /a TOTAL+=1
"!VENV_PYTHON!" -m pip --version >nul 2>&1
if !errorlevel! NEQ 0 (
    call :ItemFail "pip" "不可用"
    set "FAIL_LIST=!FAIL_LIST!pip "
    goto :EOF
)

> "!_PROBE!" (
    echo import pip
    echo print(pip.__version__^)
)
call :GetPythonOutput _pipver

if not "!_pipver!"=="" (
    call :ItemPass "pip" "!_pipver!"
) else (
    call :ItemPass "pip" "可用"
)

goto :EOF


:: ════════════════════════════════════════════════════════════════
::  [3] 检测依赖包 (含 onnxruntime-directml / onnx)
:: ════════════════════════════════════════════════════════════════

:CheckPackages
if "!VENV_PYTHON!"=="" goto :EOF

:: ── opencv-python ──
set /a TOTAL+=1
call :GetModuleVersion cv2 _cv2ver
if not "!_cv2ver!"=="" (
    call :ItemPass "opencv-python" "!_cv2ver!"
) else (
    call :ItemFail "opencv-python" "未安装 (核心依赖)"
    set "FAIL_LIST=!FAIL_LIST!opencv-python "
)

:: ── numpy ──
set /a TOTAL+=1
call :GetModuleVersion numpy _npver
if not "!_npver!"=="" (
    call :ItemPass "numpy" "!_npver!"
) else (
    call :ItemFail "numpy" "未安装 (核心依赖)"
    set "FAIL_LIST=!FAIL_LIST!numpy "
)

:: ── scipy (可选) ──
set /a TOTAL+=1
call :GetModuleVersion scipy _spver
if not "!_spver!"=="" (
    call :ItemPass "scipy" "!_spver!"
) else (
    call :ItemWarn "scipy" "未安装 (可选)"
)

:: ── onnxruntime (必须, 检测 DirectML/CUDA/CPU 后端) ──
set /a TOTAL+=1
call :CheckOnnxRuntime

:: ── onnx (Real-ESRGAN 去马赛克需要它改写模型输入形状) ──
set /a TOTAL+=1
call :GetModuleVersion onnx _onnxver
if not "!_onnxver!"=="" (
    call :ItemPass "onnx" "!_onnxver! (Real-ESRGAN 形状适配)"
) else (
    call :ItemWarn "onnx" "未安装 (仅影响 Real-ESRGAN, DeepMosaics/传统方法不受影响)"
)

goto :EOF


:: ────────────────────────────────────────────────────────────
::  探测 onnxruntime 及其推理后端 (DirectML / CUDA / CPU), 不打印
::  结果写入 _ortver / _orttag, 供 :CheckOnnxRuntime 与 :AutoFix 复用
:: ────────────────────────────────────────────────────────────
:DetectOnnxRuntime
> "!_PROBE!" (
    echo try:
    echo     import onnxruntime as ort
    echo     provs = ort.get_available_providers(^)
    echo     if 'DmlExecutionProvider' in provs:
    echo         tag = 'DirectML'
    echo     elif 'CUDAExecutionProvider' in provs:
    echo         tag = 'CUDA'
    echo     else:
    echo         tag = 'CPU'
    echo     print(ort.__version__ + '^|' + tag^)
    echo except ImportError:
    echo     pass
)
call :RunPythonGetOutput
set "_ortver="
set "_orttag="
if exist "!_RESULT!" (
    for /f "usebackq tokens=1,2 delims=|" %%A in ("!_RESULT!") do (
        set "_ortver=%%A"
        set "_orttag=%%B"
    )
    del "!_RESULT!" 2>nul
)
goto :EOF


:: ────────────────────────────────────────────────────────────
::  检测 onnxruntime 并按检测报告格式打印 (供 :CheckPackages 使用)
:: ────────────────────────────────────────────────────────────
:CheckOnnxRuntime
call :DetectOnnxRuntime

if "!_ortver!"=="" (
    call :ItemFail "onnxruntime" "未安装 (推理引擎, 必须)"
    set "FAIL_LIST=!FAIL_LIST!onnxruntime "
    goto :EOF
)

if "!_orttag!"=="DirectML" (
    call :ItemPass "onnxruntime" "!_ortver! [DirectML GPU 加速]"
    goto :EOF
)
if "!_orttag!"=="CUDA" (
    call :ItemPass "onnxruntime" "!_ortver! [CUDA GPU 加速]"
    goto :EOF
)
call :ItemPass "onnxruntime" "!_ortver! [CPU 模式, 较慢]"
echo          建议: pip install onnxruntime-directml 提速 50+ 倍 ^(Windows, 无需装CUDA^)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  [4] 检测 FFmpeg
:: ════════════════════════════════════════════════════════════════

:CheckFFmpeg
set /a TOTAL+=1
where ffmpeg >nul 2>&1
if !errorlevel! EQU 0 (
    for /f "tokens=3" %%V in ('ffmpeg -version 2^>^&1 ^| findstr /C:"ffmpeg version"') do (
        call :ItemPass "FFmpeg" "%%V"
        goto :EOF
    )
    call :ItemPass "FFmpeg" "已安装"
) else (
    call :ItemWarn "FFmpeg" "未安装 (转GIF等功能不可用)"
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  [5] 检测模型 + 主程序
:: ════════════════════════════════════════════════════════════════

:CheckModelsAndScript

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%" 2>nul

set /a TOTAL+=1
set "_ok=1"
if not exist "%MODELS_DIR%\deploy.prototxt" set "_ok=0"
if not exist "%MODELS_DIR%\res10_300x300_ssd_iter_140000.caffemodel" set "_ok=0"
if !_ok! EQU 1 (
    call :ItemPass "人脸检测模型" "SSD-Caffe"
) else (
    call :ItemWarn "人脸检测模型" "未下载"
)

set /a TOTAL+=1
set "_ok=1"
if not exist "%MODELS_DIR%\yolov4-tiny.cfg" set "_ok=0"
if not exist "%MODELS_DIR%\yolov4-tiny.weights" set "_ok=0"
if !_ok! EQU 1 (
    call :ItemPass "YOLO物体检测" "yolov4-tiny"
) else (
    call :ItemWarn "YOLO物体检测" "未下载"
)

set /a TOTAL+=1
set /a _sn=0
for %%F in (mosaic.t7 candy.t7 rain_princess.t7 udnie.t7 the_wave.t7 starry_night.t7 la_muse.t7 composition_vii.t7) do (
    if exist "%MODELS_DIR%\%%F" set /a _sn+=1
)
if !_sn! GTR 0 (
    call :ItemPass "风格迁移模型" "!_sn!/8 个可用"
) else (
    call :ItemWarn "风格迁移模型" "未下载"
)

set /a TOTAL+=1
if exist "%MODELS_DIR%\frozen_east_text_detection.pb" (
    call :ItemPass "EAST文字检测" "已下载"
) else (
    call :ItemWarn "EAST文字检测" "未下载"
)

set /a TOTAL+=1
if exist "%MODELS_DIR%\rvm_mobilenetv3_fp32.onnx" (
    call :ItemPass "人像分割模型" "RVM 已就绪"
) else (
    call :ItemWarn "人像分割模型" "未下载 (背景虚化会退回人脸框启发式)"
)

:: 字幕 OCR 要模型和字符表配套齐全才算可用
set /a TOTAL+=1
set "_ocr_have="
if exist "%MODELS_DIR%\text_recognition_CRNN_CN_2021nov.onnx" set "_ocr_have=!_ocr_have!中文 "
if exist "%MODELS_DIR%\text_recognition_CRNN_EN_2021sep.onnx" set "_ocr_have=!_ocr_have!英文 "
set "_cs_ok=1"
if not exist "%CHARSET_DIR%\charset_3944_CN.txt" set "_cs_ok=0"
if not exist "%CHARSET_DIR%\charset_36_EN.txt" set "_cs_ok=0"
if !_cs_ok! EQU 0 (
    call :ItemWarn "字幕OCR模型" "%CHARSET_DIR%\ 字符表缺失, OCR 无法使用"
) else if not "!_ocr_have!"=="" (
    call :ItemPass "字幕OCR模型" "!_ocr_have!"
) else (
    call :ItemWarn "字幕OCR模型" "未下载"
)

set /a TOTAL+=1
set "_dn_have="
if exist "%MODELS_DIR%\dncnn_color.onnx" set "_dn_have=!_dn_have!DnCNN "
if exist "%MODELS_DIR%\fastdvdnet_s25.onnx" set "_dn_have=!_dn_have!FastDVDnet "
if exist "%MODELS_DIR%\scunet_color_real_psnr.onnx" if exist "%MODELS_DIR%\scunet_color_real_psnr.onnx.data" set "_dn_have=!_dn_have!SCUNet "
if not "!_dn_have!"=="" (
    call :ItemPass "视频降噪模型" "!_dn_have!"
) else (
    call :ItemWarn "视频降噪模型" "未下载 (快档 FFmpeg 滤镜仍可用)"
)

:: ── 去马赛克模型 (Real-ESRGAN 超分 / DeepMosaics 生成式重建) ──
:: 体积大且托管在 HuggingFace/GitHub, 网络不稳定时无法用 curl 直接下载,
:: 因此这里只检测, 不在 :DownloadModels 里自动拉取, 需要时看 :ShowHelp 里的手动获取说明
set /a TOTAL+=1
set "_dm_have="
if exist "%MODELS_DIR%\realesrgan-x4plus.onnx" set "_dm_have=!_dm_have!Real-ESRGAN "
set "_dmp_ok=1"
if not exist "%MODELS_DIR%\mosaic_position.onnx" set "_dmp_ok=0"
if not exist "%MODELS_DIR%\clean_youknow_video.onnx" set "_dmp_ok=0"
if !_dmp_ok! EQU 1 set "_dm_have=!_dm_have!DeepMosaics "
if not "!_dm_have!"=="" (
    call :ItemPass "去马赛克模型" "!_dm_have!(传统方法始终可用)"
) else (
    call :ItemWarn "去马赛克模型" "未下载 (仅传统方法可用, 见帮助[5]手动获取)"
)

set /a TOTAL+=1
if exist "%SCRIPT_NAME%" (
    for %%A in ("%SCRIPT_NAME%") do (
        call :ItemPass "主程序" "%SCRIPT_NAME% (%%~zA bytes)"
    )
) else (
    call :ItemFail "主程序" "%SCRIPT_NAME% 不存在"
    set "FAIL_LIST=!FAIL_LIST!main.py "
)

goto :EOF


:: ════════════════════════════════════════════════════════════════
::  自动修复 (含 onnxruntime-directml / onnx)
:: ════════════════════════════════════════════════════════════════

:AutoFix
echo.
echo   === 自动修复 ===
echo.

if "!VENV_PYTHON!"=="" (
    echo   [XX] 无可用 Python
    goto :EOF
)

if "!VENV_DIR!"=="" (
    echo   [^^!^^!] 无私有环境, 先创建...
    call :CreateVenvFlow
    if "!VENV_DIR!"=="" goto :EOF
)

echo   --- 检查并安装缺失的 pip 包 ---
echo.

call :GetModuleVersion cv2 _cv2ver
if not "!_cv2ver!"=="" (
    echo     [跳过] opencv-python 已安装 ^(!_cv2ver!^)
) else (
    call :PipInstall "opencv-python" opencv-python
)

call :GetModuleVersion numpy _npver
if not "!_npver!"=="" (
    echo     [跳过] numpy 已安装 ^(!_npver!^)
) else (
    call :PipInstall "numpy" numpy
)

call :GetModuleVersion scipy _spver
if not "!_spver!"=="" (
    echo     [跳过] scipy 已安装 ^(!_spver!^)
) else (
    call :PipInstall "scipy" scipy
)

call :DetectOnnxRuntime
if "!_ortver!"=="" (
    call :PipInstall "onnxruntime-directml (GPU加速)" onnxruntime-directml
    goto :_AutoFixOrtDone
)
if "!_orttag!"=="DirectML" goto :_AutoFixOrtSkip
if "!_orttag!"=="CUDA" goto :_AutoFixOrtSkip

echo.
echo     [^^!^^!] 当前 onnxruntime 是 CPU 模式 ^(!_ortver!^), 去马赛克会很慢
echo          切换到 onnxruntime-directml 可提速 50+ 倍 ^(Windows GPU, 无需装CUDA^)
set /p "_UPG=     是否切换？会先卸载当前 onnxruntime (Y/N): "
if /i "!_UPG!"=="Y" (
    "!VENV_PYTHON!" -m pip uninstall -y onnxruntime onnxruntime-gpu >nul 2>nul
    call :PipInstall "onnxruntime-directml" onnxruntime-directml
)
goto :_AutoFixOrtDone

:_AutoFixOrtSkip
echo     [跳过] onnxruntime 已安装 ^(!_ortver! [!_orttag!]^)

:_AutoFixOrtDone
call :GetModuleVersion onnx _onnxver
if not "!_onnxver!"=="" (
    echo     [跳过] onnx 已安装 ^(!_onnxver!^)
) else (
    call :PipInstall "onnx (Real-ESRGAN 形状适配)" onnx
)

echo.
echo   --- 检查模型 ---
call :DownloadModels

:: 重新检测
echo.
echo   === 重新检测 ===
echo.
set /a TOTAL=0
set /a PASS=0
set /a FAIL=0
set /a WARN=0
set "FAIL_LIST="

call :CheckPythonPip
echo.
call :CheckPackages
echo.
call :CheckFFmpeg
echo.
call :CheckModelsAndScript
echo.
call :Report

if !FAIL! EQU 0 (
    echo.
    echo   [OK] 修复完成！
    set /p "GO=  立即启动？ (Y/N): "
    if /i "!GO!"=="Y" call :Launch
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  安装 pip 依赖 (含 onnxruntime-directml / onnx)
:: ════════════════════════════════════════════════════════════════

:InstallPackages
echo.
echo   === 安装 Python 依赖包 ===
echo.

if "!VENV_PYTHON!"=="" (
    echo   [XX] 无可用 Python
    goto :EOF
)

if not "!VENV_DIR!"=="" (
    echo     环境: !VENV_DIR!\
    echo     安装到: !VENV_DIR!\Lib\site-packages\
) else (
    echo     [^^!^^!] 将安装到系统环境
    set /p "CONF=     继续？ (Y/N): "
    if /i not "!CONF!"=="Y" goto :EOF
)

echo     主镜像: %PIP_MIRROR%  (备用: %PIP_MIRROR2%)
echo.

if exist "%REQUIREMENTS_FILE%" (
    echo     使用 %REQUIREMENTS_FILE% ...
    "!VENV_PYTHON!" -m pip install -r "%REQUIREMENTS_FILE%" -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
    if !errorlevel! EQU 0 (
        echo     [OK] 安装完成
        goto :EOF
    )
    echo     [^^!^^!] requirements.txt 主镜像失败, 切换备用镜像重试...
    "!VENV_PYTHON!" -m pip install -r "%REQUIREMENTS_FILE%" -i %PIP_MIRROR2% --trusted-host %PIP_TRUSTED2% --prefer-binary --no-warn-script-location
    if !errorlevel! EQU 0 (
        echo     [OK] 安装完成
        goto :EOF
    )
    echo     [^^!^^!] requirements.txt 仍失败, 改为逐个安装
    echo.
)

echo     [1/5] opencv-python ...
call :PipInstall "opencv-python" opencv-python

echo     [2/5] numpy ...
call :PipInstall "numpy" numpy

echo     [3/5] scipy ...
call :PipInstall "scipy" scipy

echo     [4/5] onnxruntime-directml (Windows GPU 加速, 无需装CUDA) ...
call :PipInstall "onnxruntime-directml" onnxruntime-directml

echo     [5/5] onnx (Real-ESRGAN 去马赛克形状适配) ...
call :PipInstall "onnx" onnx

echo.
echo     安装完成
echo     [提示] torch 仅 export_deepmosaics_onnx.py (一次性模型导出) 需要,
echo            日常运行不需要装 torch
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  下载 DNN 模型
:: ════════════════════════════════════════════════════════════════

:DownloadModels
echo.
echo   === 下载缺失的 DNN 模型 ===
echo     目标: %MODELS_DIR%\
echo.

if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

set /a _skip=0
set /a _dl=0

echo   [1/7] 人脸检测模型

if exist "%MODELS_DIR%\deploy.prototxt" (
    echo     [跳过] deploy.prototxt
    set /a _skip+=1
) else (
    echo     [下载] deploy.prototxt ...
    call :DL "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt" "%MODELS_DIR%\deploy.prototxt"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\res10_300x300_ssd_iter_140000.caffemodel" (
    echo     [跳过] caffemodel
    set /a _skip+=1
) else (
    echo     [下载] caffemodel ~10MB ...
    call :DL "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel" "%MODELS_DIR%\res10_300x300_ssd_iter_140000.caffemodel"
    set /a _dl+=1
)

echo.
echo   [2/7] YOLOv4-tiny

if exist "%MODELS_DIR%\yolov4-tiny.cfg" (
    echo     [跳过] yolov4-tiny.cfg
    set /a _skip+=1
) else (
    echo     [下载] yolov4-tiny.cfg ...
    call :DL "https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg" "%MODELS_DIR%\yolov4-tiny.cfg"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\yolov4-tiny.weights" (
    echo     [跳过] yolov4-tiny.weights
    set /a _skip+=1
) else (
    echo     [下载] yolov4-tiny.weights ~24MB ...
    call :DL "https://github.com/AlexeyAB/darknet/releases/download/yolov4/yolov4-tiny.weights" "%MODELS_DIR%\yolov4-tiny.weights"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\coco.names" (
    echo     [跳过] coco.names
    set /a _skip+=1
) else (
    echo     [下载] coco.names ...
    call :DL "https://raw.githubusercontent.com/AlexeyAB/darknet/master/data/coco.names" "%MODELS_DIR%\coco.names"
    set /a _dl+=1
)

echo.
echo   [3/7] 风格迁移模型

set "STYLE_URL=https://cs.stanford.edu/people/jcjohns/fast-neural-style/models"
call :DLStyleIfMissing "instance_norm/mosaic.t7" "mosaic.t7"
call :DLStyleIfMissing "instance_norm/candy.t7" "candy.t7"
call :DLStyleIfMissing "instance_norm/rain_princess.t7" "rain_princess.t7"
call :DLStyleIfMissing "instance_norm/udnie.t7" "udnie.t7"
call :DLStyleIfMissing "eccv16/the_wave.t7" "the_wave.t7"
call :DLStyleIfMissing "eccv16/starry_night.t7" "starry_night.t7"
call :DLStyleIfMissing "eccv16/la_muse.t7" "la_muse.t7"
call :DLStyleIfMissing "eccv16/composition_vii.t7" "composition_vii.t7"

echo.
echo   [4/7] EAST 文字检测

if exist "%MODELS_DIR%\frozen_east_text_detection.pb" (
    echo     [跳过] frozen_east_text_detection.pb
    set /a _skip+=1
) else (
    echo     [下载] frozen_east_text_detection.pb ~96MB ...
    call :DL "https://raw.githubusercontent.com/oyyd/frozen_east_text_detection.pb/master/frozen_east_text_detection.pb" "%MODELS_DIR%\frozen_east_text_detection.pb"
    set /a _dl+=1
)

echo.
echo   [5/7] 人像分割 / 字幕识别模型

if exist "%MODELS_DIR%\rvm_mobilenetv3_fp32.onnx" (
    echo     [跳过] rvm_mobilenetv3_fp32.onnx
    set /a _skip+=1
) else (
    echo     [下载] rvm_mobilenetv3_fp32.onnx ~15MB ...
    call :DL "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx" "%MODELS_DIR%\rvm_mobilenetv3_fp32.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\text_recognition_CRNN_CN_2021nov.onnx" (
    echo     [跳过] text_recognition_CRNN_CN_2021nov.onnx
    set /a _skip+=1
) else (
    echo     [下载] text_recognition_CRNN_CN_2021nov.onnx ~69MB ...
    call :DL "https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_CN_2021nov.onnx" "%MODELS_DIR%\text_recognition_CRNN_CN_2021nov.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\text_recognition_CRNN_EN_2021sep.onnx" (
    echo     [跳过] text_recognition_CRNN_EN_2021sep.onnx
    set /a _skip+=1
) else (
    echo     [下载] text_recognition_CRNN_EN_2021sep.onnx ~32MB ...
    call :DL "https://github.com/opencv/opencv_zoo/raw/main/models/text_recognition_crnn/text_recognition_CRNN_EN_2021sep.onnx" "%MODELS_DIR%\text_recognition_CRNN_EN_2021sep.onnx"
    set /a _dl+=1
)

if not exist "%CHARSET_DIR%\charset_3944_CN.txt" (
    echo     [^^!^^!] 缺少 %CHARSET_DIR%\charset_3944_CN.txt, 字幕 OCR 无法使用
    echo          这个文件随项目一起分发, 请从项目里补回来
)

echo.
echo   [6/7] 视频降噪模型

if exist "%MODELS_DIR%\dncnn_color.onnx" (
    echo     [跳过] dncnn_color.onnx
    set /a _skip+=1
) else (
    echo     [下载] dncnn_color.onnx ~2.6MB ...
    call :DL "https://github.com/ikeno-web/npuscale/releases/download/v1.2/dncnn_color.onnx" "%MODELS_DIR%\dncnn_color.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\fastdvdnet_s15.onnx" (
    echo     [跳过] fastdvdnet_s15.onnx
    set /a _skip+=1
) else (
    echo     [下载] fastdvdnet_s15.onnx ~9.5MB ...
    call :DL "https://github.com/ikeno-web/npuscale/releases/download/v1.3/fastdvdnet_s15.onnx" "%MODELS_DIR%\fastdvdnet_s15.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\fastdvdnet_s25.onnx" (
    echo     [跳过] fastdvdnet_s25.onnx
    set /a _skip+=1
) else (
    echo     [下载] fastdvdnet_s25.onnx ~9.5MB ...
    call :DL "https://github.com/ikeno-web/npuscale/releases/download/v1.3/fastdvdnet_s25.onnx" "%MODELS_DIR%\fastdvdnet_s25.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\fastdvdnet_s50.onnx" (
    echo     [跳过] fastdvdnet_s50.onnx
    set /a _skip+=1
) else (
    echo     [下载] fastdvdnet_s50.onnx ~9.5MB ...
    call :DL "https://github.com/ikeno-web/npuscale/releases/download/v1.3/fastdvdnet_s50.onnx" "%MODELS_DIR%\fastdvdnet_s50.onnx"
    set /a _dl+=1
)

if exist "%MODELS_DIR%\scunet_color_real_psnr.onnx" if exist "%MODELS_DIR%\scunet_color_real_psnr.onnx.data" (
    echo     [跳过] scunet_color_real_psnr.onnx
    set /a _skip+=1
) else (
    echo     [下载] scunet_color_real_psnr.onnx + .data ~74MB ...
    call :DL "https://huggingface.co/Heliosoph/scunet-onnx/resolve/main/scunet_color_real_psnr.onnx" "%MODELS_DIR%\scunet_color_real_psnr.onnx"
    call :DL "https://huggingface.co/Heliosoph/scunet-onnx/resolve/main/scunet_color_real_psnr.onnx.data" "%MODELS_DIR%\scunet_color_real_psnr.onnx.data"
    set /a _dl+=1
)

echo.
echo   [7/7] 去马赛克模型 (Real-ESRGAN / DeepMosaics)

set "_dm_ok=1"
if not exist "%MODELS_DIR%\realesrgan-x4plus.onnx" set "_dm_ok=0"
if not exist "%MODELS_DIR%\mosaic_position.onnx" set "_dm_ok=0"
if not exist "%MODELS_DIR%\clean_youknow_video.onnx" set "_dm_ok=0"
if !_dm_ok! EQU 1 (
    echo     [跳过] 已齐全
    set /a _skip+=1
) else (
    echo     [^^!^^!] 体积大 ^(共 ~320MB^) 且托管在 HuggingFace/GitHub,
    echo          在此网络环境下无法用 curl 稳定下载, 不自动拉取。
    echo          手动获取步骤 ^(详见帮助[5]^):
    echo            1. Real-ESRGAN: 下载 realesrgan-x4plus.onnx 放入 %MODELS_DIR%\
    echo            2. DeepMosaics: 需要 %DM_EXPORT_DIR%\ 下的 .pth 权重,
    echo               装好 torch 后运行:
    echo               "!VENV_PYTHON!" %DM_EXPORT_SCRIPT% --src %DM_EXPORT_DIR% --dst %MODELS_DIR%
    echo               导出完成后可以 pip uninstall torch ^(运行期不需要它^)
)

echo.
echo   模型: 跳过 !_skip! 个, 下载 !_dl! 个
goto :EOF


:DLStyleIfMissing
if exist "%MODELS_DIR%\%~2" (
    echo     [跳过] %~2
    set /a _skip+=1
) else (
    echo     [下载] %~2 ...
    call :DL "%STYLE_URL%/%~1" "%MODELS_DIR%\%~2"
    set /a _dl+=1
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  通用下载
:: ════════════════════════════════════════════════════════════════

:DL
set "_URL=%~1"
set "_OUT=%~2"

where curl >nul 2>&1
if !errorlevel! EQU 0 (
    curl -L -o "!_OUT!" "!_URL!" --progress-bar --connect-timeout 30 --max-time 600 2>&1
    if !errorlevel! EQU 0 (
        if exist "!_OUT!" (
            for %%F in ("!_OUT!") do (
                if %%~zF GTR 100 (
                    echo     [OK] 下载成功
                    goto :EOF
                )
            )
        )
    )
    echo     curl 失败, 尝试 PowerShell...
)

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try{(New-Object Net.WebClient).DownloadFile('%_URL%','%_OUT%'); Write-Host '    [OK] 下载成功'} catch{Write-Host '    [XX] 下载失败:' $_.Exception.Message}}" 2>nul

if not exist "!_OUT!" (
    echo     [XX] 下载失败, 请手动下载:
    echo          !_URL!
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  启动
:: ════════════════════════════════════════════════════════════════

:Launch
echo.
echo   启动 VideoToolbox ...
echo     命令: "!VENV_PYTHON!" %SCRIPT_NAME%
echo.
"!VENV_PYTHON!" "%SCRIPT_NAME%"
if !errorlevel! NEQ 0 (
    echo.
    echo   [XX] 程序异常退出 (code: !errorlevel!)
)
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  帮助
:: ════════════════════════════════════════════════════════════════

:ShowHelp
echo.
echo   === VideoToolbox 环境搭建指南 ===
echo.
echo   1. 安装 Python 3.8+ (勾选 Add to PATH + tcl/tk)
echo   2. 运行 setup.bat, 选 [4] 创建私有环境
echo   3. 选 [1] 自动修复
echo   4. 检测通过后选 [Y] 启动
echo.
echo   === 依赖清单 ===
echo   [必须] opencv-python         - 图像/视频处理核心
echo   [必须] numpy                 - 数组计算
echo   [必须] onnxruntime-directml  - ONNX 推理引擎, Windows GPU 加速
echo                                  (比纯 CPU 版快 50+ 倍, 不需要装 CUDA/cuDNN;
echo                                   有独立 NVIDIA 显卡也可用 onnxruntime-gpu 代替)
echo   [必须] onnx                  - Real-ESRGAN 分块推理时改写模型输入形状
echo   [可选] scipy                 - 科学计算
echo   [可选] FFmpeg                - 视频转码/GIF
echo   [一次性] torch               - 只有重新导出 DeepMosaics 模型时才需要,
echo                                  日常运行/打包给别人用都不需要装它
echo.
echo   === 去马赛克模型 (体积大, 不随代码仓库分发) ===
echo   models\realesrgan-x4plus.onnx           - Real-ESRGAN 超分, 对马赛克本身无效,
echo                                              只用于普通画质增强/放大
echo   models\mosaic_position.onnx             - DeepMosaics 马赛克区域检测 (BiSeNet)
echo   models\clean_youknow_video.onnx         - DeepMosaics 生成式重建 (BVDNet),
echo                                              真正能去马赛克, 有前后帧时序平滑
echo.
echo   获取方式 (任选, 传统方法始终可用不受影响):
echo     A. 直接找一份现成的 .onnx 放进 models\ 目录即可, 文件名要对上
echo     B. 从源码自己导出 (适合已经有 dmp\ 目录和 .pth 权重的情况):
echo        1) pip install torch  (装 CPU 版即可, 只是临时用来导出)
echo        2) "!VENV_PYTHON!" export_deepmosaics_onnx.py --src dmp --dst models
echo        3) 导出成功后可以 pip uninstall torch, 主程序不再需要它
echo.
echo   === v2.5 更新 (本次去马赛克重构) ===
echo   1. onnxruntime -^> onnxruntime-directml, 检测项会显示当前用的是
echo      DirectML/CUDA/CPU 哪种后端, CPU 模式会提示升级
echo   2. 新增 onnx 依赖检测 (缺失只影响 Real-ESRGAN, 不影响 DeepMosaics)
echo   3. 新增去马赛克模型检测 (不自动下载, 见上方"获取方式")
echo   4. pip 主镜像改为阿里云, 清华源作为备用自动重试
echo.
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  清理临时文件
:: ════════════════════════════════════════════════════════════════

:Cleanup
if exist "!_PROBE!" del "!_PROBE!" 2>nul
if exist "!_RESULT!" del "!_RESULT!" 2>nul
if exist "!_RUNNER!" del "!_RUNNER!" 2>nul
goto :EOF


:: ════════════════════════════════════════════════════════════════
::  格式化输出
:: ════════════════════════════════════════════════════════════════

:ItemPass
set /a PASS+=1
set "_n=%~1                      "
echo     [OK] %_n:~0,22% %~2
goto :EOF

:ItemFail
set /a FAIL+=1
set "_n=%~1                      "
echo     [XX] %_n:~0,22% %~2
goto :EOF

:ItemWarn
set /a WARN+=1
set "_n=%~1                      "
echo     [^^!^^!] %_n:~0,22% %~2
goto :EOF

:Report
echo.
echo   --- 检测报告 ---
echo.
echo     检查: %TOTAL% 项
echo     通过: %PASS%
echo     失败: %FAIL%
echo     警告: %WARN%
echo.

if not "!VENV_DIR!"=="" (
    echo     环境: 私有 ^(!VENV_DIR!\^)
    echo     权限: 不需要管理员
) else (
    echo     环境: 系统 (建议创建私有环境)
)

if not "!FAIL_LIST!"=="" (
    echo.
    echo     必须修复: !FAIL_LIST!
)
goto :EOF

:Banner
echo.
echo   ==================================================
echo.
echo     VideoToolbox - 环境检测与安装工具 v2.5
echo     使用项目私有 Python 环境 (无需管理员权限)
echo.
echo   ==================================================
echo.
echo     目录: %CD%
echo     时间: %date% %time:~0,8%
goto :EOF