from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QComboBox,
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

from app.controllers.package_controller import PackageController

_TYPE_COLORS = {
    "deb": QColor("#2ea043"),
    "snap": QColor("#d29922"),
    "flatpak": QColor("#58a6ff"),
}


class _SizeItem(QTableWidgetItem):
    """Table item that sorts numerically by size_bytes."""

    def __init__(self, text: str, size_bytes: int):
        super().__init__(text)
        self._size_bytes = size_bytes

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _SizeItem):
            return self._size_bytes < other._size_bytes
        return super().__lt__(other)


class PackagesView(QWidget):
    """Installed package list with uninstall/purge/reinstall/reset/update."""

    COLUMNS = ["Name", "Version", "Size", "Type", "Source", "Description"]

    def __init__(self, controller: PackageController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_packages: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F4E6  Packages")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar — action buttons
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._uninstall_btn = QPushButton("\U0001F5D1  Uninstall")
        self._purge_btn = QPushButton("\u2716  Purge")
        self._reinstall_btn = QPushButton("\U0001F504  Reinstall")
        self._reset_btn = QPushButton("\u267B  Reset")
        self._update_btn = QPushButton("\u2B06  Update")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._uninstall_btn, self._purge_btn, self._reinstall_btn,
            self._reset_btn, self._update_btn, self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Filter row — type combo + search
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Type:"))
        self._type_combo = QComboBox()
        self._type_combo.addItems(["All", "Deb", "Snap", "Flatpak"])
        self._type_combo.setFixedWidth(120)
        self._type_combo.currentIndexChanged.connect(self._apply_filter)
        filter_row.addWidget(self._type_combo)
        filter_row.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter packages...")
        self._search.setMaximumWidth(250)
        self._search.textChanged.connect(self._apply_filter)
        filter_row.addWidget(self._search)
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
            QHeaderView.ResizeMode.Interactive
        )
        self._table.setColumnWidth(0, 200)
        self._table.setColumnWidth(1, 140)
        self._table.setColumnWidth(2, 90)
        self._table.setColumnWidth(3, 70)
        self._table.setColumnWidth(4, 120)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.packages_loaded.connect(self._on_packages_loaded)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._uninstall_btn.clicked.connect(lambda: self._on_action("uninstall"))
        self._purge_btn.clicked.connect(lambda: self._on_action("purge"))
        self._reinstall_btn.clicked.connect(lambda: self._on_action("reinstall"))
        self._reset_btn.clicked.connect(lambda: self._on_action("reset"))
        self._update_btn.clicked.connect(lambda: self._on_action("update"))
        self._refresh_btn.clicked.connect(self._ctrl.refresh_packages)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\U0001F5D1  Uninstall", self,
            triggered=lambda: self._on_action("uninstall"),
        ))
        menu.addAction(QAction(
            "\u2716  Purge", self,
            triggered=lambda: self._on_action("purge"),
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\U0001F504  Reinstall", self,
            triggered=lambda: self._on_action("reinstall"),
        ))
        menu.addAction(QAction(
            "\u267B  Reset", self,
            triggered=lambda: self._on_action("reset"),
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\u2B06  Update", self,
            triggered=lambda: self._on_action("update"),
        ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_package(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        name_item = self._table.item(row, 0)
        type_item = self._table.item(row, 3)
        if not name_item or not type_item:
            return None
        return {"name": name_item.text(), "type": type_item.text()}

    def _on_packages_loaded(self, packages: list[dict]) -> None:
        self._all_packages = packages
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        type_filter = self._type_combo.currentText().lower()

        filtered = []
        for p in self._all_packages:
            if type_filter != "all" and p["type"] != type_filter:
                continue
            if text and text not in p["name"].lower() and text not in p.get("description", "").lower():
                continue
            filtered.append(p)
        self._populate_table(filtered)

    def _populate_table(self, packages: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(packages))
        for row, p in enumerate(packages):
            self._table.setItem(row, 0, QTableWidgetItem(p["name"]))
            self._table.setItem(row, 1, QTableWidgetItem(p["version"]))

            size_item = _SizeItem(p["size"], p["size_bytes"])
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 2, size_item)

            type_item = QTableWidgetItem(p["type"])
            color = _TYPE_COLORS.get(p["type"], QColor("#8b949e"))
            type_item.setForeground(color)
            self._table.setItem(row, 3, type_item)

            self._table.setItem(row, 4, QTableWidgetItem(p.get("source", "")))
            self._table.setItem(row, 5, QTableWidgetItem(p.get("description", "")))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_action(self, action: str) -> None:
        pkg = self._selected_package()
        if not pkg:
            return

        # Confirm destructive actions
        if action in ("uninstall", "purge", "reset"):
            label = {"uninstall": "Uninstall", "purge": "Purge", "reset": "Reset"}[action]
            reply = QMessageBox.question(
                self,
                f"Confirm {label}",
                f"{label} package '{pkg['name']}' ({pkg['type']})?\n\n"
                f"This action requires sudo privileges.",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self._ctrl.run_action(pkg["name"], pkg["type"], action)
