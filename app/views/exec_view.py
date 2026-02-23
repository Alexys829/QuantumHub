from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
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
from app.workers.docker_worker import ExecWorker


class ExecView(QWidget):
    """Interactive exec shell into a Docker container."""

    def __init__(
        self, docker_service: DockerService, container_id: str, parent=None
    ):
        super().__init__(parent)
        self._docker_service = docker_service
        self._container_id = container_id
        self._worker: ExecWorker | None = None

        self.setWindowTitle(f"Exec - {container_id}")
        self.resize(800, 500)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header_row = QHBoxLayout()
        title = QLabel(f"\U0001F4BB  Exec: {container_id}")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        header_row.addWidget(title)
        header_row.addStretch()

        header_row.addWidget(QLabel("Shell:"))
        self._shell_combo = QComboBox()
        self._shell_combo.addItems(["/bin/bash", "/bin/sh", "/bin/zsh"])
        self._shell_combo.setFixedWidth(120)
        header_row.addWidget(self._shell_combo)

        layout.addLayout(header_row)

        # Output area
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setMaximumBlockCount(5000)
        mono = QFont("Monospace", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._output.setFont(mono)
        self._output.setStyleSheet(
            "QPlainTextEdit { background-color: #1a1a1a; color: #00ff41;"
            " border: 1px solid #333333; border-radius: 4px; }"
        )
        layout.addWidget(self._output)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._prompt = QLabel("$")
        self._prompt.setStyleSheet(
            "color: #00ff41; font-size: 14px; font-weight: bold;"
        )
        input_row.addWidget(self._prompt)

        self._input = QLineEdit()
        self._input.setFont(mono)
        self._input.setPlaceholderText("Enter command...")
        self._input.setStyleSheet(
            "QLineEdit { background-color: #1a1a1a; color: #00ff41;"
            " border: 1px solid #333333; border-radius: 4px; padding: 6px; }"
        )
        self._input.returnPressed.connect(self._on_run_command)
        input_row.addWidget(self._input)

        run_btn = QPushButton("\u25B6  Run")
        run_btn.clicked.connect(self._on_run_command)
        input_row.addWidget(run_btn)

        layout.addLayout(input_row)

        # Command history
        self._history: list[str] = []
        self._history_idx = -1

        self._input.setFocus()

    def _on_run_command(self) -> None:
        cmd = self._input.text().strip()
        if not cmd:
            return

        self._history.append(cmd)
        self._history_idx = -1
        self._input.clear()

        shell = self._shell_combo.currentText()
        full_cmd = f"{shell} -c {self._quote(cmd)}"

        self._output.appendPlainText(f"$ {cmd}")
        self._input.setEnabled(False)

        self._worker = ExecWorker(
            self._docker_service, self._container_id, full_cmd, parent=self
        )
        self._worker.output_received.connect(self._on_output)
        self._worker.error.connect(self._on_error)
        self._worker.finished_signal.connect(self._on_exec_finished)
        self._worker.start()

    def _on_output(self, text: str) -> None:
        self._output.appendPlainText(text.rstrip())
        sb = self._output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_error(self, msg: str) -> None:
        self._output.appendPlainText(f"[ERROR] {msg}")
        self._input.setEnabled(True)
        self._input.setFocus()

    def _on_exec_finished(self, exit_code: int) -> None:
        if exit_code != 0:
            self._output.appendPlainText(f"[exit code: {exit_code}]")
        self._input.setEnabled(True)
        self._input.setFocus()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Up and self._history:
            if self._history_idx == -1:
                self._history_idx = len(self._history) - 1
            elif self._history_idx > 0:
                self._history_idx -= 1
            self._input.setText(self._history[self._history_idx])
        elif event.key() == Qt.Key.Key_Down and self._history:
            if self._history_idx >= 0 and self._history_idx < len(self._history) - 1:
                self._history_idx += 1
                self._input.setText(self._history[self._history_idx])
            else:
                self._history_idx = -1
                self._input.clear()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def _quote(cmd: str) -> str:
        """Shell-quote a command for passing to sh -c."""
        return "'" + cmd.replace("'", "'\\''") + "'"

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.wait(2000)
        super().closeEvent(event)
