# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\DBSMENA\\OneDrive - AlDawaa Medical Service Company\\Work\\Batch Files\\pos_admin_tool\\app\\main.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\DBSMENA\\OneDrive - AlDawaa Medical Service Company\\Work\\Batch Files\\pos_admin_tool\\assets', 'assets')],
    hiddenimports=['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets', 'win32crypt', 'win32cryptcon', 'win32timezone', 'win32api', 'win32service', 'win32serviceutil', 'win32event', 'zipfile', 'shutil', 'json', 'os', 'sys', 'pathlib', 'ctypes', 'subprocess', 'threading', 'time', 'logging', 'datetime', 'base64', 'dataclasses', 'typing', 'enum'],
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
    name='RMSPlus_POSAdmin_v1.0',
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
    icon=['C:\\Users\\DBSMENA\\OneDrive - AlDawaa Medical Service Company\\Work\\Batch Files\\pos_admin_tool\\assets\\icons\\app_icon.ico'],
)
