#!/usr/bin/env python3
"""
POS Admin Tool - Main Application Entry Point
"""
import sys
import os
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.logic.admin import AdminManager
from app.ui.main_window import MainWindow
from app.utils.logger import setup_logger


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

    # Load stylesheet
    style_path = Path(__file__).parent.parent / "assets" / "styles" / "theme.qss"
    if style_path.exists():
        with open(style_path, "r") as f:
            app.setStyleSheet(f.read())

    # Create and show main window
    window = MainWindow()
    window.show()

    # Start service monitoring
    QTimer.singleShot(1000, window.start_service_monitoring)

    # Run application
    return_code = app.exec()

    logger.info("Application shutdown")
    return return_code


if __name__ == "__main__":
    sys.exit(main())
