@echo off
cd /d "%~dp0"
title PyGameTools

where python >nul 2>nul
if errorlevel 1 (
    echo Python not found, running setup ...
    call "%~dp0一键安装.bat"
    exit /b %ERRORLEVEL%
)
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo tkinter missing, running setup ...
    call "%~dp0一键安装.bat"
    exit /b %ERRORLEVEL%
)
if not exist "tools\apktool.jar" (
    echo tools missing, running setup ...
    call "%~dp0一键安装.bat"
    exit /b %ERRORLEVEL%
)
if not exist "tools\jre\bin\java.exe" (
    echo JRE missing, running setup ...
    call "%~dp0一键安装.bat"
    exit /b %ERRORLEVEL%
)
python PyGameTools.py
if errorlevel 1 pause