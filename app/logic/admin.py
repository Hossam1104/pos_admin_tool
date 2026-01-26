"""
Handles administrator privilege requests
"""

import ctypes
import sys
import os
from pathlib import Path
from app.utils.logger import get_logger

logger = get_logger()


class AdminManager:
    """Manages administrator privilege requests"""

    def is_admin(self) -> bool:
        """Check if running with administrator privileges"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin()
        except Exception:
            return False

    def request_admin(self) -> bool:
        """Request administrator privileges by restarting with UAC prompt"""
        try:
            # Get the current executable path
            if getattr(sys, "frozen", False):
                # Running as PyInstaller executable
                exe_path = sys.executable
            else:
                # Running as Python script
                exe_path = sys.executable
                script_path = Path(__file__).parent.parent / "main.py"
                if script_path.exists():
                    exe_path = f'"{exe_path}" "{script_path}"'

            # Parameters for ShellExecute
            params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])

            # Request admin privileges
            ctypes.windll.shell32.ShellExecuteW(
                None,  # hwnd
                "runas",  # operation
                exe_path,  # file
                params,  # parameters
                None,  # directory
                1,  # show command (SW_SHOWNORMAL)
            )

            return True

        except Exception as e:
            logger.error(f"Failed to request admin privileges: {e}")
            return False
