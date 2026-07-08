@echo off
cd /d "%~dp0"

set "TARGET=%~dp0START HERE.bat"
set "WORKDIR=%~dp0"
set "LINK=%USERPROFILE%\Desktop\Dodgeville PD Scheduler.lnk"
set "ICON=%WORKDIR%dist\Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $s = $ws.CreateShortcut('%LINK%'); ^
   $s.TargetPath = '%TARGET%'; ^
   $s.WorkingDirectory = '%WORKDIR%'; ^
   $s.Description = 'Dodgeville PD Tactical Duty Scheduler'; ^
   if (Test-Path '%ICON%') { $s.IconLocation = '%ICON%,0' }; ^
   $s.Save()"

if errorlevel 1 (
    echo Could not create desktop shortcut.
    pause
    exit /b 1
)

echo Desktop shortcut created:
echo   %LINK%
echo.
echo Double-click "Dodgeville PD Scheduler" on your Desktop to start.
pause
