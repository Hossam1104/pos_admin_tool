"""
Services monitoring tab UI component
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QLabel,
    QPushButton,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont


class ServicesTab(QWidget):
    """Services monitoring tab UI"""

    # Signals
    service_control_requested = Signal(str, str)  # service_name, action
    start_all_requested = Signal()
    stop_all_requested = Signal()
    refresh_requested = Signal()

    def __init__(self, service_names):
        super().__init__()
        self.service_names = service_names
        self.service_widgets = {}
        self.init_ui()

    def init_ui(self):
        """Initialize the UI"""
        layout = QVBoxLayout(self)

        # Create service status widgets
        for service in self.service_names:
            service_widget = self.create_service_widget(service)
            layout.addWidget(service_widget)

        layout.addStretch()

        # Control buttons
        control_layout = QHBoxLayout()
        start_all_btn = QPushButton("Start All Services")
        stop_all_btn = QPushButton("Stop All Services")
        refresh_btn = QPushButton("Refresh Status")

        start_all_btn.clicked.connect(lambda: self.start_all_requested.emit())
        stop_all_btn.clicked.connect(lambda: self.stop_all_requested.emit())
        refresh_btn.clicked.connect(lambda: self.refresh_requested.emit())

        control_layout.addWidget(start_all_btn)
        control_layout.addWidget(stop_all_btn)
        control_layout.addWidget(refresh_btn)
        control_layout.addStretch()

        layout.addLayout(control_layout)

    def create_service_widget(self, service_name: str) -> QFrame:
        """Create a widget for a single service"""
        service_frame = QFrame()
        service_frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        service_layout = QHBoxLayout(service_frame)

        service_label = QLabel(service_name)
        service_label.setFont(QFont("Arial", 10, QFont.Bold))

        status_label = QLabel("Unknown")
        status_label.setFont(QFont("Arial", 10))
        status_label.setObjectName(f"status_{service_name}")

        start_btn = QPushButton("Start")
        stop_btn = QPushButton("Stop")
        restart_btn = QPushButton("Restart")

        # Connect buttons
        start_btn.clicked.connect(
            lambda: self.service_control_requested.emit(service_name, "start")
        )
        stop_btn.clicked.connect(
            lambda: self.service_control_requested.emit(service_name, "stop")
        )
        restart_btn.clicked.connect(
            lambda: self.service_control_requested.emit(service_name, "restart")
        )

        # Store widget references
        self.service_widgets[service_name] = {
            "label": status_label,
            "start": start_btn,
            "stop": stop_btn,
            "restart": restart_btn,
        }

        service_layout.addWidget(service_label)
        service_layout.addWidget(status_label)
        service_layout.addStretch()
        service_layout.addWidget(start_btn)
        service_layout.addWidget(stop_btn)
        service_layout.addWidget(restart_btn)

        return service_frame

    def update_service_status(self, service_name: str, status: str, color: str):
        """Update service status display"""
        if service_name in self.service_widgets:
            widgets = self.service_widgets[service_name]
            widgets["label"].setText(status)
            widgets["label"].setStyleSheet(f"color: {color}; font-weight: bold;")

    def update_service_buttons(self, service_name: str, is_running: bool):
        """Update service control button states"""
        if service_name in self.service_widgets:
            widgets = self.service_widgets[service_name]
            widgets["start"].setEnabled(not is_running)
            widgets["stop"].setEnabled(is_running)
            widgets["restart"].setEnabled(is_running)
