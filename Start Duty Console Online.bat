@echo off
REM Host for officers to open from any device on the network
cd /d "%~dp0"
set SCHEDULER_UI_MODE=web
echo.
echo Starting online Duty Console...
echo Officers open: http://THIS-PC-IP:8080  (see console for bind address)
echo Press Ctrl+C to stop.
echo.
python main.py --web --host 0.0.0.0 --port 8080 %*
if errorlevel 1 pause
