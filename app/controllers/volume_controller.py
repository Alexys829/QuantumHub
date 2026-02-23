from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.utils import format_docker_datetime
from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class VolumeController(QObject):
    """Business logic for volume operations."""

    volumes_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()

    def refresh_volumes(self) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            volumes = self._cm.docker.list_volumes()
            result = []
            for vol in volumes:
                attrs = vol.attrs
                result.append(
                    {
                        "name": vol.name,
                        "driver": attrs.get("Driver", ""),
                        "mountpoint": attrs.get("Mountpoint", ""),
                        "created": format_docker_datetime(attrs.get("CreatedAt", "")),
                    }
                )
            return result

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.volumes_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def create_volume(self, name: str) -> None:
        def _create():
            self._cm.docker.create_volume(name)
            return f"Volume '{name}' created."

        worker = DockerWorker(fn=_create)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_volumes)
        self._pool.start(worker)

    def remove_volume(self, volume_name: str, force: bool = False) -> None:
        def _remove():
            self._cm.docker.remove_volume(volume_name, force=force)
            return f"Volume '{volume_name}' removed."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_volumes)
        self._pool.start(worker)
