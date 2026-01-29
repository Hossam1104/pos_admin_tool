#!/usr/bin/env python3
"""
POS Admin Tool - Main Application Entry Point
"""

import sys
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os

# Disable Qt translations to prevent PyInstaller extraction errors
os.environ["QT_TRANSLATIONS_PATH"] = ""

# Set AppUserModelID for Windows Taskbar icon consistency
if os.name == "nt":
    import ctypes

    myappid = "dbs.rmsplus.pos_admin.v1.0"  # arbitrary string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

from PySide6.QtWidgets import QApplication
from app.admin import AdminManager
from app.ui import MainWindow
from app.logger import setup_logger


def main():
    """Application entry point"""
    # Setup logging
    logger = setup_logger()
    logger.info("Starting POS Admin Tool")

    # Check and request admin privileges
    admin_manager = AdminManager()
    if not admin_manager.is_admin():
        logger.info("Requesting administrator privileges...")
        if admin_manager.request_admin():
            logger.info("Restarting with admin privileges")
            sys.exit(0)
        else:
            logger.error("Admin privileges required but not granted")
            return 1

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("POS Admin Tool")
    app.setOrganizationName("RMS")

    from PySide6.QtGui import QIcon
    from app.utils import resource_path

    icon_path = resource_path(os.path.join("assets", "icons", "app_icon.ico"))
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    # Load stylesheet
    style_path = resource_path(os.path.join("assets", "styles", "theme.qss"))
    if os.path.exists(style_path):
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run application
    return_code = app.exec()

    logger.info("Application shutdown")
    return return_code


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # Emergency logging if normal logging fails or isn't set up
        error_msg = f"Critical application error: {e}"
        print(error_msg, file=sys.stderr)

        # Try to log to file
        try:
            from app.logger import setup_logger
            import traceback

            logger = setup_logger()
            logger.critical("Uncaught exception:")
            logger.critical(traceback.format_exc())
        except Exception:
            pass

        sys.exit(1)
