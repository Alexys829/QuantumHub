from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class StartupController(QObject):
    """Controller for startup application management (systemd + XDG autostart)."""

    entries_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_entries(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_startup_entries()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.entries_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def toggle_entry(
        self, name: str, entry_type: str, enable: bool, file: str = ""
    ) -> None:
        label = "Enabled" if enable else "Disabled"

        def _toggle():
            if entry_type == "systemd":
                output, rc = self._sys.toggle_systemd_startup(name, enable)
            else:
                output, rc = self._sys.toggle_autostart_entry(file, enable)
            if rc != 0:
                raise RuntimeError(output or f"Failed to toggle '{name}'")
            return f"{label} '{name}'"

        worker = DockerWorker(fn=_toggle)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_entries)
        self._pool.start(worker)

    def add_entry(self, name: str, command: str, description: str) -> None:
        def _add():
            output, rc = self._sys.add_autostart_entry(name, command, description)
            if rc != 0:
                raise RuntimeError(output or f"Failed to add '{name}'")
            return f"Added autostart entry '{name}'"

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_entries)
        self._pool.start(worker)

    def remove_entry(self, name: str, file: str) -> None:
        def _remove():
            output, rc = self._sys.remove_autostart_entry(file)
            if rc != 0:
                raise RuntimeError(output or f"Failed to remove '{name}'")
            return f"Removed '{name}'"

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_entries)
        self._pool.start(worker)
