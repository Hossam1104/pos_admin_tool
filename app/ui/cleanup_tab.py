"""
Cleanup operations tab UI component
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QTextEdit,
    QCheckBox,
    QPushButton,
    QLabel,
)
from PySide6.QtCore import Qt, Signal


class CleanupTab(QWidget):
    """Cleanup operations tab UI"""

    # Signals
    cleanup_requested = Signal()

    def __init__(self, folders_to_delete):
        super().__init__()
        self.folders_to_delete = folders_to_delete
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

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
        self.folders_input.setPlainText("\n".join(self.folders_to_delete))
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
        self.cleanup_btn.clicked.connect(lambda: self.cleanup_requested.emit())
        layout.addWidget(self.cleanup_btn)

        layout.addStretch()

    def get_folders(self):
        """Get folders list from UI"""
        text = self.folders_input.toPlainText().strip()
        return [f.strip() for f in text.split("\n") if f.strip()]

    def is_confirmed(self):
        """Check if user confirmed the operation"""
        return self.confirm_checkbox.isChecked()

    def set_cleanup_enabled(self, enabled: bool):
        """Enable or disable cleanup button"""
        self.cleanup_btn.setEnabled(enabled)
