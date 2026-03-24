@echo off
setlocal EnableDelayedExpansion

:: ============================================================
::  视频去闪烁工具 - 启动脚本
:: ============================================================

title 视频去闪烁工具 - 环境检测与启动

:: 状态标记
set "PYTHON_OK=0"
set "PYTHON_CMD="
set "PIP_CMD="
set "FFMPEG_OK=0"
set "FFPROBE_OK=0"
set "VENV_USED=0"
set "NEED_INSTALL=0"
set "TKINTER_OK=0"
set "SCRIPT_OK=0"

:: 镜像源
set "MIRROR_PYPI="
set "MIRROR_NAME=默认官方源"
set "MIRROR_HOST="

:: ============================================================
::  主流程 - 用 call 保证每步都执行
:: ============================================================

call :banner
echo.
echo  正在检测环境，请稍候...
echo.

call :check_python
call :check_ffmpeg
call :check_venv
call :check_dependencies
call :show_summary

echo.
echo  按任意键继续...
pause >nul

if "!NEED_INSTALL!"=="1" (
    call :ask_install
)

call :final_check
if "!READY!"=="0" (
    echo.
    echo  ============================================
    echo   环境不满足最低要求，无法启动程序
    echo   请解决以上问题后重新运行此脚本
    echo  ============================================
    echo.
    pause
    goto :real_end
)

call :launch
goto :real_end

:: ============================================================
::  Banner
:: ============================================================
:banner
cls
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║                                                      ║
echo  ║     视频去闪烁工具 Video Deflicker                   ║
echo  ║     环境检测与自动配置启动脚本 v1.0                  ║
echo  ║                                                      ║
echo  ╚══════════════════════════════════════════════════════╝
echo.
goto :eof

:: ============================================================
::  检测 Python
:: ============================================================
:check_python
echo  [1/4] 检测 Python 环境...

:: 依次尝试 python / python3 / py
for %%P in (python python3 py) do (
    if "!PYTHON_OK!"=="0" (
        %%P --version >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "tokens=2 delims= " %%V in ('%%P --version 2^>^&1') do (
                set "PY_VERSION=%%V"
            )
            for /f "tokens=1,2 delims=." %%A in ("!PY_VERSION!") do (
                set "PY_MAJOR=%%A"
                set "PY_MINOR=%%B"
            )
            if !PY_MAJOR! geq 3 if !PY_MINOR! geq 7 (
                set "PYTHON_OK=1"
                set "PYTHON_CMD=%%P"
                echo         [OK] Python !PY_VERSION! (命令: %%P^)
            )
        )
    )
)

if "!PYTHON_OK!"=="0" (
    echo         [X]  未找到 Python 3.7+
    echo              请安装: https://www.python.org/downloads/
    echo              安装时务必勾选 "Add Python to PATH"
    set "NEED_INSTALL=1"
    goto :eof
)

:: 检测 pip
!PYTHON_CMD! -m pip --version >nul 2>&1
if !errorlevel! equ 0 (
    set "PIP_CMD=!PYTHON_CMD! -m pip"
    echo         [OK] pip 可用
) else (
    echo         [!]  pip 不可用
    set "NEED_INSTALL=1"
)
goto :eof

:: ============================================================
::  检测 FFmpeg
:: ============================================================
:check_ffmpeg
echo.
echo  [2/4] 检测 FFmpeg / FFprobe...

where ffmpeg >nul 2>&1
if !errorlevel! equ 0 (
    echo         [OK] FFmpeg 已找到 (PATH^)
    set "FFMPEG_OK=1"
) else (
    :: 检查本地目录
    if exist "ffmpeg_bin\ffmpeg.exe" (
        echo         [OK] FFmpeg 已找到 (.\ffmpeg_bin\^)
        set "PATH=%CD%\ffmpeg_bin;!PATH!"
        set "FFMPEG_OK=1"
    ) else if exist "ffmpeg\bin\ffmpeg.exe" (
        echo         [OK] FFmpeg 已找到 (.\ffmpeg\bin\^)
        set "PATH=%CD%\ffmpeg\bin;!PATH!"
        set "FFMPEG_OK=1"
    ) else (
        echo         [X]  未找到 FFmpeg
        set "NEED_INSTALL=1"
    )
)

where ffprobe >nul 2>&1
if !errorlevel! equ 0 (
    echo         [OK] FFprobe 已找到
    set "FFPROBE_OK=1"
) else (
    if exist "ffmpeg_bin\ffprobe.exe" (
        echo         [OK] FFprobe 已找到 (本地^)
        set "FFPROBE_OK=1"
    ) else (
        echo         [!]  FFprobe 未找到 (部分功能受限^)
    )
)
goto :eof

