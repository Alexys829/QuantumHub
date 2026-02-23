from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager


class NetworkController(QObject):
    """Business logic for network operations."""

    networks_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, connection_manager: ConnectionManager, parent=None):
        super().__init__(parent)
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()

    def refresh_networks(self) -> None:
        if not self._cm.is_connected:
            return

        def _fetch():
            networks = self._cm.docker.list_networks()
            result = []
            for net in networks:
                attrs = net.attrs
                ipam = attrs.get("IPAM", {})
                configs = ipam.get("Config", [])
                subnet = configs[0].get("Subnet", "") if configs else ""
                containers = attrs.get("Containers", {})
                result.append(
                    {
                        "id": net.short_id,
                        "name": net.name,
                        "driver": attrs.get("Driver", ""),
                        "scope": attrs.get("Scope", ""),
                        "subnet": subnet,
                        "containers": str(len(containers)),
                    }
                )
            return result

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.networks_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def create_network(self, name: str, driver: str = "bridge") -> None:
        def _create():
            self._cm.docker.create_network(name, driver=driver)
            return f"Network '{name}' created."

        worker = DockerWorker(fn=_create)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_networks)
        self._pool.start(worker)

    def remove_network(self, network_id: str) -> None:
        def _remove():
            self._cm.docker.remove_network(network_id)
            return f"Network '{network_id}' removed."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_networks)
        self._pool.start(worker)
