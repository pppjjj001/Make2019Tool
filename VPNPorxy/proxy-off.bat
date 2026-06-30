@echo off
chcp 65001 >nul
echo [*] 正在清除代理环境变量...

REM 用 reg delete 彻底删除用户级环境变量
reg delete "HKCU\Environment" /F /V HTTP_PROXY  >nul 2>&1
reg delete "HKCU\Environment" /F /V HTTPS_PROXY >nul 2>&1
reg delete "HKCU\Environment" /F /V ALL_PROXY   >nul 2>&1

REM 通知系统刷新环境变量
powershell -Command "[System.Environment]::SetEnvironmentVariable('HTTP_PROXY', $null, 'User'); [System.Environment]::SetEnvironmentVariable('HTTPS_PROXY', $null, 'User'); [System.Environment]::SetEnvironmentVariable('ALL_PROXY', $null, 'User')" >nul

REM 当前会话也清掉
set HTTP_PROXY=
set HTTPS_PROXY=
set ALL_PROXY=

echo.
echo [✓] 代理已关闭，环境变量已删除
echo.
pause