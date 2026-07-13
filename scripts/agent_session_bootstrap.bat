@echo off
REM Shared free bootstrap for every new AI agent session.
cd /d "%~dp0.."
if exist "%~dp0prepend_python_path.bat" call "%~dp0prepend_python_path.bat"

if not defined SCHEDULER_SLICE set SCHEDULER_SLICE=general
if not defined SCHEDULER_AGENT_TASK set SCHEDULER_AGENT_TASK=Agent session — Chronos token-min
set SCHEDULER_FORCE_BOOTSTRAP=1

echo.
echo ============================================================
echo  Dodgeville PD — auto session bootstrap
echo  Slice: %SCHEDULER_SLICE%
echo ============================================================
echo.

python scripts\session_auto_bootstrap.py
if errorlevel 1 (
    echo  bootstrap reported issues — continuing.
)

echo.
echo  Auto rules: AGENTS.md + logs\SESSION_CONTRACT.md
echo  Kit: logs\agent_kit\latest.md
echo  No paste required when opening Grok in this folder.
echo  Ship: python dev.py verify --tier check
echo.
exit /b 0
