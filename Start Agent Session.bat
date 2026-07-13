@echo off
REM Universal agent session bootstrap (Grok / Cursor / Claude paste kit)
title Dodgeville PD — Agent Session Bootstrap
cd /d "%~dp0"
call "%~dp0scripts\agent_session_bootstrap.bat"
echo.
echo  Open your agent (Grok / Cursor / Claude) in this folder, then paste the @files listed above.
echo.
pause
