"""
Unified UI module - Modern Windows-Native Design (Refactored)
"""

import os
import sys
import time
from typing import List

from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QLabel,
    QMessageBox,
    QFileDialog,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QApplication,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QObject, QUrl, QSize
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtGui import QStandardItemModel, QStandardItem

from app.config import ConfigManager
from app.logic import BatchRunner
from app.services import ServiceMonitor, ServiceStatus
from app.models import OperationResult, OperationStatus, AppSettings
from app.logger import get_logger

logger = get_logger()

# ===== THEME & CONSTANTS =====

COLORS = {
    "PRIMARY": "#0078D4",  # High-Visibility Blue
    "PRIMARY_HOVER": "#106EBE",
    "PRIMARY_PRESSED": "#005A9E",
    "SECONDARY_TEAL": "#008272",
    "SECONDARY_AMBER": "#FFB900",
    "DISABLED": "#323130",
    "SUCCESS": "#107C10",
    "WARNING": "#D83B01",
    "DANGER": "#A4262C",
    "BG": "#0A0A0A",  # Pure Deep Dark
    "CARD_BG": "#161616",  # Slightly lighter charcoal
    "BORDER": "#333333",  # Subtle border
    "TEXT_PRI": "#FFFFFF",  # High contrast white
    "TEXT_SEC": "#BABABA",  # Readable gray
    "INFO": "#00A2AD",
}

# ===== CUSTOM WIDGETS =====


class CheckableComboBox(QComboBox):
    """Multi-select dropdown with checkmarks"""

    selectionChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view().pressed.connect(self.handle_item_pressed)
        self.setModel(QStandardItemModel(self))
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.setMinimumWidth(300)
        self.setMinimumHeight(35)
        # Styled to match checkboxes in restore section
        self.setStyleSheet(
            """
            QComboBox {
                background: #0F172A;
                color: white;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 5px;
            }
            QComboBox::drop-down {
                background-color: #3B82F6; /* Blue Dropdown Button */
                border-left: 1px solid #334155;
                width: 30px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QComboBox::down-arrow {
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0iI2ZmZmZmZiI+PHBhdGggZD0iTTcgMTBsNSA1IDUtNXoiLz48L3N2Zz4="); /* White Arrow */
                width: 14px;
                height: 14px;
            }
        """
        )
        # Ensure the popup view supports the styling
        view = self.view()
        view.setStyleSheet(
            """
            QListView {
                background-color: #161616;
                border: 1px solid #333333;
                outline: none;
            }
            QListView::item {
                background: #161616;
                color: #FFFFFF;
                padding: 8px;
                border-bottom: 1px solid #2A2A2A;
            }
            QListView::item:selected {
                background: #0078D4;
                color: white;
            }
            QListView::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #444444;
                background: #222222;
                border-radius: 4px;
            }
            QListView::indicator:checked {
                background-color: #107C10;
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4=");
            }
            QListView::item:hover {
                background: #2A2A2A;
                color: white;
            }
        """
        )

    def handle_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self.update_display_text()
        self.selectionChanged.emit()

    def hidePopup(self):
        if self.view().underMouse():
            pass
        else:
            super().hidePopup()

    def update_display_text(self):
        checked_items = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                checked_items.append(item.text())

        if not checked_items:
            self.lineEdit().setText("Select items...")
        elif len(checked_items) <= 3:
            self.lineEdit().setText(", ".join(checked_items))
        else:
            self.lineEdit().setText(f"{len(checked_items)} items selected")

    def set_items(self, items: List[str], selected_items: List[str]):
        self.clear()
        for text in items:
            item = QStandardItem(text)
            # Add checkbox icon via style or checkstate
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            # Ensure proper checkstate handling requires the view to respect it
            # The standard item view should render the checkbox if checkable.
            if text in selected_items:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.model().appendRow(item)
        self.update_display_text()

    def get_checked_items(self) -> List[str]:
        checked_items = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                checked_items.append(item.text())
        return checked_items

    def get_all_items(self) -> List[str]:
        items = []
        for i in range(self.model().rowCount()):
            items.append(self.model().item(i).text())
        return items


# ===== CONTROLLER LAYER =====


class WorkerThread(QThread):
    operation_complete = Signal(OperationResult)
    output_received = Signal(str, bool)
    # Generic signal for non-OperationResult tasks
    generic_result = Signal(object)

    def __init__(
        self,
        operation_type: str,
        runner: BatchRunner = None,
        generic_func=None,
        **kwargs,
    ):
        super().__init__()
        self.operation_type = operation_type
        self.runner = runner
        self.generic_func = generic_func
        self.kwargs = kwargs
        self._is_cancelled = False

    def emit_output(self, message: str, is_error: bool = False):
        if not self._is_cancelled:
            self.output_received.emit(message, is_error)

    def run(self):
        try:
            # Mode A: Generic Function Execution
            if self.operation_type == "generic" and self.generic_func:
                result = self.generic_func(**self.kwargs)
                self.generic_result.emit(result)
                return

            # Mode B: Standard Batch Operations
            result = None
            if self.operation_type == "cleanup":
                result = self.runner.execute_cleanup()
            elif self.operation_type == "restore":
                result = self.runner.execute_restore(
                    self.kwargs.get("backup_path"),
                    self.kwargs.get("target_db"),
                    mdf_path=self.kwargs.get("mdf_path"),
                    ldf_path=self.kwargs.get("ldf_path"),
                )
            elif self.operation_type == "backup":
                result = self.runner.execute_backup(
                    selected_dbs=self.kwargs.get("selected_dbs"),
                    selected_appsettings=self.kwargs.get("selected_appsettings"),
                )
            elif self.operation_type == "uninstall_branch":
                result = self.runner.execute_uninstall_branch()
            elif self.operation_type == "uninstall_pos":
                result = self.runner.execute_uninstall_pos()
            else:
                result = OperationResult.create(self.operation_type)
                result.add_error(f"Unknown operation: {self.operation_type}")
                result.finalize(OperationStatus.FAILED)

            if not self._is_cancelled:
                self.operation_complete.emit(result)

        except Exception as e:
            if not self._is_cancelled:
                if self.operation_type == "generic":
                    self.generic_result.emit((False, f"Thread Error: {str(e)}"))
                else:
                    self.output_received.emit(f"Error in worker thread: {e}", True)
                    result = OperationResult.create(self.operation_type)
                    result.add_error(f"Worker thread error: {e}")
                    result.finalize(OperationStatus.FAILED)
                    self.operation_complete.emit(result)


