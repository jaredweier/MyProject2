@echo off
REM New Grok session — full bootstrap (agent-kit + graphify + tool policy)
cd /d "%~dp0"
if exist "%~dp0scripts\prepend_python_path.bat" call "%~dp0scripts\prepend_python_path.bat"

if not defined SCHEDULER_SLICE set SCHEDULER_SLICE=day-off-requests
if not defined SCHEDULER_AGENT_TASK set SCHEDULER_AGENT_TASK=Grok session — Dodgeville PD Scheduler

call "%~dp0scripts\agent_session_bootstrap.bat"
if errorlevel 1 pause

REM Prefer grok CLI if available; otherwise print paste instructions only
where grok >nul 2>&1
if errorlevel 1 (
    echo.
    echo  grok CLI not on PATH — paste the @files above into a new Grok chat.
    echo  Or install Grok CLI / open this folder in Grok Build TUI.
    echo.
    pause
    exit /b 0
)

grok --cwd "%CD%" "New session bootstrap complete. Read first: logs/agent_kit/latest.md, graphify-out/KNOWLEDGE_HUB.md, AGENTS.md, docs/AGENT_STABLE.md. Auto-context OFF. For ANY project knowledge use graphify query/path/explain first (not whole-repo reads). Use tools when helpful: graphify, stop-slop, gstack, frontend-design XOR taste-skill, domain .grok/skills. After structural edits: python dev.py graphify-gate. After edits: verify --tier fast; ship with verify --tier check. Awaiting task."
