@echo off
title Dodgeville PD Scheduler
cd /d "%~dp0"
call "%~dp0scripts\prepend_python_path.bat"

set SCHEDULER_AUTO_LOGIN=0
set SKIP_DEMO_USERS=0

REM Live source = latest UI. Set USE_FROZEN=1 to force the packaged .exe instead.
if exist "main.py" if /i not "%USE_FROZEN%"=="1" (
    python main.py
    if not errorlevel 1 exit /b 0
    echo.
    echo  Python launch failed — trying frozen build...
    echo.
)

set "EXE_DIR=dist\Dodgeville_PD_Scheduler"
set "EXE=%EXE_DIR%\Dodgeville_PD_Scheduler.exe"

if not exist "%EXE%" (
    echo.
    echo  First run - building Dodgeville PD Scheduler...
    echo  One-time step; may take a few minutes.
    echo.
    call build_quick.bat
    if errorlevel 1 (
        echo.
        echo  Build failed. Fix errors above, then double-click START HERE.bat again.
        pause
        exit /b 1
    )
)

if not exist "%EXE%" (
    echo.
    echo  Could not find: %CD%\%EXE%
    echo  Run build_quick.bat manually or check PyInstaller output.
    pause
    exit /b 1
)

cd "%EXE_DIR%"
start "" "Dodgeville_PD_Scheduler.exe"
exit /b 0
