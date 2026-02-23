from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.registry_controller import RegistryController
from app.views.toast import show_toast


class RegistryView(QWidget):
    """Docker Hub registry search view."""

    COLUMNS = ["Name", "Description", "Stars", "Official", "Automated"]

    def __init__(self, controller: RegistryController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._results: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F50D  Docker Registry")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Search bar
        search_row = QHBoxLayout()
        search_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search Docker Hub (e.g. nginx, ubuntu, python)...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self._search_input)

        self._search_btn = QPushButton("\U0001F50D  Search")
        self._search_btn.clicked.connect(self._on_search)
        search_row.addWidget(self._search_btn)

        self._pull_btn = QPushButton("\u2B07  Pull")
        self._pull_btn.clicked.connect(self._on_pull)
        search_row.addWidget(self._pull_btn)

        layout.addLayout(search_row)

        # Results table
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
        layout.addWidget(self._table)

        # Status
        self._status = QLabel()
        self._status.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self._status)

    def _connect_signals(self) -> None:
        self._ctrl.results_loaded.connect(self._populate_table)
        self._ctrl.operation_success.connect(
            lambda msg: show_toast(self.window(), msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    def _on_search(self) -> None:
        term = self._search_input.text().strip()
        if not term:
            return
        self._status.setText(f"Searching for '{term}'...")
        self._ctrl.search(term)

    def _populate_table(self, results: list[dict]) -> None:
        self._results = results
        self._table.setRowCount(len(results))
        for row, r in enumerate(results):
            self._table.setItem(row, 0, QTableWidgetItem(r.get("name", "")))
            self._table.setItem(row, 1, QTableWidgetItem(r.get("description", "") or ""))

            stars_item = QTableWidgetItem(str(r.get("star_count", 0)))
            stars_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, stars_item)

            official = "\u2705" if r.get("is_official") else ""
            off_item = QTableWidgetItem(official)
            off_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 3, off_item)

            automated = "\u2705" if r.get("is_automated") else ""
            auto_item = QTableWidgetItem(automated)
            auto_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 4, auto_item)

        self._table.resizeColumnsToContents()
        self._status.setText(f"{len(results)} results found.")

    def _on_pull(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._results):
            return
        name = self._results[row].get("name", "")
        tag, ok = QInputDialog.getText(
            self, "Pull Image", f"Tag for '{name}':", text="latest"
        )
        if ok and tag:
            self._status.setText(f"Pulling {name}:{tag}...")
            self._ctrl.pull_image(name, tag)
