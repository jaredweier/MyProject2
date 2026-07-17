@echo off
call "%~dp0scripts\prepend_python_path.bat"
echo === Dodgeville PD Scheduler - Quick Build (skip tests) ===
pip install -r requirements.txt pyinstaller -q
python scripts\generate_assets.py
pyinstaller --noconfirm --onedir --windowed --clean ^
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
echo Build complete: dist\Dodgeville_PD_Scheduler\Dodgeville_PD_Scheduler.exe
exit /b 0