:: ============================================================
::  检测虚拟环境
:: ============================================================
:check_venv
echo.
echo  [3/4] 检测虚拟环境...

if exist "venv\Scripts\activate.bat" (
    echo         [OK] 虚拟环境已存在 (.\venv^)
    set "VENV_USED=1"
    set "PYTHON_CMD=venv\Scripts\python.exe"
    set "PIP_CMD=venv\Scripts\python.exe -m pip"
) else (
    echo         [i]  未创建虚拟环境 (可选^)
)
goto :eof

:: ============================================================
::  检测依赖
:: ============================================================
:check_dependencies
echo.
echo  [4/4] 检测运行依赖...

:: 检查主脚本
if exist "deflicker_gui.py" (
    echo         [OK] deflicker_gui.py 已找到
    set "SCRIPT_OK=1"
) else (
    echo         [X]  deflicker_gui.py 未找到!
    echo              请确保 start.bat 与主程序在同一目录
    set "NEED_INSTALL=1"
)

:: 检查 tkinter
if "!PYTHON_OK!"=="1" (
    !PYTHON_CMD! -c "import tkinter" >nul 2>&1
    if !errorlevel! equ 0 (
        echo         [OK] tkinter 可用
        set "TKINTER_OK=1"
    ) else (
        echo         [X]  tkinter 不可用
        echo              请重新安装 Python 并勾选 tcl/tk 组件
        set "NEED_INSTALL=1"
    )
) else (
    echo         [--] 跳过依赖检测 (Python 未就绪^)
)
goto :eof

:: ============================================================
::  显示检测汇总
:: ============================================================
:show_summary
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  环境检测汇总                                        ║
echo  ╠══════════════════════════════════════════════════════╣

if "!PYTHON_OK!"=="1" (
    echo  ║  Python       :  [OK]  !PY_VERSION!
) else (
    echo  ║  Python       :  [X]   缺失
)

if "!FFMPEG_OK!"=="1" (
    echo  ║  FFmpeg       :  [OK]  已就绪
) else (
    echo  ║  FFmpeg       :  [X]   缺失
)

if "!FFPROBE_OK!"=="1" (
    echo  ║  FFprobe      :  [OK]  已就绪
) else (
    echo  ║  FFprobe      :  [!]   缺失
)

if "!TKINTER_OK!"=="1" (
    echo  ║  tkinter      :  [OK]  可用
) else if "!PYTHON_OK!"=="1" (
    echo  ║  tkinter      :  [X]   不可用
) else (
    echo  ║  tkinter      :  [--]  未检测
)

if "!VENV_USED!"=="1" (
    echo  ║  虚拟环境     :  [OK]  已激活
) else (
    echo  ║  虚拟环境     :  [i]   未创建
)

if "!SCRIPT_OK!"=="1" (
    echo  ║  主程序       :  [OK]  已找到
) else (
    echo  ║  主程序       :  [X]   未找到
)

if "!NEED_INSTALL!"=="1" (
    echo  ╠══════════════════════════════════════════════════════╣
    echo  ║  状态: 存在缺失组件，需要安装                        ║
) else (
    echo  ╠══════════════════════════════════════════════════════╣
    echo  ║  状态: 所有环境检测通过!                              ║
)

echo  ╚══════════════════════════════════════════════════════╝
goto :eof

:: ============================================================
::  询问安装
:: ============================================================
:ask_install
echo.
echo  检测到缺失组件，请选择操作：
echo.
echo    [1] 自动安装全部 (官方源)
echo    [2] 自动安装全部 (使用国内镜像加速)
echo    [3] 仅创建虚拟环境
echo    [4] 仅安装 FFmpeg
echo    [5] 跳过，直接尝试启动
echo    [0] 退出
echo.
set /p "INSTALL_CHOICE=  请输入选项 [0-5]: "

if "!INSTALL_CHOICE!"=="1" (
    call :setup_all
) else if "!INSTALL_CHOICE!"=="2" (
    call :select_mirror
    call :setup_all
) else if "!INSTALL_CHOICE!"=="3" (
    call :setup_venv
    echo.
    pause
) else if "!INSTALL_CHOICE!"=="4" (
    call :install_ffmpeg
    echo.
    pause
) else if "!INSTALL_CHOICE!"=="5" (
    echo.
    echo  跳过安装...
) else if "!INSTALL_CHOICE!"=="0" (
    echo.
    echo  再见！
    pause
    exit /b 0
) else (
    echo.
    echo  无效输入，跳过安装
)
echo.
goto :eof

