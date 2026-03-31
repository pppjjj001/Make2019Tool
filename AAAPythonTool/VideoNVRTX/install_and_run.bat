@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  NVEncC Video Enhancer - 安装与启动脚本 v2.0
:: ============================================================

title NVEncC Video Enhancer - 安装程序

set "VENV_DIR=%~dp0.venv"
set "PY_SCRIPT=%~dp0nvencc_enhancer.py"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"
set "INSTALLED_FLAG=%VENV_DIR%\.installed_ok"
set "LINE=────────────────────────────────────────────────"

echo.
echo  ╔══════════════════════════════════════════════════╗
echo  ║     NVEncC Video Enhancer  安装 ^& 启动脚本     ║
echo  ╚══════════════════════════════════════════════════╝
echo.

:: ============================================================
::  第1步: 检测 Python
:: ============================================================
echo  [1/4] 检测 Python 环境...
echo  %LINE%

set "PYTHON_CMD="

where py >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_CMD=py -3"
    goto :py_found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    :: 排除 Windows Store 假 python
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do (
        echo %%i | findstr /i "Python 3" >nul 2>&1
        if !errorlevel! equ 0 (
            set "PYTHON_CMD=python"
            goto :py_found
        )
    )
)

:: 扫描常见路径
for %%V in (313 312 311 310 39 38) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        set "PYTHON_CMD=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe"
        goto :py_found
    )
)

echo  [X] 未找到 Python！请安装 Python 3.8+
echo      https://www.python.org/downloads/
echo.
pause
exit /b 1

:py_found
for /f "tokens=*" %%i in ('!PYTHON_CMD! --version 2^>^&1') do set "PY_VER_STR=%%i"
echo  [OK] !PY_VER_STR!  (!PYTHON_CMD!)

:: 版本检查
for /f "tokens=2 delims= " %%a in ("!PY_VER_STR!") do set "PY_VER=%%a"
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    if %%a lss 3 goto :py_old
    if %%a equ 3 if %%b lss 8 goto :py_old
)
goto :py_ok
:py_old
echo  [X] Python 版本过低，需要 3.8+
pause
exit /b 1
:py_ok

:: ============================================================
::  第2步: 虚拟环境
:: ============================================================
echo.
echo  [2/4] 检查虚拟环境...
echo  %LINE%

if exist "%VENV_PYTHON%" (
    echo  [OK] 虚拟环境已存在
    goto :venv_ok
)

echo  [..] 正在创建虚拟环境...
!PYTHON_CMD! -m venv "%VENV_DIR%"
if not exist "%VENV_PYTHON%" (
    echo  [X] 创建失败！
    echo      尝试: !PYTHON_CMD! -m pip install virtualenv
    pause
    exit /b 1
)
echo  [OK] 虚拟环境创建成功

:: 新环境，删除安装标记，强制重新检查依赖
if exist "%INSTALLED_FLAG%" del "%INSTALLED_FLAG%"

:venv_ok

:: ============================================================
::  第3步: 检查依赖 (只在首次或标记缺失时执行)
:: ============================================================
echo.
echo  [3/4] 检查依赖...
echo  %LINE%

:: 如果已安装标记存在，跳过所有检查
if exist "%INSTALLED_FLAG%" (
    echo  [OK] 依赖已就绪 (跳过检查)
    echo       删除 .venv\.installed_ok 可强制重新检查
    goto :deps_ok
)

:: --- pip 检查 (不升级，只确保可用) ---
"%VENV_PYTHON%" -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [..] 安装 pip...
    "%VENV_PYTHON%" -m ensurepip --default-pip >nul 2>&1
)
for /f "tokens=2 delims= " %%v in ('"%VENV_PYTHON%" -m pip --version 2^>^&1') do (
    echo  [OK] pip %%v (已就绪，不强制升级)
)

:: --- tkinter 检查 ---
"%VENV_PYTHON%" -c "import tkinter" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [X] tkinter 不可用！请重新安装 Python 并勾选 tcl/tk
    pause
    exit /b 1
)
echo  [OK] tkinter 可用

