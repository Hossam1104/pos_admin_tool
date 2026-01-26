"""
Monitors Windows services status
"""

import subprocess
import threading
import time
from typing import List, Dict, Optional
from PySide6.QtCore import QObject, Signal
from app.utils.logger import get_logger

logger = get_logger()


class ServiceStatus:
    """Service status constants"""

    RUNNING = "Running"
    STOPPED = "Stopped"
    NOT_FOUND = "Not Found"
    START_PENDING = "Start Pending"
    STOP_PENDING = "Stop Pending"
    UNKNOWN = "Unknown"


class ServiceMonitor(QObject):
    """Monitors Windows services"""

    service_status_changed = Signal(dict)  # Emits service name -> status mapping

    def __init__(self, service_names: List[str]):
        super().__init__()
        self.service_names = service_names
        self.running = False
        self.monitor_thread = None
        self.update_interval = 5  # seconds

    def get_service_status(self, service_name: str) -> str:
        """Get current status of a Windows service"""
        try:
            result = subprocess.run(
                ["sc", "query", service_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if result.returncode != 0:
                return ServiceStatus.NOT_FOUND

            # Parse the output to find STATE line
            for line in result.stdout.split("\n"):
                if "STATE" in line.upper():
                    if "RUNNING" in line.upper():
                        return ServiceStatus.RUNNING
                    elif "STOPPED" in line.upper():
                        return ServiceStatus.STOPPED
                    elif "START_PENDING" in line.upper():
                        return ServiceStatus.START_PENDING
                    elif "STOP_PENDING" in line.upper():
                        return ServiceStatus.STOP_PENDING

            return ServiceStatus.UNKNOWN

        except Exception as e:
            logger.error(f"Error checking service {service_name}: {e}")
            return ServiceStatus.UNKNOWN

    def get_all_service_statuses(self) -> Dict[str, str]:
        """Get status for all monitored services"""
        statuses = {}
        for service in self.service_names:
            statuses[service] = self.get_service_status(service)
        return statuses

    def monitor_services(self):
        """Continuously monitor services (run in separate thread)"""
        while self.running:
            try:
                statuses = self.get_all_service_statuses()
                self.service_status_changed.emit(statuses)
            except Exception as e:
                logger.error(f"Error in service monitor: {e}")

            time.sleep(self.update_interval)

    def start_monitoring(self):
        """Start the service monitoring thread"""
        if not self.running:
            self.running = True
            self.monitor_thread = threading.Thread(
                target=self.monitor_services, daemon=True
            )
            self.monitor_thread.start()
            logger.info("Service monitoring started")

    def stop_monitoring(self):
        """Stop the service monitoring thread"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        logger.info("Service monitoring stopped")
