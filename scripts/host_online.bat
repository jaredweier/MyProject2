@echo off
REM Chronos Command — online host (Weierworks Technologies, LLC)
cd /d "%~dp0.."
if "%SCHEDULER_STORAGE_SECRET%"=="" (
  echo WARNING: SCHEDULER_STORAGE_SECRET not set — generating local secret file on first run.
)
set SCHEDULER_UI_MODE=web
set SCHEDULER_HOST=0.0.0.0
if "%SCHEDULER_PORT%"=="" set SCHEDULER_PORT=8080
echo Starting Chronos Command online on 0.0.0.0:%SCHEDULER_PORT%
python main.py --web --host 0.0.0.0 --port %SCHEDULER_PORT%