:: ============================================================
::  选择镜像源
:: ============================================================
:select_mirror
echo.
echo  选择 PyPI 镜像站：
echo.
echo    [1] 清华大学       (推荐)
echo    [2] 阿里云
echo    [3] 中科大
echo    [4] 豆瓣
echo    [5] 华为云
echo    [6] 腾讯云
echo    [0] 不使用镜像
echo.
set /p "MIRROR_CHOICE=  请输入选项 [0-6]: "

if "!MIRROR_CHOICE!"=="1" (
    set "MIRROR_PYPI=https://pypi.tuna.tsinghua.edu.cn/simple"
    set "MIRROR_NAME=清华大学"
    set "MIRROR_HOST=pypi.tuna.tsinghua.edu.cn"
) else if "!MIRROR_CHOICE!"=="2" (
    set "MIRROR_PYPI=https://mirrors.aliyun.com/pypi/simple"
    set "MIRROR_NAME=阿里云"
    set "MIRROR_HOST=mirrors.aliyun.com"
) else if "!MIRROR_CHOICE!"=="3" (
    set "MIRROR_PYPI=https://pypi.mirrors.ustc.edu.cn/simple"
    set "MIRROR_NAME=中科大"
    set "MIRROR_HOST=pypi.mirrors.ustc.edu.cn"
) else if "!MIRROR_CHOICE!"=="4" (
    set "MIRROR_PYPI=https://pypi.douban.com/simple"
    set "MIRROR_NAME=豆瓣"
    set "MIRROR_HOST=pypi.douban.com"
) else if "!MIRROR_CHOICE!"=="5" (
    set "MIRROR_PYPI=https://repo.huaweicloud.com/repository/pypi/simple"
    set "MIRROR_NAME=华为云"
    set "MIRROR_HOST=repo.huaweicloud.com"
) else if "!MIRROR_CHOICE!"=="6" (
    set "MIRROR_PYPI=https://mirrors.cloud.tencent.com/pypi/simple"
    set "MIRROR_NAME=腾讯云"
    set "MIRROR_HOST=mirrors.cloud.tencent.com"
) else (
    set "MIRROR_PYPI="
    set "MIRROR_NAME=官方源"
    set "MIRROR_HOST="
)

if defined MIRROR_PYPI (
    echo.
    echo  已选择镜像: !MIRROR_NAME!
    echo  !MIRROR_PYPI!
    echo.
    set /p "SET_GLOBAL=  设为 pip 全局默认？[Y/n]: "
    if /i "!SET_GLOBAL!"=="" set "SET_GLOBAL=Y"
    if /i "!SET_GLOBAL!"=="Y" (
        call :set_pip_mirror_global
    )
)
goto :eof

:: ============================================================
::  设置 pip 全局镜像
:: ============================================================
:set_pip_mirror_global
if "!PYTHON_OK!"=="0" goto :eof

!PYTHON_CMD! -m pip config set global.index-url "!MIRROR_PYPI!" >nul 2>&1
if !errorlevel! equ 0 (
    !PYTHON_CMD! -m pip config set global.trusted-host "!MIRROR_HOST!" >nul 2>&1
    echo  [OK] 已设置 pip 全局镜像: !MIRROR_NAME!
) else (
    set "PIP_DIR=%APPDATA%\pip"
    if not exist "!PIP_DIR!" mkdir "!PIP_DIR!"
    (
        echo [global]
        echo index-url = !MIRROR_PYPI!
        echo trusted-host = !MIRROR_HOST!
    ) > "!PIP_DIR!\pip.ini"
    echo  [OK] 已写入 %APPDATA%\pip\pip.ini
)
goto :eof

:: ============================================================
::  构建 pip 额外参数
:: ============================================================
:build_pip_args
set "PIP_EXTRA_ARGS="
if defined MIRROR_PYPI (
    set "PIP_EXTRA_ARGS=-i !MIRROR_PYPI! --trusted-host !MIRROR_HOST!"
)
goto :eof

:: ============================================================
::  全部安装
:: ============================================================
:setup_all
echo.
echo  ============================================
echo   开始自动安装配置
echo   镜像源: !MIRROR_NAME!
echo  ============================================
echo.

call :build_pip_args

