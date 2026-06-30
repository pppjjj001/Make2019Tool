@echo off
chcp 65001 >nul

REM 检查 HTTP_PROXY 是否存在来判断当前状态
reg query "HKCU\Environment" /v HTTP_PROXY >nul 2>&1
if %errorlevel%==0 (
    echo [当前状态] 代理已开启 → 即将关闭...
    echo.
    call "%~dp0proxy-off.bat"
) else (
    echo [当前状态] 代理已关闭 → 即将开启...
    echo.
    call "%~dp0proxy-on.bat"
)