"""
Build script for PyInstaller
"""

import sys
from pathlib import Path
import PyInstaller.__main__


def build_exe():
    """Build the executable using PyInstaller"""
    app_name = "POSAdminTool"

    # Get the main script path
    main_script = Path(__file__).parent / "app" / "main.py"

    # PyInstaller arguments
    args = [
        str(main_script),
        f"--name={app_name}",
        "--onefile",
        "--windowed",  # Hide console window
        "--clean",
        "--noconfirm",
        "--add-data=assets;assets",
        "--add-data=config;config",
        "--icon=assets/icons/app_icon.ico",
        "--hidden-import=PySide6",
        "--hidden-import=zipfile",
        "--hidden-import=shutil",
        "--hidden-import=json",
        "--hidden-import=os",
        "--hidden-import=sys",
        "--hidden-import=pathlib",
        "--hidden-import=ctypes",
        "--hidden-import=subprocess",
        "--hidden-import=threading",
        "--hidden-import=time",
        "--hidden-import=logging",
        "--hidden-import=datetime",
    ]

    # Run PyInstaller
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build_exe()
