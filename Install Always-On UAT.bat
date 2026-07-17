@echo off
cd /d "%~dp0"
echo.
echo === Install Chronos Always-On Remote UAT ===
echo Starts at Windows logon + starts now.
echo Code changes auto-restart Chronos; tunnel stays up when possible.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_always_on_uat.ps1" %*
echo.
pause
