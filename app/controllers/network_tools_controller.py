from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class NetworkToolsController(QObject):
    """Controller for network diagnostic tools (ping, tracepath, DNS)."""

    ping_result = pyqtSignal(dict)
    tracepath_result = pyqtSignal(str)
    dns_result = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()

    def run_ping(self, host: str, count: int = 4) -> None:
        def _do():
            return self._sys.run_ping(host, count)

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.ping_result.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def run_tracepath(self, host: str) -> None:
        def _do():
            return self._sys.run_tracepath(host)

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.tracepath_result.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def run_dns_lookup(self, host: str) -> None:
        def _do():
            return self._sys.run_dns_lookup(host)

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.dns_result.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
