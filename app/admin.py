"""
Handles administrator privilege requests
"""

import ctypes
import sys

from pathlib import Path
from app.logger import get_logger

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
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            else:
                # Running as Python script from source
                exe_path = sys.executable
                project_root = Path(__file__).parent.parent

                # Use -m app.main to preserve package structure
                args = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
                params = f"-m app.main {args}"

            # Request admin privileges
            ctypes.windll.shell32.ShellExecuteW(
                None,  # hwnd
                "runas",  # operation
                exe_path,  # file
                params,  # parameters
                (
                    str(project_root) if not getattr(sys, "frozen", False) else None
                ),  # directory
                1,  # show command (SW_SHOWNORMAL)
            )

            return True

        except Exception as e:
            logger.error(f"Failed to request admin privileges: {e}")
            return False
