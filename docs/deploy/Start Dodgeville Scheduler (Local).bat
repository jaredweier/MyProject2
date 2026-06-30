@echo off
REM Local launcher — run from the same folder as Dodgeville_PD_Scheduler.exe
cd /d "%~dp0"

if not exist "Dodgeville_PD_Scheduler.exe" (
    echo Dodgeville_PD_Scheduler.exe not found in:
    echo   %~dp0
    pause
    exit /b 1
)

set SCHEDULER_AUTO_LOGIN=0
set SKIP_DEMO_USERS=0

start "" "%~dp0Dodgeville_PD_Scheduler.exe"
exit /b 0
