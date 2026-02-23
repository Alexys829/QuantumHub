from __future__ import annotations

from PyQt6.QtCore import QPropertyAnimation, QTimer, Qt, QEasingCurve
from PyQt6.QtWidgets import QGraphicsOpacityEffect, QLabel, QVBoxLayout, QWidget


_LEVEL_STYLES = {
    "success": "background-color: #1a7f37; border: 1px solid #2ea043;",
    "info": "background-color: #0d419d; border: 1px solid #58a6ff;",
    "warning": "background-color: #7a4e05; border: 1px solid #d29922;",
    "error": "background-color: #8b1a1a; border: 1px solid #f85149;",
}

_LEVEL_ICONS = {
    "success": "\u2714",
    "info": "\u2139",
    "warning": "\u26A0",
    "error": "\u2716",
}


class ToastNotification(QWidget):
    """Non-blocking toast notification overlay."""

    _active_toasts: list[ToastNotification] = []

    def __init__(
        self,
        parent: QWidget,
        message: str,
        level: str = "success",
        duration: int = 3000,
    ):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        style = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
        icon = _LEVEL_ICONS.get(level, "")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        label = QLabel(f"{icon}  {message}")
        label.setWordWrap(True)
        label.setStyleSheet("color: #ffffff; font-size: 13px;")
        layout.addWidget(label)

        self.setStyleSheet(
            f"ToastNotification {{ {style} border-radius: 8px; }}"
        )
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        self.adjustSize()

        # Opacity animation
        self._opacity = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity)
        self._opacity.setOpacity(0.0)

        self._fade_in = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_in.setDuration(250)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(0.95)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self._opacity, b"opacity")
        self._fade_out.setDuration(400)
        self._fade_out.setStartValue(0.95)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InCubic)
        self._fade_out.finished.connect(self._on_fade_out_done)

        self._duration = duration

    def show_toast(self) -> None:
        """Position and show the toast."""
        ToastNotification._active_toasts.append(self)
        self._reposition_all()
        self.show()
        self.raise_()
        self._fade_in.start()
        QTimer.singleShot(self._duration, self._start_fade_out)

    def _start_fade_out(self) -> None:
        self._fade_out.start()

    def _on_fade_out_done(self) -> None:
        if self in ToastNotification._active_toasts:
            ToastNotification._active_toasts.remove(self)
            self._reposition_all()
        self.close()

    @staticmethod
    def _reposition_all() -> None:
        margin = 16
        bottom_offset = margin
        for toast in reversed(ToastNotification._active_toasts):
            parent = toast.parentWidget()
            if parent is None:
                continue
            x = parent.width() - toast.width() - margin
            y = parent.height() - toast.height() - bottom_offset
            toast.move(x, y)
            bottom_offset += toast.height() + 8


def show_toast(
    parent: QWidget,
    message: str,
    level: str = "success",
    duration: int = 3000,
) -> None:
    """Factory function to create and show a toast notification."""
    toast = ToastNotification(parent, message, level, duration)
    toast.show_toast()
