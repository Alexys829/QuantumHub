from __future__ import annotations

import time
from collections import deque

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.system_controller import SystemController


def _fmt_bytes(b: int | float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} PB"


def _fmt_speed(bps: float) -> str:
    for unit in ("B/s", "KB/s", "MB/s", "GB/s"):
        if abs(bps) < 1024:
            return f"{bps:.1f} {unit}"
        bps /= 1024
    return f"{bps:.1f} TB/s"


# ── Circular Gauge Widget ─────────────────────────────────────


class CircularGauge(QWidget):
    """A donut-style circular gauge that displays a percentage value."""

    def __init__(
        self,
        label: str = "",
        color: QColor | str = "#007acc",
        size: int = 140,
        parent=None,
    ):
        super().__init__(parent)
        self._percent = 0.0
        self._label = label
        self._detail = ""
        self._color = QColor(color) if isinstance(color, str) else color
        self._size = size
        # Extra vertical space for label + detail below the circle
        self.setMinimumSize(size + 20, size + 50)
        self.setFixedWidth(size + 20)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)

    def set_value(self, percent: float, detail: str = "") -> None:
        self._percent = max(0.0, min(percent, 100.0))
        self._detail = detail
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        circle_d = self._size - 10
        pen_width = max(8, circle_d // 14)
        margin = pen_width / 2 + 2
        rect = QRectF(
            (w - circle_d) / 2 + margin,
            margin,
            circle_d - 2 * margin,
            circle_d - 2 * margin,
        )

        # Background arc
        bg_pen = QPen(QColor("#3a3a3a"), pen_width)
        bg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Value arc
        if self._percent > 0:
            fg_pen = QPen(self._color, pen_width)
            fg_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(fg_pen)
            span = -int(self._percent / 100.0 * 360 * 16)
            painter.drawArc(rect, 90 * 16, span)

        # Percentage text inside circle
        pct_fs = max(10, circle_d // 7)
        painter.setFont(QFont("Segoe UI", pct_fs, QFont.Weight.Bold))
        painter.setPen(QColor("#e0e0e0"))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._percent:.0f}%")

        # Label below circle
        label_y = rect.bottom() + 8
        lbl_fs = max(9, pct_fs - 4)
        painter.setFont(QFont("Segoe UI", lbl_fs, QFont.Weight.DemiBold))
        painter.setPen(QColor("#bbbbbb"))
        painter.drawText(
            QRectF(0, label_y, w, 20),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            self._label,
        )

        # Detail text below label
        if self._detail:
            det_fs = max(8, pct_fs - 6)
            painter.setFont(QFont("Segoe UI", det_fs))
            painter.setPen(QColor("#888888"))
            painter.drawText(
                QRectF(0, label_y + 18, w, 20),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                self._detail,
            )

        painter.end()


# ── Sparkline Widget ──────────────────────────────────────────


class SparkLine(QWidget):
    """A mini area chart showing a scrolling time-series."""

    def __init__(
        self,
        color: QColor | str = "#007acc",
        max_points: int = 60,
        parent=None,
    ):
        super().__init__(parent)
        self._color = QColor(color) if isinstance(color, str) else color
        self._data: deque[float] = deque(maxlen=max_points)
        self.setFixedHeight(70)
        self.setMinimumWidth(200)

    def set_data(self, data: deque[float]) -> None:
        """Replace internal data buffer and repaint."""
        self._data = data
        self.update()

    def add_point(self, value: float) -> None:
        self._data.append(value)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        pad = 2
        draw_w = w - 2 * pad
        draw_h = h - 2 * pad

        # Background
        painter.fillRect(self.rect(), QColor("#1a1a1a"))
        # Grid lines
        grid_pen = QPen(QColor("#2a2a2a"), 1)
        painter.setPen(grid_pen)
        for i in range(1, 4):
            y = pad + draw_h * i // 4
            painter.drawLine(pad, y, pad + draw_w, y)

        if len(self._data) < 2:
            painter.end()
            return

        max_val = max(self._data) or 1
        n = len(self._data)
        step = draw_w / max(n - 1, 1)

        path = QPainterPath()
        fill_path = QPainterPath()

        first_x = pad
        first_y = pad + draw_h - (self._data[0] / max_val) * draw_h
        path.moveTo(first_x, first_y)
        fill_path.moveTo(first_x, pad + draw_h)
        fill_path.lineTo(first_x, first_y)

        for i in range(1, n):
            x = pad + i * step
            y = pad + draw_h - (self._data[i] / max_val) * draw_h
            path.lineTo(x, y)
            fill_path.lineTo(x, y)

        last_x = pad + (n - 1) * step
        fill_path.lineTo(last_x, pad + draw_h)
        fill_path.closeSubpath()

        fill_color = QColor(self._color)
        fill_color.setAlpha(50)
        painter.fillPath(fill_path, fill_color)

        pen = QPen(self._color, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        # Current value label top-right
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.setPen(self._color)
        cur = self._data[-1]
        painter.drawText(
            QRectF(pad, pad, draw_w - 2, 16),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop,
            _fmt_speed(cur),
        )

        painter.end()


# ── Dashboard View ─────────────────────────────────────────────


class DashboardView(QWidget):
    """Server dashboard with circular gauges, per-core bars, network graphs, tables."""

    def __init__(self, controller: SystemController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._cpu_bars: list[QProgressBar] = []
        # Network state
        self._prev_net: dict[str, dict] = {}
        self._prev_net_time: float = 0.0
        self._net_rx_history: dict[str, deque] = {}
        self._net_tx_history: dict[str, deque] = {}
        self._net_current: dict[str, dict] = {}  # iface → latest stats
        self._net_ips: dict[str, list[str]] = {}  # iface → [ip1, ip2, ...]
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 12, 16, 12)
        self._layout.setSpacing(14)
        scroll.setWidget(content)

        # ── Header ────────────────────────────────────────────
        header = QLabel("\U0001F4CA  Dashboard")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        self._layout.addWidget(header)

        # ── Power buttons ─────────────────────────────────────
        power_row = QHBoxLayout()
        power_row.setSpacing(6)

        _danger_style = (
            "QPushButton { background-color: #5a1d1d; color: #f48771; border: 1px solid #f48771;"
            "  padding: 4px 12px; border-radius: 4px; font-size: 12px; }"
            "QPushButton:hover { background-color: #6e2d2d; color: #ffffff; }"
        )
        _normal_style = (
            "QPushButton { padding: 4px 12px; font-size: 12px; }"
        )

        self._reboot_btn = QPushButton("\u25B6  Reboot")
        self._reboot_btn.setStyleSheet(_danger_style)
        self._reboot_btn.clicked.connect(self._on_reboot)
        power_row.addWidget(self._reboot_btn)

        self._poweroff_btn = QPushButton("\u25A0  Power Off")
        self._poweroff_btn.setStyleSheet(_danger_style)
        self._poweroff_btn.clicked.connect(self._on_poweroff)
        power_row.addWidget(self._poweroff_btn)

        self._shutdown_btn = QPushButton("Shutdown...")
        self._shutdown_btn.setStyleSheet(_normal_style)
        self._shutdown_btn.clicked.connect(self._on_shutdown)
        power_row.addWidget(self._shutdown_btn)

        self._cancel_shutdown_btn = QPushButton("Cancel Shutdown")
        self._cancel_shutdown_btn.setStyleSheet(_normal_style)
        self._cancel_shutdown_btn.clicked.connect(self._on_cancel_shutdown)
        power_row.addWidget(self._cancel_shutdown_btn)

        power_row.addStretch()
        self._layout.addLayout(power_row)

        # ── Info cards ────────────────────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self._card_hostname = self._make_card("Hostname", "-")
        self._card_os = self._make_card("OS", "-")
        self._card_kernel = self._make_card("Kernel", "-")
        self._card_uptime = self._make_card("Uptime", "-")
        self._card_cores = self._make_card("CPU Cores", "-")
        for card in (
            self._card_hostname, self._card_os, self._card_kernel,
            self._card_uptime, self._card_cores,
        ):
            cards_row.addWidget(card)
        self._layout.addLayout(cards_row)

        # ── CPU section ───────────────────────────────────────
        cpu_section = QHBoxLayout()
        cpu_section.setSpacing(16)

        self._cpu_gauge = CircularGauge("CPU", "#007acc", size=140)
        cpu_section.addWidget(self._cpu_gauge)

        cores_frame = QFrame()
        cores_frame.setObjectName("dashboardCard")
        cores_inner = QVBoxLayout(cores_frame)
        cores_inner.setContentsMargins(12, 8, 12, 8)
        cores_inner.setSpacing(4)
        cores_title = QLabel("Per-Core Usage")
        cores_title.setStyleSheet("font-weight: 600; color: #bbbbbb; font-size: 12px;")
        cores_inner.addWidget(cores_title)
        self._cores_grid = QGridLayout()
        self._cores_grid.setSpacing(4)
        cores_inner.addLayout(self._cores_grid)
        cores_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        cpu_section.addWidget(cores_frame, 1)

        self._layout.addLayout(cpu_section)

        # ── Memory / Swap / Load ──────────────────────────────
        mem_row = QHBoxLayout()
        mem_row.setSpacing(16)

        self._mem_gauge = CircularGauge("Memory", "#2ea043", size=140)
        self._swap_gauge = CircularGauge("Swap", "#d29922", size=140)
        mem_row.addWidget(self._mem_gauge)
        mem_row.addWidget(self._swap_gauge)

        load_frame = QFrame()
        load_frame.setObjectName("dashboardCard")
        load_inner = QVBoxLayout(load_frame)
        load_inner.setContentsMargins(14, 10, 14, 10)
        load_title = QLabel("Load Average")
        load_title.setObjectName("cardTitle")
        load_inner.addWidget(load_title)
        self._load_labels: list[QLabel] = []
        for period in ("1 min", "5 min", "15 min"):
            row = QHBoxLayout()
            plbl = QLabel(period)
            plbl.setStyleSheet("color: #888888; font-size: 11px; min-width: 46px;")
            vlbl = QLabel("-")
            vlbl.setStyleSheet("color: #e0e0e0; font-size: 15px; font-weight: bold;")
            row.addWidget(plbl)
            row.addWidget(vlbl)
            row.addStretch()
            load_inner.addLayout(row)
            self._load_labels.append(vlbl)
        load_inner.addStretch()
        mem_row.addWidget(load_frame)
        mem_row.addStretch()

        self._layout.addLayout(mem_row)

        # ── Network section (2 independent rows) ────────────────
        net_title = QLabel("\U0001F310  Network")
        net_title.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #e0e0e0;"
        )
        self._layout.addWidget(net_title)

        # We build two identical "net row" widgets, each with its own combo + sparklines
        self._net_rows: list[dict] = []
        for row_idx in range(2):
            row_data = self._build_net_row(row_idx)
            self._net_rows.append(row_data)
            self._layout.addWidget(row_data["card"])

        # ── Bottom tables ─────────────────────────────────────
        tables_row = QHBoxLayout()
        tables_row.setSpacing(10)

        disk_col = QVBoxLayout()
        disk_title = QLabel("Disk Usage")
        disk_title.setStyleSheet("font-weight: 600; color: #bbbbbb; font-size: 13px;")
        disk_col.addWidget(disk_title)
        self._disk_table = self._make_table(["Device", "Size", "Used", "Avail", "%", "Mount"])
        disk_col.addWidget(self._disk_table)
        tables_row.addLayout(disk_col)

        port_col = QVBoxLayout()
        port_title = QLabel("Listening Ports")
        port_title.setStyleSheet("font-weight: 600; color: #bbbbbb; font-size: 13px;")
        port_col.addWidget(port_title)
        self._port_table = self._make_table(["Protocol", "State", "Address", "Port"])
        port_col.addWidget(self._port_table)
        tables_row.addLayout(port_col)

        self._layout.addLayout(tables_row)

    # ── Helpers ───────────────────────────────────────────────

    def _build_net_row(self, row_idx: int) -> dict:
        """Build one network row card with combo + Download/Upload sparklines + stats."""
        card = QFrame()
        card.setObjectName("dashboardCard")
        inner = QVBoxLayout(card)
        inner.setContentsMargins(12, 8, 12, 8)
        inner.setSpacing(4)

        # Header: combo + speed label
        header = QHBoxLayout()
        combo = QComboBox()
        combo.setMinimumWidth(180)
        combo.currentTextChanged.connect(
            lambda _iface, r=row_idx: self._on_net_row_changed(r)
        )
        header.addWidget(combo)
        header.addSpacing(12)

        speed_lbl = QLabel("-")
        speed_lbl.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold;")
        header.addWidget(speed_lbl)
        header.addStretch()

        ip_lbl = QLabel("")
        ip_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        header.addWidget(ip_lbl)

        inner.addLayout(header)

        # Sparklines: Download + Upload side by side
        sparks = QHBoxLayout()
        sparks.setSpacing(14)

        rx_col = QVBoxLayout()
        rx_col.setSpacing(2)
        rx_label = QLabel("\u2B07  Download")
        rx_label.setStyleSheet("color: #2ea043; font-size: 11px; font-weight: 600;")
        rx_col.addWidget(rx_label)
        rx_spark = SparkLine("#2ea043", max_points=60)
        rx_col.addWidget(rx_spark)
        sparks.addLayout(rx_col)

        tx_col = QVBoxLayout()
        tx_col.setSpacing(2)
        tx_label = QLabel("\u2B06  Upload")
        tx_label.setStyleSheet("color: #007acc; font-size: 11px; font-weight: 600;")
        tx_col.addWidget(tx_label)
        tx_spark = SparkLine("#007acc", max_points=60)
        tx_col.addWidget(tx_spark)
        sparks.addLayout(tx_col)

        inner.addLayout(sparks)

        # Stats line
        stats_lbl = QLabel("-")
        stats_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        inner.addWidget(stats_lbl)

        return {
            "card": card,
            "combo": combo,
            "speed_lbl": speed_lbl,
            "ip_lbl": ip_lbl,
            "rx_spark": rx_spark,
            "tx_spark": tx_spark,
            "stats_lbl": stats_lbl,
        }

    def _make_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("dashboardCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 10, 14, 10)
        card_layout.setSpacing(4)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        card_layout.addWidget(t)
        v = QLabel(value)
        v.setObjectName("cardValue")
        card_layout.addWidget(v)
        card._value_label = v  # type: ignore[attr-defined]
        return card

    @staticmethod
    def _make_table(columns: list[str]) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setMinimumHeight(180)
        return table

    def reset_network_state(self) -> None:
        """Clear all network state — must be called on connection change."""
        self._prev_net.clear()
        self._prev_net_time = 0.0
        self._net_rx_history.clear()
        self._net_tx_history.clear()
        self._net_current.clear()
        self._net_ips.clear()
        for row_data in self._net_rows:
            row_data["combo"].blockSignals(True)
            row_data["combo"].clear()
            row_data["combo"].blockSignals(False)
            row_data["speed_lbl"].setText("-")
            row_data["ip_lbl"].setText("")
            row_data["stats_lbl"].setText("-")
            row_data["rx_spark"].set_data(deque(maxlen=60))
            row_data["tx_spark"].set_data(deque(maxlen=60))

    def set_power_buttons_visible(self, visible: bool) -> None:
        self._reboot_btn.setVisible(visible)
        self._poweroff_btn.setVisible(visible)
        self._shutdown_btn.setVisible(visible)
        self._cancel_shutdown_btn.setVisible(visible)

    def _connect_signals(self) -> None:
        self._ctrl.system_info_loaded.connect(self._on_system_info)
        self._ctrl.metrics_updated.connect(self._on_metrics)
        self._ctrl.ports_loaded.connect(self._on_ports)
        self._ctrl.interface_ips_loaded.connect(self._on_interface_ips)
        self._ctrl.power_action_success.connect(self._on_power_success)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    # ── Slots ─────────────────────────────────────────────────

    def _on_system_info(self, info: dict) -> None:
        self._card_hostname._value_label.setText(info.get("hostname", "-"))  # type: ignore[attr-defined]
        self._card_os._value_label.setText(info.get("os", "-"))  # type: ignore[attr-defined]
        self._card_kernel._value_label.setText(info.get("kernel", "-"))  # type: ignore[attr-defined]
        self._card_cores._value_label.setText(info.get("cpu_cores", "-"))  # type: ignore[attr-defined]

    def _on_metrics(self, data: dict) -> None:
        self._update_cpu(data)
        self._update_memory(data)
        self._update_network(data)
        self._update_disk(data)

        uptime_info = data.get("uptime", {})
        self._card_uptime._value_label.setText(uptime_info.get("uptime_str", "-"))  # type: ignore[attr-defined]
        loads = [uptime_info.get(k, "-") for k in ("load_1", "load_5", "load_15")]
        for i, v in enumerate(loads):
            if i < len(self._load_labels):
                self._load_labels[i].setText(str(v))

    def _on_interface_ips(self, ips: dict) -> None:
        self._net_ips = ips
        for row_idx in range(len(self._net_rows)):
            self._refresh_net_row(row_idx)

    def _on_ports(self, ports: list[dict]) -> None:
        self._port_table.setRowCount(len(ports))
        for row, p in enumerate(ports):
            self._port_table.setItem(row, 0, QTableWidgetItem(p["protocol"]))
            self._port_table.setItem(row, 1, QTableWidgetItem(p["state"]))
            self._port_table.setItem(row, 2, QTableWidgetItem(p["local_address"]))
            self._port_table.setItem(row, 3, QTableWidgetItem(p["local_port"]))

    # ── CPU ───────────────────────────────────────────────────

    def _update_cpu(self, data: dict) -> None:
        cpu_list: list[float] = data.get("cpu", [])
        if not cpu_list:
            return

        avg = sum(cpu_list) / len(cpu_list)
        self._cpu_gauge.set_value(avg)

        if len(cpu_list) != len(self._cpu_bars):
            while self._cores_grid.count():
                item = self._cores_grid.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            self._cpu_bars.clear()

            cols = 4 if len(cpu_list) > 8 else 2
            for i in range(len(cpu_list)):
                lbl = QLabel(f"C{i}")
                lbl.setStyleSheet("color:#888; font-size:10px; min-width:20px;")
                bar = QProgressBar()
                bar.setObjectName("cpuBar")
                bar.setFixedHeight(14)
                bar.setTextVisible(True)
                bar.setRange(0, 100)
                bar.setStyleSheet("QProgressBar{font-size:9px;}")
                row = i // cols
                col = (i % cols) * 2
                self._cores_grid.addWidget(lbl, row, col)
                self._cores_grid.addWidget(bar, row, col + 1)
                self._cpu_bars.append(bar)

        for i, pct in enumerate(cpu_list):
            if i < len(self._cpu_bars):
                self._cpu_bars[i].setValue(int(pct))
                self._cpu_bars[i].setFormat(f"{pct:.0f}%")

    # ── Memory ────────────────────────────────────────────────

    def _update_memory(self, data: dict) -> None:
        mem = data.get("memory", {})
        total = mem.get("total", 1)
        used = mem.get("used", 0)
        mem_pct = (used * 100 / total) if total > 0 else 0
        self._mem_gauge.set_value(mem_pct, f"{_fmt_bytes(used)} / {_fmt_bytes(total)}")

        swap_total = mem.get("swap_total", 0)
        swap_used = mem.get("swap_used", 0)
        if swap_total > 0:
            self._swap_gauge.set_value(
                swap_used * 100 / swap_total,
                f"{_fmt_bytes(swap_used)} / {_fmt_bytes(swap_total)}",
            )
        else:
            self._swap_gauge.set_value(0, "No swap")

    # ── Network ───────────────────────────────────────────────

    def _update_network(self, data: dict) -> None:
        nets: list[dict] = data.get("network", [])
        now = time.monotonic()
        dt = now - self._prev_net_time if self._prev_net_time else 0
        self._prev_net_time = now

        for n in nets:
            iface = n["interface"]
            rx = n["rx_bytes"]
            tx = n["tx_bytes"]

            rx_speed = 0.0
            tx_speed = 0.0
            if dt > 0 and iface in self._prev_net:
                prev = self._prev_net[iface]
                rx_speed = max(0.0, (rx - prev["rx"]) / dt)
                tx_speed = max(0.0, (tx - prev["tx"]) / dt)
            self._prev_net[iface] = {"rx": rx, "tx": tx}

            if iface not in self._net_rx_history:
                self._net_rx_history[iface] = deque(maxlen=60)
                self._net_tx_history[iface] = deque(maxlen=60)
            self._net_rx_history[iface].append(rx_speed)
            self._net_tx_history[iface].append(tx_speed)

            self._net_current[iface] = {
                "rx_bytes": rx,
                "tx_bytes": tx,
                "rx_packets": n["rx_packets"],
                "tx_packets": n["tx_packets"],
                "rx_speed": rx_speed,
                "tx_speed": tx_speed,
            }

        # Update combo items for each row (preserve selection)
        known = sorted(self._net_rx_history.keys())
        for row_data in self._net_rows:
            combo = row_data["combo"]
            current_items = [combo.itemText(i) for i in range(combo.count())]
            if current_items != known:
                prev_sel = combo.currentText()
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(known)
                if prev_sel in known:
                    combo.setCurrentText(prev_sel)
                combo.blockSignals(False)

        # Auto-select different interfaces for the two rows on first population
        if known and not self._net_rows[0]["combo"].currentText():
            self._net_rows[0]["combo"].setCurrentText(known[0])
            if len(known) > 1:
                self._net_rows[1]["combo"].setCurrentText(known[1])
            else:
                self._net_rows[1]["combo"].setCurrentText(known[0])

        # Refresh both rows
        for row_idx in range(len(self._net_rows)):
            self._refresh_net_row(row_idx)

    def _on_net_row_changed(self, row_idx: int) -> None:
        self._refresh_net_row(row_idx)

    def _refresh_net_row(self, row_idx: int) -> None:
        row_data = self._net_rows[row_idx]
        iface = row_data["combo"].currentText()
        if not iface:
            return

        if iface in self._net_rx_history:
            row_data["rx_spark"].set_data(self._net_rx_history[iface])
        if iface in self._net_tx_history:
            row_data["tx_spark"].set_data(self._net_tx_history[iface])

        cur = self._net_current.get(iface)
        if cur:
            row_data["speed_lbl"].setText(
                f"\u2B07 {_fmt_speed(cur['rx_speed'])}    "
                f"\u2B06 {_fmt_speed(cur['tx_speed'])}"
            )
            ip_addrs = self._net_ips.get(iface)
            row_data["ip_lbl"].setText(
                f"IP: {', '.join(ip_addrs)}" if ip_addrs else ""
            )
            row_data["stats_lbl"].setText(
                f"Total RX: {_fmt_bytes(cur['rx_bytes'])}    "
                f"TX: {_fmt_bytes(cur['tx_bytes'])}    |    "
                f"Packets RX: {cur['rx_packets']:,}    "
                f"TX: {cur['tx_packets']:,}"
            )

    # ── Disk ──────────────────────────────────────────────────

    def _update_disk(self, data: dict) -> None:
        disks: list[dict] = data.get("disks", [])
        self._disk_table.setRowCount(len(disks))
        for row, d in enumerate(disks):
            self._disk_table.setItem(row, 0, QTableWidgetItem(d["device"]))
            self._disk_table.setItem(row, 1, QTableWidgetItem(_fmt_bytes(d["size"])))
            self._disk_table.setItem(row, 2, QTableWidgetItem(_fmt_bytes(d["used"])))
            self._disk_table.setItem(row, 3, QTableWidgetItem(_fmt_bytes(d["avail"])))
            self._disk_table.setItem(row, 4, QTableWidgetItem(d["percent"]))
            self._disk_table.setItem(row, 5, QTableWidgetItem(d["mount"]))

    # ── Power actions ────────────────────────────────────────

    def _confirm(self, title: str, message: str) -> bool:
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _on_reboot(self) -> None:
        if self._confirm("Reboot", "Reboot the server now?"):
            self._ctrl.reboot_server()

    def _on_poweroff(self) -> None:
        if self._confirm("Power Off", "Power off the server now?"):
            self._ctrl.poweroff_server()

    def _on_shutdown(self) -> None:
        minutes, ok = QInputDialog.getInt(
            self, "Scheduled Shutdown",
            "Shutdown in how many minutes?",
            value=1, min=1, max=1440,
        )
        if ok:
            if self._confirm("Shutdown", f"Shutdown the server in {minutes} min?"):
                self._ctrl.shutdown_server(minutes)

    def _on_cancel_shutdown(self) -> None:
        if self._confirm("Cancel Shutdown", "Cancel the scheduled shutdown?"):
            self._ctrl.cancel_shutdown_server()

    def _on_power_success(self, msg: str) -> None:
        QMessageBox.information(self, "Power", msg)
