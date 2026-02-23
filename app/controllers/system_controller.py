from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker
from app.workers.system_worker import SystemMetricsWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class SystemController(QObject):
    """Controller for dashboard / system metrics."""

    system_info_loaded = pyqtSignal(dict)
    metrics_updated = pyqtSignal(dict)
    ports_loaded = pyqtSignal(list)
    interface_ips_loaded = pyqtSignal(dict)
    operation_error = pyqtSignal(str)
    power_action_success = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._metrics_worker: SystemMetricsWorker | None = None
        self._dying_workers: list[SystemMetricsWorker] = []

    def refresh_system_info(self) -> None:
        def _fetch():
            return self._sys.get_system_info()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.system_info_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_ports(self) -> None:
        def _fetch():
            return self._sys.get_listening_ports()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.ports_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_interface_ips(self) -> None:
        def _fetch():
            return self._sys.get_interface_ips()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.interface_ips_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def start_metrics_polling(self) -> None:
        if self._metrics_worker is not None:
            return
        from app.constants import DASHBOARD_POLL_INTERVAL_MS

        self._metrics_worker = SystemMetricsWorker(
            self._sys, interval_ms=DASHBOARD_POLL_INTERVAL_MS
        )
        self._metrics_worker.metrics_update.connect(self.metrics_updated.emit)
        self._metrics_worker.error.connect(self.operation_error.emit)
        self._metrics_worker.start()

    def stop_metrics_polling(self, wait: bool = False) -> None:
        if self._metrics_worker is not None:
            worker = self._metrics_worker
            self._metrics_worker = None
            try:
                worker.metrics_update.disconnect(self.metrics_updated.emit)
            except TypeError:
                pass
            try:
                worker.error.disconnect(self.operation_error.emit)
            except TypeError:
                pass
            worker.stop()
            if wait:
                worker.wait(3000)
            else:
                # Keep a reference so the thread isn't destroyed while running
                self._dying_workers.append(worker)
                worker.finished.connect(lambda w=worker: self._cleanup_worker(w))

    def _cleanup_worker(self, worker: SystemMetricsWorker) -> None:
        if worker in self._dying_workers:
            self._dying_workers.remove(worker)
        worker.deleteLater()

    # ── Power management ─────────────────────────────────────

    def _run_power_action(self, fn, label: str) -> None:
        def _action():
            output, rc = fn()
            if rc != 0 and output:
                raise RuntimeError(output)
            return label

        worker = DockerWorker(fn=_action)
        worker.signals.result.connect(self.power_action_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def reboot_server(self) -> None:
        self._run_power_action(self._sys.reboot, "Reboot command sent")

    def poweroff_server(self) -> None:
        self._run_power_action(self._sys.poweroff, "Power off command sent")

    def shutdown_server(self, minutes: int) -> None:
        self._run_power_action(
            lambda: self._sys.shutdown_scheduled(minutes),
            f"Shutdown scheduled in {minutes} min",
        )

    def cancel_shutdown_server(self) -> None:
        self._run_power_action(self._sys.cancel_shutdown, "Shutdown cancelled")