:: --- Python ---
if "!PYTHON_OK!"=="0" (
    echo  [Step 1/5] 安装 Python...
    call :install_python
    :: 重新检测
    set "PYTHON_OK=0"
    for %%P in (python python3 py) do (
        if "!PYTHON_OK!"=="0" (
            %%P --version >nul 2>&1
            if !errorlevel! equ 0 (
                set "PYTHON_OK=1"
                set "PYTHON_CMD=%%P"
            )
        )
    )
    if "!PYTHON_OK!"=="0" (
        echo.
        echo  [X] Python 安装失败，请手动安装后重试
        pause
        goto :eof
    )
) else (
    echo  [Step 1/5] Python 已就绪，跳过
)

:: --- pip ---
echo.
echo  [Step 2/5] 确保 pip 可用...
!PYTHON_CMD! -m pip --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  正在安装 pip...
    !PYTHON_CMD! -m ensurepip --upgrade 2>nul
    if !errorlevel! neq 0 (
        echo  ensurepip 失败，尝试 get-pip.py...
        curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py 2>nul
        if exist "get-pip.py" (
            !PYTHON_CMD! get-pip.py !PIP_EXTRA_ARGS!
            del /f get-pip.py >nul 2>&1
        )
    )
)
set "PIP_CMD=!PYTHON_CMD! -m pip"
!PIP_CMD! --version >nul 2>&1
if !errorlevel! equ 0 (
    echo  [OK] pip 就绪
) else (
    echo  [X] pip 安装失败
)

:: --- 升级 pip ---
echo.
echo  [Step 3/5] 升级 pip...
!PIP_CMD! install --upgrade pip !PIP_EXTRA_ARGS! >nul 2>&1
echo  [OK] 完成

:: --- 虚拟环境 ---
echo.
echo  [Step 4/5] 创建虚拟环境...
call :setup_venv

:: --- 安装依赖 ---
echo.
echo  [Step 5/5] 安装依赖...
call :install_pip_deps

:: --- FFmpeg ---
if "!FFMPEG_OK!"=="0" (
    echo.
    echo  [额外] 安装 FFmpeg...
    call :install_ffmpeg
) else (
    echo.
    echo  FFmpeg 已就绪，跳过
)

echo.
echo  ============================================
echo   安装配置完成!
echo  ============================================
echo.
pause
goto :eof

:: ============================================================
::  安装 Python
:: ============================================================
:install_python
echo.

where winget >nul 2>&1
if !errorlevel! equ 0 (
    echo  使用 winget 安装 Python 3.12...
    winget install Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if !errorlevel! equ 0 (
        echo  [OK] Python 安装成功
        set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;!PATH!"
        goto :eof
    )
)

where scoop >nul 2>&1
if !errorlevel! equ 0 (
    echo  使用 scoop 安装 Python...
    scoop install python
    if !errorlevel! equ 0 (
        echo  [OK] 安装成功
        goto :eof
    )
)

where choco >nul 2>&1
if !errorlevel! equ 0 (
    echo  使用 Chocolatey 安装 Python...
    choco install python3 -y
    if !errorlevel! equ 0 (
        echo  [OK] 安装成功
        goto :eof
    )
)

echo.
echo  自动安装失败，请手动安装 Python:
echo    https://www.python.org/downloads/
echo    安装时勾选 "Add Python to PATH"
echo.
pause
goto :eof

:: ============================================================
::  创建虚拟环境
:: ============================================================
:setup_venv
if "!PYTHON_OK!"=="0" (
    echo  [--] Python 不可用，跳过虚拟环境
    goto :eof
)

if exist "venv\Scripts\activate.bat" (
    echo  [OK] 虚拟环境已存在
) else (
    echo  创建虚拟环境 .\venv ...
    !PYTHON_CMD! -m venv venv
    if !errorlevel! equ 0 (
        echo  [OK] 虚拟环境创建成功
    ) else (
        echo  [!] 创建失败，将使用全局环境
        goto :eof
    )
)

set "VENV_USED=1"
set "PYTHON_CMD=venv\Scripts\python.exe"
set "PIP_CMD=venv\Scripts\python.exe -m pip"
echo  已切换到虚拟环境
goto :eof

:: ============================================================
::  安装 pip 依赖
:: ============================================================
:install_pip_deps
call :build_pip_args

:: 升级虚拟环境 pip
!PIP_CMD! install --upgrade pip !PIP_EXTRA_ARGS! >nul 2>&1

if exist "requirements.txt" (
    echo  从 requirements.txt 安装...
    !PIP_CMD! install -r requirements.txt !PIP_EXTRA_ARGS!
    if !errorlevel! equ 0 (
        echo  [OK] 依赖安装完成
    ) else (
        echo  [!] 部分依赖安装失败
    )
) else (
    echo  [i] 未找到 requirements.txt (基础功能无需额外依赖^)
)
goto :eof

