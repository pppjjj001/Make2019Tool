@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  视频去闪烁工具 - 启动脚本 v2.0
::  功能：环境检测 → 缺失组件安装 → 启动程序
::  特点：不重复升级pip、精确检测requirements.txt依赖
:: ============================================================

title 视频去闪烁工具 - 启动

:: ---------- 全局变量 ----------
set "PYTHON_CMD="
set "PIP_CMD="
set "PY_VER="
set "VENV_DIR=venv"
set "SCRIPT=deflicker_gui.py"
set "REQFILE=requirements.txt"
set "READY=1"
set "MIRROR_URL="
set "MIRROR_HOST="

:: ============================================================
::  主流程
:: ============================================================

call :banner
echo.
echo  [1/6] 检测 Python ...
call :find_python
if "!PYTHON_CMD!"=="" (
    echo        未找到 Python 3.7+
    echo        请安装: https://www.python.org/downloads/
    echo        安装时勾选 "Add Python to PATH"
    set "READY=0"
    goto :summary
)
echo        OK  Python !PY_VER!  (!PYTHON_CMD!)

echo.
echo  [2/6] 检测 pip ...
call :find_pip
if "!PIP_CMD!"=="" (
    echo        pip 不可用，尝试安装 ...
    !PYTHON_CMD! -m ensurepip --default-pip >nul 2>&1
    call :find_pip
)
if "!PIP_CMD!"=="" (
    echo        pip 安装失败
    set "READY=0"
    goto :summary
)
echo        OK  pip 可用

echo.
echo  [3/6] 检测 FFmpeg ...
call :find_ffmpeg
if "!FFMPEG_OK!"=="1" (
    echo        OK  FFmpeg 已找到
) else (
    echo        未找到 FFmpeg (程序内可手动指定路径)
)

echo.
echo  [4/6] 检测虚拟环境 ...
call :check_venv

echo.
echo  [5/6] 检测 tkinter ...
!PYTHON_CMD! -c "import tkinter" >nul 2>&1
if !errorlevel! equ 0 (
    echo        OK  tkinter 可用
) else (
    echo        tkinter 不可用
    echo        需重新安装 Python 并勾选 tcl/tk
    set "READY=0"
)

echo.
echo  [6/6] 检测主程序 ...
if exist "!SCRIPT!" (
    echo        OK  !SCRIPT! 已找到
) else (
    echo        !SCRIPT! 不存在
    echo        请确保 start.bat 与主程序在同一目录
    set "READY=0"
)

:: ---------- 检测 requirements.txt ----------
echo.
if exist "!REQFILE!" (
    echo  [额外] 检测 requirements.txt 依赖 ...
    call :check_requirements
) else (
    echo  [额外] 未找到 requirements.txt，跳过依赖检查
)

:summary
echo.
echo  ========================================
if "!READY!"=="0" (
    echo   环境不满足最低要求，无法启动
    echo  ========================================
    echo.
    pause
    goto :real_exit
)
echo   环境检测通过
echo  ========================================

:: ---------- 启动 ----------
call :launch
goto :real_exit

:: ============================================================
::  Banner
:: ============================================================
:banner
cls
echo.
echo  ============================================
echo    视频去闪烁工具  Video Deflicker
echo    环境检测 ^& 启动脚本
echo  ============================================
goto :eof

:: ============================================================
::  查找 Python  (python / python3 / py)
:: ============================================================
:find_python
set "PYTHON_CMD="
for %%P in (python python3 py) do (
    if "!PYTHON_CMD!"=="" (
        %%P --version >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=2 delims= " %%V in ('%%P --version 2^>^&1') do set "PY_VER=%%V"
            for /f "tokens=1,2 delims=." %%A in ("!PY_VER!") do (
                if %%A geq 3 if %%B geq 7 (
                    set "PYTHON_CMD=%%P"
                )
            )
        )
    )
)
goto :eof

:: ============================================================
::  查找 pip (不主动升级)
:: ============================================================
:find_pip
set "PIP_CMD="
!PYTHON_CMD! -m pip --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PIP_CMD=!PYTHON_CMD! -m pip"
)
goto :eof

