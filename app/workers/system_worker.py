from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

if TYPE_CHECKING:
    from app.services.system_service import SystemService

logger = logging.getLogger(__name__)


class SystemMetricsWorker(QThread):
    """Periodically polls CPU, memory, disk, network, and uptime metrics.

    Emits ``metrics_update(dict)`` every *interval_ms* milliseconds.
    CPU measurement uses two /proc/stat snapshots 1 s apart, but the sleep
    is interruptible so ``stop()`` takes effect within ~100 ms.
    """

    metrics_update = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        system_service: SystemService,
        interval_ms: int = 5000,
        parent=None,
    ):
        super().__init__(parent)
        self._sys = system_service
        self._interval_ms = interval_ms
        self._running = True

    def run(self) -> None:
        while self._running:
            try:
                # CPU: two reads with interruptible 1 s gap
                stat1 = self._sys.read_cpu_stat()
                for _ in range(10):
                    if not self._running:
                        return
                    self.msleep(100)
                stat2 = self._sys.read_cpu_stat()
                cpu = self._sys.calc_cpu_percent(stat1, stat2)

                if not self._running:
                    return

                memory = self._sys.get_memory()
                disks = self._sys.get_disk_usage()
                network = self._sys.get_network_stats()
                uptime = self._sys.get_uptime()

                self.metrics_update.emit({
                    "cpu": cpu,
                    "memory": memory,
                    "disks": disks,
                    "network": network,
                    "uptime": uptime,
                })
            except Exception as e:
                logger.warning("Metrics poll error: %s", e)
                self.error.emit(str(e))

            # Sleep in small increments so stop() is responsive
            remaining = self._interval_ms
            while remaining > 0 and self._running:
                sleep_ms = min(remaining, 250)
                self.msleep(sleep_ms)
                remaining -= sleep_ms

    def stop(self) -> None:
        self._running = False
