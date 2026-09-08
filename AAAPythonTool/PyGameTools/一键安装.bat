@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title PyGameTools Setup
color 0A
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================
echo   PyGameTools one-click setup
echo   Existing files will be skipped
echo ============================================
echo.

set "PYEXE="
set "ERR=0"
set "SILENT="
if /I "%~1"=="/s" set "SILENT=1"
if /I "%~1"=="/silent" set "SILENT=1"
set "PY_VER_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-amd64.exe"
set "PY_SETUP=%TEMP%\PyGameTools-python-3.12.9-amd64.exe"

call :find_python
if not defined PYEXE (
    echo [1/3] Python not found, installing Python 3.12.9 ...
    call :install_python
    call :find_python
)
if not defined PYEXE (
    echo.
    echo [FAIL] Python not found.
    echo Install from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH"
    set "ERR=1"
    goto :done
)

echo [1/3] Python: %PYEXE%
"%PYEXE%" -c "import sys; print('       version', sys.version.split()[0])"
"%PYEXE%" -c "import tkinter" 2>nul
if errorlevel 1 (
    echo [FAIL] tkinter missing. Install official Windows Python, not embeddable.
    set "ERR=1"
    goto :done
)

echo.
echo [2/3] apktool / signer / portable JRE ...
"%PYEXE%" PyGameTools.py --setup
if errorlevel 1 (
    echo [FAIL] tool setup failed, check network and retry.
    set "ERR=1"
    goto :done
)

echo.
echo [3/3] done
echo Copy the whole PyGameTools folder to another PC,
echo then run this bat again. Installed parts will be skipped.
echo After that, run 启动.bat

:done
echo.
echo ============================================
if "%ERR%"=="0" (
    echo   Setup OK
    echo ============================================
    if not defined SILENT (
        echo.
        choice /C YN /N /M "Start PyGameTools now? [Y/N] "
        if errorlevel 2 goto :end
        if errorlevel 1 start "" "%~dp0启动.bat"
    )
) else (
    echo   Setup FAILED
    echo ============================================
)
:end
if not defined SILENT (
    echo.
    pause
)
exit /b %ERR%

:find_python
set "PYEXE="
where python >nul 2>nul
if not errorlevel 1 (
    for /f "delims=" %%I in ('where python 2^>nul') do (
        if not defined PYEXE (
            "%%I" -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
            if not errorlevel 1 set "PYEXE=%%I"
        )
    )
)
if defined PYEXE goto :eof

where py >nul 2>nul
if not errorlevel 1 (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info>=(3,10) else 1)" 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%I in ('py -3 -c "import sys; print(sys.executable)"') do set "PYEXE=%%I"
        goto :eof
    )
)

if exist "%LocalAppData%\Programs\Python\Python312\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PYEXE goto :eof
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if defined PYEXE goto :eof
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" set "PYEXE=%LocalAppData%\Programs\Python\Python310\python.exe"
goto :eof

:install_python
echo        downloading Python installer ...
curl.exe -L --retry 3 --retry-delay 2 -o "%PY_SETUP%" "%PY_VER_URL%"
if not exist "%PY_SETUP%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri '%PY_VER_URL%' -OutFile '%PY_SETUP%'"
)
if not exist "%PY_SETUP%" (
    echo        download Python failed
    goto :eof
)
echo        silent install for current user ...
"%PY_SETUP%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_tcltk=1 Include_test=0 Include_doc=0 SimpleInstall=1
set "PATH=%LocalAppData%\Programs\Python\Python312;%LocalAppData%\Programs\Python\Python312\Scripts;%PATH%"
del /q "%PY_SETUP%" >nul 2>nul
goto :eof