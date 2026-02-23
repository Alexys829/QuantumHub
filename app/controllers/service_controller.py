from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class ServiceController(QObject):
    """Controller for systemd service management."""

    services_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_services(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_services()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.services_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def _run_action(self, unit: str, action: str) -> None:
        def _act():
            output, rc = self._sys.service_action(unit, action)
            if rc != 0:
                raise RuntimeError(output or f"Failed to {action} {unit}")
            return f"{action.capitalize()} {unit} succeeded"

        worker = DockerWorker(fn=_act)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_services)
        self._pool.start(worker)

    def start_service(self, unit: str) -> None:
        self._run_action(unit, "start")

    def stop_service(self, unit: str) -> None:
        self._run_action(unit, "stop")

    def restart_service(self, unit: str) -> None:
        self._run_action(unit, "restart")

    def enable_service(self, unit: str) -> None:
        self._run_action(unit, "enable")

    def disable_service(self, unit: str) -> None:
        self._run_action(unit, "disable")
