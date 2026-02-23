from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class FirewallController(QObject):
    """Controller for ufw firewall management."""

    rules_loaded = pyqtSignal(dict)  # {available, enabled, rules}
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    def refresh_rules(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_firewall_status()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.rules_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def toggle_firewall(self, enabled: bool) -> None:
        def _do():
            output, rc = self._sys.set_firewall_enabled(enabled)
            if rc != 0:
                raise RuntimeError(output or "Failed to toggle firewall")
            state = "enabled" if enabled else "disabled"
            return f"Firewall {state}"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_rules)
        self._pool.start(worker)

    def add_rule(
        self, port: str, protocol: str, action: str, source: str
    ) -> None:
        def _do():
            output, rc = self._sys.add_firewall_rule(
                port, protocol, action, source
            )
            if rc != 0:
                raise RuntimeError(output or "Failed to add rule")
            return f"Rule added: {action} {port}/{protocol}"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_rules)
        self._pool.start(worker)

    def delete_rule(self, rule_num: int) -> None:
        def _do():
            output, rc = self._sys.delete_firewall_rule(rule_num)
            if rc != 0:
                raise RuntimeError(output or "Failed to delete rule")
            return f"Rule #{rule_num} deleted"

        worker = DockerWorker(fn=_do)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_rules)
        self._pool.start(worker)
