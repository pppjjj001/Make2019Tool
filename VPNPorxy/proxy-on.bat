@echo off
chcp 65001 >nul
echo [*] 正在设置代理环境变量...

setx HTTP_PROXY  "http://127.0.0.1:10888"  >nul
setx HTTPS_PROXY "http://127.0.0.1:10888"  >nul
setx ALL_PROXY   "socks5://127.0.0.1:10888" >nul

REM 同时在当前会话生效（避免重启终端）
set HTTP_PROXY=http://127.0.0.1:10888
set HTTPS_PROXY=http://127.0.0.1:10888
set ALL_PROXY=socks5://127.0.0.1:10888

echo.
echo [✓] 代理已开启（端口 10888）
echo     HTTP_PROXY  = %HTTP_PROXY%
echo     HTTPS_PROXY = %HTTPS_PROXY%
echo     ALL_PROXY   = %ALL_PROXY%
echo.
echo 提示：新开终端窗口自动生效，已开的窗口需重启或重新加载环境。
pause