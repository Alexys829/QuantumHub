from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
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

from app.controllers.cron_controller import CronController
from app.views.toast import show_toast


class _AddCronDialog(QDialog):
    """Dialog to add a new cron job."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Cron Job")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._minute = QLineEdit("*")
        self._hour = QLineEdit("*")
        self._dom = QLineEdit("*")
        self._month = QLineEdit("*")
        self._dow = QLineEdit("*")
        self._command = QLineEdit()
        self._command.setPlaceholderText("/path/to/script.sh")

        form.addRow("Minute (0-59):", self._minute)
        form.addRow("Hour (0-23):", self._hour)
        form.addRow("Day of Month (1-31):", self._dom)
        form.addRow("Month (1-12):", self._month)
        form.addRow("Day of Week (0-7):", self._dow)
        form.addRow("Command:", self._command)
        layout.addLayout(form)

        # Presets
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Presets:"))
        presets = {
            "Every minute": "* * * * *",
            "Every hour": "0 * * * *",
            "Daily (midnight)": "0 0 * * *",
            "Weekly (Sun)": "0 0 * * 0",
            "Monthly": "0 0 1 * *",
            "@reboot": "@reboot",
        }
        self._preset_combo = QComboBox()
        self._preset_combo.addItem("Custom", "")
        for label, val in presets.items():
            self._preset_combo.addItem(label, val)
        self._preset_combo.currentIndexChanged.connect(self._on_preset)
        preset_row.addWidget(self._preset_combo)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_preset(self, index: int) -> None:
        val = self._preset_combo.currentData()
        if not val:
            return
        if val.startswith("@"):
            self._minute.setText(val)
            self._hour.setText("")
            self._dom.setText("")
            self._month.setText("")
            self._dow.setText("")
        else:
            parts = val.split()
            self._minute.setText(parts[0])
            self._hour.setText(parts[1])
            self._dom.setText(parts[2])
            self._month.setText(parts[3])
            self._dow.setText(parts[4])

    def get_schedule(self) -> str:
        m = self._minute.text().strip()
        if m.startswith("@"):
            return m
        return f"{m} {self._hour.text().strip()} {self._dom.text().strip()} {self._month.text().strip()} {self._dow.text().strip()}"

    def get_command(self) -> str:
        return self._command.text().strip()


class CronView(QWidget):
    """Cron job management view."""

    COLUMNS = ["Enabled", "Schedule", "Command"]

    def __init__(self, controller: CronController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\u23F0  Cron Jobs")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)

        toolbar.addWidget(QLabel("User:"))
        self._user_combo = QComboBox()
        self._user_combo.addItem("Current User", None)
        self._user_combo.addItem("root", "root")
        self._user_combo.currentIndexChanged.connect(self._on_user_changed)
        toolbar.addWidget(self._user_combo)

        self._add_btn = QPushButton("\u2795  Add")
        self._add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(self._add_btn)

        self._toggle_btn = QPushButton("\u23EF  Toggle")
        self._toggle_btn.clicked.connect(self._on_toggle)
        toolbar.addWidget(self._toggle_btn)

        self._remove_btn = QPushButton("\U0001F5D1  Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        toolbar.addWidget(self._remove_btn)

        self._refresh_btn = QPushButton("\U0001F504  Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)

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
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

        self._jobs: list[dict] = []

    def _connect_signals(self) -> None:
        self._ctrl.cron_loaded.connect(self._populate_table)
        self._ctrl.operation_success.connect(
            lambda msg: show_toast(self.window(), msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    def _on_refresh(self) -> None:
        user = self._user_combo.currentData()
        self._ctrl.refresh_cron(user)

    def _on_user_changed(self) -> None:
        self._on_refresh()

    def _populate_table(self, jobs: list[dict]) -> None:
        self._jobs = jobs
        self._table.setRowCount(len(jobs))
        for row, j in enumerate(jobs):
            enabled_item = QTableWidgetItem("\u2705" if j["enabled"] else "\u274C")
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 0, enabled_item)

            schedule = j["minute"]
            if j["hour"]:
                schedule += f" {j['hour']} {j['dom']} {j['month']} {j['dow']}"
            self._table.setItem(row, 1, QTableWidgetItem(schedule))
            self._table.setItem(row, 2, QTableWidgetItem(j["command"]))
        self._table.resizeColumnsToContents()

    def _selected_job(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._jobs):
            return None
        return self._jobs[row]

    def _on_add(self) -> None:
        dialog = _AddCronDialog(self)
        if dialog.exec():
            schedule = dialog.get_schedule()
            command = dialog.get_command()
            if schedule and command:
                self._ctrl.add_job(schedule, command)

    def _on_toggle(self) -> None:
        job = self._selected_job()
        if job:
            self._ctrl.toggle_job(job["index"])

    def _on_remove(self) -> None:
        job = self._selected_job()
        if not job:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Remove cron job?\n{job['command']}"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.remove_job(job["index"])

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u23EF  Toggle", self, triggered=self._on_toggle))
        menu.addAction(QAction("\U0001F5D1  Remove", self, triggered=self._on_remove))
        menu.exec(self._table.viewport().mapToGlobal(pos))
