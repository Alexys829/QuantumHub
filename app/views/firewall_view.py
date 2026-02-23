from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from app.controllers.firewall_controller import FirewallController

_ACTION_COLORS = {
    "ALLOW IN": QColor("#2ea043"),
    "ALLOW": QColor("#2ea043"),
    "DENY IN": QColor("#f85149"),
    "DENY": QColor("#f85149"),
    "REJECT IN": QColor("#d29922"),
    "REJECT": QColor("#d29922"),
}


class _AddRuleDialog(QDialog):
    """Dialog for adding a new firewall rule."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Firewall Rule")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        info = QLabel("Add a new ufw firewall rule.")
        info.setStyleSheet("color: #bbbbbb;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self._port_input = QLineEdit()
        self._port_input.setPlaceholderText("80, 443, 8080-8090")
        form.addRow("Port:", self._port_input)

        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["tcp", "udp", "both"])
        form.addRow("Protocol:", self._proto_combo)

        self._action_combo = QComboBox()
        self._action_combo.addItems(["allow", "deny"])
        form.addRow("Action:", self._action_combo)

        self._source_input = QLineEdit()
        self._source_input.setPlaceholderText("Anywhere (leave empty)")
        form.addRow("From:", self._source_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, str, str, str]:
        return (
            self._port_input.text().strip(),
            self._proto_combo.currentText(),
            self._action_combo.currentText(),
            self._source_input.text().strip(),
        )


class FirewallView(QWidget):
    """Firewall (ufw) management view."""

    COLUMNS = ["#", "Port / Service", "Action", "From"]

    def __init__(self, controller: FirewallController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_rules: list[dict] = []
        self._fw_enabled = False
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F6E1  Firewall (ufw)")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Unavailable warning (hidden by default)
        self._unavailable_warning = QLabel(
            "\u26A0  ufw is not installed. "
            "Install with: sudo apt install ufw"
        )
        self._unavailable_warning.setStyleSheet(
            "color: #f48771; font-size: 13px; padding: 8px;"
            "background-color: #3a1d1d; border-radius: 4px;"
        )
        self._unavailable_warning.setVisible(False)
        layout.addWidget(self._unavailable_warning)

        # Status row
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self._status_label = QLabel("Status: —")
        self._status_label.setStyleSheet(
            "font-weight: 600; color: #e0e0e0; font-size: 14px;"
        )
        status_row.addWidget(self._status_label)
        status_row.addSpacing(12)

        self._enable_btn = QPushButton("\u2705  Enable")
        self._enable_btn.clicked.connect(lambda: self._on_toggle(True))
        status_row.addWidget(self._enable_btn)

        self._disable_btn = QPushButton("\u274C  Disable")
        self._disable_btn.clicked.connect(lambda: self._on_toggle(False))
        status_row.addWidget(self._disable_btn)
        status_row.addStretch()
        layout.addLayout(status_row)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._add_btn = QPushButton("\u2795  Add Rule")
        self._delete_btn = QPushButton("\U0001F5D1  Delete Rule")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (self._add_btn, self._delete_btn, self._refresh_btn):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter rules...")
        self._search.setMaximumWidth(250)
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search)
        layout.addLayout(toolbar)

        # Table
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
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(1, 200)
        self._table.setColumnWidth(2, 120)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.rules_loaded.connect(self._on_rules_loaded)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._add_btn.clicked.connect(self._on_add)
        self._delete_btn.clicked.connect(self._on_delete)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_rules)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\U0001F5D1  Delete Rule", self, triggered=self._on_delete,
        ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _on_rules_loaded(self, data: dict) -> None:
        available = data.get("available", True)
        self._unavailable_warning.setVisible(not available)
        self._fw_enabled = data.get("enabled", False)

        if not available:
            self._status_label.setText("Status: not installed")
            self._status_label.setStyleSheet(
                "font-weight: 600; color: #8b949e; font-size: 14px;"
            )
            self._enable_btn.setEnabled(False)
            self._disable_btn.setEnabled(False)
            self._add_btn.setEnabled(False)
            self._delete_btn.setEnabled(False)
            return

        self._enable_btn.setEnabled(not self._fw_enabled)
        self._disable_btn.setEnabled(self._fw_enabled)
        self._add_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)

        if self._fw_enabled:
            self._status_label.setText("Status: \U0001F7E2 Active")
            self._status_label.setStyleSheet(
                "font-weight: 600; color: #2ea043; font-size: 14px;"
            )
        else:
            self._status_label.setText("Status: \U0001F534 Inactive")
            self._status_label.setStyleSheet(
                "font-weight: 600; color: #f85149; font-size: 14px;"
            )

        self._all_rules = data.get("rules", [])
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        filtered = [
            r for r in self._all_rules
            if not text or text in str(r).lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, rules: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(rules))
        for row, r in enumerate(rules):
            num_item = QTableWidgetItem(str(r["num"]))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, num_item)
            self._table.setItem(row, 1, QTableWidgetItem(r["to"]))

            action_item = QTableWidgetItem(r["action"])
            action_color = _ACTION_COLORS.get(r["action"], QColor("#8b949e"))
            action_item.setForeground(action_color)
            self._table.setItem(row, 2, action_item)

            self._table.setItem(row, 3, QTableWidgetItem(r["from_addr"]))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_toggle(self, enable: bool) -> None:
        action = "enable" if enable else "disable"
        reply = QMessageBox.question(
            self,
            "Firewall",
            f"Are you sure you want to {action} the firewall?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.toggle_firewall(enable)

    def _on_add(self) -> None:
        dialog = _AddRuleDialog(parent=self)
        if dialog.exec():
            port, protocol, action, source = dialog.get_values()
            if not port:
                QMessageBox.warning(
                    self, "Validation", "Port is required."
                )
                return
            self._ctrl.add_rule(port, protocol, action, source)

    def _on_delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        num_item = self._table.item(row, 0)
        to_item = self._table.item(row, 1)
        if not num_item:
            return
        rule_num = int(num_item.text())
        rule_desc = to_item.text() if to_item else ""
        reply = QMessageBox.question(
            self,
            "Delete Rule",
            f"Delete rule #{rule_num}?\n\n{rule_desc}",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_rule(rule_num)
