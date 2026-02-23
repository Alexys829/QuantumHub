from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.controllers.disk_controller import DiskController


def _format_size(bytes_val: int) -> str:
    """Format bytes to human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(bytes_val) < 1024:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f} PB"


class _DiskCard(QFrame):
    """Card widget showing disk usage with a progress bar."""

    def __init__(self, disk: dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background-color: #2d2d2d; border: 1px solid #404040;"
            " border-radius: 8px; padding: 12px; }"
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # Device & mount
        device_label = QLabel(f"\U0001F4BE  {disk['device']}")
        device_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(device_label)

        mount_label = QLabel(f"Mount: {disk['mount']}")
        mount_label.setStyleSheet("font-size: 12px; color: #888888;")
        layout.addWidget(mount_label)

        # Progress bar
        percent_str = disk["percent"].rstrip("%")
        try:
            percent = int(percent_str)
        except ValueError:
            percent = 0

        bar = QProgressBar()
        bar.setValue(percent)
        bar.setTextVisible(True)
        bar.setFormat(f"{percent}%")
        bar.setFixedHeight(22)

        if percent >= 90:
            color = "#f85149"
        elif percent >= 70:
            color = "#d29922"
        else:
            color = "#2ea043"

        bar.setStyleSheet(
            f"QProgressBar {{ background-color: #1e1e1e; border: 1px solid #404040;"
            f" border-radius: 4px; text-align: center; color: #ffffff; font-size: 12px; }}"
            f"QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}"
        )
        layout.addWidget(bar)

        # Size details
        details = QHBoxLayout()
        for label_text, value in [
            ("Total", _format_size(disk["size"])),
            ("Used", _format_size(disk["used"])),
            ("Free", _format_size(disk["avail"])),
        ]:
            col = QVBoxLayout()
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(val_lbl)
            desc_lbl = QLabel(label_text)
            desc_lbl.setStyleSheet("font-size: 11px; color: #888888;")
            desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            col.addWidget(desc_lbl)
            details.addLayout(col)
        layout.addLayout(details)


class DiskUsageView(QWidget):
    """Disk usage view with card-based layout and progress bars."""

    def __init__(self, controller: DiskController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        header = QPushButton("\U0001F4BE  Disk Usage")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        header_row.addWidget(header)
        header_row.addStretch()

        self._refresh_btn = QPushButton("\U0001F504  Refresh")
        self._refresh_btn.clicked.connect(self._ctrl.refresh_disk)
        header_row.addWidget(self._refresh_btn)
        layout.addLayout(header_row)

        # Scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll)

        self._cards_container = QWidget()
        self._cards_layout = QGridLayout(self._cards_container)
        self._cards_layout.setSpacing(12)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(self._cards_container)

    def _connect_signals(self) -> None:
        self._ctrl.disk_loaded.connect(self._populate)
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    def _populate(self, disks: list[dict]) -> None:
        # Clear existing cards
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 3
        for i, disk in enumerate(disks):
            card = _DiskCard(disk)
            row = i // cols
            col = i % cols
            self._cards_layout.addWidget(card, row, col)

        # Fill remaining cells in last row
        remainder = len(disks) % cols
        if remainder:
            for c in range(remainder, cols):
                spacer = QWidget()
                self._cards_layout.addWidget(spacer, len(disks) // cols, c)
