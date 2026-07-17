@echo off
cd /d "C:\Users\Windows\MyProject"
set PATH=%PATH%;C:\Program Files (x86)\cloudflared
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\Windows\MyProject\scripts\always_on_uat.ps1" -Port 8080