:: --- 检查可选依赖 ---
echo.
echo  检查可选依赖包...

set "MISSING_PKGS="
set "MISSING_NAMES="
set "ALL_INSTALLED=1"

:: 检查 Pillow
"%VENV_PYTHON%" -c "import PIL" >nul 2>&1
if %errorlevel% equ 0 (
    echo    [OK] Pillow       - 已安装
) else (
    echo    [--] Pillow       - 未安装 (视频缩略图预览)
    set "MISSING_PKGS=!MISSING_PKGS! Pillow"
    set "MISSING_NAMES=!MISSING_NAMES! Pillow"
    set "ALL_INSTALLED=0"
)

:: 检查 psutil
"%VENV_PYTHON%" -c "import psutil" >nul 2>&1
if %errorlevel% equ 0 (
    echo    [OK] psutil       - 已安装
) else (
    echo    [--] psutil       - 未安装 (系统资源监控)
    set "MISSING_PKGS=!MISSING_PKGS! psutil"
    set "MISSING_NAMES=!MISSING_NAMES! psutil"
    set "ALL_INSTALLED=0"
)

:: 检查 ttkthemes
"%VENV_PYTHON%" -c "import ttkthemes" >nul 2>&1
if %errorlevel% equ 0 (
    echo    [OK] ttkthemes    - 已安装
) else (
    echo    [--] ttkthemes    - 未安装 (更多GUI主题)
    set "MISSING_PKGS=!MISSING_PKGS! ttkthemes"
    set "MISSING_NAMES=!MISSING_NAMES! ttkthemes"
    set "ALL_INSTALLED=0"
)

:: 只在有缺失包时才询问
if "!ALL_INSTALLED!"=="1" (
    echo.
    echo  [OK] 所有可选依赖已安装
    goto :write_flag
)

echo.
echo  以上未安装的包为可选项，不影响核心功能。
echo.
set /p "INSTALL_OPT=  是否安装缺失的可选包？(Y/N) [默认=N]: "
if /i "!INSTALL_OPT!"=="Y" (
    echo.
    echo  [..] 正在安装:!MISSING_PKGS!
    "%VENV_PYTHON%" -m pip install !MISSING_PKGS! --quiet 2>nul
    if %errorlevel% equ 0 (
        echo  [OK] 安装完成
    ) else (
        echo  [!!] 部分安装失败，不影响核心功能
    )
) else (
    echo  [OK] 跳过
)

:write_flag
:: 写入安装完成标记
echo installed=%date% %time% > "%INSTALLED_FLAG%"
echo  [OK] 依赖检查完成，已标记

:deps_ok

:: ============================================================
::  第4步: 启动程序
:: ============================================================
echo.
echo  [4/4] 启动程序...
echo  %LINE%

if not exist "%PY_SCRIPT%" (
    echo  [X] 未找到主程序: %PY_SCRIPT%
    echo      请确保 nvencc_enhancer.py 在同一目录下
    pause
    exit /b 1
)

echo  [OK] 主程序: %PY_SCRIPT%
echo.
echo  正在启动 NVEncC Video Enhancer ...
echo  %LINE%
echo.

:: ========================================
::  关键：用 python.exe 启动并保持窗口
::  这样如果py报错，能看到错误信息
:: ========================================

cd /d "%~dp0"
"%VENV_PYTHON%" "%PY_SCRIPT%"

:: 如果程序退出了(正常关闭GUI或出错)，会到这里
set "EXIT_CODE=%errorlevel%"

echo.
if %EXIT_CODE% neq 0 (
    echo  %LINE%
    echo  [!] 程序异常退出，错误码: %EXIT_CODE%
    echo.
    echo  常见问题:
    echo    1. 缺少模块 → 删除 .venv\.installed_ok 后重新运行本脚本
    echo    2. Python脚本语法错误 → 检查 nvencc_enhancer.py
    echo    3. 权限问题 → 右键以管理员身份运行
    echo  %LINE%
    echo.
    pause
) else (
    echo  程序已正常关闭。
    timeout /t 2 /nobreak >nul
)

exit /b %EXIT_CODE%