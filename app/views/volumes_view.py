from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.volume_controller import VolumeController


class VolumesView(QWidget):
    """Table-based volume list with create/remove actions and context menu."""

    COLUMNS = ["Name", "Driver", "Mountpoint", "Created"]

    def __init__(self, controller: VolumeController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F4BE  Volumes")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._create_btn = QPushButton("\u2795  Create Volume")
        self._remove_btn = QPushButton("\U0001F5D1  Remove")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (self._create_btn, self._remove_btn, self._refresh_btn):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

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
        self._ctrl.volumes_loaded.connect(self._populate_table)
        self._ctrl.operation_success.connect(
            lambda msg: self.window().statusBar().showMessage(msg, 5000)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._create_btn.clicked.connect(self._on_create)
        self._remove_btn.clicked.connect(self._on_remove)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_volumes)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u2795  Create Volume", self, triggered=self._on_create))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Remove", self, triggered=self._on_remove))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _populate_table(self, volumes: list[dict]) -> None:
        self._table.setRowCount(len(volumes))
        for row, vol in enumerate(volumes):
            self._table.setItem(row, 0, QTableWidgetItem(vol["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(vol["driver"]))
            self._table.setItem(row, 2, QTableWidgetItem(vol["mountpoint"]))
            self._table.setItem(row, 3, QTableWidgetItem(vol["created"]))
        self._table.resizeColumnsToContents()

    def _on_create(self) -> None:
        name, ok = QInputDialog.getText(self, "Create Volume", "Volume name:")
        if ok and name.strip():
            self._ctrl.create_volume(name.strip())

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._table.item(row, 0).text()
        reply = QMessageBox.question(
            self, "Confirm", f"Remove volume '{name}'?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.remove_volume(name, force=True)
