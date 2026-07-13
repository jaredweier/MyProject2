@echo off
REM Shared free bootstrap for every new AI agent session.
REM Call from Start Grok.bat or run alone: scripts\agent_session_bootstrap.bat
cd /d "%~dp0.."
if exist "%~dp0prepend_python_path.bat" call "%~dp0prepend_python_path.bat"

if not defined SCHEDULER_SLICE set SCHEDULER_SLICE=day-off-requests
if not defined SCHEDULER_AGENT_TASK set SCHEDULER_AGENT_TASK=Agent session — Dodgeville PD Scheduler

echo.
echo ============================================================
echo  Dodgeville PD — agent session bootstrap
echo  Slice: %SCHEDULER_SLICE%
echo ============================================================
echo.

REM Full session-start: doctor + agent-kit + graphify-gate (soft) + tool checklist
python dev.py session-start
if errorlevel 1 (
    echo.
    echo  session-start reported issues — fix doctor/env before large changes.
    echo.
)

REM Ensure context-window task label is set for this session
python dev.py context-window task "%SCHEDULER_AGENT_TASK%" >nul 2>&1

echo.
echo ------------------------------------------------------------
echo  Paste / attach into the agent ^(token-minimized^):
echo    @logs/agent_kit/latest.md
echo    @graphify-out/KNOWLEDGE_HUB.md
echo    @AGENTS.md
echo    @docs/AGENT_STABLE.md
echo.
echo  Then: graphify query "..." for ANY project knowledge first.
echo  Tools: graphify · stop-slop · gstack · frontend-design XOR taste · domain skills
echo  Ship:  python dev.py verify --tier check
echo ------------------------------------------------------------
echo.
exit /b 0
