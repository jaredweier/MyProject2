@echo off
REM Cloudflare Tunnel Setup Script for Windows
REM Run this to quickly set up and start the tunnel

setlocal enabledelayedexpansion

echo.
echo 🚀 Dodgeville Scheduler - Cloudflare Tunnel Setup (Windows)
echo ===========================================================
echo.

REM Check if cloudflared is installed
where cloudflared >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ❌ cloudflared not found. Installing...
    echo.
    echo To install Cloudflare Tunnel on Windows:
    echo 1. Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
    echo 2. Run the installer
    echo 3. Open a new PowerShell/Command Prompt
    echo 4. Run this script again
    echo.
    pause
    exit /b 1
)

echo ✅ cloudflared is installed
echo.

REM Check if tunnel exists
cloudflared tunnel list | findstr "dodgeville-scheduler" >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo ✅ Tunnel 'dodgeville-scheduler' already exists
) else (
    echo 🔐 Creating tunnel 'dodgeville-scheduler'...
    cloudflared tunnel create dodgeville-scheduler
    echo.
)

echo.
echo 📋 Next steps:
echo.
echo 1. Edit config file:
echo    - Open: %%APPDATA%%\.cloudflared\config.yml
echo    - Use template: .cloudflared\config.yml.example in this repo
echo.
echo 2. Replace 'yourdomain.com' with your actual Cloudflare domain
echo.
echo 3. Verify the port matches your scheduler (check main.py)
echo.
echo 4. Run the tunnel:
echo    cloudflared tunnel run dodgeville-scheduler
echo.
echo 🌐 Then update your Cloudflare DNS:
echo    - Go to DNS ^> Records in Cloudflare dashboard
echo    - Add CNAME: @ ^→ ^<TUNNEL_ID^>.cfargotunnel.com (Proxied)
echo.
pause
