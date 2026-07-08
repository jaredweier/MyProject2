@echo off
title Dodgeville PD Scheduler
cd /d "%~dp0"

REM Demo logins work out of the box; login screen appears on first launch.
set SCHEDULER_AUTO_LOGIN=0
set SKIP_DEMO_USERS=0

if exist "Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe" (
    cd /d "%~dp0\Dodgeville_PD_Scheduler"
    start "" "Dodgeville_PD_Scheduler.exe"
    exit /b 0
)

if exist "Dodgeville_PD_Scheduler.exe" (
    start "" "%~dp0\Dodgeville_PD_Scheduler.exe"
    exit /b 0
)

echo.
echo  Could not find Dodgeville_PD_Scheduler.exe
echo.
echo  Copy the ENTIRE folder to this PC — do not move only the .bat file.
echo  Then double-click START HERE.bat again.
echo.
pause
exit /b 1