class MainController(QObject):
    """
    Mediator between UI and Logic.
    Handles threading, signals, and business logic orchestration.
    """

    # Signals to UI
    log_msg = Signal(str, bool)
    status_msg = Signal(str)
    service_status_updated = Signal(dict)
    config_loaded = Signal(AppSettings)
    op_started = Signal()
    op_finished = Signal(OperationResult)

    def __init__(self):
        super().__init__()
        self.config_manager = ConfigManager()
        self.settings = self.config_manager.load()
        self.batch_runner = BatchRunner(self.config_manager)
        # Connect Logic Signals to Controller Signals
        self.batch_runner.log_message.connect(self.log_msg.emit)

        self.service_monitor = ServiceMonitor(self.settings.services)
        self.worker = None

        # Connect Monitor
        self.service_monitor.service_status_changed.connect(self.service_status_updated)

    def start_app(self):
        """Initial startup sequence"""
        self.auto_import_rms_settings()
        self.config_loaded.emit(self.settings)
        # Delay service start slightly to allow UI to show
        QTimer.singleShot(1000, self.service_monitor.start_monitoring)
        self.log_msg.emit("Application started. Monitor active.", False)

    def auto_import_rms_settings(self):
        """Silently import settings from RMS+ on startup"""
        success, result = self.batch_runner.import_rms_settings()
        if success and isinstance(result, dict):
            for k, v in result.items():
                if hasattr(self.settings, k):
                    setattr(self.settings, k, v)
            # Save the auto-imported settings
            self.config_manager.save()
            self.log_msg.emit("Settings auto-loaded from RMS+.", False)

    def shutdown(self):
        self.service_monitor.stop_monitoring()

    def load_config(self):
        self.settings = self.config_manager.load()
        self.config_loaded.emit(self.settings)

    def save_config(self, updates: dict):
        try:
            # Update settings object
            for k, v in updates.items():
                if hasattr(self.settings, k):
                    setattr(self.settings, k, v)

            # Persist to disk
            self.config_manager.save()
            self.log_msg.emit("Configuration saved successfully.", False)

            # Refresh Monitor if services changed
            if "services" in updates:
                self.service_monitor.service_names = updates["services"]
                self.service_monitor.stop_monitoring()
                self.service_monitor.start_monitoring()

            # Emit reload to ensure UI is in sync
            self.config_loaded.emit(self.settings)

        except Exception as e:
            self.log_msg.emit(f"Failed to save config: {e}", True)

    def test_sql_connection(self, instance, user, password):
        self.log_msg.emit(f"Testing SQL connection to {instance}...", False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success = self.batch_runner.test_sql_connection(instance, user, password)
            if success:
                self.log_msg.emit("SQL Connection Successful!", False)
                # Success Alert for DB Connection (triggers on_op_finished)
                from app.models import OperationStatus

                test_result = OperationResult.create("test_connection")
                test_result.finalize(OperationStatus.SUCCESS)
                self.op_finished.emit(test_result)

                try:
                    dbs = self.batch_runner.fetch_databases(instance, user, password)
                    if dbs:
                        self.log_msg.emit(
                            f"Auto-discovered {len(dbs)} databases.", False
                        )
                        # Update settings with new DBs and refresh UI
                        # Use discovered DBs as the source of truth for the NEW instance
                        # Update settings with new DBs
                        # Update settings with new DBs
                        self.settings.databases = dbs
                        self.config_manager.save()

                        # Emit config_loaded to refresh ALL panels including ConfigurationPanel
                        self.config_loaded.emit(self.settings)

                    else:
                        self.log_msg.emit("No databases found.", True)
                except Exception as e:
                    self.log_msg.emit(f"DB Discovery failed: {e}", True)

            else:
                self.log_msg.emit("SQL Connection Failed.", True)
        finally:
            QApplication.restoreOverrideCursor()

    def discover_services(self):
        self.log_msg.emit("Scanning for services...", False)
        svcs = self.service_monitor.discover_services()
        if svcs:
            self.log_msg.emit(f"Discovered {len(svcs)} services.", False)
            # Update settings temporarily so UI sees them?
            # Or assume user has to click save?
            # The previous UI pattern was `populate_ui` taking a list.
            # We can update settings.services and emit config_loaded.
            # But that might overwrite user preference if not saved.
            # Let's just update the settings object in memory and refresh UI.
            self.settings.services = list(set(self.settings.services + svcs))
            self.config_manager.save()  # Persist services
            self.config_loaded.emit(self.settings)
        else:
            self.log_msg.emit(
                "No new services found.", False
            )  # Changed to False to not alarm
            # Provide UI feedback anyway?
            # self.config_loaded.emit(self.settings) # Optional: refresh just in case

    def control_service(self, name: str, action: str):
        self.log_msg.emit(f"Requesting {action} for {name}...", False)
        # Run in thread to not block UI
        # But BatchRunner.control_service is synchronous?
        # Yes, let's use a quick thread or just run it if it's fast.
        # `net start` can take seconds. Better use thread/worker logic.
        # For simplicity in this Controller, we'll run it directly but with UI update awareness
        # blocking is bad. Let's start a worker.
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            success = self.batch_runner.control_service(name, action)
            if success:
                self.log_msg.emit(f"Service {action} command sent successfully.", False)
                # Force instant refresh
                time.sleep(1)
                self.service_monitor.get_all_service_statuses()  # This updates internal state?
                # Actually Monitor runs in loop. It will catch it.
            else:
                self.log_msg.emit(f"Service {action} failed.", True)
        finally:
            QApplication.restoreOverrideCursor()

    def execute_operation(self, op_type: str, **kwargs):
        if self.worker and self.worker.isRunning():
            self.log_msg.emit("Operation already in progress.", True)
            return

        self.op_started.emit()
        self.worker = WorkerThread(op_type, self.batch_runner, **kwargs)
        self.worker.output_received.connect(self.log_msg)
        self.worker.operation_complete.connect(self.on_op_complete)
        self.worker.start()

    def on_op_complete(self, result: OperationResult):
        self.op_finished.emit(result)
        if result.status == OperationStatus.SUCCESS:
            self.log_msg.emit("Operation completed successfully.", False)
        else:
            self.log_msg.emit("Operation failed with errors.", True)


# ===== UI COMPONENTS =====


class ConfigurationPanel(QGroupBox):
    def __init__(self, controller: MainController):
        super().__init__("Configuration")
        self.controller = controller
        self.init_ui()

    def init_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 25, 20, 20)

        # Row 0: Basic Headers
        headers = ["Client Name", "SQL Instance", "SQL User", "Password"]
        for i, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(
                f"font-weight: 600; color: {COLORS['TEXT_SEC']}; font-size: 13px;"
            )
            layout.addWidget(lbl, 0, i)
            layout.setColumnStretch(i, 1)

        # Row 1: Basic Inputs
        self.client_name = QLineEdit()
        self.sql_instance = QLineEdit()
        self.sql_user = QLineEdit()
        self.sql_password = QLineEdit()
        self.sql_password.setEchoMode(QLineEdit.Password)
        self.sql_password.setPlaceholderText("(Unchanged)")

        for w in [
            self.client_name,
            self.sql_instance,
            self.sql_user,
            self.sql_password,
        ]:
            w.setMinimumWidth(
                200
            )  # Reduced to allow more columns if needed, but grid handles it
            w.setMinimumHeight(35)
            layout.addWidget(w)  # Placeholder

        layout.addWidget(self.client_name, 1, 0)
        layout.addWidget(self.sql_instance, 1, 1)
        layout.addWidget(self.sql_user, 1, 2)
        layout.addWidget(self.sql_password, 1, 3)

        # Row 2: Resources Headers
        layout.addWidget(QLabel("Databases"), 2, 0)

        svc_layout = QHBoxLayout()
        svc_layout.addWidget(QLabel("Services"))
        # Refresh button moved to input row
        svc_layout.addStretch()
        layout.addLayout(svc_layout, 2, 1)

        layout.addWidget(QLabel("Backup Folder"), 2, 2, 1, 2)

        # Row 3: Resources Inputs
        self.db_combo = CheckableComboBox()
        self.svc_combo = CheckableComboBox()

        self.backup_path = QLineEdit()
        self.backup_path.setMinimumHeight(35)
        btn_browse = QPushButton("...")
        btn_browse.setFixedSize(40, 35)
        btn_browse.setStyleSheet(
            f"background-color: {COLORS['INFO']}; color: white; font-weight: bold; border-radius: 4px;"
        )
        btn_browse.clicked.connect(self.browse_path)

        path_layout = QHBoxLayout()
        path_layout.addWidget(self.backup_path)
        path_layout.addWidget(btn_browse)

        for w in [self.db_combo, self.svc_combo]:
            w.setMinimumWidth(200)
            w.setFixedHeight(35)

        layout.addWidget(self.db_combo, 3, 0)

        # Database Layout with Refresh Button
        db_input_layout = QHBoxLayout()
        db_input_layout.addWidget(self.db_combo)

        # Load Refresh Icon
        from app.utils import resource_path

        refresh_icon_path = resource_path(
            os.path.join("assets", "icons", "white_refresh.svg")
        )
        refresh_icon = QIcon(refresh_icon_path)

        btn_db_refresh = QPushButton()
        btn_db_refresh.setFixedSize(35, 35)
        btn_db_refresh.setToolTip("Refresh Databases")
        # Use White Refresh Icon
        btn_db_refresh.setIcon(refresh_icon)
        btn_db_refresh.setIconSize(QSize(20, 20))
        btn_db_refresh.setStyleSheet(
            f"background-color: {COLORS['PRIMARY']}; border-radius: 4px;"
        )
        btn_db_refresh.clicked.connect(self.refresh_databases)
        db_input_layout.addWidget(btn_db_refresh)

        # Service Layout with Refresh Button
        svc_input_layout = QHBoxLayout()
        svc_input_layout.addWidget(self.svc_combo)

        btn_refresh = QPushButton()
        btn_refresh.setFixedSize(35, 35)
        btn_refresh.setToolTip("Refresh Services")
        btn_refresh.setIcon(refresh_icon)
        btn_refresh.setIconSize(QSize(20, 20))
        btn_refresh.setStyleSheet(
            f"background-color: {COLORS['PRIMARY']}; border-radius: 4px;"
        )
        btn_refresh.clicked.connect(self.controller.discover_services)
        svc_input_layout.addWidget(btn_refresh)

        layout.addLayout(db_input_layout, 3, 0)
        layout.addLayout(svc_input_layout, 3, 1)
        layout.addLayout(path_layout, 3, 2, 1, 2)

        # Row 4: Advanced Config Headers (New)
        new_headers = [
            "Branch Code",
            "Machine No.",
            "RMS Base URL",
        ]
        for i, h in enumerate(new_headers):
            lbl = QLabel(h)
            lbl.setStyleSheet(
                f"font-weight: 600; color: {COLORS['TEXT_SEC']}; margin-top: 10px; font-size: 13px;"
            )
            layout.addWidget(lbl, 4, i)

        # Server Status Header (Col 3)
        lbl_status = QLabel("Main Server Status")
        lbl_status.setStyleSheet(
            f"font-weight: 600; color: {COLORS['TEXT_SEC']}; margin-top: 10px; font-size: 13px;"
        )
        layout.addWidget(lbl_status, 4, 3)

        # Row 5: Advanced Config Inputs (New)
        from PySide6.QtGui import QIntValidator

        self.branch_code = QLineEdit()
        self.branch_code.setPlaceholderText("e.g. P001")
        # Removing strict integer validator to allow alphanumeric characters
        # self.branch_code.setValidator(QIntValidator(0, 9999))
        self.branch_code.setMaxLength(
            10
        )  # Increased length to accommodate alphanumeric codes if needed, kept reasonable

        self.pos_number = QLineEdit()
        self.pos_number.setPlaceholderText("e.g. 1")
        self.pos_number.setValidator(QIntValidator(0, 99))
        self.pos_number.setMaxLength(2)

        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("http://Host:Port/rmsmainserverApi")

        # Server Status Indicator
        self.lbl_server_status = QLabel("Checking...")
        self.lbl_server_status.setStyleSheet(
            f"font-weight: 600; color: #FFFFFF; border: 1px solid {COLORS['BORDER']}; border-radius: 6px; padding: 4px; background: #222;"
        )
        self.lbl_server_status.setAlignment(Qt.AlignCenter)

        for w in [
            self.branch_code,
            self.pos_number,
            self.api_url,
            self.lbl_server_status,
        ]:
            w.setMinimumHeight(35)

        layout.addWidget(self.branch_code, 5, 0)
        layout.addWidget(self.pos_number, 5, 1)
        layout.addWidget(self.api_url, 5, 2)
        layout.addWidget(self.lbl_server_status, 5, 3)

        # Row 6: Actions
        btn_test = QPushButton("Test DB Connection")
        btn_test.setMinimumHeight(40)
        btn_test.clicked.connect(self.test_conn)

        btn_save = QPushButton("Save Configuration")
        btn_save.setMinimumHeight(40)
        btn_save.clicked.connect(self.save)

        action_layout = QHBoxLayout()
        # Import Button (New)
        btn_import = QPushButton("Import from RMS+")
        btn_import.setMinimumHeight(40)
        btn_import.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['PRIMARY']}; color: white; border-radius: 20px; font-weight: 900; }}"
            f"QPushButton:hover {{ background-color: {COLORS['PRIMARY_HOVER']}; }}"
        )
        btn_import.clicked.connect(self.import_settings)

        # Verify Button (New)
        btn_verify = QPushButton("Verify Branch")
        btn_verify.setMinimumHeight(40)
        btn_verify.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['INFO']}; color: white; font-weight: 900; border-radius: 20px; }}"
            f"QPushButton:hover {{ background-color: #008992; }}"
        )
        btn_verify.clicked.connect(self.verify_branch)

        action_layout.addWidget(btn_import)
        action_layout.addWidget(btn_verify)
        action_layout.addStretch()
        action_layout.addWidget(btn_test)
        action_layout.addWidget(btn_save)

        layout.addLayout(action_layout, 6, 0, 1, 4)

        # Ensure row 6 is not squashed
        layout.setRowStretch(6, 0)

    def refresh_databases(self):
        instance = self.sql_instance.text()
        user = self.sql_user.text()
        password = self.sql_password.text() or self.controller.settings.sql_password

        if not instance:
            QMessageBox.warning(
                self, "Missing Info", "Please enter SQL Instance first."
            )
            return

        self.controller.test_sql_connection(instance, user, password)

    def import_settings(self):
        """Import settings from RMS+ Info file"""
        reply = QMessageBox.question(
            self,
            "Import Settings",
            "This will overwrite your current configuration with values from RMS+. Continue?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            success, result = self.controller.batch_runner.import_rms_settings()
            if success and isinstance(result, dict):
                # Update Controller Settings
                for k, v in result.items():
                    if hasattr(self.controller.settings, k):
                        setattr(self.controller.settings, k, v)

                # Refresh UI fully from updated settings
                self.load_state(self.controller.settings)

                QMessageBox.information(
                    self,
                    "Import Success",
                    "Settings imported from RMS+. Please Click 'Save' to persist.",
                )
            else:
                QMessageBox.warning(self, "Import Failed", f"{result}")

    def update_server_status(self, is_connected: bool, text: str):
        color = COLORS["SUCCESS"] if is_connected else COLORS["DANGER"]
        self.lbl_server_status.setText(text)
        self.lbl_server_status.setStyleSheet(
            f"font-weight: 900; color: white; border: none; border-radius: 6px; padding: 4px; background: {color};"
        )

    def load_state(self, settings: AppSettings):
        self.client_name.setText(settings.client_name or "")
        self.sql_instance.setText(settings.sql_instance or "")
        self.sql_user.setText(settings.sql_user or "")
        self.sql_password.setText(settings.sql_password or "")
        self.backup_path.setText(settings.backup_folder or r"D:\DB Backups")

        default_dbs = ["RmsBranchSrv", "RmsCashierSrv"]
        all_dbs = list(set(default_dbs + (settings.databases or [])))
        self.db_combo.set_items(all_dbs, settings.databases or [])

        all_services = list(
            set((settings.known_services or []) + (settings.services or []))
        )
        self.svc_combo.set_items(all_services, settings.services or [])

        # Load new fields with Defaults
        self.branch_code.setText(
            str(settings.branch_code) if settings.branch_code else "P001"
        )
        self.pos_number.setText(
            str(settings.pos_number) if settings.pos_number else "1"
        )
        self.api_url.setText(
            settings.api_base_url or "http://10.10.9.181:8080/rmsmainserverApi"
        )

    def browse_path(self):
        d = QFileDialog.getExistingDirectory(self, "Select Backup Folder")
        if d:
            self.backup_path.setText(d)

    def test_conn(self):
        self.controller.test_sql_connection(
            self.sql_instance.text(),
            self.sql_user.text(),
            self.sql_password.text() or self.controller.settings.sql_password,
        )

    def verify_branch(self):
        # 1. Update config first (in memory or temp)
        self.controller.settings.branch_code = self.branch_code.text().strip()
        self.controller.settings.api_base_url = self.api_url.text().strip()

        # 2. Call Logic directly via controller's batch runner (thread safe check?)
        # Ideally, we should use a worker thread to avoid freezing UI
        # But for simplicity, we call logic synchronously or wrap in a quick method

        # Using a worker thread for network call
        # Using a worker thread for network call
        self.controller.log_msg.emit("Verifying Branch Install Status...", False)

        def run_verify():
            try:
                found, msg = self.controller.batch_runner.verify_branch_install_status()
                return found, msg
            except Exception as e:
                return False, f"Crash prevented: {e}"

        worker = WorkerThread(operation_type="generic", generic_func=run_verify)
        worker.generic_result.connect(self.on_verify_complete)
        worker.start()

        # Keep reference to avoid GC
        self._verify_worker = worker

    def on_verify_complete(self, result):
        found, msg = result
        if found:
            QMessageBox.information(self, "Verification Success", msg)
        else:
            QMessageBox.warning(self, "Verification Failed", msg)

    def save(self):
        # Validation
        b_code = self.branch_code.text().strip()
        p_num = self.pos_number.text().strip()

        if not b_code:
            QMessageBox.warning(self, "Invalid Input", "Branch Code is required.")
            self.branch_code.setFocus()
            return

        if not p_num.isdigit() or len(p_num) > 2:
            QMessageBox.warning(
                self, "Invalid Input", "POS Number must be numeric (max 2 digits)."
            )
            self.pos_number.setFocus()
            return

        data = {
            "client_name": self.client_name.text(),
            "sql_instance": self.sql_instance.text(),
            "sql_user": self.sql_user.text(),
            "sql_password": self.sql_password.text()
            or self.controller.settings.sql_password,
            "backup_folder": self.backup_path.text(),
            "databases": self.db_combo.get_checked_items(),
            "services": self.svc_combo.get_checked_items(),
            "known_services": self.svc_combo.get_all_items(),
            # New fields
            "branch_code": b_code,
            "pos_number": p_num,
            "api_base_url": self.api_url.text().strip(),
        }
        self.controller.save_config(data)


class ServiceControlPanel(QGroupBox):
    def __init__(self, controller: MainController):
        super().__init__("Service Status")
        self.controller = controller
        self.cards = {}
        self.last_statuses = {}  # Cache to prevent flickering
        self.layout = QGridLayout(self)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(15, 20, 15, 15)

    def refresh_layout(self, services: List[str]):
        # Guard: Check if list actually changed to prevent resetting to "Checking..."
        if set(services) == set(self.cards.keys()) and self.cards:
            return

        # Clear existing
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.cards = {}
        self.last_statuses = {}  # Clear cache to prevent "stuck" labels after refresh

        cols = 4
        for i, svc in enumerate(services):
            card = self.create_card(svc)
            self.layout.addWidget(card, i // cols, i % cols)

    def create_card(self, name: str) -> QFrame:
        frame = QFrame()
        frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        frame.setStyleSheet(
            f"background-color: #202020; border: 1px solid {COLORS['BORDER']}; border-radius: 8px;"
        )
        frame.setFixedHeight(110)

        vbox = QVBoxLayout(frame)

        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("font-weight: bold; border: none;")

        lbl_status = QLabel("Checking...")
        lbl_status.setAlignment(Qt.AlignRight)
        lbl_status.setStyleSheet(f"color: {COLORS['TEXT_SEC']}; border: none;")

        hbox_top = QHBoxLayout()
        hbox_top.addWidget(lbl_name)
        hbox_top.addWidget(lbl_status)

        hbox_btn = QHBoxLayout()
        btn_start = QPushButton("Start")
        btn_stop = QPushButton("Stop")
        btn_restart = QPushButton("Restart")

        # Explicit Button Styles REMOVED to enforce Global Baby Blue
        # common = "font-weight: bold; border-radius: 4px; border: 1px solid"
        # Styles removed

        for b, act in [
            (btn_start, "start"),
            (btn_stop, "stop"),
            (btn_restart, "restart"),
        ]:
            b.setCursor(Qt.PointingHandCursor)
            b.setFixedHeight(34)  # Increased height
            # Use factory to capture variable
            b.clicked.connect(
                lambda checked=False, n=name, a=act: self.controller.control_service(
                    n, a
                )
            )

        hbox_btn.addWidget(btn_start)
        hbox_btn.addWidget(btn_stop)
        hbox_btn.addWidget(btn_restart)

        vbox.addLayout(hbox_top)
        vbox.addLayout(hbox_btn)

        self.cards[name] = {
            "status_lbl": lbl_status,
            "btns": {"start": btn_start, "stop": btn_stop, "restart": btn_restart},
        }
        return frame

    def update_statuses(self, status_map: dict):
        for name, status_enum in status_map.items():
            if name not in self.cards:
                continue

            # Check if status actually changed to prevent flickering
            if self.last_statuses.get(name) == status_enum:
                continue

            self.last_statuses[name] = status_enum
            w = self.cards[name]
            lbl = w["status_lbl"]
            btns = w["btns"]

            # Map Enum to UI
            text = status_enum.value.upper()

            # Helper for button style
            def set_btn_style(btn_name, active_color, is_enabled):
                btn = btns[btn_name]
                btn.setEnabled(is_enabled)
                if is_enabled:
                    # Apply background color and white text for better visibility on bold colors
                    btn.setStyleSheet(
                        f"background-color: {active_color}; color: white; border-radius: 6px; font-weight: bold;"
                    )
                else:
                    # Muted background for disabled state
                    btn.setStyleSheet(
                        f"background-color: {COLORS['DISABLED']}; color: #666; border-radius: 6px;"
                    )

            if status_enum == ServiceStatus.RUNNING:
                lbl.setText(f"✓ {text}")
                lbl.setStyleSheet(
                    f"color: {COLORS['SUCCESS']}; border: none; font-weight: 900; font-size: 13px;"
                )

                set_btn_style("start", COLORS["SUCCESS"], False)
                set_btn_style("stop", COLORS["DANGER"], True)
                set_btn_style("restart", COLORS["PRIMARY"], True)

            elif status_enum == ServiceStatus.STOPPED:
                lbl.setText(f"⏹ {text}")
                lbl.setStyleSheet(
                    f"color: {COLORS['DANGER']}; border: none; font-weight: 900; font-size: 13px;"
                )

                set_btn_style("start", COLORS["SUCCESS"], True)
                set_btn_style("stop", COLORS["DANGER"], False)
                set_btn_style("restart", COLORS["PRIMARY"], False)
            else:
                lbl.setText(f"? {text}")
                lbl.setStyleSheet(
                    f"color: {COLORS['WARNING']}; border: none; font-weight: 900; font-size: 13px;"
                )

                set_btn_style("start", COLORS["SUCCESS"], False)
                set_btn_style("stop", COLORS["DANGER"], False)
                set_btn_style("restart", COLORS["PRIMARY"], False)


class OperationsPanel(QGroupBox):
    def __init__(self, controller: MainController):
        super().__init__("Operations")
        self.controller = controller
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(30)
        main_layout.setContentsMargins(15, 20, 15, 15)

        # LEFT: BACKUP
        grp_backup = QGroupBox("Backup")
        grp_backup.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {COLORS['SECONDARY_TEAL']}; background-color: #101F1F; }} "
            f"QGroupBox::title {{ color: {COLORS['SECONDARY_TEAL']}; font-weight: 900; }}"
        )
        l_backup = QVBoxLayout(grp_backup)

        self.dbs_layout = QVBoxLayout()
        l_backup.addLayout(self.dbs_layout)

        self.config_layout = QVBoxLayout()
        l_backup.addLayout(self.config_layout)

        btn_backup = QPushButton("RUN BACKUP")
        btn_backup.setMinimumHeight(45)
        # Teal Button for Backup
        btn_backup.setStyleSheet(
            f"background-color: {COLORS['SECONDARY_TEAL']}; color: white; font-weight: bold; border-radius: 6px;"
        )
        btn_backup.clicked.connect(self.run_backup)
        l_backup.addStretch()
        l_backup.addWidget(btn_backup)

        # RIGHT: RESTORE
        grp_restore = QGroupBox("Restore")
        grp_restore.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {COLORS['SECONDARY_AMBER']}; background-color: #1F1B10; }} "
            f"QGroupBox::title {{ color: {COLORS['SECONDARY_AMBER']}; font-weight: 900; }}"
        )
        l_restore = QGridLayout(grp_restore)

        l_restore.addWidget(QLabel("Type:"), 0, 0)
        self.res_type = QComboBox()
        self.res_type.addItems(["Branch", "Cashier"])
        self.res_type.currentIndexChanged.connect(self.update_target_preview)
        l_restore.addWidget(self.res_type, 0, 1)

        l_restore.addWidget(QLabel("Target DB:"), 1, 0)
        self.res_target = QLineEdit()
        self.res_target.setPlaceholderText("Target Database Name")
        self.res_target.setToolTip("Editable: Use [ClientName]_[DBName] format")
        l_restore.addWidget(self.res_target, 1, 1)

        l_restore.addWidget(QLabel("Backup File:"), 2, 0)
        self.res_file = QLineEdit()
        btn_res_browse = QPushButton("...")
        btn_res_browse.setFixedSize(40, 30)
        # Helper style for Browse Buttons
        browse_style = f"background-color: {COLORS['INFO']}; color: white; font-weight: bold; border-radius: 4px;"
        btn_res_browse.setStyleSheet(browse_style)
        btn_res_browse.clicked.connect(self.browse_bak)
        hb_file = QHBoxLayout()
        hb_file.addWidget(self.res_file)
        hb_file.addWidget(btn_res_browse)
        l_restore.addLayout(hb_file, 2, 1)

        l_restore.addWidget(QLabel("DB Files Path:"), 3, 0)
        self.db_path = QLineEdit()
        btn_db = QPushButton("...")
        btn_db.setFixedSize(40, 30)
        btn_db.setStyleSheet(browse_style)
        btn_db.clicked.connect(lambda: self.browse_folder(self.db_path))
        hb_db = QHBoxLayout()
        hb_db.addWidget(self.db_path)
        hb_db.addWidget(btn_db)
        l_restore.addLayout(hb_db, 3, 1, 1, 1)

        btn_restore = QPushButton("RESTORE DATABASE")
        btn_restore.setMinimumHeight(45)
        # Amber Button for Restore
        btn_restore.setStyleSheet(
            f"background-color: {COLORS['SECONDARY_AMBER']}; color: white; font-weight: bold; border-radius: 6px;"
        )
        btn_restore.clicked.connect(self.run_restore)
        l_restore.addWidget(btn_restore, 5, 0, 1, 2)
        l_restore.setRowStretch(6, 1)

        main_layout.addWidget(grp_backup, 1)
        main_layout.addWidget(grp_restore, 1)

    def load_state(self, settings: AppSettings):
        self.client_name = settings.client_name
        self.update_target_preview()

        # Populate Backup Checkboxes
        # Clear
        while self.dbs_layout.count():
            self.dbs_layout.takeAt(0).widget().deleteLater()
        while self.config_layout.count():
            self.config_layout.takeAt(0).widget().deleteLater()

        self.chk_dbs = []
        for db in ["RmsBranchSrv", "RmsCashierSrv"]:
            chk = QCheckBox(f"{db} Database")
            chk.setObjectName(db)
            chk.setStyleSheet(
                f"QCheckBox {{ font-weight: 600; color: white; }} QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {COLORS['BORDER']}; background: #222; border-radius: 4px; }} QCheckBox::indicator:checked {{ background: {COLORS['SUCCESS']}; image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4='); }}"
            )
            chk.setChecked(True)
            self.chk_dbs.append(chk)
            self.dbs_layout.addWidget(chk)

        self.chk_configs = []
        if settings.appsettings_files:
            for item in settings.appsettings_files:
                name = item.get("name", "Unknown")
                chk = QCheckBox(name)
                chk.setObjectName(name)
                chk.setStyleSheet(
                    f"QCheckBox {{ font-weight: 600; color: white; }} QCheckBox::indicator {{ width: 18px; height: 18px; border: 1px solid {COLORS['BORDER']}; background: #222; border-radius: 4px; }} QCheckBox::indicator:checked {{ background: {COLORS['SUCCESS']}; image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4='); }}"
                )
                chk.setChecked(True)
                self.chk_configs.append(chk)
                self.config_layout.addWidget(chk)

        if settings.mdf_path:
            self.db_path.setText(settings.mdf_path)
        else:
            self.db_path.setText(r"D:\DB Backups")

    def update_target_preview(self):
        # Update client name from config panel if available
        prefix = self.controller.settings.client_name or "UPC"
        t = self.res_type.currentText()
        suffix = "RmsBranchSrv" if "Branch" in t else "RmsCashierSrv"
        self.res_target.setText(f"{prefix}_{suffix}")
        self.res_target.setReadOnly(False)  # Allow manual editing

    def browse_bak(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Select Backup", filter="SQL Backup (*.bak)"
        )
        if f:
            self.res_file.setText(f)

    def browse_folder(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, "Select Folder")
        if d:
            line_edit.setText(d)

    def run_backup(self):
        dbs = [c.objectName() for c in self.chk_dbs if c.isChecked()]
        cfgs = [c.objectName() for c in self.chk_configs if c.isChecked()]

        if not dbs and not cfgs:
            QMessageBox.warning(
                self,
                "Selection",
                "Please select at least one database or file to backup.",
            )
            return

        self.controller.execute_operation(
            "backup", selected_dbs=dbs, selected_appsettings=cfgs
        )

    def run_restore(self):
        path = self.db_path.text()
        data = {
            "target_db": self.res_target.text(),
            "backup_path": self.res_file.text(),
            "mdf_path": path,
            "ldf_path": path,
        }
        if not data["backup_path"]:
            QMessageBox.warning(self, "Input", "Please select a backup file.")
            return

        self.controller.execute_operation("restore", **data)

        # Persist paths
        self.controller.save_config({"mdf_path": path, "ldf_path": path})


