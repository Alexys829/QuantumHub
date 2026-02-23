from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
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

from app.controllers.startup_controller import StartupController

_TYPE_COLORS = {
    "systemd": QColor("#58a6ff"),
    "autostart": QColor("#d29922"),
}


class _AddStartupDialog(QDialog):
    """Dialog for adding a new autostart entry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Startup Application")
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel("Create a new XDG autostart entry (~/.config/autostart/)")
        info.setStyleSheet("color: #bbbbbb;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(10)

        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("My App")
        form.addRow("Name:", self._name_input)

        self._command_input = QLineEdit()
        self._command_input.setPlaceholderText("/usr/bin/myapp --start")
        form.addRow("Command:", self._command_input)

        self._desc_input = QLineEdit()
        self._desc_input.setPlaceholderText("Start My App on login")
        form.addRow("Description:", self._desc_input)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self) -> tuple[str, str, str]:
        return (
            self._name_input.text().strip(),
            self._command_input.text().strip(),
            self._desc_input.text().strip(),
        )


class StartupView(QWidget):
    """Startup application manager: systemd services + XDG autostart."""

    COLUMNS = ["Name", "Type", "Status", "Command / Description"]

    def __init__(self, controller: StartupController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_entries: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F680  Startup Applications")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._enable_btn = QPushButton("\u2705  Enable")
        self._disable_btn = QPushButton("\u274C  Disable")
        self._add_btn = QPushButton("\u2795  Add")
        self._remove_btn = QPushButton("\U0001F5D1  Remove")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._enable_btn, self._disable_btn, self._add_btn,
            self._remove_btn, self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter startup apps...")
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
        self._table.setColumnWidth(0, 220)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(2, 90)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.entries_loaded.connect(self._on_entries_loaded)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._enable_btn.clicked.connect(lambda: self._on_toggle(True))
        self._disable_btn.clicked.connect(lambda: self._on_toggle(False))
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn.clicked.connect(self._on_remove)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_entries)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\u2705  Enable", self, triggered=lambda: self._on_toggle(True)
        ))
        menu.addAction(QAction(
            "\u274C  Disable", self, triggered=lambda: self._on_toggle(False)
        ))
        entry = self._selected_entry()
        if entry and entry["entry_type"] == "autostart":
            menu.addSeparator()
            menu.addAction(QAction(
                "\U0001F5D1  Remove", self, triggered=self._on_remove
            ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_entry(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        name_item = self._table.item(row, 0)
        type_item = self._table.item(row, 1)
        if not name_item or not type_item:
            return None
        name = name_item.text()
        entry_type = type_item.text()
        for e in self._all_entries:
            if e["name"] == name and e["entry_type"] == entry_type:
                return e
        return None

    def _on_entries_loaded(self, entries: list[dict]) -> None:
        self._all_entries = entries
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        filtered = [
            e for e in self._all_entries
            if not text or text in e["name"].lower()
            or text in e.get("description", "").lower()
            or text in e.get("command", "").lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, entries: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(entries))
        for row, e in enumerate(entries):
            self._table.setItem(row, 0, QTableWidgetItem(e["name"]))

            type_item = QTableWidgetItem(e["entry_type"])
            type_color = _TYPE_COLORS.get(e["entry_type"], QColor("#8b949e"))
            type_item.setForeground(type_color)
            self._table.setItem(row, 1, type_item)

            status = "enabled" if e["enabled"] else "disabled"
            status_item = QTableWidgetItem(status)
            status_color = QColor("#2ea043") if e["enabled"] else QColor("#8b949e")
            status_item.setForeground(status_color)
            self._table.setItem(row, 2, status_item)

            desc = e.get("command") or e.get("description", "")
            self._table.setItem(row, 3, QTableWidgetItem(desc))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_toggle(self, enable: bool) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        self._ctrl.toggle_entry(
            entry["name"], entry["entry_type"], enable, entry.get("file", "")
        )

    def _on_add(self) -> None:
        dialog = _AddStartupDialog(parent=self)
        if dialog.exec():
            name, command, description = dialog.get_values()
            if not name or not command:
                QMessageBox.warning(
                    self, "Validation", "Name and Command are required."
                )
                return
            self._ctrl.add_entry(name, command, description)

    def _on_remove(self) -> None:
        entry = self._selected_entry()
        if not entry:
            return
        if entry["entry_type"] == "systemd":
            QMessageBox.information(
                self,
                "Remove",
                "Systemd services cannot be removed from here.\n"
                "Use 'Disable' to prevent them from starting at boot.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Remove Startup Entry",
            f"Remove autostart entry '{entry['name']}'?\n\n"
            f"File: {entry.get('file', '')}",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.remove_entry(entry["name"], entry.get("file", ""))
