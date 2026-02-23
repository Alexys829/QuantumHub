from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.services.compose_service import ComposeService
from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class ComposeController(QObject):
    """Business logic for Docker Compose operations."""

    projects_loaded = pyqtSignal(list)
    services_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)
    compose_logs = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._compose = ComposeService(connection_manager)
        self._pool = QThreadPool.globalInstance()

    def refresh_projects(self) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            return self._compose.list_projects()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.projects_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_services(self, project_name: str) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            return self._compose.project_services(project_name)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.services_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def up(self, project_name: str) -> None:
        def _up():
            self._compose.up(project_name)
            return f"Compose project '{project_name}' started."

        worker = DockerWorker(fn=_up)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_projects)
        self._pool.start(worker)

    def down(self, project_name: str) -> None:
        def _down():
            self._compose.down(project_name)
            return f"Compose project '{project_name}' stopped."

        worker = DockerWorker(fn=_down)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_projects)
        self._pool.start(worker)

    def restart(self, project_name: str) -> None:
        def _restart():
            self._compose.restart(project_name)
            return f"Compose project '{project_name}' restarted."

        worker = DockerWorker(fn=_restart)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_projects)
        self._pool.start(worker)

    def pull(self, project_name: str) -> None:
        def _pull():
            self._compose.pull(project_name)
            return f"Compose project '{project_name}' images pulled."

        worker = DockerWorker(fn=_pull)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def view_logs(self, project_name: str) -> None:
        def _logs():
            return self._compose.logs(project_name)

        worker = DockerWorker(fn=_logs)
        worker.signals.result.connect(self.compose_logs.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
