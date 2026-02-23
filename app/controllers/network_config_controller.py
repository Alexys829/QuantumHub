from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class NetworkConfigController(QObject):
    """Controller for network interface configuration via nmcli."""

    connections_loaded = pyqtSignal(list)
    details_loaded = pyqtSignal(dict)
    nm_status = pyqtSignal(bool)  # True if NetworkManager available
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def check_nm(self) -> None:
        def _check():
            return self._sys.check_networkmanager()

        worker = DockerWorker(fn=_check)
        worker.signals.result.connect(self.nm_status.emit)
        self._pool.start(worker)

    def refresh_connections(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_network_connections()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.connections_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def load_details(self, conn_name: str) -> None:
        def _fetch():
            return self._sys.get_connection_details(conn_name)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.details_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def save_static(
        self, conn_name: str, address: str, prefix: str,
        gateway: str, dns: str
    ) -> None:
        def _save():
            output, rc = self._sys.set_connection_static(
                conn_name, address, prefix, gateway, dns
            )
            if rc != 0:
                raise RuntimeError(output or "Failed to set static IP")
            return f"Static IP applied to '{conn_name}'"

        worker = DockerWorker(fn=_save)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def save_dhcp(self, conn_name: str) -> None:
        def _save():
            output, rc = self._sys.set_connection_dhcp(conn_name)
            if rc != 0:
                raise RuntimeError(output or "Failed to set DHCP")
            return f"DHCP applied to '{conn_name}'"

        worker = DockerWorker(fn=_save)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def rename_connection(self, old_name: str, new_name: str) -> None:
        def _do():
            output, rc = self._sys.rename_connection(old_name, new_name)
            if rc != 0:
                raise RuntimeError(output or "Failed to rename connection")
            return f"Renamed '{old_name}' → '{new_name}'"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def clone_connection(self, source_name: str, new_name: str) -> None:
        def _do():
            output, rc = self._sys.clone_connection(source_name, new_name)
            if rc != 0:
                raise RuntimeError(output or "Failed to clone connection")
            return f"Cloned '{source_name}' as '{new_name}'"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def set_connection_active(self, conn_name: str, activate: bool) -> None:
        def _do():
            output, rc = self._sys.set_connection_active(conn_name, activate)
            if rc != 0:
                action = "activate" if activate else "deactivate"
                raise RuntimeError(output or f"Failed to {action}")
            action = "Activated" if activate else "Deactivated"
            return f"{action} '{conn_name}'"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def delete_connection(self, conn_name: str) -> None:
        def _do():
            output, rc = self._sys.delete_connection(conn_name)
            if rc != 0:
                raise RuntimeError(output or "Failed to delete connection")
            return f"Deleted '{conn_name}'"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_connections)
        self._pool.start(worker)

    def set_autoconnect(self, conn_name: str, enabled: bool) -> None:
        def _do():
            output, rc = self._sys.set_connection_autoconnect(conn_name, enabled)
            if rc != 0:
                raise RuntimeError(output or "Failed to set autoconnect")
            state = "enabled" if enabled else "disabled"
            return f"Autoconnect {state} for '{conn_name}'"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
