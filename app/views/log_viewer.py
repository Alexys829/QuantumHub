from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.docker_service import DockerService
from app.workers.docker_worker import LogStreamWorker


class LogViewer(QWidget):
    """Separate window for streaming container logs with filtering."""

    def __init__(
        self, docker_service: DockerService, container_id: str, parent=None
    ):
        super().__init__(parent)
        self._docker_service = docker_service
        self._container_id = container_id
        self._worker: LogStreamWorker | None = None

        self.setWindowTitle(f"Logs - {container_id}")
        self.resize(900, 550)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header_row = QHBoxLayout()
        title = QLabel(f"\U0001F4C4  Container Logs: {container_id}")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        header_row.addWidget(title)
        header_row.addStretch()

        self._stop_btn = QPushButton("\u23F9  Stop Streaming")
        self._stop_btn.clicked.connect(self._stop_stream)
        header_row.addWidget(self._stop_btn)
        layout.addLayout(header_row)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("Tail:"))
        self._tail_combo = QComboBox()
        self._tail_combo.addItems(["100", "500", "1000", "5000"])
        self._tail_combo.setCurrentText("100")
        self._tail_combo.setFixedWidth(80)
        toolbar.addWidget(self._tail_combo)

        toolbar.addWidget(QLabel("Filter:"))
        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Keyword filter...")
        self._filter_input.setClearButtonEnabled(True)
        self._filter_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._filter_input)

        self._auto_scroll = QCheckBox("Auto-scroll")
        self._auto_scroll.setChecked(True)
        toolbar.addWidget(self._auto_scroll)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear_logs)
        toolbar.addWidget(clear_btn)

        restart_btn = QPushButton("\U0001F504  Restart")
        restart_btn.clicked.connect(self._restart_stream)
        toolbar.addWidget(restart_btn)

        layout.addLayout(toolbar)

        # Log text area
        self._text = QPlainTextEdit()
        self._text.setReadOnly(True)
        self._text.setMaximumBlockCount(10000)
        layout.addWidget(self._text)

        # Internal buffer for filtering
        self._all_lines: list[str] = []
        self._max_lines = 10000

        # Start streaming
        self._start_stream()

    def _start_stream(self) -> None:
        tail = int(self._tail_combo.currentText())
        self._worker = LogStreamWorker(
            self._docker_service, self._container_id, tail=tail, parent=self
        )
        self._worker.new_line.connect(self._on_new_line)
        self._worker.error.connect(
            lambda e: self._text.appendPlainText(f"[ERROR] {e}")
        )
        self._worker.start()
        self._stop_btn.setText("\u23F9  Stop Streaming")
        self._stop_btn.setEnabled(True)

    def _on_new_line(self, line: str) -> None:
        self._all_lines.append(line)
        if len(self._all_lines) > self._max_lines:
            self._all_lines = self._all_lines[-self._max_lines:]

        keyword = self._filter_input.text().strip().lower()
        if not keyword or keyword in line.lower():
            self._text.appendPlainText(line)
            if self._auto_scroll.isChecked():
                self._text.verticalScrollBar().setValue(
                    self._text.verticalScrollBar().maximum()
                )

    def _apply_filter(self) -> None:
        keyword = self._filter_input.text().strip().lower()
        self._text.clear()
        for line in self._all_lines:
            if not keyword or keyword in line.lower():
                self._text.appendPlainText(line)

    def _clear_logs(self) -> None:
        self._all_lines.clear()
        self._text.clear()

    def _restart_stream(self) -> None:
        self._stop_stream()
        self._clear_logs()
        self._start_stream()

    def _stop_stream(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
            self._worker = None
        self._stop_btn.setText("\u23F9  Stopped")
        self._stop_btn.setEnabled(False)

    def closeEvent(self, event) -> None:
        self._stop_stream()
        super().closeEvent(event)