:: ============================================================
::  查找 FFmpeg
:: ============================================================
:find_ffmpeg
set "FFMPEG_OK=0"
where ffmpeg >nul 2>&1
if !errorlevel! equ 0 (
    set "FFMPEG_OK=1"
    goto :eof
)
for %%F in (
    "ffmpeg_bin\ffmpeg.exe"
    "ffmpeg\bin\ffmpeg.exe"
    "C:\ffmpeg\bin\ffmpeg.exe"
) do (
    if exist %%F (
        set "FFMPEG_OK=1"
        goto :eof
    )
)
goto :eof

:: ============================================================
::  虚拟环境检测与创建
:: ============================================================
:check_venv
if exist "!VENV_DIR!\Scripts\activate.bat" (
    echo        OK  虚拟环境已存在
    set "PYTHON_CMD=!VENV_DIR!\Scripts\python.exe"
    set "PIP_CMD=!VENV_DIR!\Scripts\python.exe -m pip"
    goto :eof
)
echo        虚拟环境不存在
set /p "CREATE_VENV=       是否创建虚拟环境? [Y/n]: "
if /i "!CREATE_VENV!"=="n" (
    echo        跳过，使用全局环境
    goto :eof
)
echo        创建中 ...
!PYTHON_CMD! -m venv "!VENV_DIR!"
if !errorlevel! equ 0 (
    echo        OK  创建成功
    set "PYTHON_CMD=!VENV_DIR!\Scripts\python.exe"
    set "PIP_CMD=!VENV_DIR!\Scripts\python.exe -m pip"
    :: 虚拟环境新建后 pip 可能需要安装
    !PYTHON_CMD! -m pip --version >nul 2>&1
    if !errorlevel! neq 0 (
        !PYTHON_CMD! -m ensurepip --default-pip >nul 2>&1
        set "PIP_CMD=!PYTHON_CMD! -m pip"
    )
) else (
    echo        创建失败，使用全局环境
)
goto :eof

:: ============================================================
::  检测 requirements.txt 中的依赖
::  逐行读取包名，用 pip show 检测是否已安装
::  只安装缺失的包，不做升级
:: ============================================================
:check_requirements
set "MISSING_PKGS="
set "MISSING_COUNT=0"
set "INSTALLED_COUNT=0"

:: 逐行解析 requirements.txt
for /f "usebackq tokens=1 delims=>=<;![ " %%A in ("!REQFILE!") do (
    set "PKG=%%A"
    :: 跳过注释和空行
    set "FIRST_CHAR=!PKG:~0,1!"
    if not "!FIRST_CHAR!"=="#" if not "!FIRST_CHAR!"=="" if not "!FIRST_CHAR!"=="-" (
        :: 用 pip show 检测是否安装
        !PIP_CMD! show "!PKG!" >nul 2>&1
        if !errorlevel! equ 0 (
            echo        OK  !PKG!
            set /a INSTALLED_COUNT+=1
        ) else (
            echo        缺失  !PKG!
            if "!MISSING_PKGS!"=="" (
                set "MISSING_PKGS=!PKG!"
            ) else (
                set "MISSING_PKGS=!MISSING_PKGS! !PKG!"
            )
            set /a MISSING_COUNT+=1
        )
    )
)

echo.
echo        已安装: !INSTALLED_COUNT!  缺失: !MISSING_COUNT!

if !MISSING_COUNT! equ 0 (
    echo        所有依赖已满足
    goto :eof
)

:: 询问安装
echo.
echo        缺失的包: !MISSING_PKGS!
echo.
echo        [1] 安装缺失包 (官方源)
echo        [2] 安装缺失包 (清华镜像)
echo        [3] 安装缺失包 (阿里镜像)
echo        [4] 安装缺失包 (中科大镜像)
echo        [5] 安装缺失包 (选择其他镜像)
echo        [0] 跳过
echo.
set /p "DEP_CHOICE=       请选择 [0-5]: "

if "!DEP_CHOICE!"=="0" goto :eof

