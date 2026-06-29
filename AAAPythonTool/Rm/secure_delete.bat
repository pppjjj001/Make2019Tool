@echo off
chcp 65001 >nul
setlocal

REM ===== secure_delete.bat =====
REM Usage:
REM   1. Drag a folder onto this .bat
REM   2. Or run:  secure_delete.bat "C:\path\to\folder"

set "SCRIPT_DIR=%~dp0"
set "SH_SCRIPT=%SCRIPT_DIR%secure_delete.sh"

REM --- Locate Git Bash ---
set "BASH="

REM 1) Allow user override via env var:  set BASH=D:\tools\Git\bin\bash.exe
if defined BASH_EXE if exist "%BASH_EXE%" set "BASH=%BASH_EXE%"

REM 2) Search PATH (works if Git\bin or Git\cmd is on PATH)
if not defined BASH for %%I in (bash.exe) do if exist "%%~$PATH:I" set "BASH=%%~$PATH:I"

REM 3) Derive from GIT_INSTALL_ROOT / GIT_HOME if set
if not defined BASH if defined GIT_INSTALL_ROOT if exist "%GIT_INSTALL_ROOT%\bin\bash.exe" set "BASH=%GIT_INSTALL_ROOT%\bin\bash.exe"
if not defined BASH if defined GIT_HOME         if exist "%GIT_HOME%\bin\bash.exe"         set "BASH=%GIT_HOME%\bin\bash.exe"

REM 4) Derive from `where git` (Git\cmd\git.exe -> ..\bin\bash.exe)
if not defined BASH (
    for /f "delims=" %%G in ('where git 2^>nul') do (
        if not defined BASH (
            for %%P in ("%%~dpG..\bin\bash.exe") do if exist "%%~fP" set "BASH=%%~fP"
        )
    )
)

REM 5) Fallback to well-known install locations
if not defined BASH if exist "C:\Program Files\Git\bin\bash.exe"          set "BASH=C:\Program Files\Git\bin\bash.exe"
if not defined BASH if exist "C:\Program Files (x86)\Git\bin\bash.exe"    set "BASH=C:\Program Files (x86)\Git\bin\bash.exe"
if not defined BASH if exist "%LOCALAPPDATA%\Programs\Git\bin\bash.exe"   set "BASH=%LOCALAPPDATA%\Programs\Git\bin\bash.exe"
if not defined BASH if exist "%ProgramW6432%\Git\bin\bash.exe"            set "BASH=%ProgramW6432%\Git\bin\bash.exe"

if not defined BASH (
    echo [ERROR] Git Bash not found. Install Git for Windows first: https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist "%SH_SCRIPT%" (
    echo [ERROR] secure_delete.sh not found next to this .bat
    echo         Expected at: %SH_SCRIPT%
    pause
    exit /b 1
)

if "%~1"=="" (
    echo Usage:
    echo   Drag a folder onto this .bat file
    echo   OR run:  %~nx0 "C:\path\to\folder"
    pause
    exit /b 1
)

set "TARGET=%~1"

if not exist "%TARGET%" (
    echo [ERROR] Target does not exist: %TARGET%
    pause
    exit /b 1
)

echo ============================================================
echo  Secure Folder Deletion  (anti-recovery)
echo ============================================================
echo  Target : %TARGET%
echo.
echo  This will:
echo    1) overwrite every file with random data (3 passes)
echo    2) rename files and folders to random names
echo    3) delete the whole tree
echo.
echo  WARNING: on SSDs / USB sticks / SD cards, wear-leveling
echo           means user-space overwrite is NOT 100%% reliable.
echo           Full-disk encryption + TRIM is the only safe way
echo           to make SSD data unrecoverable.
echo ============================================================
echo.

set /p "CONFIRM=Type DELETE to confirm: "
if /i not "%CONFIRM%"=="DELETE" (
    echo Cancelled.
    pause
    exit /b 0
)

echo.
"%BASH%" --noprofile --norc "%SH_SCRIPT%" "%TARGET%"
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" (
    echo [DONE] Securely deleted.
) else (
    echo [FAILED] exit code %RC%
)
pause
endlocal
