from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class ProcessController(QObject):
    """Controller for process management."""

    processes_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False
        self._prev_disk: dict[str, dict[str, int]] = {}
        self._prev_net: dict[str, dict[str, int]] = {}
        self._prev_time: float = 0.0

    def refresh_processes(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            procs = self._sys.get_processes()
            disk_io = self._sys.get_processes_io()
            net_io = self._sys.get_network_io_by_pid()
            return procs, disk_io, net_io

        worker = DockerWorker(fn=_fetch)

        def _on_result(result):
            procs, disk_io, net_io = result
            now = time.monotonic()
            elapsed = now - self._prev_time if self._prev_time > 0 else 0

            for p in procs:
                pid = p["pid"]
                # Disk rate
                cur_d = disk_io.get(pid, {})
                prev_d = self._prev_disk.get(pid, {})
                if elapsed > 0 and prev_d:
                    p["disk_read_rate"] = max(
                        0,
                        (cur_d.get("read_bytes", 0) - prev_d.get("read_bytes", 0))
                        / elapsed,
                    )
                    p["disk_write_rate"] = max(
                        0,
                        (cur_d.get("write_bytes", 0) - prev_d.get("write_bytes", 0))
                        / elapsed,
                    )
                else:
                    p["disk_read_rate"] = 0.0
                    p["disk_write_rate"] = 0.0
                # Net rate
                cur_n = net_io.get(pid, {})
                prev_n = self._prev_net.get(pid, {})
                if elapsed > 0 and prev_n:
                    p["net_send_rate"] = max(
                        0,
                        (cur_n.get("bytes_sent", 0) - prev_n.get("bytes_sent", 0))
                        / elapsed,
                    )
                    p["net_recv_rate"] = max(
                        0,
                        (
                            cur_n.get("bytes_received", 0)
                            - prev_n.get("bytes_received", 0)
                        )
                        / elapsed,
                    )
                else:
                    p["net_send_rate"] = 0.0
                    p["net_recv_rate"] = 0.0

            self._prev_disk = disk_io
            self._prev_net = net_io
            self._prev_time = now
            self.processes_loaded.emit(procs)

        def _done():
            self._busy = False

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def kill_process(self, pid: int, signal: int = 15) -> None:
        def _kill():
            output, rc = self._sys.kill_process(pid, signal)
            if rc != 0:
                raise RuntimeError(output or f"Failed to kill PID {pid}")
            return f"Signal {signal} sent to PID {pid}"

        worker = DockerWorker(fn=_kill)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_processes)
        self._pool.start(worker)
