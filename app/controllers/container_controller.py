from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.utils import format_docker_datetime
from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class ContainerController(QObject):
    """Business logic for container operations."""

    containers_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()

    def refresh_containers(self) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            containers = self._cm.docker.list_containers(all=True)
            result = []
            for c in containers:
                tags = c.image.tags if c.image.tags else []
                image_name = tags[0] if tags else c.image.short_id
                result.append(
                    {
                        "id": c.short_id,
                        "name": c.name,
                        "image": image_name,
                        "status": c.status,
                        "ports": self._format_ports(c.ports),
                        "created": format_docker_datetime(c.attrs.get("Created", "")),
                    }
                )
            return result

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.containers_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def start_container(self, container_id: str) -> None:
        def _start():
            self._cm.docker.start_container(container_id)
            return f"Container {container_id} started."

        worker = DockerWorker(fn=_start)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_containers)
        self._pool.start(worker)

    def stop_container(self, container_id: str) -> None:
        def _stop():
            self._cm.docker.stop_container(container_id)
            return f"Container {container_id} stopped."

        worker = DockerWorker(fn=_stop)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_containers)
        self._pool.start(worker)

    def restart_container(self, container_id: str) -> None:
        def _restart():
            self._cm.docker.restart_container(container_id)
            return f"Container {container_id} restarted."

        worker = DockerWorker(fn=_restart)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_containers)
        self._pool.start(worker)

    def kill_container(self, container_id: str) -> None:
        def _kill():
            self._cm.docker.kill_container(container_id)
            return f"Container {container_id} killed."

        worker = DockerWorker(fn=_kill)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_containers)
        self._pool.start(worker)

    def remove_container(self, container_id: str, force: bool = False) -> None:
        def _remove():
            self._cm.docker.remove_container(container_id, force=force)
            return f"Container {container_id} removed."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_containers)
        self._pool.start(worker)

    @staticmethod
    def _format_ports(ports: dict) -> str:
        if not ports:
            return ""
        parts = []
        for container_port, host_bindings in ports.items():
            if host_bindings:
                for binding in host_bindings:
                    host_ip = binding.get("HostIp", "0.0.0.0")
                    host_port = binding.get("HostPort", "")
                    parts.append(f"{host_ip}:{host_port}->{container_port}")
            else:
                parts.append(container_port)
        return ", ".join(parts)
