from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.file_transfer_controller import FileTransferController
from app.services.connection_manager import ConnectionManager


class _SizeItem(QTableWidgetItem):
    """Table item that sorts numerically by raw byte count."""

    def __init__(self, text: str, size_bytes: int):
        super().__init__(text)
        self._size_bytes = size_bytes

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, _SizeItem):
            return self._size_bytes < other._size_bytes
        return super().__lt__(other)


class _FilePaneWidget(QWidget):
    """Single file browser pane (reused for local and server side)."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._title_text = title
        self._current_path = ""
        self._entries = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Title
        self._title_label = QLabel(self._title_text)
        self._title_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0; padding: 2px 0;"
        )
        layout.addWidget(self._title_label)

        # Path bar
        path_bar = QHBoxLayout()
        path_bar.setSpacing(4)

        _pb_style = (
            "QPushButton { background-color: #333333; color: #e0e0e0;"
            "  border: 1px solid #444444; border-radius: 4px;"
            "  font-size: 13px; font-weight: bold;"
            "  padding: 4px 10px; min-width: 0px; }"
            "QPushButton:hover { background-color: #444444; color: #ffffff; }"
        )

        self._parent_btn = QPushButton("..")
        self._parent_btn.setToolTip("Parent directory")
        self._parent_btn.setStyleSheet(_pb_style)
        path_bar.addWidget(self._parent_btn)

        self._home_btn = QPushButton("~")
        self._home_btn.setToolTip("Home directory")
        self._home_btn.setStyleSheet(_pb_style)
        path_bar.addWidget(self._home_btn)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Path...")
        path_bar.addWidget(self._path_edit)

        self._refresh_btn = QPushButton("R")
        self._refresh_btn.setToolTip("Refresh")
        self._refresh_btn.setStyleSheet(_pb_style)
        path_bar.addWidget(self._refresh_btn)

        layout.addLayout(path_bar)

        # Table
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["Name", "Size", "Modified", "Permissions"])
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

        self._table.setStyleSheet(
            "QTableWidget { gridline-color: #3a3a3a; }"
            "QTableWidget::item { padding: 4px 8px; }"
            "QHeaderView::section { background-color: #2d2d2d; color: #bbbbbb;"
            "  border: none; border-bottom: 1px solid #3a3a3a; padding: 6px 8px;"
            "  font-weight: 600; }"
        )
        layout.addWidget(self._table)

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def current_path(self) -> str:
        return self._current_path

    def set_path(self, path: str) -> None:
        self._current_path = path
        self._path_edit.setText(path)

    def selected_entries(self) -> list:
        rows = set()
        for idx in self._table.selectedIndexes():
            rows.add(idx.row())
        return [self._entries[r] for r in sorted(rows) if r < len(self._entries)]

    def populate(self, entries: list) -> None:
        self._entries = entries
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(entries))

        for row, entry in enumerate(entries):
            # Name
            icon = "\U0001F4C1 " if entry.is_dir else "\U0001F4C4 "
            name_item = QTableWidgetItem(f"{icon}{entry.name}")
            name_item.setData(Qt.ItemDataRole.UserRole, entry)
            if entry.is_dir:
                name_item.setForeground(Qt.GlobalColor.cyan)
            self._table.setItem(row, 0, name_item)

            # Size
            size_item = _SizeItem(entry.size_human, entry.size)
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._table.setItem(row, 1, size_item)

            # Modified
            mod_item = QTableWidgetItem(entry.modified_str)
            self._table.setItem(row, 2, mod_item)

            # Permissions
            perm_item = QTableWidgetItem(entry.permissions)
            perm_item.setForeground(Qt.GlobalColor.darkGray)
            self._table.setItem(row, 3, perm_item)

        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)


class FileTransferView(QWidget):
    """Dual-pane file manager with upload/download and progress bar."""

    def __init__(self, controller: FileTransferController,
                 connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._cm = connection_manager
        self._loaded = False
        self._local_path = ""
        self._server_path = ""
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F4C2  File Transfer")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Transfer buttons
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)
        btn_bar.addStretch()

        self._upload_btn = QPushButton("Upload  \u25B6\u25B6")
        self._upload_btn.setToolTip("Upload selected local files to server")
        self._upload_btn.setStyleSheet(
            "QPushButton { background-color: #094771; color: #ffffff; border: none;"
            "  padding: 6px 16px; border-radius: 4px; font-weight: 600; }"
            "QPushButton:hover { background-color: #0d5a8f; }"
            "QPushButton:disabled { background-color: #333333; color: #666666; }"
        )
        btn_bar.addWidget(self._upload_btn)

        self._download_btn = QPushButton("\u25C0\u25C0  Download")
        self._download_btn.setToolTip("Download selected server files to local")
        self._download_btn.setStyleSheet(
            "QPushButton { background-color: #1a7f37; color: #ffffff; border: none;"
            "  padding: 6px 16px; border-radius: 4px; font-weight: 600; }"
            "QPushButton:hover { background-color: #238636; }"
            "QPushButton:disabled { background-color: #333333; color: #666666; }"
        )
        btn_bar.addWidget(self._download_btn)

        btn_bar.addStretch()
        layout.addLayout(btn_bar)

        # Splitter with two panes
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._local_pane = _FilePaneWidget("\U0001F4BB  Local")
        self._server_pane = _FilePaneWidget("\U0001F5A5  Server")
        splitter.addWidget(self._local_pane)
        splitter.addWidget(self._server_pane)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, 1)

        # Progress bar area
        self._progress_widget = QWidget()
        progress_layout = QHBoxLayout(self._progress_widget)
        progress_layout.setContentsMargins(0, 4, 0, 0)
        progress_layout.setSpacing(8)

        self._progress_label = QLabel("")
        self._progress_label.setStyleSheet("color: #bbbbbb; font-size: 12px;")
        progress_layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(100)
        self._progress_bar.setFixedHeight(18)
        self._progress_bar.setStyleSheet(
            "QProgressBar { background-color: #2d2d2d; border: 1px solid #3a3a3a;"
            "  border-radius: 4px; text-align: center; color: #e0e0e0; font-size: 11px; }"
            "QProgressBar::chunk { background-color: #094771; border-radius: 3px; }"
        )
        progress_layout.addWidget(self._progress_bar, 1)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedWidth(70)
        self._cancel_btn.setStyleSheet(
            "QPushButton { background-color: #6e2d2d; color: #ffffff; border: none;"
            "  padding: 4px 10px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #8b3a3a; }"
        )
        progress_layout.addWidget(self._cancel_btn)

        self._progress_widget.setVisible(False)
        layout.addWidget(self._progress_widget)

    def _connect_signals(self) -> None:
        # Controller signals
        self._ctrl.local_directory_listed.connect(self._on_local_listed)
        self._ctrl.server_directory_listed.connect(self._on_server_listed)
        self._ctrl.transfer_started.connect(self._on_transfer_started)
        self._ctrl.transfer_progress.connect(self._on_transfer_progress)
        self._ctrl.transfer_complete.connect(self._on_transfer_complete)
        self._ctrl.transfer_error.connect(self._on_transfer_error)
        self._ctrl.operation_success.connect(self._on_operation_success)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

        # Upload / Download buttons
        self._upload_btn.clicked.connect(self._on_upload)
        self._download_btn.clicked.connect(self._on_download)
        self._cancel_btn.clicked.connect(self._ctrl.cancel_transfer)

        # Local pane
        self._local_pane._parent_btn.clicked.connect(self._local_go_parent)
        self._local_pane._home_btn.clicked.connect(self._local_go_home)
        self._local_pane._refresh_btn.clicked.connect(self._refresh_local)
        self._local_pane._path_edit.returnPressed.connect(self._local_path_entered)
        self._local_pane._table.doubleClicked.connect(self._local_double_click)
        self._local_pane._table.customContextMenuRequested.connect(
            self._local_context_menu
        )

        # Server pane
        self._server_pane._parent_btn.clicked.connect(self._server_go_parent)
        self._server_pane._home_btn.clicked.connect(self._server_go_home)
        self._server_pane._refresh_btn.clicked.connect(self._refresh_server)
        self._server_pane._path_edit.returnPressed.connect(self._server_path_entered)
        self._server_pane._table.doubleClicked.connect(self._server_double_click)
        self._server_pane._table.customContextMenuRequested.connect(
            self._server_context_menu
        )

    # ── first-entry loading ─────────────────────────────────

    def load_initial(self) -> None:
        if self._loaded:
            return
        self._loaded = True

        self._local_path = self._ctrl.get_local_home()
        self._local_pane.set_path(self._local_path)
        self._ctrl.refresh_local_directory(self._local_path)

        try:
            self._server_path = self._ctrl.get_server_home()
        except Exception:
            self._server_path = "/"
        self._server_pane.set_path(self._server_path)
        self._ctrl.refresh_server_directory(self._server_path)

        # Update server pane title
        if self._cm.active_server:
            self._server_pane.set_title(
                f"\U0001F5A5  Server ({self._cm.active_server.name})"
            )
        else:
            self._server_pane.set_title("\U0001F5A5  Server (localhost)")

    def reset(self) -> None:
        self._loaded = False

    # ── listing callbacks ───────────────────────────────────

    def _on_local_listed(self, entries: list) -> None:
        self._local_pane.populate(entries)

    def _on_server_listed(self, entries: list) -> None:
        self._server_pane.populate(entries)

    # ── local navigation ────────────────────────────────────

    def _refresh_local(self) -> None:
        self._ctrl.refresh_local_directory(self._local_path)

    def _local_go_parent(self) -> None:
        parent = os.path.dirname(self._local_path)
        if parent and parent != self._local_path:
            self._local_path = parent
            self._local_pane.set_path(parent)
            self._ctrl.refresh_local_directory(parent)

    def _local_go_home(self) -> None:
        self._local_path = self._ctrl.get_local_home()
        self._local_pane.set_path(self._local_path)
        self._ctrl.refresh_local_directory(self._local_path)

    def _local_path_entered(self) -> None:
        path = self._local_pane._path_edit.text().strip()
        if path and os.path.isdir(path):
            self._local_path = path
            self._ctrl.refresh_local_directory(path)

    def _local_double_click(self, index) -> None:
        row = index.row()
        if row < len(self._local_pane._entries):
            entry = self._local_pane._entries[row]
            if entry.is_dir:
                self._local_path = entry.path
                self._local_pane.set_path(entry.path)
                self._ctrl.refresh_local_directory(entry.path)

    # ── server navigation ───────────────────────────────────

    def _refresh_server(self) -> None:
        self._ctrl.refresh_server_directory(self._server_path)

    def _server_go_parent(self) -> None:
        if self._cm.is_local:
            parent = os.path.dirname(self._server_path)
        else:
            from pathlib import PurePosixPath
            parent = str(PurePosixPath(self._server_path).parent)
        if parent and parent != self._server_path:
            self._server_path = parent
            self._server_pane.set_path(parent)
            self._ctrl.refresh_server_directory(parent)

    def _server_go_home(self) -> None:
        try:
            self._server_path = self._ctrl.get_server_home()
        except Exception:
            self._server_path = "/"
        self._server_pane.set_path(self._server_path)
        self._ctrl.refresh_server_directory(self._server_path)

    def _server_path_entered(self) -> None:
        path = self._server_pane._path_edit.text().strip()
        if path:
            self._server_path = path
            self._ctrl.refresh_server_directory(path)

    def _server_double_click(self, index) -> None:
        row = index.row()
        if row < len(self._server_pane._entries):
            entry = self._server_pane._entries[row]
            if entry.is_dir:
                self._server_path = entry.path
                self._server_pane.set_path(entry.path)
                self._ctrl.refresh_server_directory(entry.path)

    # ── transfer actions ────────────────────────────────────

    def _on_upload(self) -> None:
        selected = self._local_pane.selected_entries()
        if not selected:
            QMessageBox.information(self, "Upload", "Select files on the local pane first.")
            return
        for entry in selected:
            self._ctrl.upload(entry.path, self._server_path, entry.is_dir)

    def _on_download(self) -> None:
        selected = self._server_pane.selected_entries()
        if not selected:
            QMessageBox.information(self, "Download", "Select files on the server pane first.")
            return
        for entry in selected:
            self._ctrl.download(entry.path, self._local_path, entry.is_dir)

    # ── transfer progress ───────────────────────────────────

    def _on_transfer_started(self, msg: str) -> None:
        self._progress_widget.setVisible(True)
        self._progress_label.setText(msg)
        self._progress_bar.setValue(0)
        self._upload_btn.setEnabled(False)
        self._download_btn.setEnabled(False)

    def _on_transfer_progress(self, file_name: str, bytes_done: int,
                               bytes_total: int, files_done: int,
                               files_total: int) -> None:
        if bytes_total > 0:
            pct = int(bytes_done * 100 / bytes_total)
        else:
            pct = 0
        self._progress_bar.setValue(pct)
        if files_total > 1:
            self._progress_label.setText(
                f"{file_name}  ({files_done}/{files_total} files)  {pct}%"
            )
        else:
            self._progress_label.setText(f"{file_name}  {pct}%")

    def _on_transfer_complete(self, msg: str) -> None:
        self._progress_widget.setVisible(False)
        self._upload_btn.setEnabled(True)
        self._download_btn.setEnabled(True)
        self._refresh_local()
        self._refresh_server()

    def _on_transfer_error(self, msg: str) -> None:
        self._progress_widget.setVisible(False)
        self._upload_btn.setEnabled(True)
        self._download_btn.setEnabled(True)
        QMessageBox.warning(self, "Transfer Error", msg)

    # ── file operation callback ─────────────────────────────

    def _on_operation_success(self, msg: str) -> None:
        self._refresh_local()
        self._refresh_server()

    # ── context menus ───────────────────────────────────────

    def _local_context_menu(self, pos) -> None:
        menu = QMenu(self)
        new_folder = QAction("New Folder", self)
        new_folder.triggered.connect(self._local_new_folder)
        menu.addAction(new_folder)

        selected = self._local_pane.selected_entries()
        if selected:
            rename = QAction("Rename", self)
            rename.triggered.connect(self._local_rename)
            menu.addAction(rename)

            delete = QAction("Delete", self)
            delete.triggered.connect(self._local_delete)
            menu.addAction(delete)

            menu.addSeparator()
            upload = QAction("Upload to Server \u25B6\u25B6", self)
            upload.triggered.connect(self._on_upload)
            menu.addAction(upload)

        menu.exec(self._local_pane._table.viewport().mapToGlobal(pos))

    def _server_context_menu(self, pos) -> None:
        menu = QMenu(self)
        new_folder = QAction("New Folder", self)
        new_folder.triggered.connect(self._server_new_folder)
        menu.addAction(new_folder)

        selected = self._server_pane.selected_entries()
        if selected:
            rename = QAction("Rename", self)
            rename.triggered.connect(self._server_rename)
            menu.addAction(rename)

            delete = QAction("Delete", self)
            delete.triggered.connect(self._server_delete)
            menu.addAction(delete)

            menu.addSeparator()
            download = QAction("\u25C0\u25C0  Download to Local", self)
            download.triggered.connect(self._on_download)
            menu.addAction(download)

        menu.exec(self._server_pane._table.viewport().mapToGlobal(pos))

    # ── local file ops ──────────────────────────────────────

    def _local_new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            path = os.path.join(self._local_path, name)
            self._ctrl.create_directory_local(path)

    def _local_rename(self) -> None:
        selected = self._local_pane.selected_entries()
        if not selected:
            return
        entry = selected[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=entry.name
        )
        if ok and new_name and new_name != entry.name:
            new_path = os.path.join(os.path.dirname(entry.path), new_name)
            self._ctrl.rename_local(entry.path, new_path)

    def _local_delete(self) -> None:
        selected = self._local_pane.selected_entries()
        if not selected:
            return
        names = ", ".join(e.name for e in selected[:5])
        if len(selected) > 5:
            names += f", ... ({len(selected)} total)"
        reply = QMessageBox.question(
            self, "Delete", f"Delete {names}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for entry in selected:
                self._ctrl.delete_local(entry.path)

    # ── server file ops ─────────────────────────────────────

    def _server_new_folder(self) -> None:
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if ok and name:
            if self._cm.is_local:
                path = os.path.join(self._server_path, name)
            else:
                from pathlib import PurePosixPath
                path = str(PurePosixPath(self._server_path) / name)
            self._ctrl.create_directory_server(path)

    def _server_rename(self) -> None:
        selected = self._server_pane.selected_entries()
        if not selected:
            return
        entry = selected[0]
        new_name, ok = QInputDialog.getText(
            self, "Rename", "New name:", text=entry.name
        )
        if ok and new_name and new_name != entry.name:
            if self._cm.is_local:
                new_path = os.path.join(os.path.dirname(entry.path), new_name)
            else:
                from pathlib import PurePosixPath
                parent = str(PurePosixPath(entry.path).parent)
                new_path = str(PurePosixPath(parent) / new_name)
            self._ctrl.rename_server(entry.path, new_path)

    def _server_delete(self) -> None:
        selected = self._server_pane.selected_entries()
        if not selected:
            return
        names = ", ".join(e.name for e in selected[:5])
        if len(selected) > 5:
            names += f", ... ({len(selected)} total)"
        reply = QMessageBox.question(
            self, "Delete", f"Delete {names}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            for entry in selected:
                self._ctrl.delete_server(entry.path)
