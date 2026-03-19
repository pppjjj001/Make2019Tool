@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title 代码注释处理工具 启动器
color 0A

echo ============================================
echo    代码注释处理工具 启动器
echo ============================================
echo.

:: ── 检测 Python 环境 ──
set "PYTHON_CMD="

where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python"
    goto :found
)

where python3 >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=python3"
    goto :found
)

where py >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_CMD=py"
    goto :found
)

for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
) do (
    if exist %%P (
        set "PYTHON_CMD=%%~P"
        goto :found
    )
)

echo [ERROR] No Python found!
echo.
echo Please install Python 3.7+ :
echo   https://www.python.org/downloads/
echo   Check "Add Python to PATH" during install
echo.
echo Press any key to open download page...
pause >nul
start https://www.python.org/downloads/
goto :eof

:found
echo [OK] Python found: %PYTHON_CMD%
%PYTHON_CMD% --version 2>&1
echo.

:: ── 检测脚本文件 ──
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_NAME=comment_remover.py"
set "SCRIPT_PATH=%SCRIPT_DIR%%SCRIPT_NAME%"

if not exist "%SCRIPT_PATH%" (
    echo [!] %SCRIPT_NAME% not found, searching .py files...
    echo.

    for %%F in ("%SCRIPT_DIR%*.py") do (
        findstr /i /c:"CommentRemoverApp" "%%F" >nul 2>&1
        if !ERRORLEVEL! equ 0 (
            set "SCRIPT_PATH=%%F"
            set "SCRIPT_NAME=%%~nxF"
            echo [OK] Found script: %%~nxF
            goto :run
        )
    )

    echo [ERROR] Script not found in current directory!
    echo.
    echo Please make sure the .py file is in the same folder as this .bat
    echo Current directory: %SCRIPT_DIR%
    echo.
    pause
    goto :eof
)

echo [OK] Found script: %SCRIPT_NAME%

:run
echo.
echo ============================================
echo  Starting Comment Remover Tool...
echo  This window will close after the tool exits
echo ============================================
echo.

:: ── 检测 tkinter ──
%PYTHON_CMD% -c "import tkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] tkinter module is missing!
    echo.
    echo Fix:
    echo   Windows - Reinstall Python, check "tcl/tk and IDLE"
    echo   Ubuntu  - sudo apt install python3-tk
    echo   CentOS  - sudo yum install python3-tkinter
    echo   macOS   - brew install python-tk
    echo.
    pause
    goto :eof
)

:: ── 启动程序 ──
cd /d "%SCRIPT_DIR%"
%PYTHON_CMD% "%SCRIPT_PATH%"

:: ── 异常退出处理 ──
if %ERRORLEVEL% neq 0 (
    echo.
    echo ============================================
    echo  [!] Program exited with error: %ERRORLEVEL%
    echo ============================================
    echo.
    echo Possible causes:
    echo   [1] Syntax error in the Python script
    echo   [2] Python version too old (need 3.7+)
    echo   [3] Missing dependencies
    echo.
    echo Try running manually:
    echo   %PYTHON_CMD% "%SCRIPT_PATH%"
    echo.
    pause
)

endlocal
goto :eof