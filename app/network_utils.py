import sys
import os
import json
import time
import subprocess
import platform
import logging
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject

# Configure logging if not already configured
logger = logging.getLogger(__name__)


class ConnectivityMonitor(QThread):
    """
    Background thread to monitor server connectivity via Ping.
    Target IP: 10.10.10.181
    """

    status_changed = Signal(bool, str)  # is_connected, status_text

    def __init__(self, target_ip="10.10.10.181", interval=5):
        super().__init__()
        self.target_ip = target_ip
        self.interval = interval
        self._is_running = True

    def run(self):
        while self._is_running:
            is_connected = self.ping_server()
            status_text = "Connected" if is_connected else "Not Reachable"
            self.status_changed.emit(is_connected, status_text)

            # Sleep for interval or until stopped
            for _ in range(self.interval):
                if not self._is_running:
                    break
                time.sleep(1)

    def stop(self):
        self._is_running = False
        self.wait()

    def ping_server(self) -> bool:
        """
        Executes a single ping to the target IP.
        Returns True if successful (0% packet loss), False otherwise.
        """
        try:
            # Platform specific ping parameters
            param = "-n" if platform.system().lower() == "windows" else "-c"

            # Timeout param (Windows: -w in ms, Linux: -W in s)
            # We want a relatively quick check so UI doesn't lag if logic was blocking (it's threaded though)
            timeout_param = "-w" if platform.system().lower() == "windows" else "-W"
            timeout_val = "1000" if platform.system().lower() == "windows" else "1"

            command = ["ping", param, "1", timeout_param, timeout_val, self.target_ip]

            # Check for Windows specifically to avoid console popping up
            if platform.system().lower() == "windows":
                creationflags = subprocess.CREATE_NO_WINDOW
                result = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
            else:
                result = subprocess.run(
                    command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )

            return result.returncode == 0
        except Exception as e:
            logger.error(f"Ping failed: {e}")
            return False


class EnvironmentDetector:
    """
    Detects the current environment (PRODUCTION vs TESTING) based on appsettings.json.
    Target File: C:\\Workspaces\\DBS\\RMS\\RMS.CashierServer\\appsettings.json
    Attributes: 'MainServerBaseUrl'
    """

    # Static Configuration
    CONFIG_PATH = r"C:\Workspaces\DBS\RMS\RMS.CashierServer\appsettings.json"

    # Detection Rules
    URL_TESTING = "http://10.10.10.181:8080/RmsMainServerApi/"
    URL_PRODUCTION = "http://10.10.10.181/RmsMainServerApi/"

    @staticmethod
    def detect(config_path: str = None) -> str:
        """
        Returns 'PRODUCTION', 'TESTING', or 'UNKNOWN'
        """
        # Use provided path or fallback to static default
        target_path = config_path if config_path else EnvironmentDetector.CONFIG_PATH
        path = Path(target_path)

        if not path.exists():
            logger.warning(f"Environment Config not found at: {path}")
            return "UNKNOWN"

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Navigate JSON structure: Root -> PosBasicInfoSettings -> MainServerBaseUrl
            # Based on user context provided file structure
            settings = data.get("PosBasicInfoSettings", {})
            base_url = settings.get("MainServerBaseUrl", "").strip()

            if not base_url:
                logger.warning("MainServerBaseUrl missing in appsettings.json")
                return "UNKNOWN"

            # Normalize for comparison (ignore case, maybe trailing slash)
            base_url_norm = base_url.lower().rstrip("/")
            test_norm = EnvironmentDetector.URL_TESTING.lower().rstrip("/")
            prod_norm = EnvironmentDetector.URL_PRODUCTION.lower().rstrip("/")

            if base_url_norm == test_norm:
                return "TESTING"
            elif base_url_norm == prod_norm:
                return "PRODUCTION"
            else:
                logger.warning(f"Unrecognized API URL: {base_url}")
                return "UNKNOWN"

        except Exception as e:
            logger.error(f"Failed to parse appsettings.json: {e}")
            return "UNKNOWN"
