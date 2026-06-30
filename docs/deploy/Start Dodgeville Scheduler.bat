@echo off
REM Dodgeville PD Scheduler — department launcher
REM Copy this file next to Dodgeville_PD_Scheduler.exe on the file server.
REM Edit UNCPATH below to match your environment.

set "UNCPATH=\\PD-SERVER\PDApps\DodgevilleScheduler"

cd /d "%UNCPATH%"
if errorlevel 1 (
    echo Could not reach scheduler folder:
    echo   %UNCPATH%
    echo Check network connection and permissions.
    pause
    exit /b 1
)

REM Production: no demo users, login required
set SKIP_DEMO_USERS=1
set SCHEDULER_AUTO_LOGIN=0

REM Optional: store database on a different path (uncomment and edit)
REM set SCHEDULER_DB_PATH=\\PD-SERVER\PDData\dodgeville_scheduler.db

start "" "%UNCPATH%\Dodgeville_PD_Scheduler.exe"
exit /b 0
