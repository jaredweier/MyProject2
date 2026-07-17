@echo off
REM Chronos Command — virtual UAT lab (isolated DB, LAN-ready)
cd /d "%~dp0"

echo.
echo === Chronos Command virtual lab ===
echo Running readiness pack (doctor + readiness + UAT scenarios + residual)...
echo.

set SCHEDULER_SKIP_GATES=1
python dev.py virtual-lab
if errorlevel 1 (
  echo.
  echo virtual-lab gates FAILED — fix before inviting testers.
  echo See logs\virtual_lab_status.json
  pause
  exit /b 1
)

if not exist lab_data mkdir lab_data
set SCHEDULER_DB_PATH=%~dp0lab_data\virtual_uat.db
set SCHEDULER_UI_MODE=web
if "%SCHEDULER_PORT%"=="" set SCHEDULER_PORT=8080
set SCHEDULER_HOST=0.0.0.0

echo.
echo Starting isolated lab DB:
echo   %SCHEDULER_DB_PATH%
echo URL: http://127.0.0.1:%SCHEDULER_PORT%  (LAN: http://^<this-pc-ip^>:%SCHEDULER_PORT%^)
echo Logins: admin/admin  supervisor/supervisor  officer/officer
echo Doc: docs\VIRTUAL_UAT.md
echo ONE server only on this port.
echo.

python main.py --browser --host 0.0.0.0 --port %SCHEDULER_PORT%
pause
