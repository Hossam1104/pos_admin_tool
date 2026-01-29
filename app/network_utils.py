import json
import time
import logging
from pathlib import Path
from PySide6.QtCore import QThread, Signal

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
        self.target_port = 80
        self.interval = interval
        self._is_running = True

    def set_target_from_url(self, url: str):
        """Extract IP or Hostname and Port from URL and update target"""
        if not url:
            return

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port

            if hostname:
                if hostname != self.target_ip:
                    logger.info(f"ConnectivityMonitor: Updating target to {hostname}")
                    self.target_ip = hostname

                # Update port (default to 80 if common, or 8080 if detected)
                new_port = port if port else (8080 if ":8080" in url else 80)
                if new_port != self.target_port:
                    logger.info(f"ConnectivityMonitor: Updating port to {new_port}")
                    self.target_port = new_port
        except Exception as e:
            logger.error(f"Failed to extract hostname from URL {url}: {e}")

    def run(self):
        while self._is_running:
            is_connected = self.check_connection()
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

    def check_connection(self) -> bool:
        """
        Tests connectivity using a TCP socket connection.
        This is more reliable than Ping if ICMP is blocked.
        """
        import socket

        try:
            # Create a socket and try to connect
            with socket.create_connection(
                (self.target_ip, self.target_port), timeout=2
            ):
                return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
        except Exception as e:
            logger.error(f"Socket connection check failed: {e}")
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
