@echo off
chcp 65001 >nul
title CMD 安全粘贴工具 - 启动器

echo ============================================================
echo           CMD 安全粘贴工具 - 启动中...
echo ============================================================
echo.

:: 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python 环境
    echo.
    echo 请先安装 Python 3.7+:
    echo   https://www.python.org/downloads/
    echo.
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo [√] Python 环境检测通过
python --version
echo.

:: 检查 pyperclip 是否安装
python -c "import pyperclip" >nul 2>&1
if errorlevel 1 (
    echo [!] 检测到缺少依赖 pyperclip，正在自动安装...
    echo.
    python -m pip install pyperclip -i https://pypi.tuna.tsinghua.edu.cn/simple/
    if errorlevel 1 (
        echo.
        echo [错误] 依赖安装失败，请手动执行：
        echo   pip install pyperclip
        echo.
        pause
        exit /b 1
    )
    echo.
    echo [√] 依赖安装完成
    echo.
)

echo [√] 所有依赖检查通过
echo.
echo 正在启动 GUI 程序...
echo ============================================================
echo.

:: 使用 pythonw 启动（无控制台窗口）
start "" pythonw "%~dp0safe_paste_gui.py"

:: 等待 2 秒后关闭启动窗口
timeout /t 2 /nobreak >nul
exit