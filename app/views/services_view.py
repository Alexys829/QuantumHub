from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QCheckBox,
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

from app.controllers.service_controller import ServiceController

_ACTIVE_COLORS = {
    "active": QColor("#2ea043"),
    "inactive": QColor("#8b949e"),
    "failed": QColor("#f85149"),
    "activating": QColor("#d29922"),
    "deactivating": QColor("#d29922"),
}

_ENABLED_COLORS = {
    "enabled": QColor("#2ea043"),
    "disabled": QColor("#8b949e"),
    "static": QColor("#58a6ff"),
    "masked": QColor("#f85149"),
    "indirect": QColor("#d29922"),
    "generated": QColor("#58a6ff"),
    "alias": QColor("#d2a8ff"),
}


class ServicesView(QWidget):
    """Systemd service list with start/stop/restart/enable/disable actions."""

    COLUMNS = ["Unit", "Active", "Sub-state", "Boot", "Description"]

    def __init__(self, controller: ServiceController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_services: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F527  Services")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._start_btn = QPushButton("\u25B6  Start")
        self._stop_btn = QPushButton("\u23F9  Stop")
        self._restart_btn = QPushButton("\U0001F504  Restart")
        self._enable_btn = QPushButton("\u2705  Enable at Boot")
        self._disable_btn = QPushButton("\u274C  Disable at Boot")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._start_btn, self._stop_btn, self._restart_btn,
            self._enable_btn, self._disable_btn, self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter services...")
        self._search.setMaximumWidth(250)
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search)

        layout.addLayout(toolbar)

        # Filter: show inactive
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)
        self._show_inactive_cb = QCheckBox("Show inactive services")
        self._show_inactive_cb.setChecked(False)
        self._show_inactive_cb.setStyleSheet("color: #bbbbbb;")
        self._show_inactive_cb.toggled.connect(self._apply_filter)
        filter_row.addWidget(self._show_inactive_cb)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(len(self.COLUMNS))
        self._table.setHorizontalHeaderLabels(self.COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.services_loaded.connect(self._on_services_loaded)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._start_btn.clicked.connect(lambda: self._on_action("start"))
        self._stop_btn.clicked.connect(lambda: self._on_action("stop"))
        self._restart_btn.clicked.connect(lambda: self._on_action("restart"))
        self._enable_btn.clicked.connect(lambda: self._on_action("enable"))
        self._disable_btn.clicked.connect(lambda: self._on_action("disable"))
        self._refresh_btn.clicked.connect(self._ctrl.refresh_services)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\u25B6  Start", self, triggered=lambda: self._on_action("start"),
        ))
        menu.addAction(QAction(
            "\u23F9  Stop", self, triggered=lambda: self._on_action("stop"),
        ))
        menu.addAction(QAction(
            "\U0001F504  Restart", self, triggered=lambda: self._on_action("restart"),
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\u2705  Enable at Boot", self, triggered=lambda: self._on_action("enable"),
        ))
        menu.addAction(QAction(
            "\u274C  Disable at Boot", self, triggered=lambda: self._on_action("disable"),
        ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_unit(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _on_services_loaded(self, services: list[dict]) -> None:
        self._all_services = services
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        show_inactive = self._show_inactive_cb.isChecked()

        filtered = []
        for s in self._all_services:
            # Hide inactive unless checkbox is checked
            if not show_inactive and s.get("active") == "inactive":
                continue
            # Text filter
            if text and text not in str(s).lower():
                continue
            filtered.append(s)

        self._populate_table(filtered)

    def _populate_table(self, services: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(services))
        for row, s in enumerate(services):
            self._table.setItem(row, 0, QTableWidgetItem(s.get("unit", "")))

            active = s.get("active", "")
            active_item = QTableWidgetItem(active)
            color = _ACTIVE_COLORS.get(active, QColor("#8b949e"))
            active_item.setForeground(color)
            self._table.setItem(row, 1, active_item)

            self._table.setItem(row, 2, QTableWidgetItem(s.get("sub", "")))

            enabled = s.get("enabled", "")
            enabled_item = QTableWidgetItem(enabled)
            enabled_color = _ENABLED_COLORS.get(enabled, QColor("#8b949e"))
            enabled_item.setForeground(enabled_color)
            self._table.setItem(row, 3, enabled_item)

            self._table.setItem(row, 4, QTableWidgetItem(s.get("description", "")))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_action(self, action: str) -> None:
        unit = self._selected_unit()
        if not unit:
            return
        getattr(self._ctrl, f"{action}_service")(unit)
