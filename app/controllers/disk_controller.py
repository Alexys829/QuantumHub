from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class DiskController(QObject):
    """Controller for disk usage monitoring."""

    disk_loaded = pyqtSignal(list)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_disk(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_disk_usage()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.disk_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: setattr(self, '_busy', False))
        self._pool.start(worker)
