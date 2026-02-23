from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class AptRepoController(QObject):
    """Controller for APT repository management."""

    repos_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_repos(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_apt_repos()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.repos_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def toggle_repo(self, file: str, line_num: int, enable: bool) -> None:
        label = "Enabled" if enable else "Disabled"

        def _toggle():
            output, rc = self._sys.toggle_apt_repo(file, line_num, enable)
            if rc != 0:
                raise RuntimeError(output or f"Failed to toggle repo")
            return f"{label} repository"

        worker = DockerWorker(fn=_toggle)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_repos)
        self._pool.start(worker)

    def add_repo(self, repo_line: str) -> None:
        def _add():
            output, rc = self._sys.add_apt_repo(repo_line)
            if rc != 0:
                raise RuntimeError(output or "Failed to add repository")
            return "Repository added"

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_repos)
        self._pool.start(worker)

    def delete_repo(self, file: str, line_num: int) -> None:
        def _delete():
            output, rc = self._sys.delete_apt_repo(file, line_num)
            if rc != 0:
                raise RuntimeError(output or "Failed to delete repository")
            return "Repository deleted"

        worker = DockerWorker(fn=_delete)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_repos)
        self._pool.start(worker)

    def run_update(self) -> None:
        def _update():
            output, rc = self._sys.run_apt_update()
            if rc != 0:
                raise RuntimeError(output or "apt update failed")
            return "apt update completed"

        worker = DockerWorker(fn=_update)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
