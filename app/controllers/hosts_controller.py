from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class HostsController(QObject):
    """Controller for /etc/hosts file editing."""

    hosts_loaded = pyqtSignal(str)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()

    def load_hosts(self) -> None:
        def _fetch():
            return self._sys.get_hosts_file()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.hosts_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def save_hosts(self, content: str) -> None:
        def _save():
            output, rc = self._sys.save_hosts_file(content)
            if rc != 0:
                raise RuntimeError(output or "Failed to save /etc/hosts")
            return "Hosts file saved successfully"

        worker = DockerWorker(fn=_save)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
