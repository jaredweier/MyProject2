@echo off
pip install pyinstaller customtkinter pillow reportlab --quiet
pyinstaller --onedir --windowed --clean --hidden-import customtkinter --hidden-import PIL --hidden-import PIL._tkinter_finder --name "Dodgeville_PD_Scheduler" main.py
pause
