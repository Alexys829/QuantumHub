from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.controllers.journal_controller import JournalController


class JournalView(QWidget):
    """System Logs view using journalctl."""

    def __init__(self, controller: JournalController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F4CB  System Logs")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("Unit:"))
        self._unit_combo = QComboBox()
        self._unit_combo.addItem("All", None)
        self._unit_combo.setMinimumWidth(200)
        self._unit_combo.setEditable(True)
        toolbar.addWidget(self._unit_combo)

        toolbar.addWidget(QLabel("Priority:"))
        self._priority_combo = QComboBox()
        self._priority_combo.addItems([
            "All", "0 - emerg", "1 - alert", "2 - crit", "3 - err",
            "4 - warning", "5 - notice", "6 - info", "7 - debug",
        ])
        toolbar.addWidget(self._priority_combo)

        toolbar.addWidget(QLabel("Since:"))
        self._since_combo = QComboBox()
        self._since_combo.addItems([
            "All", "1 hour ago", "6 hours ago", "24 hours ago",
            "7 days ago", "30 days ago",
        ])
        toolbar.addWidget(self._since_combo)

        toolbar.addWidget(QLabel("Lines:"))
        self._lines_combo = QComboBox()
        self._lines_combo.addItems(["100", "200", "500", "1000", "5000"])
        self._lines_combo.setCurrentText("200")
        self._lines_combo.setFixedWidth(80)
        toolbar.addWidget(self._lines_combo)

        self._refresh_btn = QPushButton("\U0001F504  Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        toolbar.addWidget(self._refresh_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Filter
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Filter:"))
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Keyword filter...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._filter_input)
        layout.addLayout(filter_row)

        # Log output
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(10000)
        self._text.setStyleSheet(
            "QPlainTextEdit { font-family: monospace; font-size: 12px; }"
        )
        layout.addWidget(self._text)

        self._all_lines: list[str] = []

    def _connect_signals(self) -> None:
        self._ctrl.logs_loaded.connect(self._on_logs_loaded)
        self._ctrl.units_loaded.connect(self._on_units_loaded)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    def _on_refresh(self) -> None:
        unit = self._unit_combo.currentData()
        if unit is None and self._unit_combo.currentText() != "All":
            unit = self._unit_combo.currentText()

        priority_text = self._priority_combo.currentText()
        priority = None
        if priority_text != "All":
            priority = priority_text.split(" - ")[0]

        since_text = self._since_combo.currentText()
        since = None if since_text == "All" else since_text

        lines = int(self._lines_combo.currentText())

        self._ctrl.refresh_logs(unit=unit, priority=priority, since=since, lines=lines)

    def _on_logs_loaded(self, lines: list[str]) -> None:
        self._all_lines = lines
        self._apply_filter()

    def _on_units_loaded(self, units: list[str]) -> None:
        current = self._unit_combo.currentText()
        self._unit_combo.clear()
        self._unit_combo.addItem("All", None)
        for u in units:
            self._unit_combo.addItem(u, u)
        idx = self._unit_combo.findText(current)
        if idx >= 0:
            self._unit_combo.setCurrentIndex(idx)

    def _apply_filter(self) -> None:
        keyword = self._filter_input.text().strip().lower()
        self._text.clear()
        for line in self._all_lines:
            if not keyword or keyword in line.lower():
                self._text.appendPlainText(line)
