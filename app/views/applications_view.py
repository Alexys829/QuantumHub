from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
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

from app.controllers.application_controller import ApplicationController
from app.utils import format_rate


class ApplicationsView(QWidget):
    """Grouped application list with resource usage and I/O rates."""

    COLUMNS = [
        "App", "PIDs", "CPU%", "RAM (MB)",
        "Disk R/s", "Disk W/s", "Net Send/s", "Net Recv/s",
    ]

    def __init__(self, controller: ApplicationController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_apps: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F4F1  Applications")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._kill_btn = QPushButton("\U0001F480  Kill (SIGTERM)")
        self._fkill_btn = QPushButton("\U0001F4A5  Force Kill (SIGKILL)")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")
        for btn in (self._kill_btn, self._fkill_btn, self._refresh_btn):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter applications...")
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
        col_widths = [180, 60, 70, 90, 85, 85, 85]
        for col, w in enumerate(col_widths):
            self._table.setColumnWidth(col, w)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.applications_loaded.connect(self._on_apps_loaded)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._ctrl.operation_success.connect(
            lambda msg: self.parent().statusBar().showMessage(msg, 3000)
            if self.parent() and hasattr(self.parent(), "statusBar")
            else None
        )
        self._kill_btn.clicked.connect(lambda: self._on_kill(15))
        self._fkill_btn.clicked.connect(lambda: self._on_kill(9))
        self._refresh_btn.clicked.connect(self._ctrl.refresh_applications)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(
            QAction(
                "\U0001F480  Kill All (SIGTERM)",
                self,
                triggered=lambda: self._on_kill(15),
            )
        )
        menu.addAction(
            QAction(
                "\U0001F4A5  Force Kill All (SIGKILL)",
                self,
                triggered=lambda: self._on_kill(9),
            )
        )
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_app(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        text = self._search.text().lower()
        filtered = [
            a for a in self._all_apps if not text or text in str(a).lower()
        ]
        if row < len(filtered):
            return filtered[row]
        return None

    def _on_apps_loaded(self, apps: list[dict]) -> None:
        self._all_apps = apps
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        filtered = [
            a for a in self._all_apps if not text or text in str(a).lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, apps: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(apps))
        for row, a in enumerate(apps):
            self._table.setItem(row, 0, QTableWidgetItem(a.get("app_name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(str(a.get("pids", 0))))
            self._table.setItem(row, 2, QTableWidgetItem(str(a.get("cpu", 0))))
            self._table.setItem(
                row, 3, QTableWidgetItem(f"{a.get('ram_mb', 0):.1f}")
            )
            self._table.setItem(
                row, 4, QTableWidgetItem(format_rate(a.get("disk_read_rate", 0)))
            )
            self._table.setItem(
                row, 5, QTableWidgetItem(format_rate(a.get("disk_write_rate", 0)))
            )
            self._table.setItem(
                row, 6, QTableWidgetItem(format_rate(a.get("net_send_rate", 0)))
            )
            self._table.setItem(
                row, 7, QTableWidgetItem(format_rate(a.get("net_recv_rate", 0)))
            )
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_kill(self, signal: int) -> None:
        app = self._selected_app()
        if app is None:
            return
        name = app["app_name"]
        pids = app.get("pid_list", [])
        sig_name = "SIGKILL" if signal == 9 else "SIGTERM"
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Send {sig_name} to all {len(pids)} processes of '{name}'?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.kill_application(pids, signal)