class CleanupPanel(QGroupBox):
    def __init__(self, controller: MainController):
        super().__init__("Danger Zone")
        self.controller = controller
        # Distinct Red Border for Danger Zone
        self.setStyleSheet(
            f"QGroupBox {{ border: 1px solid {COLORS['DANGER']}; margin-top: 1em; background-color: #1A0A0A; }} "
            f"QGroupBox::title {{ color: {COLORS['DANGER']}; font-weight: 900; subcontrol-origin: margin; left: 10px; padding: 0 5px; }}"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Warning Label (Top)
        lbl = QLabel(
            "⚠️ WARNING: This action is irreversible. It stops services and clears logs."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLORS['DANGER']}; font-weight: bold;")

        # Controls Row (Bottom)
        hbox_controls = QHBoxLayout()

        # Safety Checkbox
        self.chk_confirm = QCheckBox("I understand the risks")
        self.chk_confirm.setStyleSheet(
            f"QCheckBox {{ font-weight: 900; color: {COLORS['DANGER']}; font-size: 13px; }} "
            f"QCheckBox::indicator {{ width: 22px; height: 22px; border: 2px solid {COLORS['DANGER']}; background: #2D1A1A; border-radius: 4px; }} "
            f"QCheckBox::indicator:checked {{ background: {COLORS['DANGER']}; image: url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik05IDE2LjE3TDQuODMgMTJsLTEuNDIgMS40MUw5IDE5IDIxIDdsLTEuNDEtMS40MXoiLz48L3N2Zz4='); }}"
        )
        self.chk_confirm.setCursor(Qt.PointingHandCursor)
        self.chk_confirm.stateChanged.connect(self.on_check_changed)

        # Action Buttons
        self.btn_cleanup = QPushButton("Cleanup")
        self.btn_cleanup.setEnabled(False)
        self.btn_cleanup.clicked.connect(self.run_cleanup)
        self.btn_cleanup.setStyleSheet(
            f"""
            QPushButton {{ background-color: {COLORS['DANGER']}; color: white; border: none; font-weight: bold; border-radius: 6px; padding: 10px; }}
            QPushButton:hover {{ background-color: #C53030; }}
            QPushButton:disabled {{ background-color: #2D1A1A; color: #666; }}
            """
        )

        self.btn_uninstall_branch = QPushButton("Uninstall Branch")
        self.btn_uninstall_branch.setEnabled(False)
        self.btn_uninstall_branch.clicked.connect(self.run_uninstall_branch)
        self.btn_uninstall_branch.setStyleSheet(
            f"""
            QPushButton {{ background-color: {COLORS['DANGER']}; color: white; border: none; font-weight: bold; border-radius: 6px; padding: 10px; }}
            QPushButton:hover {{ background-color: #C53030; }}
            QPushButton:disabled {{ background-color: #2D1A1A; color: #666; }}
            """
        )

        self.btn_uninstall_pos = QPushButton("Uninstall POS")
        self.btn_uninstall_pos.setEnabled(False)
        self.btn_uninstall_pos.clicked.connect(self.run_uninstall_pos)
        self.btn_uninstall_pos.setStyleSheet(
            f"""
            QPushButton {{ background-color: {COLORS['DANGER']}; color: white; border: none; font-weight: bold; border-radius: 6px; padding: 10px; }}
            QPushButton:hover {{ background-color: #C53030; }}
            QPushButton:disabled {{ background-color: #2D1A1A; color: #666; }}
            """
        )

        hbox_controls.addWidget(self.chk_confirm)

        hbox_controls.addWidget(self.btn_cleanup)
        hbox_controls.addWidget(self.btn_uninstall_branch)
        hbox_controls.addWidget(self.btn_uninstall_pos)

        layout.addWidget(lbl)
        layout.addLayout(hbox_controls)

    def on_check_changed(self):
        # Simplified Logic: only checkbox required to enable buttons
        is_safe = self.chk_confirm.isChecked()
        self.btn_cleanup.setEnabled(is_safe)
        self.btn_uninstall_branch.setEnabled(is_safe)
        self.btn_uninstall_pos.setEnabled(is_safe)

    def run_cleanup(self):
        if (
            QMessageBox.question(
                self,
                "Confirm Cleanup",
                "Are you sure? This will stop services and delete files.",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.controller.execute_operation("cleanup")

    def run_uninstall_branch(self):
        b_code = self.controller.settings.branch_code
        if not b_code:
            QMessageBox.critical(self, "Config Error", "Branch Code is not configured.")
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Uninstall",
                f"Are you sure you want to uninstall Branch {b_code}?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.controller.execute_operation("uninstall_branch")

    def run_uninstall_pos(self):
        b_code = self.controller.settings.branch_code
        p_num = self.controller.settings.pos_number
        if not b_code or not p_num:
            QMessageBox.critical(
                self, "Config Error", "Branch Code or POS Number is not configured."
            )
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Uninstall",
                f"Are you sure you want to uninstall POS Machine {p_num} at Branch {b_code}?",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.controller.execute_operation("uninstall_pos")


# ===== MAIN WINDOW =====


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("mainWindow")
        self.controller = MainController()
        self.init_ui()
        self.bind_controller()

        # Startup
        self.controller.start_app()

        # Auto-Update Check (Silent)
        QTimer.singleShot(2000, lambda: self.check_for_updates(silent=True))

    def init_ui(self):
        from app.config import TOOL_VERSION

        release_num = self.controller.batch_runner.get_release_number()
        self.setWindowTitle(
            f"RMS+ | POS Admin Tool v{TOOL_VERSION} (POS Release {release_num})"
        )
        # Allow resizing smaller than content
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # Set Window Icon for Taskbar Consistency
        from app.utils import resource_path

        icon_path = resource_path(os.path.join("assets", "icons", "app_icon.ico"))
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(
            f"""
            QMainWindow#mainWindow, QWidget#centralWidget {{
                background-color: {COLORS['BG']};
                font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
                font-size: 14px;
            }}
            QLabel {{
                color: {COLORS['TEXT_PRI']};
            }}
            QLineEdit, QTextEdit, QComboBox {{
                background-color: #202020;
                border: 1px solid {COLORS['BORDER']};
                border-radius: 4px;
                padding: 6px;
                color: {COLORS['TEXT_PRI']};
                selection-background-color: {COLORS['PRIMARY']};
            }}
            QLineEdit:focus, QComboBox:focus {{
                border: 1px solid {COLORS['PRIMARY']};
            }}
            QPushButton {{
                background-color: {COLORS['PRIMARY']};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['PRIMARY_HOVER']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['PRIMARY_PRESSED']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['DISABLED']};
                color: #666666;
            }}
            QGroupBox {{
                font-weight: 800;
                font-size: 15px;
                border: 1px solid {COLORS['BORDER']};
                border-radius: 8px;
                margin-top: 25px;
                background-color: {COLORS['CARD_BG']};
                padding: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 10px;
                color: {COLORS['PRIMARY']};
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 30px;
                background: #333333;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QComboBox::down-arrow {{
                image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdib3g9IjAgMCAyNCAyNCIgZmlsbD0id2hpdGUiPjxwYXRoIGQ9Ik03IDEwbNSA1IDUtNXoiLz48L3N2Zz4=");
                width: 14px;
                height: 14px;
            }}
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
            QScrollBar:vertical {{
                border: none;
                background: {COLORS['BG']};
                width: 12px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #444444;
                min-height: 20px;
                border: none;
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #555555;
            }}
            QMessageBox {{
                background-color: #161616;
                color: #FFFFFF;
            }}
            QMessageBox QLabel {{
                color: #FFFFFF;
                font-size: 14px;
            }}
            QMessageBox QPushButton {{
                min-width: 80px;
                min-height: 25px;
            }}
            """
        )

        # Main Container (Not Scrollable)
        main_container = QWidget()
        main_container.setObjectName("mainWindowContainer")
        self.setCentralWidget(main_container)

        # Top Level Layout (Vertical)
        # Header (Fixed) -> Scroll Area (Flexible)
        root_layout = QVBoxLayout(main_container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ==========================
        # 1. HEADER SECTION (FIXED)
        # ==========================
        header_widget = QWidget()
        # Add background color to header to ensure opacity over content if needed (though layout prevents overlap)
        header_widget.setStyleSheet(
            f"background-color: {COLORS['BG']}; border-bottom: 1px solid {COLORS['BORDER']};"
        )
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 10, 20, 15)  # Comfortable padding

        # Title Block
        title_widget = QWidget()
        title_layout = QVBoxLayout(title_widget)
        title_layout.setSpacing(0)
        title_layout.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("Digital Business Systems (DBS)")
        lbl_title.setStyleSheet(
            "font-size: 28px; font-weight: 900; color: #FFFFFF; letter-spacing: 1px;"
        )

        from app.config import TOOL_VERSION

        lbl_subtitle = QLabel(
            f"RMS+ POS Admin Tool v{TOOL_VERSION} - Enterprise Edition"
        )
        lbl_subtitle.setStyleSheet(
            f"font-size: 14px; font-weight: 400; color: {COLORS['TEXT_SEC']}; margin-top: -5px;"
        )

        # Release Info
        release_num = self.controller.batch_runner.get_release_number()
        lbl_release = QLabel(f"POS Installed Release: {release_num}")
        lbl_release.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {COLORS['TEXT_SEC']}; margin-top: 2px;"
        )

        # Environment Badge
        from app.network_utils import ConnectivityMonitor, EnvironmentDetector

        # Detect Environment
        env_path = self.controller.settings.env_config_path
        self.env_type = EnvironmentDetector.detect(env_path)
        env_color = (
            COLORS["SUCCESS"] if self.env_type == "PRODUCTION" else COLORS["WARNING"]
        )

        lbl_env = QLabel(self.env_type)
        lbl_env.setStyleSheet(
            f"background-color: {env_color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 12px;"
        )

        title_layout.addWidget(lbl_title)
        title_layout.addWidget(lbl_subtitle)

        # Row for Release and Env
        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 2, 0, 0)
        meta_layout.setSpacing(10)
        meta_layout.addWidget(lbl_release)
        meta_layout.addWidget(lbl_env)
        meta_layout.addStretch()

        title_layout.addWidget(meta_row)

        # Buttons
        # POS Prerequisites Button
        btn_prereqs = QPushButton("POS Prerequisites")
        btn_prereqs.setCursor(Qt.PointingHandCursor)
        btn_prereqs.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['INFO']}; color: white; padding: 10px 20px; border-radius: 25px; font-weight: 900; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}"
            f"QPushButton:hover {{ background-color: #0369A1; margin-top: -2px; }}"
            f"QPushButton:pressed {{ background-color: #075985; margin-top: 0px; }}"
        )
        btn_prereqs.clicked.connect(self.open_prereqs)

        # Extract POS Setup Button
        btn_extract = QPushButton("Extract POS Setup")
        btn_extract.setCursor(Qt.PointingHandCursor)
        btn_extract.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['SUCCESS']}; color: white; padding: 10px 20px; border-radius: 25px; font-weight: 900; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}"
            f"QPushButton:hover {{ background-color: #0D6429; margin-top: -2px; }}"
            f"QPushButton:pressed {{ background-color: #0A4F20; margin-top: 0px; }}"
        )
        btn_extract.clicked.connect(self.extract_pos_setup)

        # Docs Button
        btn_docs = QPushButton("Open Documentation")
        btn_docs.setCursor(Qt.PointingHandCursor)
        btn_docs.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['PRIMARY']}; color: white; padding: 10px 20px; border-radius: 25px; font-weight: 900; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}"
            f"QPushButton:hover {{ background-color: {COLORS['PRIMARY_HOVER']}; margin-top: -2px; }}"
            f"QPushButton:pressed {{ background-color: {COLORS['PRIMARY_PRESSED']}; margin-top: 0px; }}"
        )
        btn_docs.clicked.connect(self.open_docs)

        # Update Button
        btn_update = QPushButton("Check for Updates")
        btn_update.setCursor(Qt.PointingHandCursor)
        btn_update.setStyleSheet(
            f"QPushButton {{ background-color: {COLORS['SECONDARY_TEAL']}; color: white; padding: 10px 20px; border-radius: 25px; font-weight: 900; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}"
            f"QPushButton:hover {{ background-color: #0D9488; margin-top: -2px; }}"
            f"QPushButton:pressed {{ background-color: #0F766E; margin-top: 0px; }}"
        )
        btn_update.clicked.connect(self.check_for_updates)

        header_layout.addWidget(title_widget)
        header_layout.addStretch()
        header_layout.addWidget(btn_update)
        header_layout.addSpacing(10)
        header_layout.addWidget(btn_extract)
        header_layout.addSpacing(10)
        header_layout.addWidget(btn_prereqs)
        header_layout.addSpacing(10)
        header_layout.addWidget(btn_docs)

        # Add Header to Root Layout
        root_layout.addWidget(header_widget)

        # ==========================
        # 2. SCROLLABLE CONTENT AREA
        # ==========================
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Remove border from scroll area itself to blend in
        scroll.setFrameShape(QFrame.NoFrame)

        # The widget that holds all the panels
        scroll_content = QWidget()
        scroll_content.setObjectName(
            "centralWidget"
        )  # Keep specific styling for content area
        # Enforce minimum width if needed
        scroll_content.setMinimumWidth(1600)

        # Layout for the scrollable content
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        # Panels
        self.config_panel = ConfigurationPanel(self.controller)
        self.service_panel = ServiceControlPanel(self.controller)
        self.ops_panel = OperationsPanel(self.controller)
        self.cleanup_panel = CleanupPanel(self.controller)

        # Log Panel
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet(
            f"background-color: #0A0A0A; color: #4AF626; border: 1px solid {COLORS['BORDER']}; "
            "border-radius: 6px; font-family: 'Consolas', 'Courier New', monospace; font-size: 13px; padding: 10px;"
        )
        self.log_area.setMaximumHeight(250)

        # Add all to content layout
        content_layout.addWidget(self.config_panel)
        content_layout.addWidget(self.service_panel)
        content_layout.addWidget(self.ops_panel)
        content_layout.addWidget(self.cleanup_panel)
        content_layout.addWidget(self.log_area)

        # Finalize Scroll Area
        scroll.setWidget(scroll_content)

        # Add Scroll Area to Root Layout (below header)
        root_layout.addWidget(scroll)

        # Initialize Connectivity Monitor
        self.conn_monitor = ConnectivityMonitor()
        self.conn_monitor.status_changed.connect(self.on_conn_status_changed)
        self.conn_monitor.start()

    def on_conn_status_changed(self, is_connected: bool, text: str):
        self.config_panel.update_server_status(is_connected, text)

    def bind_controller(self):
        # State -> UI
        self.controller.config_loaded.connect(self.config_panel.load_state)
        self.controller.config_loaded.connect(self.on_config_loaded)  # Extra bindings

        # Logs
        self.controller.log_msg.connect(self.append_log)

        # Service Status
        self.controller.service_status_updated.connect(
            self.service_panel.update_statuses
        )

        # Op Events (block UI?)
        self.controller.op_started.connect(lambda: self.set_busy(True))
        self.controller.op_finished.connect(self.on_op_finished)

    def closeEvent(self, event):
        self.conn_monitor.stop()  # Stop thread on exit
        self.controller.shutdown()
        event.accept()

    def on_config_loaded(self, settings: AppSettings):
        # Update Connectivity Monitor Target
        if settings.api_base_url:
            self.conn_monitor.set_target_from_url(settings.api_base_url)

        # Pass services to service panel to rebuild grid
        self.service_panel.refresh_layout(settings.services)
        self.ops_panel.load_state(settings)

    def append_log(self, msg: str, is_error: bool):
        ts = datetime.now().strftime("%H:%M:%S")
        color = "red" if is_error else "#0F0"
        self.log_area.append(
            f'<span style="color:gray">[{ts}]</span> <span style="color:{color}">{msg}</span>'
        )

    def set_busy(self, busy: bool):
        self.centralWidget().setEnabled(not busy)
        if busy:
            QApplication.setOverrideCursor(Qt.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()

    def on_op_finished(self, result: OperationResult):
        self.set_busy(False)
        if result.status == OperationStatus.FAILED:
            errors = "\n".join(result.errors)
            QMessageBox.critical(
                self,
                "Operation Failed",
                f"Errors:\n{result.operation_type.title()} failed.\n\n{errors}",
            )
        else:
            QMessageBox.information(
                self, "Success", "Operation completed successfully."
            )

    def open_prereqs(self):
        try:
            url = "https://drive.google.com/drive/folders/11RAkduhKXDrX8R2Tq2TRGbRdbd9-q9-z"
            QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open link:\\n{str(e)}")

    def open_docs(self):
        try:
            # Determine path whether running from source or frozen EXE
            if getattr(sys, "frozen", False):
                # If the application is run as a bundle, the PyInstaller bootloader
                # extends the sys module by a flag frozen=True and sets the app
                # path into variable _MEIPASS.
                base_path = sys._MEIPASS
            else:
                base_path = os.path.abspath(".")

            docs_path = os.path.join(base_path, "README.txt")

            if os.path.exists(docs_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(docs_path))
            else:
                QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"Documentation file not found at:\\n{docs_path}",
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Could not open documentation:\\n{str(e)}"
            )

    def extract_pos_setup(self):
        """Extract POS Setup - Zip RMS_Plus folder and move to D:\\ drive"""
        client_name = self.controller.settings.client_name
        release_number = self.controller.batch_runner.get_release_number()

        if not client_name:
            QMessageBox.warning(
                self,
                "Configuration Required",
                "Client Name is not configured. Please set the Client Name in Configuration first.",
            )
            return

        if release_number in ("N/A", "ERR"):
            QMessageBox.warning(
                self,
                "Release Number Not Found",
                "Could not read the release number from C:\\ProgramData\\RMS_Plus\\ReleaseNumber.txt",
            )
            return

        # Confirm action
        zip_name = f"{client_name}_POS_Release_v.{release_number}.zip"
        reply = QMessageBox.question(
            self,
            "Extract POS Setup",
            f"This will create:\nD:\\{zip_name}\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Run in worker thread to avoid UI freeze
        self.set_busy(True)

        def run_extract():
            return self.controller.batch_runner.extract_pos_setup(
                client_name, release_number
            )

        worker = WorkerThread(operation_type="generic", generic_func=run_extract)
        worker.generic_result.connect(self.on_extract_complete)
        worker.start()

        # CRITICAL FIX: Keep reference to prevent garbage collection causing crash
        self._extract_worker = worker

    def check_for_updates(self, silent=False):
        from app.updater import UpdateChecker
        from app.config import TOOL_VERSION

        # Visual feedback
        if not silent:
            self.set_busy(True)

        def check():
            return UpdateChecker.check_update(TOOL_VERSION)

        worker = WorkerThread(operation_type="generic", generic_func=check)
        worker.generic_result.connect(
            lambda res: self.on_update_check_complete(res, silent)
        )
        worker.start()
        self._update_worker = worker  # Keep reference

    def on_update_check_complete(self, result, silent):
        if not silent:
            self.set_busy(False)
        is_available, url, tag = result

        if is_available:
            reply = QMessageBox.question(
                self,
                "Update Available",
                f"A new version ({tag}) is available!\n\nWould you like to download it now?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes and url:
                QDesktopServices.openUrl(QUrl(url))
        elif not silent:
            QMessageBox.information(
                self, "Up to Date", "You are using the latest version."
            )

    def on_extract_complete(self, result):
        self.set_busy(False)
        success, msg = result
        if success:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Export Failed", msg)
