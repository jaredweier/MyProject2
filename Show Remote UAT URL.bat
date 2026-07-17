@echo off
cd /d "%~dp0"
echo.
echo === Chronos Remote UAT URL ===
if exist "logs\remote_uat_url.txt" (
  type "logs\remote_uat_url.txt"
  echo.
  type "logs\remote_uat_live.txt" 2>nul
) else (
  echo No URL yet. Install / start always-on:
  echo   Install Always-On UAT.bat
  echo Or: Start Remote UAT Tunnel.bat
)
echo.
pause
