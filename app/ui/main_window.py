"""
Main application window with Qt UI
"""

import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QComboBox,
    QListWidget,
    QFileDialog,
    QMessageBox,
    QGridLayout,
    QFormLayout,
    QCheckBox,
    QSpinBox,
    QProgressBar,
    QSplitter,
    QFrame,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon, QTextCursor, QColor

from app.logic.config import ConfigManager
from app.logic.batch_runner import BatchRunner
from app.logic.service_monitor import ServiceMonitor, ServiceStatus
from app.utils.logger import get_logger

logger = get_logger()


class WorkerThread(QThread):
    """Worker thread for long-running operations"""

    operation_complete = Signal(bool, str)
    output_received = Signal(str, bool)

    def __init__(self, operation_type: str, runner: BatchRunner, **kwargs):
        super().__init__()
        self.operation_type = operation_type
        self.runner = runner
        self.kwargs = kwargs

    def run(self):
        """Execute the operation in a separate thread"""
        try:
            if self.operation_type == "cleanup":
                success = self.runner.execute_cleanup()
                message = "Cleanup completed" if success else "Cleanup failed"

            elif self.operation_type == "restore":
                success = self.runner.execute_restore(
                    self.kwargs.get("client_name"),
                    self.kwargs.get("db_choice"),
                    self.kwargs.get("backup_path"),
                )
                message = "Restore completed" if success else "Restore failed"

            elif self.operation_type == "backup":
                success, zip_path = self.runner.execute_backup()
                message = (
                    f"Backup completed: {zip_path}" if success else "Backup failed"
                )

            else:
                success = False
                message = f"Unknown operation: {self.operation_type}"

            self.operation_complete.emit(success, message)

        except Exception as e:
            self.output_received.emit(f"Error in worker thread: {e}", True)
            self.operation_complete.emit(False, f"Operation failed: {e}")


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.settings = self.config_manager.load()
        self.batch_runner = BatchRunner(self.config_manager)
        self.service_monitor = ServiceMonitor(self.settings.services)

        self.init_ui()
        self.connect_signals()

        # Load saved values
        self.load_settings()

    def init_ui(self):
        """Initialize the UI"""
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

        # Create tabs
        tabs.addTab(self.create_config_tab(), "Configuration")
        tabs.addTab(self.create_services_tab(), "Services")
        tabs.addTab(self.create_cleanup_tab(), "Cleanup")
        tabs.addTab(self.create_restore_tab(), "Restore")
        tabs.addTab(self.create_backup_tab(), "Backup")

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

        # Set output callback
        self.batch_runner.set_output_callback(self.append_to_console)

    def create_config_tab(self):
        """Create configuration tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # SQL Configuration
        sql_group = QGroupBox("SQL Server Configuration")
        sql_layout = QFormLayout()

        self.sql_instance_input = QLineEdit(self.settings.sql_instance)
        self.sql_user_input = QLineEdit(self.settings.sql_user)
        self.sql_password_input = QLineEdit(self.settings.sql_password)
        self.sql_password_input.setEchoMode(QLineEdit.Password)

        sql_layout.addRow("SQL Instance:", self.sql_instance_input)
        sql_layout.addRow("SQL User:", self.sql_user_input)
        sql_layout.addRow("SQL Password:", self.sql_password_input)
        sql_group.setLayout(sql_layout)

        # Services Configuration
        services_group = QGroupBox("Services (one per line)")
        services_layout = QVBoxLayout()
        self.services_input = QTextEdit()
        self.services_input.setPlainText("\n".join(self.settings.services))
        services_layout.addWidget(self.services_input)
        services_group.setLayout(services_layout)

        # Databases Configuration
        dbs_group = QGroupBox("Databases (one per line)")
        dbs_layout = QVBoxLayout()
        self.databases_input = QTextEdit()
        self.databases_input.setPlainText("\n".join(self.settings.databases))
        dbs_layout.addWidget(self.databases_input)
        dbs_group.setLayout(dbs_layout)

        # Backup Configuration
        backup_group = QGroupBox("Backup Configuration")
        backup_layout = QFormLayout()

        self.backup_folder_input = QLineEdit(self.settings.backup_folder)
        self.backup_folder_browse = QPushButton("Browse...")
        self.backup_folder_browse.clicked.connect(self.browse_backup_folder)

        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.backup_folder_input)
        folder_layout.addWidget(self.backup_folder_browse)

        backup_layout.addRow("Backup Folder:", folder_layout)
        backup_group.setLayout(backup_layout)

        # Add all groups
        layout.addWidget(sql_group)
        layout.addWidget(services_group)
        layout.addWidget(dbs_group)
        layout.addWidget(backup_group)
        layout.addStretch()

        # Save button
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)

        return widget

    def create_services_tab(self):
        """Create services monitoring tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Service status display
        self.service_status_widgets = {}

        for service in self.settings.services:
            service_frame = QFrame()
            service_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
            service_layout = QHBoxLayout(service_frame)

            service_label = QLabel(service)
            service_label.setFont(QFont("Arial", 10, QFont.Bold))

            status_label = QLabel("Unknown")
            status_label.setFont(QFont("Arial", 10))

            start_btn = QPushButton("Start")
            stop_btn = QPushButton("Stop")
            restart_btn = QPushButton("Restart")

            # Store widgets
            self.service_status_widgets[service] = {
                "label": status_label,
                "start": start_btn,
                "stop": stop_btn,
                "restart": restart_btn,
            }

            # Connect buttons
            start_btn.clicked.connect(
                lambda checked, s=service: self.control_service(s, "start")
            )
            stop_btn.clicked.connect(
                lambda checked, s=service: self.control_service(s, "stop")
            )
            restart_btn.clicked.connect(
                lambda checked, s=service: self.control_service(s, "restart")
            )

            service_layout.addWidget(service_label)
            service_layout.addWidget(status_label)
            service_layout.addStretch()
            service_layout.addWidget(start_btn)
            service_layout.addWidget(stop_btn)
            service_layout.addWidget(restart_btn)

            layout.addWidget(service_frame)

        layout.addStretch()

        # Control buttons
        control_layout = QHBoxLayout()
        start_all_btn = QPushButton("Start All Services")
        stop_all_btn = QPushButton("Stop All Services")
        refresh_btn = QPushButton("Refresh Status")

        start_all_btn.clicked.connect(self.start_all_services)
        stop_all_btn.clicked.connect(self.stop_all_services)
        refresh_btn.clicked.connect(self.refresh_service_status)

        control_layout.addWidget(start_all_btn)
        control_layout.addWidget(stop_all_btn)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

        return widget

    def create_cleanup_tab(self):
        """Create cleanup operations tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Warning message
        warning_label = QLabel(
            "⚠️ WARNING: This operation will delete services, databases, and folders!"
        )
        warning_label.setStyleSheet("color: red; font-weight: bold; font-size: 14px;")
        warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning_label)

        # Folders to delete
        folders_group = QGroupBox("Folders to Delete (one per line)")
        folders_layout = QVBoxLayout()
        self.folders_input = QTextEdit()
        self.folders_input.setPlainText("\n".join(self.settings.folders_to_delete))
        folders_layout.addWidget(self.folders_input)
        folders_group.setLayout(folders_layout)
        layout.addWidget(folders_group)

        # Confirmation checkbox
        self.confirm_checkbox = QCheckBox(
            "I understand this will permanently delete data"
        )
        layout.addWidget(self.confirm_checkbox)

        # Execute button
        self.cleanup_btn = QPushButton("Execute Cleanup")
        self.cleanup_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold; padding: 10px;"
        )
        self.cleanup_btn.clicked.connect(self.execute_cleanup)
        layout.addWidget(self.cleanup_btn)

        layout.addStretch()
        return widget

    def create_restore_tab(self):
        """Create database restore tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()

        # Client name
        self.client_name_input = QLineEdit()
        self.client_name_input.setPlaceholderText("Enter client name (DB prefix)")
        form_layout.addRow("Client Name:", self.client_name_input)

        # Database choice
        self.db_choice_combo = QComboBox()
        self.db_choice_combo.addItems(["RmsBranchSrv", "RmsCashierSrv"])
        form_layout.addRow("Database:", self.db_choice_combo)

        # Backup file selection
        backup_layout = QHBoxLayout()
        self.backup_path_input = QLineEdit()
        self.backup_path_input.setPlaceholderText("Select backup file or directory")
        self.backup_browse_btn = QPushButton("Browse...")
        self.backup_browse_btn.clicked.connect(self.browse_backup_file)
        backup_layout.addWidget(self.backup_path_input)
        backup_layout.addWidget(self.backup_browse_btn)
        form_layout.addRow("Backup File:", backup_layout)

        # Backup files list
        self.backup_list = QListWidget()
        self.backup_list.itemClicked.connect(self.on_backup_file_selected)
        form_layout.addRow("Available Backups:", self.backup_list)

        layout.addLayout(form_layout)

        # Restore button
        self.restore_btn = QPushButton("Restore Database")
        self.restore_btn.setStyleSheet(
            "background-color: #1976d2; color: white; font-weight: bold; padding: 10px;"
        )
        self.restore_btn.clicked.connect(self.execute_restore)
        layout.addWidget(self.restore_btn)

        layout.addStretch()
        return widget

    def create_backup_tab(self):
        """Create backup operations tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Current configuration display
        config_group = QGroupBox("Backup Configuration")
        config_layout = QFormLayout()

        config_layout.addRow("Backup Folder:", QLabel(self.settings.backup_folder))
        config_layout.addRow("Databases:", QLabel(", ".join(self.settings.databases)))

        # AppSettings files
        appsets_label = QLabel(
            "\n".join(
                [
                    f"{item['name']}: {item['path']}"
                    for item in self.settings.appsettings_files
                ]
            )
        )
        appsets_label.setWordWrap(True)
        config_layout.addRow("AppSettings Files:", appsets_label)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Execute button
        self.backup_btn = QPushButton("Execute Backup")
        self.backup_btn.setStyleSheet(
            "background-color: #388e3c; color: white; font-weight: bold; padding: 10px;"
        )
        self.backup_btn.clicked.connect(self.execute_backup)
        layout.addWidget(self.backup_btn)

        layout.addStretch()
        return widget

    def connect_signals(self):
        """Connect signals and slots"""
        # Service monitor signals
        self.service_monitor.service_status_changed.connect(
            self.update_service_status_display
        )

    def load_settings(self):
        """Load saved settings into UI"""
        # Configuration is loaded in init, UI elements are created with defaults
        pass

    def save_settings(self):
        """Save current UI values to configuration"""
        try:
            # Update settings from UI
            self.settings.sql_instance = self.sql_instance_input.text()
            self.settings.sql_user = self.sql_user_input.text()
            self.settings.sql_password = self.sql_password_input.text()

            # Parse services and databases
            services_text = self.services_input.toPlainText().strip()
            self.settings.services = [
                s.strip() for s in services_text.split("\n") if s.strip()
            ]

            databases_text = self.databases_input.toPlainText().strip()
            self.settings.databases = [
                d.strip() for d in databases_text.split("\n") if d.strip()
            ]

            # Backup folder
            self.settings.backup_folder = self.backup_folder_input.text()

            # Folders to delete
            folders_text = self.folders_input.toPlainText().strip()
            self.settings.folders_to_delete = [
                f.strip() for f in folders_text.split("\n") if f.strip()
            ]

            # Save to file
            self.config_manager.save()

            # Update service monitor
            self.service_monitor.service_names = self.settings.services

            QMessageBox.information(
                self, "Success", "Configuration saved successfully!"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")

    def append_to_console(self, message: str, is_error: bool = False):
        """Append message to console output"""
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

    def browse_backup_folder(self):
        """Browse for backup folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if folder:
            self.backup_folder_input.setText(folder)

    def browse_backup_file(self):
        """Browse for backup file or directory"""
        options = QFileDialog.Options()

        # Try to get directory first
        directory = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if directory:
            self.backup_path_input.setText(directory)
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
                self.backup_path_input.setText(file_path)

    def scan_backup_files(self, directory: str):
        """Scan directory for backup files"""
        self.backup_list.clear()

        try:
            backup_files = self.batch_runner.get_backup_files(directory)
            for i, file_info in enumerate(backup_files, 1):
                self.backup_list.addItem(
                    f"{i}) {file_info['name']} ({file_info['size'] // 1024 // 1024} MB)"
                )

            if not backup_files:
                self.backup_list.addItem("No .bak files found in directory")

        except Exception as e:
            self.backup_list.addItem(f"Error scanning directory: {e}")

    def on_backup_file_selected(self, item):
        """Handle backup file selection"""
        text = item.text()
        if ")" in text:
            # Extract file number
            file_num = text.split(")")[0].strip()
            try:
                idx = int(file_num) - 1
                directory = self.backup_path_input.text()
                backup_files = self.batch_runner.get_backup_files(directory)
                if 0 <= idx < len(backup_files):
                    self.backup_path_input.setText(backup_files[idx]["path"])
            except (ValueError, IndexError):
                pass

    def start_service_monitoring(self):
        """Start service monitoring"""
        self.service_monitor.start_monitoring()
        # Initial status update
        self.refresh_service_status()

    def refresh_service_status(self):
        """Manually refresh service status"""
        statuses = self.service_monitor.get_all_service_statuses()
        self.update_service_status_display(statuses)

    def update_service_status_display(self, statuses: dict):
        """Update service status display"""
        for service, status in statuses.items():
            if service in self.service_status_widgets:
                widgets = self.service_status_widgets[service]
                widgets["label"].setText(status)

                # Update button states based on status
                widgets["start"].setEnabled(status != ServiceStatus.RUNNING)
                widgets["stop"].setEnabled(status == ServiceStatus.RUNNING)
                widgets["restart"].setEnabled(status == ServiceStatus.RUNNING)

                # Update color
                color_map = {
                    ServiceStatus.RUNNING: "green",
                    ServiceStatus.STOPPED: "red",
                    ServiceStatus.NOT_FOUND: "gray",
                    ServiceStatus.START_PENDING: "orange",
                    ServiceStatus.STOP_PENDING: "orange",
                    ServiceStatus.UNKNOWN: "gray",
                }

                widgets["label"].setStyleSheet(
                    f"color: {color_map.get(status, 'gray')}; font-weight: bold;"
                )

    def control_service(self, service_name: str, action: str):
        """Control a Windows service"""
        try:
            if action == "start":
                self.batch_runner.run_command(["net", "start", service_name])
            elif action == "stop":
                self.batch_runner.run_command(["net", "stop", service_name])
            elif action == "restart":
                self.batch_runner.run_command(["net", "stop", service_name])
                # Wait a bit before starting
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

    def execute_cleanup(self):
        """Execute cleanup operation"""
        if not self.confirm_checkbox.isChecked():
            QMessageBox.warning(
                self,
                "Confirmation Required",
                "Please confirm that you understand this will permanently delete data.",
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
            self.cleanup_btn.setEnabled(False)

            # Run in worker thread
            self.worker = WorkerThread("cleanup", self.batch_runner)
            self.worker.operation_complete.connect(self.on_operation_complete)
            self.worker.output_received.connect(self.append_to_console)
            self.worker.start()

    def execute_restore(self):
        """Execute restore operation"""
        client_name = self.client_name_input.text().strip()
        if not client_name:
            QMessageBox.warning(self, "Input Required", "Please enter a client name.")
            return

        backup_path = self.backup_path_input.text().strip()
        if not backup_path or not os.path.exists(backup_path):
            QMessageBox.warning(
                self, "Input Required", "Please select a valid backup file."
            )
            return

        db_choice = "1" if self.db_choice_combo.currentText() == "RmsBranchSrv" else "2"

        self.append_to_console(f"Starting restore operation for client: {client_name}")
        self.restore_btn.setEnabled(False)

        # Run in worker thread
        self.worker = WorkerThread(
            "restore",
            self.batch_runner,
            client_name=client_name,
            db_choice=db_choice,
            backup_path=backup_path,
        )
        self.worker.operation_complete.connect(self.on_operation_complete)
        self.worker.output_received.connect(self.append_to_console)
        self.worker.start()

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
            self.backup_btn.setEnabled(False)

            # Run in worker thread
            self.worker = WorkerThread("backup", self.batch_runner)
            self.worker.operation_complete.connect(self.on_operation_complete)
            self.worker.output_received.connect(self.append_to_console)
            self.worker.start()

    def on_operation_complete(self, success: bool, message: str):
        """Handle operation completion"""
        self.append_to_console(message)

        # Re-enable buttons
        self.cleanup_btn.setEnabled(True)
        self.restore_btn.setEnabled(True)
        self.backup_btn.setEnabled(True)

        # Update status
        status = "Operation completed successfully" if success else "Operation failed"
        self.status_label.setText(status)

        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.warning(self, "Warning", message)

    def closeEvent(self, event):
        """Handle application close"""
        self.service_monitor.stop_monitoring()
        event.accept()
