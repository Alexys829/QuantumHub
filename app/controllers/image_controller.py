from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.utils import format_docker_datetime
from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class ImageController(QObject):
    """Business logic for image operations."""

    images_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()

    def refresh_images(self) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            images = self._cm.docker.list_images()
            result = []
            for img in images:
                tags = img.tags if img.tags else ["<none>:<none>"]
                size_mb = img.attrs.get("Size", 0) / (1024 * 1024)
                created = img.attrs.get("Created", "")
                result.append(
                    {
                        "id": img.short_id.replace("sha256:", ""),
                        "tags": ", ".join(tags),
                        "size": f"{size_mb:.1f} MB",
                        "created": format_docker_datetime(created),
                    }
                )
            return result

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.images_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def pull_image(self, repository: str, tag: str = "latest") -> None:
        def _pull():
            self._cm.docker.pull_image(repository, tag)
            return f"Image {repository}:{tag} pulled."

        worker = DockerWorker(fn=_pull)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_images)
        self._pool.start(worker)

    def remove_image(self, image_id: str, force: bool = False) -> None:
        def _remove():
            self._cm.docker.remove_image(image_id, force=force)
            return f"Image {image_id} removed."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_images)
        self._pool.start(worker)
