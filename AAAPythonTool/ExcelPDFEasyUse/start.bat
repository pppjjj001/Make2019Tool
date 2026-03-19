@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion
title 文件转换工具 - 环境检测

echo ══════════════════════════════════════════════════
echo          文件转换工具 - 启动器 v1.0
echo ══════════════════════════════════════════════════
echo.

:: ====================================================
:: 第一步：检测 Python 是否安装
:: ====================================================
echo [1/4] 检测 Python 环境...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  ❌ 未检测到 Python！
    echo.
    echo  请前往以下地址下载安装 Python 3.8+：
    echo  https://www.python.org/downloads/
    echo.
    echo  ⚠ 安装时请务必勾选 "Add Python to PATH"
    echo.
    choice /C YN /M "是否立即打开 Python 下载页面？(Y/N)"
    if !errorlevel! equ 1 (
        start https://www.python.org/downloads/
    )
    echo.
    echo 安装完成后请重新运行本脚本。
    pause
    exit /b 1
)

:: 获取 Python 版本
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo  ✅ Python %PYTHON_VER% 已安装

:: ====================================================
:: 第二步：检测 pip 是否可用
:: ====================================================
echo.
echo [2/4] 检测 pip 包管理器...

python -m pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ❌ pip 不可用，正在尝试安装...
    python -m ensurepip --default-pip >nul 2>&1
    if !errorlevel! neq 0 (
        echo  ❌ pip 安装失败，请手动修复 Python 安装。
        pause
        exit /b 1
    )
)

for /f "tokens=2 delims= " %%v in ('python -m pip --version 2^>^&1') do set PIP_VER=%%v
echo  ✅ pip %PIP_VER% 已就绪

:: ====================================================
:: 第三步：逐个检测依赖包
:: ====================================================
echo.
echo [3/4] 检测依赖包...

set MISSING_PKGS=
set MISSING_COUNT=0

:: --- 检测 pandas ---
python -c "import pandas" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ⬜ pandas          - 未安装
    set MISSING_PKGS=!MISSING_PKGS! pandas
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%v in ('python -c "import pandas; print(pandas.__version__)"') do echo  ✅ pandas          - %%v
)

:: --- 检测 openpyxl ---
python -c "import openpyxl" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ⬜ openpyxl        - 未安装
    set MISSING_PKGS=!MISSING_PKGS! openpyxl
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%v in ('python -c "import openpyxl; print(openpyxl.__version__)"') do echo  ✅ openpyxl        - %%v
)

:: --- 检测 pdfplumber ---
python -c "import pdfplumber" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ⬜ pdfplumber      - 未安装
    set MISSING_PKGS=!MISSING_PKGS! pdfplumber
    set /a MISSING_COUNT+=1
) else (
    for /f "delims=" %%v in ('python -c "import pdfplumber; print(pdfplumber.__version__)"') do echo  ✅ pdfplumber      - %%v
)

:: ====================================================
:: 第四步：安装缺失的包（需用户确认）
:: ====================================================
if !MISSING_COUNT! gtr 0 (
    echo.
    echo ──────────────────────────────────────────────────
    echo  发现 !MISSING_COUNT! 个缺失的依赖包:!MISSING_PKGS!
    echo ──────────────────────────────────────────────────
    echo.
    choice /C YN /M "是否自动安装缺失的依赖包？(Y/N)"
    if !errorlevel! equ 2 (
        echo.
        echo  ⚠ 用户取消安装，程序无法运行。
        echo  您可以手动执行: pip install!MISSING_PKGS!
        pause
        exit /b 1
    )

    echo.
    echo  正在安装依赖包，请稍候...
    echo  ──────────────────────────────────────────
    
    :: 尝试使用国内镜像加速
    echo.
    choice /C YN /M "是否使用国内镜像加速下载？(推荐)(Y/N)"
    if !errorlevel! equ 1 (
        set PIP_MIRROR=-i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
        echo  使用清华镜像源...
    ) else (
        set PIP_MIRROR=
        echo  使用默认源...
    )

    echo.
    python -m pip install !MISSING_PKGS! !PIP_MIRROR!

    if !errorlevel! neq 0 (
        echo.
        echo  ❌ 安装过程中出现错误！
        echo.
        echo  可能的解决方法：
        echo  1. 以管理员身份运行本脚本
        echo  2. 检查网络连接
        echo  3. 手动执行: pip install!MISSING_PKGS!
        pause
        exit /b 1
    )

    echo.
    echo  ✅ 所有依赖包安装成功！

) else (
    echo.
    echo  ✅ 所有依赖包已就绪，无需安装。
)

:: ====================================================
:: 第五步：检测主程序文件是否存在
:: ====================================================
echo.
echo ──────────────────────────────────────────────────

:: 获取 bat 所在目录
set SCRIPT_DIR=%~dp0

if not exist "%SCRIPT_DIR%converter.py" (
    echo  ❌ 未找到主程序文件 converter.py
    echo  请确保 converter.py 与本脚本在同一目录下。
    echo  当前目录: %SCRIPT_DIR%
    pause
    exit /b 1
)

:: ====================================================
:: 第六步：启动程序
:: ====================================================
echo.
echo  🚀 正在启动文件转换工具...
echo ══════════════════════════════════════════════════
echo.

cd /d "%SCRIPT_DIR%"
python converter.py

if %errorlevel% neq 0 (
    echo.
    echo  ❌ 程序异常退出，错误码: %errorlevel%
    pause
    exit /b %errorlevel%
)

exit /b 0