"""
Build script for PyInstaller with all dependencies
"""

from pathlib import Path
import PyInstaller.__main__


def build_exe():
    """Build the executable using PyInstaller"""
    app_name = "POSAdminTool"

    # Get the main script path
    main_script = Path(__file__).parent / "app" / "main.py"

    # Additional data files
    assets_dir = Path(__file__).parent / "assets"
    config_dir = Path(__file__).parent / "config"

    # PyInstaller arguments
    args = [
        str(main_script),
        f"--name={app_name}",
        "--onefile",
        "--windowed",  # Hide console window
        "--clean",
        "--noconfirm",
        f"--add-data={assets_dir};assets",
        f"--add-data={config_dir};config",
        "--icon=assets/icons/app_icon.ico",
        "--hidden-import=PySide6",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=win32crypt",
        "--hidden-import=win32cryptcon",
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
        "--hidden-import=base64",
        "--hidden-import=dataclasses",
        "--hidden-import=typing",
        "--hidden-import=enum",
    ]

    # Run PyInstaller
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    build_exe()
