# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('logo.png', '.'), ('team_photo.jpg', '.'), ('roster_seed.json', '.')],
    hiddenimports=['customtkinter', 'PIL', 'PIL._tkinter_finder', 'PIL.Image', 'PIL.ImageTk', 'reportlab', 'reportlab.pdfgen.canvas', 'logic', 'logic.officers', 'logic.scheduling', 'logic.requests', 'logic.payroll', 'logic.users', 'logic.snapshots', 'logic.operations', 'logic.exports', 'logic.dashboard', 'logic._core', 'analytics', 'exports', 'simulator'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Dodgeville_PD_Scheduler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
