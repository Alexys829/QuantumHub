from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.system_service import SystemService


class UsersController(QObject):
    """Controller for user and group management."""

    users_loaded = pyqtSignal(list)
    groups_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, system_service: SystemService, parent=None):
        super().__init__(parent)
        self._sys = system_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    # ── Users ─────────────────────────────────────────────────

    def refresh_users(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._sys.get_users()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.users_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: setattr(self, '_busy', False))
        self._pool.start(worker)

    def add_user(
        self,
        username: str,
        home: str | None = None,
        shell: str | None = None,
        groups: str | None = None,
    ) -> None:
        def _add():
            out, rc = self._sys.add_user(username, home=home, shell=shell, groups=groups)
            if rc != 0:
                raise RuntimeError(out or f"Failed to add user {username}")
            return f"User '{username}' created."

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_users)
        self._pool.start(worker)

    def delete_user(self, username: str, remove_home: bool = False) -> None:
        def _delete():
            out, rc = self._sys.delete_user(username, remove_home=remove_home)
            if rc != 0:
                raise RuntimeError(out or f"Failed to delete user {username}")
            return f"User '{username}' deleted."

        worker = DockerWorker(fn=_delete)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_users)
        self._pool.start(worker)

    def modify_user(
        self,
        username: str,
        shell: str | None = None,
        groups: str | None = None,
    ) -> None:
        def _modify():
            out, rc = self._sys.modify_user(username, shell=shell, groups=groups)
            if rc != 0:
                raise RuntimeError(out or f"Failed to modify user {username}")
            return f"User '{username}' modified."

        worker = DockerWorker(fn=_modify)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_users)
        self._pool.start(worker)

    def change_password(self, username: str, password: str) -> None:
        def _change():
            out, rc = self._sys.change_password(username, password)
            if rc != 0:
                raise RuntimeError(out or f"Failed to change password for {username}")
            return f"Password changed for '{username}'."

        worker = DockerWorker(fn=_change)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    # ── Groups ────────────────────────────────────────────────

    def refresh_groups(self) -> None:
        def _fetch():
            return self._sys.get_groups()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.groups_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def add_group(self, name: str, gid: int | None = None) -> None:
        def _add():
            out, rc = self._sys.add_group(name, gid=gid)
            if rc != 0:
                raise RuntimeError(out or f"Failed to add group {name}")
            return f"Group '{name}' created."

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_groups)
        self._pool.start(worker)

    def delete_group(self, name: str) -> None:
        def _delete():
            out, rc = self._sys.delete_group(name)
            if rc != 0:
                raise RuntimeError(out or f"Failed to delete group {name}")
            return f"Group '{name}' deleted."

        worker = DockerWorker(fn=_delete)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_groups)
        self._pool.start(worker)

    def modify_group(self, name: str, new_name: str | None = None, gid: int | None = None) -> None:
        def _modify():
            out, rc = self._sys.modify_group(name, new_name=new_name, gid=gid)
            if rc != 0:
                raise RuntimeError(out or f"Failed to modify group {name}")
            return f"Group '{name}' modified."

        worker = DockerWorker(fn=_modify)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_groups)
        self._pool.start(worker)

    def add_user_to_group(self, username: str, group: str) -> None:
        def _add():
            out, rc = self._sys.add_user_to_group(username, group)
            if rc != 0:
                raise RuntimeError(out or f"Failed to add {username} to {group}")
            return f"User '{username}' added to group '{group}'."

        worker = DockerWorker(fn=_add)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_groups)
        self._pool.start(worker)

    def remove_user_from_group(self, username: str, group: str) -> None:
        def _remove():
            out, rc = self._sys.remove_user_from_group(username, group)
            if rc != 0:
                raise RuntimeError(out or f"Failed to remove {username} from {group}")
            return f"User '{username}' removed from group '{group}'."

        worker = DockerWorker(fn=_remove)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_groups)
        self._pool.start(worker)
