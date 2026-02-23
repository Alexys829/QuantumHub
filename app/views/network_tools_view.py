from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.controllers.network_tools_controller import NetworkToolsController


class NetworkToolsView(QWidget):
    """Network diagnostic tools: ping, tracepath, DNS lookup."""

    def __init__(self, controller: NetworkToolsController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F527  Network Tools")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Input row
        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        input_row.addWidget(QLabel("Host:"))
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("8.8.8.8 or google.com")
        self._host_input.setMinimumWidth(250)
        self._host_input.returnPressed.connect(self._on_ping)
        input_row.addWidget(self._host_input)

        input_row.addWidget(QLabel("Count:"))
        self._count_spin = QSpinBox()
        self._count_spin.setRange(1, 20)
        self._count_spin.setValue(4)
        self._count_spin.setFixedWidth(60)
        input_row.addWidget(self._count_spin)

        self._ping_btn = QPushButton("\u25B6  Ping")
        self._ping_btn.clicked.connect(self._on_ping)
        input_row.addWidget(self._ping_btn)

        self._trace_btn = QPushButton("\U0001F500  Tracepath")
        self._trace_btn.clicked.connect(self._on_tracepath)
        input_row.addWidget(self._trace_btn)

        self._dns_btn = QPushButton("\U0001F50D  DNS Lookup")
        self._dns_btn.clicked.connect(self._on_dns)
        input_row.addWidget(self._dns_btn)

        input_row.addStretch()
        layout.addLayout(input_row)

        # Ping results card
        self._ping_group = QGroupBox("\U0001F4CA  Ping Results")
        self._ping_group.setObjectName("settingsGroup")
        ping_layout = QVBoxLayout(self._ping_group)
        ping_layout.setSpacing(6)

        # Stats row
        stats = QHBoxLayout()
        stats.setSpacing(20)
        self._ping_host_label = _stat_label("Host:", "—")
        self._ping_status_label = _stat_label("Status:", "—")
        self._ping_packets_label = _stat_label("Packets:", "—")
        self._ping_loss_label = _stat_label("Loss:", "—")
        self._ping_rtt_label = _stat_label("RTT:", "—")
        for lbl in (
            self._ping_host_label, self._ping_status_label,
            self._ping_packets_label, self._ping_loss_label,
            self._ping_rtt_label,
        ):
            stats.addWidget(lbl)
        stats.addStretch()
        ping_layout.addLayout(stats)
        layout.addWidget(self._ping_group)

        # Output text area
        self._output = QPlainTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Monospace", 10))
        self._output.setStyleSheet(
            "QPlainTextEdit { background-color: #1e1e1e; color: #cccccc;"
            " border: 1px solid #333333; border-radius: 4px; }"
        )
        self._output.setPlaceholderText(
            "Run a command to see output here..."
        )
        layout.addWidget(self._output)

    def _connect_signals(self) -> None:
        self._ctrl.ping_result.connect(self._on_ping_result)
        self._ctrl.tracepath_result.connect(self._on_tracepath_result)
        self._ctrl.dns_result.connect(self._on_dns_result)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    def _get_host(self) -> str | None:
        host = self._host_input.text().strip()
        if not host:
            QMessageBox.warning(self, "Validation", "Please enter a host.")
            return None
        return host

    def _set_running(self, tool: str) -> None:
        self._output.setPlainText(f"Running {tool}...")
        self._ping_btn.setEnabled(False)
        self._trace_btn.setEnabled(False)
        self._dns_btn.setEnabled(False)

    def _set_done(self) -> None:
        self._ping_btn.setEnabled(True)
        self._trace_btn.setEnabled(True)
        self._dns_btn.setEnabled(True)

    # ── Ping ─────────────────────────────────────────────────

    def _on_ping(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._set_running("ping")
        self._ctrl.run_ping(host, self._count_spin.value())

    def _on_ping_result(self, result: dict) -> None:
        self._set_done()
        self._ping_host_label.setText(f"Host: {result['host']}")

        if result["reachable"]:
            self._ping_status_label.setText("Status: \U0001F7E2 Reachable")
            self._ping_status_label.setStyleSheet(
                "color: #2ea043; font-weight: 600;"
            )
        else:
            self._ping_status_label.setText("Status: \U0001F534 Unreachable")
            self._ping_status_label.setStyleSheet(
                "color: #f85149; font-weight: 600;"
            )

        self._ping_packets_label.setText(
            f"Packets: {result['transmitted']} sent, "
            f"{result['received']} received"
        )

        loss = result["loss_pct"]
        loss_color = "#2ea043" if loss == 0 else "#f85149" if loss > 50 else "#d29922"
        self._ping_loss_label.setText(f"Loss: {loss}%")
        self._ping_loss_label.setStyleSheet(f"color: {loss_color}; font-weight: 600;")

        if result["rtt_avg"] > 0:
            self._ping_rtt_label.setText(
                f"RTT: {result['rtt_min']:.1f} / "
                f"{result['rtt_avg']:.1f} / "
                f"{result['rtt_max']:.1f} ms"
            )
        else:
            self._ping_rtt_label.setText("RTT: —")

        self._output.setPlainText(result.get("output", ""))

    # ── Tracepath ────────────────────────────────────────────

    def _on_tracepath(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._set_running("tracepath")
        self._ctrl.run_tracepath(host)

    def _on_tracepath_result(self, output: str) -> None:
        self._set_done()
        self._output.setPlainText(output or "No output.")

    # ── DNS Lookup ───────────────────────────────────────────

    def _on_dns(self) -> None:
        host = self._get_host()
        if not host:
            return
        self._set_running("DNS lookup")
        self._ctrl.run_dns_lookup(host)

    def _on_dns_result(self, output: str) -> None:
        self._set_done()
        self._output.setPlainText(output or "No records found.")


def _stat_label(title: str, value: str) -> QLabel:
    """Create a stat label for the ping results card."""
    lbl = QLabel(f"{title} {value}")
    lbl.setStyleSheet("color: #e0e0e0;")
    return lbl
