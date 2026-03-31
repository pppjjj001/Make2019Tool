@echo off
setlocal EnableDelayedExpansion

:: ════════════════════════════════════════════════════════════════
::  VideoToolbox - 私有环境检测与安装工具 v2.4
:: ════════════════════════════════════════════════════════════════
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

title VideoToolbox - 环境检测 v2.4

:: ── 配置 ──
set "SCRIPT_NAME=main.py"
set "REQUIREMENTS_FILE=requirements.txt"
set "MODELS_DIR=models"
set "PIP_MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple"
set "PIP_TRUSTED=pypi.tuna.tsinghua.edu.cn"

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
    echo   [!!] !WARN! 个警告项, 不影响基础运行
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

echo     [!!] 当前目录未找到私有环境
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
            echo     [!!] 使用系统 Python: %%P
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
    echo     [!!] 目录 !NEW_VENV! 已存在
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
::  [3] 检测依赖包 (含 onnxruntime)
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

:: ── onnxruntime (必须, CPU版) ──
set /a TOTAL+=1
call :GetModuleVersion onnxruntime _ortver
if not "!_ortver!"=="" (
    call :ItemPass "onnxruntime" "!_ortver! (CPU)"
) else (
    call :ItemFail "onnxruntime" "未安装 (推理引擎, 必须)"
    set "FAIL_LIST=!FAIL_LIST!onnxruntime "
)

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
::  自动修复 (含 onnxruntime)
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
    echo   [!!] 无私有环境, 先创建...
    call :CreateVenvFlow
    if "!VENV_DIR!"=="" goto :EOF
)

echo   --- 检查并安装缺失的 pip 包 ---
echo.

call :GetModuleVersion cv2 _cv2ver
if not "!_cv2ver!"=="" (
    echo     [跳过] opencv-python 已安装 ^(!_cv2ver!^)
) else (
    echo     [安装] opencv-python ...
    "!VENV_PYTHON!" -m pip install opencv-python -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
)

call :GetModuleVersion numpy _npver
if not "!_npver!"=="" (
    echo     [跳过] numpy 已安装 ^(!_npver!^)
) else (
    echo     [安装] numpy ...
    "!VENV_PYTHON!" -m pip install numpy -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
)

call :GetModuleVersion scipy _spver
if not "!_spver!"=="" (
    echo     [跳过] scipy 已安装 ^(!_spver!^)
) else (
    echo     [安装] scipy ...
    "!VENV_PYTHON!" -m pip install scipy -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
)

call :GetModuleVersion onnxruntime _ortver
if not "!_ortver!"=="" (
    echo     [跳过] onnxruntime 已安装 ^(!_ortver!^)
) else (
    echo     [安装] onnxruntime ...
    "!VENV_PYTHON!" -m pip install onnxruntime -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
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
::  安装 pip 依赖 (含 onnxruntime)
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
    echo     [!!] 将安装到系统环境
    set /p "CONF=     继续？ (Y/N): "
    if /i not "!CONF!"=="Y" goto :EOF
)

echo     镜像: %PIP_MIRROR%
echo.

if exist "%REQUIREMENTS_FILE%" (
    echo     使用 %REQUIREMENTS_FILE% ...
    "!VENV_PYTHON!" -m pip install -r "%REQUIREMENTS_FILE%" -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location
    if !errorlevel! EQU 0 (
        echo     [OK] 安装完成
        goto :EOF
    )
    echo     [!!] requirements.txt 部分失败, 改为逐个安装
    echo.
)

echo     [1/4] opencv-python ...
"!VENV_PYTHON!" -m pip install opencv-python -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location

echo     [2/4] numpy ...
"!VENV_PYTHON!" -m pip install numpy -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location

echo     [3/4] scipy ...
"!VENV_PYTHON!" -m pip install scipy -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location

echo     [4/4] onnxruntime ...
"!VENV_PYTHON!" -m pip install onnxruntime -i %PIP_MIRROR% --trusted-host %PIP_TRUSTED% --prefer-binary --no-warn-script-location

echo.
echo     安装完成
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

echo   [1/4] 人脸检测模型

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
echo   [2/4] YOLOv4-tiny

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
echo   [3/4] 风格迁移模型

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
echo   [4/4] EAST 文字检测

if exist "%MODELS_DIR%\frozen_east_text_detection.pb" (
    echo     [跳过] frozen_east_text_detection.pb
    set /a _skip+=1
) else (
    echo     [下载] frozen_east_text_detection.pb ~96MB ...
    call :DL "https://raw.githubusercontent.com/oyyd/frozen_east_text_detection.pb/master/frozen_east_text_detection.pb" "%MODELS_DIR%\frozen_east_text_detection.pb"
    set /a _dl+=1
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
echo   [必须] opencv-python   - 图像/视频处理核心
echo   [必须] numpy           - 数组计算
echo   [必须] onnxruntime     - ONNX 推理引擎 (CPU)
echo   [可选] scipy           - 科学计算
echo   [可选] FFmpeg          - 视频转码/GIF
echo.
echo   === v2.4 更新 ===
echo   新增 onnxruntime (CPU) 为必须依赖
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
echo     [!!] %_n:~0,22% %~2
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
echo     VideoToolbox - 环境检测与安装工具 v2.4
echo     使用项目私有 Python 环境 (无需管理员权限)
echo.
echo   ==================================================
echo.
echo     目录: %CD%
echo     时间: %date% %time:~0,8%
goto :EOF