from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
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

from app.controllers.apt_repo_controller import AptRepoController


class _AddRepoDialog(QDialog):
    """Dialog for adding a new APT repository."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Repository")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(
            "Enter a repository line (e.g. deb http://... suite component)\n"
            "or a PPA (e.g. ppa:user/repo)"
        )
        info.setStyleSheet("color: #bbbbbb;")
        layout.addWidget(info)

        self._input = QLineEdit()
        self._input.setPlaceholderText("deb http://archive.ubuntu.com/ubuntu noble main")
        layout.addWidget(self._input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_repo_line(self) -> str:
        return self._input.text().strip()


class AptReposView(QWidget):
    """APT repository manager: enable/disable/add/delete repos."""

    COLUMNS = ["Enabled", "Type", "URI", "Suite", "Components", "File"]

    def __init__(self, controller: AptRepoController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._all_repos: list[dict] = []
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F4CB  APT Repositories")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._enable_btn = QPushButton("\u2705  Enable")
        self._disable_btn = QPushButton("\u274C  Disable")
        self._add_btn = QPushButton("\u2795  Add")
        self._delete_btn = QPushButton("\U0001F5D1  Delete")
        self._update_btn = QPushButton("\U0001F504  apt update")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._enable_btn, self._disable_btn, self._add_btn,
            self._delete_btn, self._update_btn, self._refresh_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter repos...")
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
        self._table.setColumnWidth(0, 70)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 300)
        self._table.setColumnWidth(3, 100)
        self._table.setColumnWidth(4, 150)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._ctrl.repos_loaded.connect(self._on_repos_loaded)
        self._ctrl.operation_success.connect(
            lambda msg: QMessageBox.information(self, "Success", msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._enable_btn.clicked.connect(lambda: self._on_toggle(True))
        self._disable_btn.clicked.connect(lambda: self._on_toggle(False))
        self._add_btn.clicked.connect(self._on_add)
        self._delete_btn.clicked.connect(self._on_delete)
        self._update_btn.clicked.connect(self._on_update)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_repos)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction(
            "\u2705  Enable", self, triggered=lambda: self._on_toggle(True)
        ))
        menu.addAction(QAction(
            "\u274C  Disable", self, triggered=lambda: self._on_toggle(False)
        ))
        menu.addSeparator()
        menu.addAction(QAction(
            "\U0001F5D1  Delete", self, triggered=self._on_delete
        ))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _selected_repo(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        # Find original repo from _all_repos matching this row
        uri_item = self._table.item(row, 2)
        file_item = self._table.item(row, 5)
        if not uri_item or not file_item:
            return None
        uri = uri_item.text()
        file_name = file_item.text()
        for r in self._all_repos:
            if r["uri"] == uri and r["file"] == file_name:
                return r
        return None

    def _on_repos_loaded(self, repos: list[dict]) -> None:
        self._all_repos = repos
        self._apply_filter()

    def _apply_filter(self) -> None:
        text = self._search.text().lower()
        filtered = [
            r for r in self._all_repos
            if not text or text in str(r).lower()
        ]
        self._populate_table(filtered)

    def _populate_table(self, repos: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(repos))
        for row, r in enumerate(repos):
            enabled_text = "\u2705" if r["enabled"] else "\u274C"
            enabled_item = QTableWidgetItem(enabled_text)
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            color = QColor("#2ea043") if r["enabled"] else QColor("#8b949e")
            enabled_item.setForeground(color)
            self._table.setItem(row, 0, enabled_item)

            self._table.setItem(row, 1, QTableWidgetItem(r["type"]))
            self._table.setItem(row, 2, QTableWidgetItem(r["uri"]))
            self._table.setItem(row, 3, QTableWidgetItem(r["suite"]))
            self._table.setItem(row, 4, QTableWidgetItem(r["components"]))

            # Show just filename, not full path
            import os
            file_display = os.path.basename(r["file"])
            self._table.setItem(row, 5, QTableWidgetItem(file_display))
        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _on_toggle(self, enable: bool) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        self._ctrl.toggle_repo(repo["file"], repo["line_num"], enable)

    def _on_add(self) -> None:
        dialog = _AddRepoDialog(parent=self)
        if dialog.exec():
            line = dialog.get_repo_line()
            if line:
                self._ctrl.add_repo(line)
            else:
                QMessageBox.warning(
                    self, "Validation", "Repository line cannot be empty."
                )

    def _on_delete(self) -> None:
        repo = self._selected_repo()
        if not repo:
            return
        reply = QMessageBox.question(
            self,
            "Delete Repository",
            f"Delete this repository?\n\n{repo['raw_line']}\n\n"
            f"From: {repo['file']}",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_repo(repo["file"], repo["line_num"])

    def _on_update(self) -> None:
        reply = QMessageBox.question(
            self,
            "apt update",
            "Run 'sudo apt update'?\n\nThis may take a minute.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.run_update()
