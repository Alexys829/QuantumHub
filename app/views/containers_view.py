from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.container_controller import ContainerController
from app.services.connection_manager import ConnectionManager

# Status colors
_STATUS_COLORS = {
    "running": QColor("#2ea043"),
    "exited": QColor("#f85149"),
    "paused": QColor("#d29922"),
    "created": QColor("#58a6ff"),
    "restarting": QColor("#d29922"),
    "removing": QColor("#f85149"),
    "dead": QColor("#8b949e"),
}


class ContainersView(QWidget):
    """Table-based container list with action buttons and context menu."""

    COLUMNS = ["ID", "Name", "Image", "Status", "Ports", "Created"]

    def __init__(self, controller: ContainerController, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._conn_manager = connection_manager
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QPushButton("\u25B6  Containers")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._start_btn = QPushButton("\u25B6  Start")
        self._stop_btn = QPushButton("\u23F9  Stop")
        self._kill_btn = QPushButton("\U0001F480  Kill")
        self._restart_btn = QPushButton("\U0001F504  Restart")
        self._remove_btn = QPushButton("\U0001F5D1  Remove")
        self._logs_btn = QPushButton("\U0001F4C4  Logs")
        self._stats_btn = QPushButton("\U0001F4CA  Stats")
        self._exec_btn = QPushButton("\U0001F4BB  Exec")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._start_btn,
            self._stop_btn,
            self._kill_btn,
            self._restart_btn,
            self._remove_btn,
            self._logs_btn,
            self._stats_btn,
            self._exec_btn,
            self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
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
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.containers_loaded.connect(self._populate_table)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._start_btn.clicked.connect(self._on_start)
        self._stop_btn.clicked.connect(self._on_stop)
        self._kill_btn.clicked.connect(self._on_kill)
        self._restart_btn.clicked.connect(self._on_restart)
        self._remove_btn.clicked.connect(self._on_remove)
        self._logs_btn.clicked.connect(self._on_logs)
        self._stats_btn.clicked.connect(self._on_stats)
        self._exec_btn.clicked.connect(self._on_exec)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_containers)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u25B6  Start", self, triggered=self._on_start))
        menu.addAction(QAction("\u23F9  Stop", self, triggered=self._on_stop))
        menu.addAction(QAction("\U0001F480  Kill", self, triggered=self._on_kill))
        menu.addAction(QAction("\U0001F504  Restart", self, triggered=self._on_restart))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F4C4  View Logs", self, triggered=self._on_logs))
        menu.addAction(QAction("\U0001F4CA  Stats", self, triggered=self._on_stats))
        menu.addAction(QAction("\U0001F4BB  Exec Shell", self, triggered=self._on_exec))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Remove", self, triggered=self._on_remove))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_container_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        return self._table.item(row, 0).text()

    def _populate_table(self, containers: list[dict]) -> None:
        self._table.setRowCount(len(containers))
        for row, c in enumerate(containers):
            self._table.setItem(row, 0, QTableWidgetItem(c["id"]))
            self._table.setItem(row, 1, QTableWidgetItem(c["name"]))
            self._table.setItem(row, 2, QTableWidgetItem(c["image"]))

            # Status with color indicator
            status = c["status"]
            status_item = QTableWidgetItem(f"  {status}")
            color = _STATUS_COLORS.get(status, QColor("#8b949e"))
            status_item.setForeground(color)
            self._table.setItem(row, 3, status_item)

            self._table.setItem(row, 4, QTableWidgetItem(c["ports"]))
            self._table.setItem(row, 5, QTableWidgetItem(c["created"]))

        self._table.resizeColumnsToContents()

    def _on_start(self) -> None:
        cid = self._selected_container_id()
        if cid:
            self._ctrl.start_container(cid)

    def _on_stop(self) -> None:
        cid = self._selected_container_id()
        if cid:
            self._ctrl.stop_container(cid)

    def _on_kill(self) -> None:
        cid = self._selected_container_id()
        if cid:
            reply = QMessageBox.question(
                self, "Confirm", f"Force kill container {cid}? (SIGKILL)"
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._ctrl.kill_container(cid)

    def _on_restart(self) -> None:
        cid = self._selected_container_id()
        if cid:
            self._ctrl.restart_container(cid)

    def _on_remove(self) -> None:
        cid = self._selected_container_id()
        if cid:
            reply = QMessageBox.question(
                self, "Confirm", f"Remove container {cid}?"
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._ctrl.remove_container(cid, force=True)

    def _on_logs(self) -> None:
        cid = self._selected_container_id()
        if not cid:
            return
        from app.views.log_viewer import LogViewer

        self._log_viewer = LogViewer(self._conn_manager.docker, cid, parent=None)
        self._log_viewer.show()

    def _on_exec(self) -> None:
        cid = self._selected_container_id()
        if not cid:
            return
        from app.views.exec_view import ExecView

        self._exec_viewer = ExecView(self._conn_manager.docker, cid, parent=None)
        self._exec_viewer.show()

    def _on_stats(self) -> None:
        cid = self._selected_container_id()
        if not cid:
            return
        from app.views.container_stats_view import ContainerStatsView

        self._stats_viewer = ContainerStatsView(
            self._conn_manager.docker, cid, parent=None
        )
        self._stats_viewer.show()
