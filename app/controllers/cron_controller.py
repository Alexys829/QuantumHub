from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class CronController(QObject):
    """Controller for cron job management."""

    cron_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False
        self._current_user: str | None = None

    def refresh_cron(self, user: str | None = None) -> None:
        if self._busy:
            return
        self._busy = True
        self._current_user = user

        def _fetch():
            return self._sys.get_cron_jobs(user=user)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.cron_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: setattr(self, '_busy', False))
        self._pool.start(worker)

    def add_job(self, schedule: str, command: str) -> None:
        def _add():
            self._sys.add_cron_job(schedule, command, user=self._current_user)
            return "Cron job added."

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: self.refresh_cron(self._current_user))
        self._pool.start(worker)

    def remove_job(self, line_index: int) -> None:
        def _remove():
            self._sys.remove_cron_job(line_index, user=self._current_user)
            return "Cron job removed."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: self.refresh_cron(self._current_user))
        self._pool.start(worker)

    def toggle_job(self, line_index: int) -> None:
        def _toggle():
            self._sys.toggle_cron_job(line_index, user=self._current_user)
            return "Cron job toggled."

        worker = DockerWorker(fn=_toggle)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: self.refresh_cron(self._current_user))
        self._pool.start(worker)
