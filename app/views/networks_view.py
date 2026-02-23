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
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.network_controller import NetworkController


class NetworksView(QWidget):
    """Table-based network list with create/remove actions and context menu."""

    COLUMNS = ["ID", "Name", "Driver", "Scope", "Subnet", "Containers"]

    def __init__(self, controller: NetworkController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F310  Networks")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._create_btn = QPushButton("\u2795  Create Network")
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
        self._ctrl.networks_loaded.connect(self._populate_table)
        self._ctrl.operation_success.connect(
            lambda msg: self.window().statusBar().showMessage(msg, 5000)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._create_btn.clicked.connect(self._on_create)
        self._remove_btn.clicked.connect(self._on_remove)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_networks)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u2795  Create Network", self, triggered=self._on_create))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Remove", self, triggered=self._on_remove))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _populate_table(self, networks: list[dict]) -> None:
        self._table.setRowCount(len(networks))
        for row, net in enumerate(networks):
            self._table.setItem(row, 0, QTableWidgetItem(net["id"]))
            self._table.setItem(row, 1, QTableWidgetItem(net["name"]))
            self._table.setItem(row, 2, QTableWidgetItem(net["driver"]))
            self._table.setItem(row, 3, QTableWidgetItem(net["scope"]))
            self._table.setItem(row, 4, QTableWidgetItem(net["subnet"]))
            self._table.setItem(row, 5, QTableWidgetItem(net["containers"]))
        self._table.resizeColumnsToContents()

    def _on_create(self) -> None:
        dialog = _CreateNetworkDialog(self)
        if dialog.exec():
            name = dialog.name()
            driver = dialog.driver()
            if name:
                self._ctrl.create_network(name, driver)

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        net_id = self._table.item(row, 0).text()
        net_name = self._table.item(row, 1).text()
        reply = QMessageBox.question(
            self, "Confirm", f"Remove network '{net_name}' ({net_id})?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.remove_network(net_id)


class _CreateNetworkDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Network")
        self.setMinimumWidth(380)

        layout = QFormLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("my-network")
        layout.addRow("Name:", self._name_edit)

        self._driver_combo = QComboBox()
        self._driver_combo.addItems(["bridge", "host", "overlay", "macvlan", "none"])
        layout.addRow("Driver:", self._driver_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def name(self) -> str:
        return self._name_edit.text().strip()

    def driver(self) -> str:
        return self._driver_combo.currentText()
