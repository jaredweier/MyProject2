@echo off
cd /d "%~dp0"
echo.
echo === Uninstall Chronos Always-On Remote UAT ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install_always_on_uat.ps1" -Uninstall %*
echo.
pause
