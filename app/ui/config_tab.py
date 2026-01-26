"""
Configuration tab UI component
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QLabel,
)
from PySide6.QtCore import Signal


class ConfigTab(QWidget):
    """Configuration tab UI"""

    # Signals
    save_requested = Signal()
    backup_folder_browsed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

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
        self.backup_folder_browse.clicked.connect(
            lambda: self.backup_folder_browsed.emit()
        )

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
        save_btn.clicked.connect(lambda: self.save_requested.emit())
        layout.addWidget(save_btn)

    def get_settings(self):
        """Get current UI values as settings dict"""
        return {
            "sql_instance": self.sql_instance_input.text(),
            "sql_user": self.sql_user_input.text(),
            "sql_password": self.sql_password_input.text(),
            "services": [
                s.strip()
                for s in self.services_input.toPlainText().split("\n")
                if s.strip()
            ],
            "databases": [
                d.strip()
                for d in self.databases_input.toPlainText().split("\n")
                if d.strip()
            ],
            "backup_folder": self.backup_folder_input.text(),
        }

    def set_backup_folder(self, folder_path: str):
        """Set backup folder path"""
        self.backup_folder_input.setText(folder_path)
