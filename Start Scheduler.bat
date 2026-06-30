@echo off
REM Dodgeville PD Scheduler — local launcher (development / evaluation)
cd /d "%~dp0"

if exist "dist\Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe" (
    where python >nul 2>&1
    if not errorlevel 1 (
        python scripts\startup_gates.py -q
        if errorlevel 1 if "%SCHEDULER_BLOCK_ON_GATE_FAIL%"=="1" (
            echo Startup health check failed. Run: python dev.py fix-hint
            pause
            exit /b 1
        )
    )
    cd "dist\Dodgeville_PD_Scheduler"
    set SCHEDULER_AUTO_LOGIN=0
    set SKIP_DEMO_USERS=0
    start "" "Dodgeville_PD_Scheduler.exe"
    exit /b 0
)

set SCHEDULER_AUTO_LOGIN=0
set SKIP_DEMO_USERS=0

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found on PATH.
    echo Install Python 3.11+ or run dist\Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe
    pause
    exit /b 1
)

REM main.py runs automatic startup gates (cheap-check) before the GUI opens
python main.py
if errorlevel 1 (
    echo.
    echo The scheduler exited with an error. See logs\dodgeville_scheduler.log
    pause
)
