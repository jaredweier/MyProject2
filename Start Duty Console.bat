@echo off
REM Dodgeville PD Duty Console — downloadable desktop window
cd /d "%~dp0"
set SCHEDULER_UI_MODE=native
python main.py --native %*
if errorlevel 1 pause
