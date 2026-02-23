from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from app.models.server import Server


class ServerDialog(QDialog):
    """Modal dialog for adding or editing a server."""

    def __init__(self, server: Server | None = None, parent=None):
        super().__init__(parent)
        self._server = server or Server()
        self.setWindowTitle(
            "\u270F\uFE0F  Edit Server" if server else "\u2795  Add Server"
        )
        self.setMinimumWidth(450)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Title
        title = QLabel(
            "\U0001F5A5  Server Configuration"
        )
        title.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #e0e0e0; padding-bottom: 8px;"
        )
        layout.addRow(title)

        self._name_edit = QLineEdit(self._server.name)
        self._name_edit.setPlaceholderText("My production server")
        layout.addRow("Name:", self._name_edit)

        self._host_edit = QLineEdit(self._server.host)
        self._host_edit.setPlaceholderText("192.168.1.100 or server.example.com")
        layout.addRow("Host / IP:", self._host_edit)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1, 65535)
        self._port_spin.setValue(self._server.port)
        layout.addRow("SSH Port:", self._port_spin)

        self._username_edit = QLineEdit(self._server.username)
        self._username_edit.setPlaceholderText("root")
        layout.addRow("Username:", self._username_edit)

        self._auth_combo = QComboBox()
        self._auth_combo.addItems(["\U0001F511  SSH Key", "\U0001F512  Password"])
        self._auth_combo.setCurrentIndex(
            0 if self._server.auth_method == "key" else 1
        )
        self._auth_combo.currentIndexChanged.connect(self._on_auth_changed)
        layout.addRow("Auth Method:", self._auth_combo)

        # Key file row
        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._key_edit = QLineEdit(self._server.key_path or "")
        self._key_edit.setPlaceholderText("~/.ssh/id_rsa")
        browse_btn = QPushButton("\U0001F4C2  Browse")
        browse_btn.setFixedWidth(100)
        browse_btn.clicked.connect(self._browse_key)
        key_row.addWidget(self._key_edit)
        key_row.addWidget(browse_btn)
        layout.addRow("Key File:", key_row)

        self._password_edit = QLineEdit(self._server.password or "")
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Enter password")
        layout.addRow("Password:", self._password_edit)

        self._docker_port_spin = QSpinBox()
        self._docker_port_spin.setRange(1, 65535)
        self._docker_port_spin.setValue(self._server.docker_port)
        self._docker_port_spin.setToolTip(
            "TCP port where Docker daemon listens on the remote host.\n"
            "Default: 2375 (unencrypted) or 2376 (TLS).\n"
            "Note: with SSH dial-stdio, this field is informational."
        )
        layout.addRow("Docker Port:", self._docker_port_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._on_auth_changed(self._auth_combo.currentIndex())

    def _on_auth_changed(self, index: int) -> None:
        is_key = index == 0
        self._key_edit.setEnabled(is_key)
        self._password_edit.setEnabled(not is_key)

    def _browse_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select SSH Key", "", "All Files (*)"
        )
        if path:
            self._key_edit.setText(path)

    def get_server(self) -> Server:
        self._server.name = self._name_edit.text().strip()
        self._server.host = self._host_edit.text().strip()
        self._server.port = self._port_spin.value()
        self._server.username = self._username_edit.text().strip()
        self._server.auth_method = (
            "key" if self._auth_combo.currentIndex() == 0 else "password"
        )
        self._server.key_path = self._key_edit.text().strip() or None
        self._server.password = self._password_edit.text() or None
        self._server.docker_port = self._docker_port_spin.value()
        return self._server
