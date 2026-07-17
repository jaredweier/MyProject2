@echo off
cd /d "%~dp0"
echo.
echo === Chronos — put UAT on YOUR domain (Cloudflare DNS) ===
echo.
echo Prerequisites:
echo   1) Domain DNS is on Cloudflare
echo   2) cloudflared installed (winget install Cloudflare.cloudflared)
echo   3) Browser login to Cloudflare when asked
echo.
echo Result: stable URL like https://chronos.yourdomain.com
echo         (no more random trycloudflare.com reloads)
echo.

set /p DOMAIN=Enter your domain (example: mypd.com):
if "%DOMAIN%"=="" (
  echo Domain required.
  pause
  exit /b 1
)

set /p SUB=Subdomain [default chronos] (use @ for apex):
if "%SUB%"=="" set SUB=chronos

echo.
echo Will create: https://%SUB%.%DOMAIN%  (or apex if SUB=@)
echo.
pause

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\setup_domain_tunnel.ps1" -Domain "%DOMAIN%" -Subdomain "%SUB%"
echo.
echo If DNS is slow, wait 1-2 minutes, then open the URL printed above.
echo.
pause
