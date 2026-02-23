from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class JournalController(QObject):
    """Controller for systemd journal log viewing."""

    logs_loaded = pyqtSignal(list)
    units_loaded = pyqtSignal(list)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_units(self) -> None:
        def _fetch():
            return self._sys.get_journal_units()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.units_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_logs(
        self,
        unit: str | None = None,
        priority: str | None = None,
        since: str | None = None,
        lines: int = 200,
    ) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_journal_logs(
                unit=unit, priority=priority, since=since, lines=lines
            )

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.logs_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: setattr(self, '_busy', False))
        self._pool.start(worker)
