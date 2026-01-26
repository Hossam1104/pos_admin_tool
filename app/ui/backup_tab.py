"""
Backup operations tab UI component
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Signal


class BackupTab(QWidget):
    """Backup operations tab UI"""

    # Signals
    backup_requested = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

        # Current configuration display
        config_group = QGroupBox("Backup Configuration")
        config_layout = QFormLayout()

        config_layout.addRow("Backup Folder:", QLabel(self.settings.backup_folder))
        config_layout.addRow("Databases:", QLabel(", ".join(self.settings.databases)))

        # AppSettings files
        appsets_text = "\n".join(
            [
                f"{item['name']}: {item['path']}"
                for item in self.settings.appsettings_files
            ]
        )
        appsets_label = QLabel(appsets_text)
        appsets_label.setWordWrap(True)
        config_layout.addRow("AppSettings Files:", appsets_label)

        config_group.setLayout(config_layout)
        layout.addWidget(config_group)

        # Execute button
        self.backup_btn = QPushButton("Execute Backup")
        self.backup_btn.setStyleSheet(
            "background-color: #388e3c; color: white; font-weight: bold; padding: 10px;"
        )
        self.backup_btn.clicked.connect(lambda: self.backup_requested.emit())
        layout.addWidget(self.backup_btn)

        layout.addStretch()

    def set_backup_enabled(self, enabled: bool):
        """Enable or disable backup button"""
        self.backup_btn.setEnabled(enabled)
