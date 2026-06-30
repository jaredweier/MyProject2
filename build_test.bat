@echo off
echo === Dodgeville PD Scheduler - Evaluation Build ===
pip install -r requirements.txt pyinstaller -q
python scripts\generate_assets.py
python dev.py check
if errorlevel 1 (
    echo Build aborted: tests or audit failed.
    exit /b 1
)
pyinstaller --noconfirm --onedir --windowed --clean ^
  --add-data "logo.png;." ^
  --add-data "team_photo.jpg;." ^
  --add-data "roster_seed.json;." ^
  --hidden-import customtkinter ^
  --hidden-import PIL ^
  --hidden-import PIL._tkinter_finder ^
  --hidden-import PIL.Image ^
  --hidden-import PIL.ImageTk ^
  --name "Dodgeville_PD_Scheduler" main.py
if errorlevel 1 (
    echo PyInstaller failed.
    exit /b 1
)
copy /Y EVALUATE.txt dist\Dodgeville_PD_Scheduler\EVALUATE.txt
copy /Y "docs\deploy\Start Dodgeville Scheduler (Local).bat" "dist\Dodgeville_PD_Scheduler\Start Dodgeville Scheduler.bat"
echo.
echo Build complete: dist\Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe
echo Read EVALUATE.txt in that folder for testing instructions.
echo Copy Start Dodgeville Scheduler.bat to your file server (see docs\DEPLOYMENT.md).
exit /b 0
