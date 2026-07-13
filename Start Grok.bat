@echo off
REM New Grok session — auto bootstrap + launch in MyProject with system rules
cd /d "%~dp0"
if exist "%~dp0scripts\prepend_python_path.bat" call "%~dp0scripts\prepend_python_path.bat"

if not defined SCHEDULER_SLICE set SCHEDULER_SLICE=general
if not defined SCHEDULER_AGENT_TASK set SCHEDULER_AGENT_TASK=Grok session — Chronos token-min
set SCHEDULER_FORCE_BOOTSTRAP=1

call "%~dp0scripts\agent_session_bootstrap.bat"

set "GROK_EXE=%USERPROFILE%\.grok\bin\grok.exe"
if not exist "%GROK_EXE%" (
    where grok >nul 2>&1
    if errorlevel 1 (
        echo.
        echo  grok CLI not found. Open this folder in Grok Build TUI.
        echo  Rules auto-load from AGENTS.md when cwd is MyProject.
        echo  First time: run /hooks-trust in Grok for project SessionStart hooks.
        echo.
        pause
        exit /b 0
    )
    set "GROK_EXE=grok"
)

REM --rules injects contract into system prompt; AGENTS.md also auto-loads from cwd
"%GROK_EXE%" --cwd "%CD%" --rules "%CD%\logs\SESSION_CONTRACT.md" %*
