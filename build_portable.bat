@echo off
title Build Dodgeville PD Portable Package
cd /d "%~dp0"

echo.
echo  Building portable package (no Python needed on test PCs)...
echo  Full build runs tests first (~2 min). Use --quick to skip tests.
echo.

python scripts\build_portable.py %*
if errorlevel 1 (
    echo.
    echo  Build FAILED. See messages above.
    pause
    exit /b 1
)

echo.
echo  SUCCESS — open dist\Dodgeville_PD_Portable and double-click START HERE.bat
echo  Or share dist\Dodgeville_PD_Portable_YYYYMMDD.zip
echo.
pause
exit /b 0
