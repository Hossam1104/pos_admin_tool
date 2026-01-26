"""
Database restore tab UI component
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QComboBox,
    QPushButton,
    QListWidget,
)
from PySide6.QtCore import Signal


class RestoreTab(QWidget):
    """Database restore tab UI"""

    # Signals
    backup_browsed = Signal()
    backup_file_selected = Signal(str)
    restore_requested = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

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
        self.backup_browse_btn.clicked.connect(lambda: self.backup_browsed.emit())
        backup_layout.addWidget(self.backup_path_input)
        backup_layout.addWidget(self.backup_browse_btn)
        form_layout.addRow("Backup File:", backup_layout)

        # Backup files list
        self.backup_list = QListWidget()
        self.backup_list.itemClicked.connect(self._on_backup_selected)
        form_layout.addRow("Available Backups:", self.backup_list)

        layout.addLayout(form_layout)

        # Restore button
        self.restore_btn = QPushButton("Restore Database")
        self.restore_btn.setStyleSheet(
            "background-color: #1976d2; color: white; font-weight: bold; padding: 10px;"
        )
        self.restore_btn.clicked.connect(lambda: self.restore_requested.emit())
        layout.addWidget(self.restore_btn)

        layout.addStretch()

    def _on_backup_selected(self, item):
        """Handle backup file selection from list"""
        text = item.text()
        if ")" in text:
            # Extract file number and emit signal
            file_num = text.split(")")[0].strip()
            self.backup_file_selected.emit(file_num)

    def get_restore_data(self):
        """Get restore parameters from UI"""
        return {
            "client_name": self.client_name_input.text().strip(),
            "db_choice": (
                "1" if self.db_choice_combo.currentText() == "RmsBranchSrv" else "2"
            ),
            "backup_path": self.backup_path_input.text().strip(),
        }

    def set_backup_path(self, path: str):
        """Set backup path in UI"""
        self.backup_path_input.setText(path)

    def clear_backup_list(self):
        """Clear backup files list"""
        self.backup_list.clear()

    def add_backup_item(self, text: str):
        """Add item to backup files list"""
        self.backup_list.addItem(text)

    def set_restore_enabled(self, enabled: bool):
        """Enable or disable restore button"""
        self.restore_btn.setEnabled(enabled)