:: ============================================================
::  安装 FFmpeg
:: ============================================================
:install_ffmpeg
echo.
echo  安装 FFmpeg - 选择方式:
echo.
echo    [1] winget 安装 (Win10+推荐)
echo    [2] scoop 安装
echo    [3] choco 安装
echo    [4] 打开下载页面 (手动)
echo    [5] 跳过
echo.
set /p "FF_CHOICE=  请输入选项 [1-5]: "

if "!FF_CHOICE!"=="1" (
    where winget >nul 2>&1
    if !errorlevel! equ 0 (
        echo  正在安装...
        winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
        if !errorlevel! equ 0 (
            echo  [OK] FFmpeg 安装成功
            set "FFMPEG_OK=1"
        ) else (
            echo  [X] 安装失败
        )
    ) else (
        echo  [X] winget 不可用
    )
) else if "!FF_CHOICE!"=="2" (
    where scoop >nul 2>&1
    if !errorlevel! equ 0 (
        scoop install ffmpeg
        if !errorlevel! equ 0 (
            echo  [OK] FFmpeg 安装成功
            set "FFMPEG_OK=1"
        )
    ) else (
        echo  [X] scoop 不可用
    )
) else if "!FF_CHOICE!"=="3" (
    where choco >nul 2>&1
    if !errorlevel! equ 0 (
        choco install ffmpeg -y
        if !errorlevel! equ 0 (
            echo  [OK] FFmpeg 安装成功
            set "FFMPEG_OK=1"
        )
    ) else (
        echo  [X] choco 不可用
    )
) else if "!FF_CHOICE!"=="4" (
    echo  正在打开下载页面...
    start "" "https://www.gyan.dev/ffmpeg/builds/"
    echo.
    echo  下载后解压，将 bin 目录添加到系统 PATH
    echo  或将 ffmpeg.exe / ffprobe.exe 放到本脚本同级的 ffmpeg_bin 目录
) else (
    echo  跳过
)
goto :eof

:: ============================================================
::  最终检查
:: ============================================================
:final_check
set "READY=1"

echo.
echo  最终检查...

:: Python
!PYTHON_CMD! --version >nul 2>&1
if !errorlevel! neq 0 (
    echo  [X] Python 不可用
    set "READY=0"
) else (
    echo  [OK] Python
)

:: FFmpeg
set "FF_FOUND=0"
where ffmpeg >nul 2>&1
if !errorlevel! equ 0 set "FF_FOUND=1"
if exist "ffmpeg_bin\ffmpeg.exe" set "FF_FOUND=1"
if "!FF_FOUND!"=="1" (
    echo  [OK] FFmpeg
) else (
    echo  [!] FFmpeg 不在 PATH (程序内可手动指定路径)
)

:: 主程序
if exist "deflicker_gui.py" (
    echo  [OK] deflicker_gui.py
) else (
    echo  [X] deflicker_gui.py 未找到!
    set "READY=0"
)

:: tkinter
if "!PYTHON_OK!"=="1" (
    !PYTHON_CMD! -c "import tkinter" >nul 2>&1
    if !errorlevel! neq 0 (
        echo  [X] tkinter 不可用
        set "READY=0"
    )
)
goto :eof

:: ============================================================
::  启动程序
:: ============================================================
:launch
echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║  启动视频去闪烁工具...                               ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

:: 激活虚拟环境
if "!VENV_USED!"=="1" (
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
    )
)

echo  Python: !PYTHON_CMD!
echo  程序:   deflicker_gui.py
echo.
echo  提示: 关闭此窗口会同时关闭程序
echo        程序运行日志见下方输出
echo.
echo  ────────────────────────────────────────────────
echo.

!PYTHON_CMD! deflicker_gui.py

:: 程序退出后
echo.
echo  ────────────────────────────────────────────────
echo.

if !errorlevel! neq 0 (
    echo  程序异常退出 (错误码: !errorlevel!)
    echo.
    echo  常见问题:
    echo    1. tkinter 缺失 - 重新安装 Python 并勾选 tcl/tk
    echo    2. 模块错误 - 确认 Python 版本 3.7+
    echo    3. 权限问题 - 右键"以管理员身份运行"
    echo.
)

echo  程序已退出，按任意键关闭窗口...
pause >nul
goto :eof

:: ============================================================
::  真正的结束
:: ============================================================
:real_end
endlocal
exit /b 0