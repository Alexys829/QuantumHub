from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.network_config_controller import NetworkConfigController

_STATE_COLORS = {
    "activated": QColor("#2ea043"),
    "activating": QColor("#d29922"),
    "deactivating": QColor("#d29922"),
    "deactivated": QColor("#8b949e"),
}


class _InputDialog(QDialog):
    """Simple dialog with a single text input."""

    def __init__(self, title: str, label: str, default: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        layout.addWidget(QLabel(label))
        self._input = QLineEdit(default)
        layout.addWidget(self._input)
        self._input.selectAll()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._input.returnPressed.connect(self.accept)

    def get_text(self) -> str:
        return self._input.text().strip()


class NetworkConfigView(QWidget):
    """Network interface configuration view (nmcli / NetworkManager)."""

    COLUMNS = ["Name", "Type", "Device", "MAC", "State"]

    def __init__(self, controller: NetworkConfigController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._selected_conn: str = ""
        self._nm_available = False
        self._mac_map: dict[str, str] = {}
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F310  Network Configuration")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # NM warning (hidden by default)
        self._nm_warning = QLabel(
            "\u26A0  NetworkManager is not available. "
            "Network configuration requires NetworkManager (nmcli)."
        )
        self._nm_warning.setStyleSheet(
            "color: #f48771; font-size: 13px; padding: 8px;"
            "background-color: #3a1d1d; border-radius: 4px;"
        )
        self._nm_warning.setVisible(False)
        layout.addWidget(self._nm_warning)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._activate_btn = QPushButton("\u25B6  Activate")
        self._deactivate_btn = QPushButton("\u23F9  Deactivate")
        self._rename_btn = QPushButton("\u270F  Rename")
        self._clone_btn = QPushButton("\U0001F4CB  Clone")
        self._delete_btn = QPushButton("\U0001F5D1  Delete")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._activate_btn, self._deactivate_btn, self._rename_btn,
            self._clone_btn, self._delete_btn, self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Interfaces table
        table_label = QLabel("Connections:")
        table_label.setStyleSheet("font-weight: 600; color: #bbbbbb;")
        layout.addWidget(table_label)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(0, 200)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 140)
        self._table.setMaximumHeight(200)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.itemSelectionChanged.connect(self._on_interface_selected)
        layout.addWidget(self._table)

        # Config panel
        self._config_group = QGroupBox("Configuration")
        self._config_group.setObjectName("settingsGroup")
        config_layout = QVBoxLayout(self._config_group)
        config_layout.setSpacing(12)

        self._conn_label = QLabel("Select a connection above")
        self._conn_label.setStyleSheet("font-weight: 600; color: #e0e0e0;")
        config_layout.addWidget(self._conn_label)

        # Autoconnect checkbox
        self._autoconnect_cb = QCheckBox("Autoconnect at boot")
        self._autoconnect_cb.toggled.connect(self._on_autoconnect_changed)
        config_layout.addWidget(self._autoconnect_cb)

        form = QFormLayout()
        form.setSpacing(10)

        self._method_combo = QComboBox()
        self._method_combo.addItems(["Auto (DHCP)", "Manual (Static)"])
        self._method_combo.currentIndexChanged.connect(self._on_method_changed)
        form.addRow("Method:", self._method_combo)

        ip_row = QHBoxLayout()
        self._ip_input = QLineEdit()
        self._ip_input.setPlaceholderText("192.168.1.100")
        ip_row.addWidget(self._ip_input)
        ip_row.addWidget(QLabel("/"))
        self._prefix_input = QLineEdit()
        self._prefix_input.setPlaceholderText("24")
        self._prefix_input.setMaximumWidth(60)
        ip_row.addWidget(self._prefix_input)
        form.addRow("IP Address:", ip_row)

        self._gateway_input = QLineEdit()
        self._gateway_input.setPlaceholderText("192.168.1.1")
        form.addRow("Gateway:", self._gateway_input)

        self._dns1_input = QLineEdit()
        self._dns1_input.setPlaceholderText("8.8.8.8")
        form.addRow("DNS 1:", self._dns1_input)

        self._dns2_input = QLineEdit()
        self._dns2_input.setPlaceholderText("8.8.4.4")
        form.addRow("DNS 2:", self._dns2_input)

        config_layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._apply_btn = QPushButton("\u2705  Apply Changes")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        self._dhcp_btn = QPushButton("\U0001F504  Reset to DHCP")
        self._dhcp_btn.clicked.connect(self._on_dhcp)
        btn_row.addWidget(self._dhcp_btn)
        btn_row.addStretch()
        config_layout.addLayout(btn_row)

        layout.addWidget(self._config_group)
        self._set_fields_enabled(False)

    def _connect_signals(self) -> None:
        self._ctrl.connections_loaded.connect(self._on_connections_loaded)
        self._ctrl.details_loaded.connect(self._on_details_loaded)
        self._ctrl.nm_status.connect(self._on_nm_status)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._activate_btn.clicked.connect(lambda: self._on_set_active(True))
        self._deactivate_btn.clicked.connect(lambda: self._on_set_active(False))
        self._rename_btn.clicked.connect(self._on_rename)
        self._clone_btn.clicked.connect(self._on_clone)
        self._delete_btn.clicked.connect(self._on_delete)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_connections)

    # ── Context menu ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\u25B6  Activate", self,
            triggered=lambda: self._on_set_active(True),
        ))
        menu.addAction(QAction(
            "\u23F9  Deactivate", self,
            triggered=lambda: self._on_set_active(False),
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\u270F  Rename...", self, triggered=self._on_rename,
        ))
        menu.addAction(QAction(
            "\U0001F4CB  Clone...", self, triggered=self._on_clone,
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\U0001F5D1  Delete", self, triggered=self._on_delete,
        ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── NM status ────────────────────────────────────────────

    def _on_nm_status(self, available: bool) -> None:
        self._nm_available = available
        self._nm_warning.setVisible(not available)
        self._config_group.setEnabled(available)
        self._table.setEnabled(available)

    # ── Connections table ────────────────────────────────────

    def _on_connections_loaded(self, connections: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(len(connections))
        for row, c in enumerate(connections):
            self._table.setItem(row, 0, QTableWidgetItem(c["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(c["type"]))
            device = c["device"]
            self._table.setItem(row, 2, QTableWidgetItem(device))
            # MAC
            mac = self._mac_map.get(device, "")
            mac_item = QTableWidgetItem(mac)
            mac_item.setForeground(QColor("#888888"))
            self._table.setItem(row, 3, mac_item)
            # State
            state_item = QTableWidgetItem(c["state"])
            color = _STATE_COLORS.get(c["state"], QColor("#8b949e"))
            state_item.setForeground(color)
            self._table.setItem(row, 4, state_item)
        self._table.setUpdatesEnabled(True)

    def set_mac_map(self, macs: dict[str, str]) -> None:
        """Set the interface→MAC mapping (called by controller/main_window)."""
        self._mac_map = macs

    # ── Interface selection ──────────────────────────────────

    def _on_interface_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name_item = self._table.item(row, 0)
        if not name_item:
            return
        self._selected_conn = name_item.text()
        self._conn_label.setText(
            f"Configuration for: \"{self._selected_conn}\""
        )
        self._set_fields_enabled(True)
        self._ctrl.load_details(self._selected_conn)

    def _selected_conn_name(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    # ── Details loaded ───────────────────────────────────────

    def _on_details_loaded(self, details: dict) -> None:
        # Block signals to avoid triggering autoconnect save
        self._autoconnect_cb.blockSignals(True)
        self._autoconnect_cb.setChecked(
            details.get("autoconnect", "yes") == "yes"
        )
        self._autoconnect_cb.blockSignals(False)

        method = details.get("method", "auto")
        is_static = method == "manual"
        self._method_combo.setCurrentIndex(1 if is_static else 0)
        self._ip_input.setText(details.get("address", ""))
        self._prefix_input.setText(details.get("prefix", "24"))
        self._gateway_input.setText(details.get("gateway", ""))
        dns = details.get("dns", "")
        dns_list = [d.strip() for d in dns.replace(",", " ").split() if d.strip()]
        self._dns1_input.setText(dns_list[0] if dns_list else "")
        self._dns2_input.setText(dns_list[1] if len(dns_list) > 1 else "")
        self._on_method_changed(self._method_combo.currentIndex())

    # ── Method change ────────────────────────────────────────

    def _on_method_changed(self, index: int) -> None:
        is_static = index == 1
        self._ip_input.setEnabled(is_static)
        self._prefix_input.setEnabled(is_static)
        self._gateway_input.setEnabled(is_static)
        self._dns1_input.setEnabled(is_static)
        self._dns2_input.setEnabled(is_static)

    def _set_fields_enabled(self, enabled: bool) -> None:
        self._method_combo.setEnabled(enabled)
        self._autoconnect_cb.setEnabled(enabled)
        self._apply_btn.setEnabled(enabled)
        self._dhcp_btn.setEnabled(enabled)
        if not enabled:
            self._ip_input.setEnabled(False)
            self._prefix_input.setEnabled(False)
            self._gateway_input.setEnabled(False)
            self._dns1_input.setEnabled(False)
            self._dns2_input.setEnabled(False)

    # ── Autoconnect ──────────────────────────────────────────

    def _on_autoconnect_changed(self, checked: bool) -> None:
        if self._selected_conn:
            self._ctrl.set_autoconnect(self._selected_conn, checked)

    # ── Actions ──────────────────────────────────────────────

    def _on_set_active(self, activate: bool) -> None:
        name = self._selected_conn_name()
        if not name:
            return
        action = "Activate" if activate else "Deactivate"
        reply = QMessageBox.question(
            self, action, f"{action} connection '{name}'?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.set_connection_active(name, activate)

    def _on_rename(self) -> None:
        name = self._selected_conn_name()
        if not name:
            return
        dialog = _InputDialog(
            "Rename Connection",
            f"New name for '{name}':",
            default=name,
            parent=self,
        )
        if dialog.exec():
            new_name = dialog.get_text()
            if new_name and new_name != name:
                self._ctrl.rename_connection(name, new_name)

    def _on_clone(self) -> None:
        name = self._selected_conn_name()
        if not name:
            return
        dialog = _InputDialog(
            "Clone Connection",
            f"Name for the copy of '{name}':",
            default=f"{name} (copy)",
            parent=self,
        )
        if dialog.exec():
            new_name = dialog.get_text()
            if new_name:
                self._ctrl.clone_connection(name, new_name)

    def _on_delete(self) -> None:
        name = self._selected_conn_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Delete Connection",
            f"Permanently delete connection '{name}'?\n\n"
            "This cannot be undone.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_connection(name)
            self._selected_conn = ""
            self._conn_label.setText("Select a connection above")
            self._set_fields_enabled(False)

    def _on_apply(self) -> None:
        if not self._selected_conn:
            return
        if self._method_combo.currentIndex() == 0:
            self._on_dhcp()
            return
        address = self._ip_input.text().strip()
        prefix = self._prefix_input.text().strip() or "24"
        gateway = self._gateway_input.text().strip()
        dns1 = self._dns1_input.text().strip()
        dns2 = self._dns2_input.text().strip()
        if not address:
            QMessageBox.warning(self, "Validation", "IP Address is required.")
            return
        dns = dns1
        if dns2:
            dns += f" {dns2}"
        reply = QMessageBox.question(
            self,
            "Apply Network Changes",
            f"Apply static IP configuration to '{self._selected_conn}'?\n\n"
            f"IP: {address}/{prefix}\n"
            f"Gateway: {gateway}\n"
            f"DNS: {dns}\n\n"
            "This may briefly disconnect you.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.save_static(
                self._selected_conn, address, prefix, gateway, dns
            )

    def _on_dhcp(self) -> None:
        if not self._selected_conn:
            return
        reply = QMessageBox.question(
            self,
            "Reset to DHCP",
            f"Reset '{self._selected_conn}' to DHCP?\n\n"
            "This may briefly disconnect you.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.save_dhcp(self._selected_conn)
