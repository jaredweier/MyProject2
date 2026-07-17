@echo off
REM Chronos Command — remote UAT: local lab server + public tunnel
REM Tester (any location) opens the https:// URL this prints.
cd /d "%~dp0"

echo.
echo === Chronos Command Remote UAT Tunnel ===
echo Starts lab DB + Chronos, then cloudflared (or ngrok) public HTTPS link.
echo Docs: docs\VIRTUAL_UAT.md  ·  Cloud VM: docs\deploy\CLOUD_VM.md
echo.

where cloudflared >nul 2>&1
if errorlevel 1 (
  where ngrok >nul 2>&1
  if errorlevel 1 (
    echo cloudflared / ngrok not found yet — script will show install commands.
    echo Optional now:
    echo   winget install Cloudflare.cloudflared
    echo   winget install Ngrok.Ngrok
    echo.
  )
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\remote_uat_tunnel.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" pause
exit /b %ERR%
