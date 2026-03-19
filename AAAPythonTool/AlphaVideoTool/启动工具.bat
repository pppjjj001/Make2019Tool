@echo off
chcp 65001 >nul
title 跨平台透明视频转码工具

echo ==========================================
echo   跨平台透明视频转码工具
echo   HEVC Alpha → H.264 SBS MP4 + VP8 Alpha
echo ==========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo 请安装 Python 3.8+: https://www.python.org/downloads/
    echo 安装时勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 检查 FFmpeg
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [警告] 未找到 FFmpeg
    echo 请安装: winget install Gyan.FFmpeg
    echo 或下载: https://www.gyan.dev/ffmpeg/builds/
    echo.
)

:: 启动
echo 正在启动...
python "%~dp0alpha_video_tool.py"

if errorlevel 1 (
    echo.
    echo [错误] 程序异常退出
    pause
)