:: 设置镜像
if "!DEP_CHOICE!"=="2" (
    set "MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "MIRROR_HOST=pypi.tuna.tsinghua.edu.cn"
) else if "!DEP_CHOICE!"=="3" (
    set "MIRROR_URL=https://mirrors.aliyun.com/pypi/simple"
    set "MIRROR_HOST=mirrors.aliyun.com"
) else if "!DEP_CHOICE!"=="4" (
    set "MIRROR_URL=https://pypi.mirrors.ustc.edu.cn/simple"
    set "MIRROR_HOST=pypi.mirrors.ustc.edu.cn"
) else if "!DEP_CHOICE!"=="5" (
    call :select_mirror
) else (
    set "MIRROR_URL="
    set "MIRROR_HOST="
)

:: 构建 pip install 参数
set "PIP_ARGS="
if defined MIRROR_URL (
    set "PIP_ARGS=-i !MIRROR_URL! --trusted-host !MIRROR_HOST!"
    echo.
    echo        使用镜像: !MIRROR_URL!
)

:: 逐个安装缺失的包
echo.
for %%P in (!MISSING_PKGS!) do (
    echo        安装 %%P ...
    !PIP_CMD! install %%P !PIP_ARGS! --quiet
    if !errorlevel! equ 0 (
        echo        OK  %%P 安装成功
    ) else (
        echo        %%P 安装失败
    )
)

:: 或者直接用 requirements.txt 安装全部
:: 取消下面注释可改为一次性安装：
:: echo        使用 requirements.txt 安装 ...
:: !PIP_CMD! install -r "!REQFILE!" !PIP_ARGS!

echo.
echo        依赖安装完成
goto :eof

:: ============================================================
::  选择镜像源
:: ============================================================
:select_mirror
echo.
echo        选择 PyPI 镜像:
echo        [1] 清华大学
echo        [2] 阿里云
echo        [3] 中科大
echo        [4] 豆瓣
echo        [5] 华为云
echo        [6] 腾讯云
echo        [0] 官方源
echo.
set /p "MR=        请选择 [0-6]: "

if "!MR!"=="1" (
    set "MIRROR_URL=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "MIRROR_HOST=pypi.tuna.tsinghua.edu.cn"
) else if "!MR!"=="2" (
    set "MIRROR_URL=https://mirrors.aliyun.com/pypi/simple"
    set "MIRROR_HOST=mirrors.aliyun.com"
) else if "!MR!"=="3" (
    set "MIRROR_URL=https://pypi.mirrors.ustc.edu.cn/simple"
    set "MIRROR_HOST=pypi.mirrors.ustc.edu.cn"
) else if "!MR!"=="4" (
    set "MIRROR_URL=https://pypi.douban.com/simple"
    set "MIRROR_HOST=pypi.douban.com"
) else if "!MR!"=="5" (
    set "MIRROR_URL=https://repo.huaweicloud.com/repository/pypi/simple"
    set "MIRROR_HOST=repo.huaweicloud.com"
) else if "!MR!"=="6" (
    set "MIRROR_URL=https://mirrors.cloud.tencent.com/pypi/simple"
    set "MIRROR_HOST=mirrors.cloud.tencent.com"
) else (
    set "MIRROR_URL="
    set "MIRROR_HOST="
)
goto :eof

:: ============================================================
::  启动程序
:: ============================================================
:launch
echo.
echo  ============================================
echo   启动程序 ...
echo  ============================================
echo.
echo  Python:  !PYTHON_CMD!
echo  脚本:    !SCRIPT!
echo.
echo  提示: 关闭此窗口会同时关闭程序
echo.
echo  ----------------------------------------
echo.

:: 激活虚拟环境
if exist "!VENV_DIR!\Scripts\activate.bat" (
    call "!VENV_DIR!\Scripts\activate.bat"
)

!PYTHON_CMD! "!SCRIPT!"
set "EXIT_CODE=!errorlevel!"

echo.
echo  ----------------------------------------
echo.

if !EXIT_CODE! neq 0 (
    echo  程序异常退出 (代码: !EXIT_CODE!)
    echo.
    echo  常见原因:
    echo    1. tkinter 缺失 - 重装 Python 勾选 tcl/tk
    echo    2. 依赖缺失 - 重新运行本脚本自动安装
    echo    3. FFmpeg 缺失 - 安装 FFmpeg 到 PATH
    echo.
) else (
    echo  程序正常退出
)

echo  按任意键关闭 ...
pause >nul
goto :eof

:: ============================================================
:real_exit
endlocal
exit /b 0