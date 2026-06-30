@echo off
chcp 65001 >nul
echo ================ 当前代理状态 ================
echo.

for %%V in (HTTP_PROXY HTTPS_PROXY ALL_PROXY) do (
    call :check %%V
)

echo.
echo ============================================
pause
goto :eof

:check
setlocal enabledelayedexpansion
set "name=%~1"
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v %name% 2^>nul ^| findstr /i %name%') do set "val=%%B"
if defined val (
    echo [✓] %name% = !val!
) else (
    echo [×] %name% 未设置
)
endlocal
goto :eof