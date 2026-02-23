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

from app.controllers.process_controller import ProcessController
from app.utils import format_rate


class ProcessesView(QWidget):
    """Process list with kill actions and search filter."""

    COLUMNS = [
        "PID", "User", "CPU%", "MEM%", "RSS", "Status",
        "Disk R/s", "Disk W/s", "Net Send/s", "Net Recv/s",
        "Command",
    ]

    def __init__(self, controller: ProcessController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_processes: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\u2699  Processes")
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
        self._search.setPlaceholderText("Filter processes...")
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
        # Fixed widths for short columns; Command stretches via stretchLastSection
        col_widths = [70, 80, 60, 60, 80, 60, 80, 80, 85, 85]
        for col, w in enumerate(col_widths):
            self._table.setColumnWidth(col, w)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.processes_loaded.connect(self._on_processes_loaded)
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
        self._refresh_btn.clicked.connect(self._ctrl.refresh_processes)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\U0001F480  Kill (SIGTERM)", self, triggered=lambda: self._on_kill(15)))
        menu.addAction(QAction("\U0001F4A5  Force Kill (SIGKILL)", self, triggered=lambda: self._on_kill(9)))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_pid(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        if item is None:
            return None
        try:
            return int(item.text())
        except ValueError:
            return None

    def _on_processes_loaded(self, processes: list[dict]) -> None:
        self._all_processes = processes
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        filtered = [
            p for p in self._all_processes
            if not text or text in str(p).lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, processes: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(processes))
        for row, p in enumerate(processes):
            self._table.setItem(row, 0, QTableWidgetItem(p.get("pid", "")))
            self._table.setItem(row, 1, QTableWidgetItem(p.get("user", "")))
            self._table.setItem(row, 2, QTableWidgetItem(p.get("cpu", "")))
            self._table.setItem(row, 3, QTableWidgetItem(p.get("mem", "")))
            self._table.setItem(row, 4, QTableWidgetItem(p.get("rss", "")))
            self._table.setItem(row, 5, QTableWidgetItem(p.get("stat", "")))
            self._table.setItem(
                row, 6, QTableWidgetItem(format_rate(p.get("disk_read_rate", 0)))
            )
            self._table.setItem(
                row, 7, QTableWidgetItem(format_rate(p.get("disk_write_rate", 0)))
            )
            self._table.setItem(
                row, 8, QTableWidgetItem(format_rate(p.get("net_send_rate", 0)))
            )
            self._table.setItem(
                row, 9, QTableWidgetItem(format_rate(p.get("net_recv_rate", 0)))
            )
            self._table.setItem(row, 10, QTableWidgetItem(p.get("command", "")))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_kill(self, signal: int) -> None:
        pid = self._selected_pid()
        if pid is None:
            return
        sig_name = "SIGKILL" if signal == 9 else "SIGTERM"
        reply = QMessageBox.question(
            self, "Confirm", f"Send {sig_name} to PID {pid}?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.kill_process(pid, signal)
