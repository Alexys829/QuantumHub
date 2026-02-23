from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.compose_controller import ComposeController

_SERVICE_COLORS = {
    "running": QColor("#2ea043"),
    "exited": QColor("#f85149"),
    "paused": QColor("#d29922"),
    "created": QColor("#58a6ff"),
    "restarting": QColor("#d29922"),
    "dead": QColor("#8b949e"),
}


class ComposeView(QWidget):
    """View for Docker Compose project management."""

    PROJECT_COLUMNS = ["Name", "Status", "Config Files"]
    SERVICE_COLUMNS = ["Service", "State", "Image", "Ports"]

    def __init__(self, controller: ComposeController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._current_project: str | None = None
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QPushButton("\U0001F4E6  Compose")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._up_btn = QPushButton("\u25B6  Up")
        self._down_btn = QPushButton("\u23F9  Down")
        self._restart_btn = QPushButton("\U0001F504  Restart")
        self._pull_btn = QPushButton("\U0001F4E5  Pull")
        self._logs_btn = QPushButton("\U0001F4C4  Logs")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._up_btn,
            self._down_btn,
            self._restart_btn,
            self._pull_btn,
            self._logs_btn,
            self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Splitter: projects on top, services on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # -- Projects table --
        projects_widget = QWidget()
        projects_layout = QVBoxLayout(projects_widget)
        projects_layout.setContentsMargins(0, 0, 0, 0)
        projects_layout.setSpacing(4)

        projects_label = QLabel("\U0001F4E6  Projects")
        projects_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #a0a0a0; padding: 2px 0;"
        )
        projects_layout.addWidget(projects_label)

        self._projects_table = QTableWidget()
        self._projects_table.setColumnCount(len(self.PROJECT_COLUMNS))
        self._projects_table.setHorizontalHeaderLabels(self.PROJECT_COLUMNS)
        self._setup_table(self._projects_table)
        self._projects_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._projects_table.customContextMenuRequested.connect(
            self._show_project_context_menu
        )
        self._projects_table.currentCellChanged.connect(self._on_project_selected)
        projects_layout.addWidget(self._projects_table)
        splitter.addWidget(projects_widget)

        # -- Services table --
        services_widget = QWidget()
        services_layout = QVBoxLayout(services_widget)
        services_layout.setContentsMargins(0, 0, 0, 0)
        services_layout.setSpacing(4)

        self._services_label = QLabel("\u2699  Services")
        self._services_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #a0a0a0; padding: 2px 0;"
        )
        services_layout.addWidget(self._services_label)

        self._services_table = QTableWidget()
        self._services_table.setColumnCount(len(self.SERVICE_COLUMNS))
        self._services_table.setHorizontalHeaderLabels(self.SERVICE_COLUMNS)
        self._setup_table(self._services_table)
        services_layout.addWidget(self._services_table)
        splitter.addWidget(services_widget)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter)

    @staticmethod
    def _setup_table(table: QTableWidget) -> None:
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)

    def _connect_signals(self) -> None:
        self._ctrl.projects_loaded.connect(self._populate_projects)
        self._ctrl.services_loaded.connect(self._populate_services)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._ctrl.compose_logs.connect(self._show_logs)

        self._up_btn.clicked.connect(self._on_up)
        self._down_btn.clicked.connect(self._on_down)
        self._restart_btn.clicked.connect(self._on_restart)
        self._pull_btn.clicked.connect(self._on_pull)
        self._logs_btn.clicked.connect(self._on_logs)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_projects)

    def _show_project_context_menu(self, pos) -> None:
        if self._projects_table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u25B6  Up", self, triggered=self._on_up))
        menu.addAction(QAction("\u23F9  Down", self, triggered=self._on_down))
        menu.addAction(QAction("\U0001F504  Restart", self, triggered=self._on_restart))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F4E5  Pull", self, triggered=self._on_pull))
        menu.addAction(QAction("\U0001F4C4  Logs", self, triggered=self._on_logs))
        menu.exec(self._projects_table.viewport().mapToGlobal(pos))

    def _selected_project_name(self) -> str | None:
        row = self._projects_table.currentRow()
        if row < 0:
            return None
        return self._projects_table.item(row, 0).text()

    def _on_project_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        if row < 0:
            self._services_table.setRowCount(0)
            self._current_project = None
            return
        name = self._projects_table.item(row, 0).text()
        self._current_project = name
        self._services_label.setText(f"\u2699  Services — {name}")
        self._ctrl.refresh_services(name)

    def _populate_projects(self, projects: list[dict]) -> None:
        self._projects_table.setRowCount(len(projects))
        for row, p in enumerate(projects):
            name = p.get("Name", p.get("name", ""))
            status = p.get("Status", p.get("status", ""))
            config = p.get("ConfigFiles", p.get("configFiles", ""))

            self._projects_table.setItem(row, 0, QTableWidgetItem(name))

            status_item = QTableWidgetItem(status)
            # Color based on status text
            lower_status = status.lower()
            if "running" in lower_status:
                status_item.setForeground(QColor("#2ea043"))
            elif "exited" in lower_status or "stopped" in lower_status:
                status_item.setForeground(QColor("#f85149"))
            self._projects_table.setItem(row, 1, status_item)

            self._projects_table.setItem(row, 2, QTableWidgetItem(config))
        self._projects_table.resizeColumnsToContents()

    def _populate_services(self, services: list[dict]) -> None:
        self._services_table.setRowCount(len(services))
        for row, s in enumerate(services):
            name = s.get("Service", s.get("Name", s.get("name", "")))
            state = s.get("State", s.get("state", s.get("Status", "")))
            image = s.get("Image", s.get("image", ""))
            # Publishers can be a list of dicts or a string
            publishers = s.get("Publishers", s.get("Ports", ""))
            if isinstance(publishers, list):
                port_parts = []
                for pub in publishers:
                    if isinstance(pub, dict):
                        pp = pub.get("PublishedPort", 0)
                        tp = pub.get("TargetPort", 0)
                        if pp:
                            port_parts.append(f"{pp}->{tp}")
                        elif tp:
                            port_parts.append(str(tp))
                    else:
                        port_parts.append(str(pub))
                ports_str = ", ".join(port_parts)
            else:
                ports_str = str(publishers) if publishers else ""

            self._services_table.setItem(row, 0, QTableWidgetItem(name))

            state_item = QTableWidgetItem(state)
            color = _SERVICE_COLORS.get(state.lower(), QColor("#8b949e"))
            state_item.setForeground(color)
            self._services_table.setItem(row, 1, state_item)

            self._services_table.setItem(row, 2, QTableWidgetItem(image))
            self._services_table.setItem(row, 3, QTableWidgetItem(ports_str))
        self._services_table.resizeColumnsToContents()

    def _on_up(self) -> None:
        name = self._selected_project_name()
        if name:
            self._ctrl.up(name)

    def _on_down(self) -> None:
        name = self._selected_project_name()
        if name:
            reply = QMessageBox.question(
                self, "Confirm", f"Stop and remove project '{name}'?"
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._ctrl.down(name)

    def _on_restart(self) -> None:
        name = self._selected_project_name()
        if name:
            self._ctrl.restart(name)

    def _on_pull(self) -> None:
        name = self._selected_project_name()
        if name:
            self._ctrl.pull(name)

    def _on_logs(self) -> None:
        name = self._selected_project_name()
        if name:
            self._ctrl.view_logs(name)

    def _show_logs(self, log_text: str) -> None:
        title = self._current_project or "Compose"
        self._log_window = QWidget()
        self._log_window.setWindowTitle(f"\U0001F4C4  Logs — {title}")
        self._log_window.resize(900, 550)
        self._log_window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self._log_window)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QLabel(f"\U0001F4C4  Compose Logs: {title}")
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(header)

        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setMaximumBlockCount(5000)
        text_edit.setPlainText(log_text)
        layout.addWidget(text_edit)

        self._log_window.show()
