from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class RegistryController(QObject):
    """Controller for Docker Hub registry search."""

    results_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def search(self, term: str) -> None:
        if not self._cm.is_connected:
            self.operation_error.emit("Docker not connected.")
            return
        if self._busy:
            return
        self._busy = True

        def _search():
            return self._cm.docker.search_images(term, limit=25)

        worker = DockerWorker(fn=_search)
        worker.signals.result.connect(self.results_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: setattr(self, '_busy', False))
        self._pool.start(worker)

    def pull_image(self, name: str, tag: str = "latest") -> None:
        if not self._cm.is_connected:
            self.operation_error.emit("Docker not connected.")
            return

        def _pull():
            self._cm.docker.pull_image(name, tag=tag)
            return f"Image '{name}:{tag}' pulled successfully."

        worker = DockerWorker(fn=_pull)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
