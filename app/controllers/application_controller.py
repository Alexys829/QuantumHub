from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class ApplicationController(QObject):
    """Controller for the applications view — groups processes by app name."""

    applications_loaded = pyqtSignal(list)
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

    @staticmethod
    def _app_name(command: str) -> str:
        """Extract a readable app name from a full command string."""
        first = command.split()[0] if command.strip() else command
        # Strip common interpreter wrappers
        base = os.path.basename(first)
        # For paths like /usr/lib/firefox/firefox → firefox
        if base in ("python", "python3", "perl", "ruby", "java", "node"):
            parts = command.split()
            if len(parts) > 1:
                script = os.path.basename(parts[1])
                return f"{base}: {script}"
        return base

    def refresh_applications(self) -> None:
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

            # Compute per-process rates first
            for p in procs:
                pid = p["pid"]
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

            # Group by app name
            groups: dict[str, list[dict]] = defaultdict(list)
            for p in procs:
                name = self._app_name(p.get("command", ""))
                groups[name].append(p)

            apps: list[dict] = []
            for name, group in groups.items():
                cpu_total = sum(float(p.get("cpu", 0)) for p in group)
                ram_mb = sum(float(p.get("rss", 0)) for p in group) / 1024
                apps.append({
                    "app_name": name,
                    "pids": len(group),
                    "pid_list": [p["pid"] for p in group],
                    "cpu": round(cpu_total, 1),
                    "ram_mb": round(ram_mb, 1),
                    "disk_read_rate": sum(p["disk_read_rate"] for p in group),
                    "disk_write_rate": sum(p["disk_write_rate"] for p in group),
                    "net_send_rate": sum(p["net_send_rate"] for p in group),
                    "net_recv_rate": sum(p["net_recv_rate"] for p in group),
                })

            # Sort by CPU descending
            apps.sort(key=lambda a: a["cpu"], reverse=True)
            self.applications_loaded.emit(apps)

        def _done():
            self._busy = False

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def kill_application(self, pid_list: list[str], signal: int = 15) -> None:
        """Kill all PIDs belonging to an application."""
        def _kill():
            pids = " ".join(str(int(p)) for p in pid_list)
            cmd = f"kill -{signal} {pids}"
            out, err, rc = self._sys._run_command(cmd)
            if rc != 0:
                raise RuntimeError((out + err).strip() or "Failed to kill processes")
            return f"Signal {signal} sent to {len(pid_list)} processes"

        worker = DockerWorker(fn=_kill)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_applications)
        self._pool.start(worker)
