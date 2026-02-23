from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.controllers.hosts_controller import HostsController


class HostsView(QWidget):
    """/etc/hosts file editor with quick-add support."""

    def __init__(self, controller: HostsController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F4DD  Hosts File (/etc/hosts)")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._save_btn = QPushButton("\U0001F4BE  Save")
        self._reload_btn = QPushButton("\U0001F504  Reload")
        toolbar.addWidget(self._save_btn)
        toolbar.addWidget(self._reload_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Text editor
        self._editor = QPlainTextEdit()
        self._editor.setFont(QFont("Monospace", 11))
        self._editor.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #d4d4d4;"
            " border: 1px solid #3a3a3a; border-radius: 4px;"
            " padding: 8px; }"
        )
        self._editor.setTabStopDistance(32)
        self._editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(self._editor)

        # Quick-add row
        quick_row = QHBoxLayout()
        quick_row.setSpacing(8)
        quick_row.addWidget(QLabel("Quick Add:"))

        quick_row.addWidget(QLabel("IP:"))
        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText("192.168.1.100")
        self._ip_input.setMaximumWidth(180)
        quick_row.addWidget(self._ip_input)

        quick_row.addWidget(QLabel("Hostname:"))
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("myserver.local")
        self._host_input.setMaximumWidth(250)
        quick_row.addWidget(self._host_input)

        self._add_btn = QPushButton("\u2795  Add")
        self._add_btn.clicked.connect(self._on_quick_add)
        quick_row.addWidget(self._add_btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

    def _connect_signals(self) -> None:
        self._ctrl.hosts_loaded.connect(self._on_loaded)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._save_btn.clicked.connect(self._on_save)
        self._reload_btn.clicked.connect(self._ctrl.load_hosts)

    def _on_loaded(self, content: str) -> None:
        self._editor.setPlainText(content)

    def _on_save(self) -> None:
        content = self._editor.toPlainText()
        reply = QMessageBox.question(
            self,
            "Save Hosts File",
            "Save changes to /etc/hosts?\n\nThis requires sudo privileges.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.save_hosts(content)

    def _on_quick_add(self) -> None:
        ip = self._ip_input.text().strip()
        hostname = self._host_input.text().strip()
        if not ip or not hostname:
            QMessageBox.warning(
                self, "Validation", "Both IP and Hostname are required."
            )
            return
        # Append to editor
        current = self._editor.toPlainText()
        if current and not current.endswith("\n"):
            current += "\n"
        current += f"{ip}\t{hostname}\n"
        self._editor.setPlainText(current)
        self._ip_input.clear()
        self._host_input.clear()
