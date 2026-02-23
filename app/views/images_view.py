from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.image_controller import ImageController
from app.views.toast import show_toast


class _BuildDialog(QDialog):
    """Dialog for building a Docker image from a Dockerfile."""

    def __init__(self, connection_manager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self.setWindowTitle("Build Docker Image")
        self.setMinimumSize(650, 450)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Tag input
        tag_row = QHBoxLayout()
        tag_row.addWidget(QLabel("Tag:"))
        self._tag_input = QLineEdit()
        self._tag_input.setPlaceholderText("myimage:latest")
        tag_row.addWidget(self._tag_input)
        layout.addLayout(tag_row)

        # Path input
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Context:"))
        self._path_input = QLineEdit()
        self._path_input.setPlaceholderText("/path/to/dockerfile/directory")
        path_row.addWidget(self._path_input)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Build output
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(5000)
        self._output.setStyleSheet(
            "QPlainTextEdit { font-family: monospace; font-size: 11px;"
            " background-color: #1a1a1a; color: #cccccc; }"
        )
        layout.addWidget(self._output)

        # Buttons
        btn_row = QHBoxLayout()
        self._build_btn = QPushButton("\U0001F528  Build")
        self._build_btn.clicked.connect(self._on_build)
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addStretch()
        btn_row.addWidget(self._build_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._worker = None

    def _browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Build Context")
        if path:
            self._path_input.setText(path)

    def _on_build(self) -> None:
        tag = self._tag_input.text().strip()
        path = self._path_input.text().strip()
        if not tag or not path:
            QMessageBox.warning(self, "Validation", "Tag and path are required.")
            return

        self._build_btn.setEnabled(False)
        self._output.clear()
        self._output.appendPlainText(f"Building {tag} from {path}...")

        from app.workers.docker_worker import BuildWorker
        self._worker = BuildWorker(self._cm.docker, path, tag, parent=self)
        self._worker.build_log.connect(self._output.appendPlainText)
        self._worker.error.connect(self._on_error)
        self._worker.build_finished.connect(self._on_finished)
        self._worker.start()

    def _on_error(self, msg: str) -> None:
        self._output.appendPlainText(f"\n[ERROR] {msg}")
        self._build_btn.setEnabled(True)

    def _on_finished(self, msg: str) -> None:
        self._output.appendPlainText(f"\n{msg}")
        self._build_btn.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        super().closeEvent(event)


class ImagesView(QWidget):
    """Table-based image list with pull/remove/build actions and context menu."""

    COLUMNS = ["ID", "Tags", "Size", "Created"]

    def __init__(self, controller: ImageController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._conn_manager = None  # set externally
        self._init_ui()
        self._connect_signals()

    def set_connection_manager(self, cm) -> None:
        self._conn_manager = cm

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F4BF  Images")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._pull_btn = QPushButton("\u2B07  Pull Image")
        self._build_btn = QPushButton("\U0001F528  Build")
        self._remove_btn = QPushButton("\U0001F5D1  Remove")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (self._pull_btn, self._build_btn, self._remove_btn, self._refresh_btn):
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
        self._ctrl.images_loaded.connect(self._populate_table)
        self._ctrl.operation_success.connect(
            lambda msg: show_toast(self.window(), msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )
        self._pull_btn.clicked.connect(self._on_pull)
        self._build_btn.clicked.connect(self._on_build)
        self._remove_btn.clicked.connect(self._on_remove)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_images)

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u2B07  Pull Image", self, triggered=self._on_pull))
        menu.addAction(QAction("\U0001F528  Build Image", self, triggered=self._on_build))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Remove", self, triggered=self._on_remove))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def _populate_table(self, images: list[dict]) -> None:
        self._table.setRowCount(len(images))
        for row, img in enumerate(images):
            self._table.setItem(row, 0, QTableWidgetItem(img["id"]))
            self._table.setItem(row, 1, QTableWidgetItem(img["tags"]))
            self._table.setItem(row, 2, QTableWidgetItem(img["size"]))
            self._table.setItem(row, 3, QTableWidgetItem(img["created"]))
        self._table.resizeColumnsToContents()

    def _on_pull(self) -> None:
        text, ok = QInputDialog.getText(
            self, "Pull Image", "Image name (e.g. nginx:latest):"
        )
        if ok and text.strip():
            parts = text.strip().split(":", 1)
            repo = parts[0]
            tag = parts[1] if len(parts) > 1 else "latest"
            self._ctrl.pull_image(repo, tag)
            self.window().statusBar().showMessage(f"Pulling {repo}:{tag}...", 10000)

    def _on_build(self) -> None:
        if self._conn_manager is None:
            QMessageBox.warning(self, "Error", "Docker not connected.")
            return
        dialog = _BuildDialog(self._conn_manager, parent=self)
        dialog.exec()
        self._ctrl.refresh_images()

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        image_id = self._table.item(row, 0).text()
        tags = self._table.item(row, 1).text()
        reply = QMessageBox.question(
            self, "Confirm", f"Remove image {tags} ({image_id})?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.remove_image(image_id, force=True)
