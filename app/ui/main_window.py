"""
Main application window with modular UI components
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QTabWidget,
    QGroupBox,
    QTextEdit,
    QMessageBox,
    QFileDialog,
    QLabel,
)
from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QTextCursor, QColor

from app.logic.config import ConfigManager
from app.logic.batch_runner import BatchRunner
from app.logic.service_monitor import ServiceMonitor, ServiceStatus
from app.logic.worker_thread import WorkerThread
from app.models import OperationResult, OperationStatus
from app.utils.logger import get_logger

# Import modular UI components
from app.ui.config_tab import ConfigTab
from app.ui.services_tab import ServicesTab
from app.ui.cleanup_tab import CleanupTab
from app.ui.restore_tab import RestoreTab
from app.ui.backup_tab import BackupTab

logger = get_logger()


class MainWindow(QMainWindow):
    """Main application window with modular UI"""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.settings = self.config_manager.load()
        self.batch_runner = BatchRunner(self.config_manager)
        self.service_monitor = ServiceMonitor(self.settings.services)

        self.current_worker: Optional[WorkerThread] = None

        self.init_ui()
        self.connect_signals()

        # Validate credentials on startup
        if not self.config_manager.validate_credentials():
            self.show_warning(
                "SQL password not configured or could not be decrypted. "
                "Please enter credentials in Configuration tab."
            )

    def init_ui(self):
        """Initialize the UI with modular components"""
        self.setWindowTitle("POS Admin Tool")
        self.setMinimumSize(1200, 800)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)

        # Create tab widget
        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # Create modular tabs
        self.config_tab = ConfigTab(self.settings)
        self.services_tab = ServicesTab(self.settings.services)
        self.cleanup_tab = CleanupTab(self.settings.folders_to_delete)
        self.restore_tab = RestoreTab()
        self.backup_tab = BackupTab(self.settings)

        # Add tabs
        tabs.addTab(self.config_tab, "Configuration")
        tabs.addTab(self.services_tab, "Services")
        tabs.addTab(self.cleanup_tab, "Cleanup")
        tabs.addTab(self.restore_tab, "Restore")
        tabs.addTab(self.backup_tab, "Backup")

        # Status bar
        self.status_label = QLabel("Ready")
        self.statusBar().addWidget(self.status_label)

        # Output console
        console_group = QGroupBox("Execution Log")
        console_layout = QVBoxLayout()
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_output.setFont(QFont("Courier New", 10))
        console_layout.addWidget(self.console_output)
        console_group.setLayout(console_layout)
        main_layout.addWidget(console_group)

    def connect_signals(self):
        """Connect all signals and slots"""
        # Service monitor signals
        self.service_monitor.service_status_changed.connect(
            self.update_service_status_display
        )

        # Config tab signals
        self.config_tab.save_requested.connect(self.save_settings)
        self.config_tab.backup_folder_browsed.connect(self.browse_backup_folder)

        # Services tab signals
        self.services_tab.service_control_requested.connect(self.control_service)
        self.services_tab.start_all_requested.connect(self.start_all_services)
        self.services_tab.stop_all_requested.connect(self.stop_all_services)
        self.services_tab.refresh_requested.connect(self.refresh_service_status)

        # Cleanup tab signals
        self.cleanup_tab.cleanup_requested.connect(self.execute_cleanup)

        # Restore tab signals
        self.restore_tab.backup_browsed.connect(self.browse_backup_file)
        self.restore_tab.backup_file_selected.connect(self.on_backup_file_selected)
        self.restore_tab.restore_requested.connect(self.execute_restore)

        # Backup tab signals
        self.backup_tab.backup_requested.connect(self.execute_backup)

    def append_to_console(self, message: str, is_error: bool = False):
        """Append message to console output (thread-safe via signals)"""
        cursor = self.console_output.textCursor()
        cursor.movePosition(QTextCursor.End)

        if is_error:
            self.console_output.setTextColor(QColor(200, 0, 0))
        else:
            self.console_output.setTextColor(QColor(0, 0, 0))

        self.console_output.append(message)

        # Auto-scroll
        self.console_output.verticalScrollBar().setValue(
            self.console_output.verticalScrollBar().maximum()
        )

    def show_warning(self, message: str):
        """Show warning message"""
        QMessageBox.warning(self, "Warning", message)

    def show_error(self, message: str):
        """Show error message"""
        QMessageBox.critical(self, "Error", message)

    def show_info(self, message: str):
        """Show info message"""
        QMessageBox.information(self, "Information", message)

    # ===== CONFIGURATION HANDLERS =====

    def save_settings(self):
        """Save configuration from UI"""
        try:
            settings_data = self.config_tab.get_settings()

            # Update settings
            self.settings.sql_instance = settings_data["sql_instance"]
            self.settings.sql_user = settings_data["sql_user"]

            # Only update password if provided
            if settings_data["sql_password"]:
                self.settings.sql_password = settings_data["sql_password"]

            self.settings.services = settings_data["services"]
            self.settings.databases = settings_data["databases"]
            self.settings.backup_folder = settings_data["backup_folder"]

            # Update folders from cleanup tab
            self.settings.folders_to_delete = self.cleanup_tab.get_folders()

            # Save to file
            self.config_manager.save()

            # Update service monitor with new services
            self.service_monitor.service_names = self.settings.services

            # Update services tab if service list changed
            if set(self.settings.services) != set(self.services_tab.service_names):
                # TODO: Implement dynamic service list update
                pass

            self.show_info("Configuration saved successfully!")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            self.show_error(f"Failed to save configuration: {e}")

    def browse_backup_folder(self):
        """Browse for backup folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self.config_tab.set_backup_folder(folder)

    # ===== SERVICE HANDLERS =====

    def start_service_monitoring(self):
        """Start service monitoring"""
        self.service_monitor.start_monitoring()
        QTimer.singleShot(1000, self.refresh_service_status)

    def refresh_service_status(self):
        """Manually refresh service status"""
        statuses = self.service_monitor.get_all_service_statuses()
        self.update_service_status_display(statuses)

    def update_service_status_display(self, statuses: dict):
        """Update service status display (called from service monitor)"""
        color_map = {
            ServiceStatus.RUNNING: "green",
            ServiceStatus.STOPPED: "red",
            ServiceStatus.NOT_FOUND: "gray",
            ServiceStatus.START_PENDING: "orange",
            ServiceStatus.STOP_PENDING: "orange",
            ServiceStatus.UNKNOWN: "gray",
        }

        for service, status in statuses.items():
            color = color_map.get(status, "gray")
            is_running = status == ServiceStatus.RUNNING

            self.services_tab.update_service_status(service, status, color)
            self.services_tab.update_service_buttons(service, is_running)

    def control_service(self, service_name: str, action: str):
        """Control a Windows service"""
        try:
            if action == "start":
                self.batch_runner.run_command(["net", "start", service_name])
            elif action == "stop":
                self.batch_runner.run_command(["net", "stop", service_name])
            elif action == "restart":
                self.batch_runner.run_command(["net", "stop", service_name])
                QTimer.singleShot(
                    1000,
                    lambda: self.batch_runner.run_command(
                        ["net", "start", service_name]
                    ),
                )

            # Refresh status after a delay
            QTimer.singleShot(2000, self.refresh_service_status)

        except Exception as e:
            self.append_to_console(
                f"Failed to {action} service {service_name}: {e}", True
            )

    def start_all_services(self):
        """Start all monitored services"""
        for service in self.settings.services:
            self.control_service(service, "start")

    def stop_all_services(self):
        """Stop all monitored services"""
        for service in self.settings.services:
            self.control_service(service, "stop")

    # ===== BACKUP FILE HANDLERS =====

    def browse_backup_file(self):
        """Browse for backup file or directory"""
        options = QFileDialog.Options()

        # Try to get directory first
        directory = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if directory:
            self.restore_tab.set_backup_path(directory)
            self.scan_backup_files(directory)
        else:
            # Fall back to file selection
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Backup File",
                "",
                "Backup Files (*.bak);;All Files (*.*)",
                options=options,
            )
            if file_path:
                self.restore_tab.set_backup_path(file_path)

    def scan_backup_files(self, directory: str):
        """Scan directory for backup files"""
        self.restore_tab.clear_backup_list()

        try:
            backup_files = self.batch_runner.get_backup_files(directory)
            for i, file_info in enumerate(backup_files, 1):
                size_mb = file_info["size"] // 1024 // 1024
                self.restore_tab.add_backup_item(
                    f"{i}) {file_info['name']} ({size_mb} MB)"
                )

            if not backup_files:
                self.restore_tab.add_backup_item("No .bak files found in directory")

        except Exception as e:
            self.restore_tab.add_backup_item(f"Error scanning directory: {e}")

    def on_backup_file_selected(self, file_number: str):
        """Handle backup file selection from list"""
        try:
            idx = int(file_number) - 1
            backup_path = self.restore_tab.get_restore_data()["backup_path"]

            if backup_path and Path(backup_path).is_dir():
                backup_files = self.batch_runner.get_backup_files(backup_path)
                if 0 <= idx < len(backup_files):
                    self.restore_tab.set_backup_path(backup_files[idx]["path"])
        except (ValueError, IndexError):
            pass

    # ===== OPERATION HANDLERS =====

    def execute_cleanup(self):
        """Execute cleanup operation"""
        if not self.cleanup_tab.is_confirmed():
            self.show_warning(
                "Please confirm that you understand this will permanently delete data."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cleanup",
            "This will:\n"
            "1. Stop and delete services\n"
            "2. Drop databases\n"
            "3. Delete folders\n"
            "4. Clean registry\n\n"
            "Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.append_to_console("Starting cleanup operation...")
            self.set_operation_buttons_enabled(False)

            # Create and start worker thread
            self.current_worker = WorkerThread("cleanup", self.batch_runner)
            self.connect_worker_signals(self.current_worker)
            self.current_worker.start()

    def execute_restore(self):
        """Execute restore operation"""
        restore_data = self.restore_tab.get_restore_data()

        client_name = restore_data["client_name"]
        if not client_name:
            self.show_warning("Please enter a client name.")
            return

        backup_path = restore_data["backup_path"]
        if not backup_path or not os.path.exists(backup_path):
            self.show_warning("Please select a valid backup file.")
            return

        self.append_to_console(f"Starting restore operation for client: {client_name}")
        self.set_operation_buttons_enabled(False)

        # Create and start worker thread
        self.current_worker = WorkerThread(
            "restore",
            self.batch_runner,
            client_name=client_name,
            db_choice=restore_data["db_choice"],
            backup_path=backup_path,
        )
        self.connect_worker_signals(self.current_worker)
        self.current_worker.start()

    def execute_backup(self):
        """Execute backup operation"""
        reply = QMessageBox.question(
            self,
            "Confirm Backup",
            "This will:\n"
            "1. Shrink databases\n"
            "2. Backup databases\n"
            "3. Copy appsettings files\n"
            "4. Create ZIP archive\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.append_to_console("Starting backup operation...")
            self.set_operation_buttons_enabled(False)

            # Create and start worker thread
            self.current_worker = WorkerThread("backup", self.batch_runner)
            self.connect_worker_signals(self.current_worker)
            self.current_worker.start()

    def connect_worker_signals(self, worker: WorkerThread):
        """Connect worker thread signals to handlers"""
        worker.output_received.connect(self.append_to_console)
        worker.operation_complete.connect(self.on_operation_complete)

    def on_operation_complete(self, result: OperationResult):
        """Handle operation completion"""
        # Re-enable buttons
        self.set_operation_buttons_enabled(True)

        # Update status based on operation result
        status_messages = {
            OperationStatus.SUCCESS: "Operation completed successfully",
            OperationStatus.PARTIAL_SUCCESS: "Operation completed with warnings",
            OperationStatus.FAILED: "Operation failed",
            OperationStatus.CANCELLED: "Operation cancelled",
        }

        status_message = status_messages.get(result.status, "Operation completed")
        self.status_label.setText(status_message)

        # Show appropriate message box
        if result.status == OperationStatus.SUCCESS:
            self.show_info(result.messages[-1] if result.messages else "Success")
        elif result.status == OperationStatus.PARTIAL_SUCCESS:
            warning_msg = "Operation completed with some issues:\n"
            warning_msg += "\n".join(result.warnings[:3])  # Show first 3 warnings
            if len(result.warnings) > 3:
                warning_msg += f"\n... and {len(result.warnings) - 3} more"
            self.show_warning(warning_msg)
        elif result.status == OperationStatus.FAILED:
            error_msg = "Operation failed:\n"
            error_msg += "\n".join(result.errors[:3])  # Show first 3 errors
            if len(result.errors) > 3:
                error_msg += f"\n... and {len(result.errors) - 3} more"
            self.show_error(error_msg)

        # Clear current worker reference
        self.current_worker = None

    def set_operation_buttons_enabled(self, enabled: bool):
        """Enable or disable all operation buttons"""
        self.cleanup_tab.set_cleanup_enabled(enabled)
        self.restore_tab.set_restore_enabled(enabled)
        self.backup_tab.set_backup_enabled(enabled)

    def closeEvent(self, event):
        """Handle application close"""
        # Stop any running worker
        if self.current_worker and self.current_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "Operation in Progress",
                "An operation is still running. Do you want to cancel it and exit?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                self.current_worker.cancel()
                self.current_worker.wait(2000)  # Wait up to 2 seconds
            else:
                event.ignore()
                return

        # Stop service monitoring
        self.service_monitor.stop_monitoring()

        event.accept()
