from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from app.services.docker_service import DockerService
from app.workers.docker_worker import StatsWorker


def _fmt_bytes(b: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


class ContainerStatsView(QWidget):
    """Separate window showing real-time container stats (CPU, memory, network, I/O)."""

    def __init__(
        self, docker_service: DockerService, container_id: str, parent=None
    ):
        super().__init__(parent)
        self._container_id = container_id
        self.setWindowTitle(f"\U0001F4CA  Stats - {container_id}")
        self.resize(500, 350)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._prev_cpu = 0.0
        self._prev_sys = 0.0

        self._init_ui()

        # Start stats streaming
        self._worker = StatsWorker(docker_service, container_id, parent=self)
        self._worker.stats_update.connect(self._on_stats)
        self._worker.error.connect(
            lambda e: self._cpu_label.setText(f"Error: {e}")
        )
        self._worker.start()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        title = QLabel(f"\U0001F4CA  Container Stats: {self._container_id}")
        title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(title)

        # CPU
        cpu_row = QVBoxLayout()
        self._cpu_label = QLabel("CPU: -")
        self._cpu_label.setStyleSheet("font-weight: 600; color: #bbbbbb;")
        cpu_row.addWidget(self._cpu_label)
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setObjectName("cpuBar")
        self._cpu_bar.setFixedHeight(22)
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setTextVisible(True)
        cpu_row.addWidget(self._cpu_bar)
        layout.addLayout(cpu_row)

        # Memory
        mem_row = QVBoxLayout()
        self._mem_label = QLabel("Memory: -")
        self._mem_label.setStyleSheet("font-weight: 600; color: #bbbbbb;")
        mem_row.addWidget(self._mem_label)
        self._mem_bar = QProgressBar()
        self._mem_bar.setObjectName("memBar")
        self._mem_bar.setFixedHeight(22)
        self._mem_bar.setRange(0, 100)
        self._mem_bar.setTextVisible(True)
        mem_row.addWidget(self._mem_bar)
        layout.addLayout(mem_row)

        # Network
        net_row = QHBoxLayout()
        self._net_rx = QLabel("Net RX: -")
        self._net_rx.setStyleSheet("color: #bbbbbb;")
        self._net_tx = QLabel("Net TX: -")
        self._net_tx.setStyleSheet("color: #bbbbbb;")
        net_row.addWidget(self._net_rx)
        net_row.addWidget(self._net_tx)
        layout.addLayout(net_row)

        # Block I/O
        io_row = QHBoxLayout()
        self._io_read = QLabel("Block Read: -")
        self._io_read.setStyleSheet("color: #bbbbbb;")
        self._io_write = QLabel("Block Write: -")
        self._io_write.setStyleSheet("color: #bbbbbb;")
        io_row.addWidget(self._io_read)
        io_row.addWidget(self._io_write)
        layout.addLayout(io_row)

        layout.addStretch()

    def _on_stats(self, stats: dict) -> None:
        # CPU calculation: delta cpu_usage / delta system_cpu_usage * num_cpus * 100
        cpu_stats = stats.get("cpu_stats", {})
        precpu = stats.get("precpu_stats", {})

        cpu_delta = (
            cpu_stats.get("cpu_usage", {}).get("total_usage", 0)
            - precpu.get("cpu_usage", {}).get("total_usage", 0)
        )
        sys_delta = (
            cpu_stats.get("system_cpu_usage", 0)
            - precpu.get("system_cpu_usage", 0)
        )
        num_cpus = len(cpu_stats.get("cpu_usage", {}).get("percpu_usage", []) or [1])
        if num_cpus == 0:
            num_cpus = cpu_stats.get("online_cpus", 1) or 1

        cpu_pct = 0.0
        if sys_delta > 0 and cpu_delta >= 0:
            cpu_pct = (cpu_delta / sys_delta) * num_cpus * 100.0

        self._cpu_label.setText(f"CPU: {cpu_pct:.1f}%")
        self._cpu_bar.setValue(min(int(cpu_pct), 100))
        self._cpu_bar.setFormat(f"{cpu_pct:.1f}%")

        # Memory
        mem_stats = stats.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)
        mem_pct = (mem_usage / mem_limit * 100) if mem_limit > 0 else 0
        self._mem_label.setText(
            f"Memory: {_fmt_bytes(mem_usage)} / {_fmt_bytes(mem_limit)}"
        )
        self._mem_bar.setValue(min(int(mem_pct), 100))
        self._mem_bar.setFormat(f"{mem_pct:.1f}%")

        # Network
        networks = stats.get("networks", {})
        rx_total = sum(n.get("rx_bytes", 0) for n in networks.values())
        tx_total = sum(n.get("tx_bytes", 0) for n in networks.values())
        self._net_rx.setText(f"Net RX: {_fmt_bytes(rx_total)}")
        self._net_tx.setText(f"Net TX: {_fmt_bytes(tx_total)}")

        # Block I/O
        blkio = stats.get("blkio_stats", {})
        io_bytes = blkio.get("io_service_bytes_recursive", []) or []
        read_bytes = sum(e.get("value", 0) for e in io_bytes if e.get("op") == "read")
        write_bytes = sum(e.get("value", 0) for e in io_bytes if e.get("op") == "write")
        self._io_read.setText(f"Block Read: {_fmt_bytes(read_bytes)}")
        self._io_write.setText(f"Block Write: {_fmt_bytes(write_bytes)}")

    def closeEvent(self, event) -> None:
        self._worker.stop()
        self._worker.wait(2000)
        super().closeEvent(event)
