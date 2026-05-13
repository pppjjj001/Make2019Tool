@echo off
title 蓝噪声生成工具

echo ========================================
echo    蓝噪声纹理生成工具
echo ========================================
echo.

REM 设置 pip 中国镜像源（清华大学）
set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
set PIP_TRUSTED_HOST=pypi.tuna.tsinghua.edu.cn

echo [配置] 已设置 pip 镜像源为清华大学 TUNA
echo        镜像地址: %PIP_INDEX_URL%
echo.

REM 检查 Python 是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python！
    echo.
    echo 请先安装 Python 3.7+
    echo 下载地址: https://www.python.org/downloads/
    echo 国内镜像: https://mirrors.huaweicloud.com/python/
    echo.
    pause
    exit /b 1
)

echo [检查] Python 已安装
echo.

REM 检查依赖
echo [检查] 正在检查依赖库...
python -c "import numpy" >nul 2>&1
if errorlevel 1 (
    echo [安装] numpy 未安装，正在通过镜像源安装...
    pip install numpy -i %PIP_INDEX_URL% --trusted-host %PIP_TRUSTED_HOST%
)

python -c "import PIL" >nul 2>&1
if errorlevel 1 (
    echo [安装] Pillow 未安装，正在通过镜像源安装...
    pip install Pillow -i %PIP_INDEX_URL% --trusted-host %PIP_TRUSTED_HOST%
)

python -c "import scipy" >nul 2>&1
if errorlevel 1 (
    echo [提示] scipy 未安装 (可选，但推荐安装以获得更好效果)
    echo.
    choice /C YN /M "是否现在安装 scipy"
    if errorlevel 2 goto skip_scipy
    if errorlevel 1 (
        echo [安装] 正在通过镜像源安装 scipy...
        pip install scipy -i %PIP_INDEX_URL% --trusted-host %PIP_TRUSTED_HOST%
    )
)
:skip_scipy

echo.
echo [启动] 正在运行生成工具...
echo ========================================
echo.

REM 运行 Python 脚本
python blue_noise_generator.py

echo.
pause