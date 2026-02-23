from __future__ import annotations

import os
import shlex
import socket
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.models.database import Database
from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager
    from app.services.system_service import SystemService


class TerminalController(QObject):
    """Controller for the terminal view."""

    command_output = pyqtSignal(str)
    command_error = pyqtSignal(str)
    cwd_changed = pyqtSignal(str)
    prompt_changed = pyqtSignal(str)
    sudo_password_needed = pyqtSignal(str)
    command_started = pyqtSignal()
    command_finished = pyqtSignal()
    completions_ready = pyqtSignal(list)
    history_loaded = pyqtSignal(list)

    def __init__(
        self,
        system_service: SystemService,
        connection_manager: ConnectionManager,
        parent=None,
    ):
        super().__init__(parent)
        self._sys = system_service
        self._cm = connection_manager
        self._pool = QThreadPool.globalInstance()
        self._cwd = "~"
        self._cwd_resolved = False
        self._cancelled = False
        self._local_user = ""
        self._local_host = ""
        try:
            self._local_user = os.getlogin()
        except OSError:
            self._local_user = os.environ.get("USER", "user")
        try:
            self._local_host = socket.gethostname()
        except Exception:
            self._local_host = "localhost"

    @property
    def cwd(self) -> str:
        return self._cwd

    @property
    def prompt(self) -> str:
        return self._build_prompt()

    def _build_prompt(self) -> str:
        server = self._cm.active_server
        if server is not None:
            user = server.username
            host = server.host
        else:
            user = self._local_user
            host = self._local_host
        return f"{user}@{host}:{self._cwd}"

    def _server_id(self) -> int | None:
        server = self._cm.active_server
        return server.id if server else None

    def reset_session(self) -> None:
        """Reset cwd and sudo password — call when the server connection changes."""
        self._cwd = "~"
        self._cwd_resolved = False
        server = self._cm.active_server
        if server is not None and server.password:
            self._sys.sudo_password = server.password
        else:
            self._sys.sudo_password = None
        self.cwd_changed.emit("~")
        self.prompt_changed.emit(self._build_prompt())
        # Load persistent history for this server
        self._load_history()
        # Resolve home directory immediately
        self._resolve_home()

    def _load_history(self) -> None:
        sid = self._server_id()
        cmds = Database.instance().get_history(sid)
        self.history_loaded.emit(cmds)

    def _resolve_home(self) -> None:
        """Resolve ~ to the actual home path in the background."""

        def _resolve():
            return self._sys.run_terminal_command("pwd", "~")

        worker = DockerWorker(fn=_resolve)

        def _on_result(result):
            output, rc = result
            if rc == 0 and output.strip():
                self._cwd = output.strip().splitlines()[-1]
            else:
                self._cwd = "/tmp"
            self._cwd_resolved = True
            self.cwd_changed.emit(self._cwd)
            self.prompt_changed.emit(self._build_prompt())

        worker.signals.result.connect(_on_result)
        self._pool.start(worker)

    def set_sudo_password(self, password: str) -> None:
        self._sys.sudo_password = password

    def execute_command(self, cmd: str) -> None:
        cmd = cmd.strip()
        if not cmd:
            return

        # Save to persistent history
        Database.instance().add_history(self._server_id(), cmd)

        if not self._cwd_resolved:
            self._resolve_home_then_run(cmd)
            return

        if cmd == "cd" or cmd.startswith("cd "):
            target = cmd[3:].strip() if cmd.startswith("cd ") else "~"
            if not target:
                target = "~"
            self._execute_cd(target)
        else:
            self._execute_regular(cmd)

    def _resolve_home_then_run(self, pending_cmd: str) -> None:
        self.command_started.emit()

        def _resolve():
            return self._sys.run_terminal_command("pwd", "~")

        worker = DockerWorker(fn=_resolve)

        def _on_result(result):
            output, rc = result
            if rc == 0 and output.strip():
                self._cwd = output.strip().splitlines()[-1]
            else:
                self._cwd = "/tmp"
            self._cwd_resolved = True
            self.cwd_changed.emit(self._cwd)
            self.prompt_changed.emit(self._build_prompt())
            self.command_finished.emit()
            self.execute_command(pending_cmd)

        def _on_error(msg):
            self.command_error.emit(msg)
            self.command_finished.emit()

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        self._pool.start(worker)

    def _execute_cd(self, target: str) -> None:
        self.command_started.emit()
        self._cancelled = False
        cwd = self._cwd

        def _run():
            return self._sys.run_terminal_command(f"cd {target} && pwd", cwd)

        worker = DockerWorker(fn=_run)

        def _on_result(result):
            if self._cancelled:
                return
            output, rc = result
            if rc == 0:
                new_cwd = output.strip().splitlines()[-1]
                self._cwd = new_cwd
                self.cwd_changed.emit(new_cwd)
                self.prompt_changed.emit(self._build_prompt())
            else:
                self.command_error.emit(
                    output.strip() if output.strip()
                    else f"cd: {target}: No such file or directory"
                )
            self.command_finished.emit()

        def _on_error(msg):
            if not self._cancelled:
                self.command_error.emit(msg)
            self.command_finished.emit()

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        self._pool.start(worker)

    def _execute_regular(self, cmd: str) -> None:
        self.command_started.emit()
        self._cancelled = False
        cwd = self._cwd

        def _run():
            return self._sys.run_terminal_command(cmd, cwd)

        worker = DockerWorker(fn=_run)

        def _on_result(result):
            if self._cancelled:
                self.command_finished.emit()
                return
            output, rc = result
            if cmd.startswith("sudo ") and rc != 0:
                low = output.lower()
                if (
                    "incorrect password" in low
                    or "sorry, try again" in low
                    or "non corretto" in low
                    or "a password is required" in low
                    or "no password was provided" in low
                    or "necessaria una password" in low
                    # sudo -n failed: any "sudo:" error means password needed
                    or (self._sys.sudo_password is None and "sudo:" in low)
                ):
                    self._sys.sudo_password = None
                    self.command_finished.emit()
                    self.sudo_password_needed.emit(cmd)
                    return
            if output.strip():
                self.command_output.emit(output.rstrip())
            if rc != 0 and not output.strip():
                self.command_error.emit(f"Command exited with code {rc}")
            self.command_finished.emit()

        def _on_error(msg):
            if not self._cancelled:
                self.command_error.emit(msg)
            self.command_finished.emit()

        worker.signals.result.connect(_on_result)
        worker.signals.error.connect(_on_error)
        self._pool.start(worker)

    def cancel_command(self) -> None:
        """Mark the current command as cancelled (output will be ignored)."""
        self._cancelled = True
        self.command_output.emit("^C")
        self.command_finished.emit()

    def tab_complete(self, text: str) -> None:
        """Run shell completion for the current input text."""
        # Extract the last word (the one being completed)
        parts = text.rsplit(None, 1)
        partial = parts[-1] if parts else ""
        if not partial:
            return

        cwd = self._cwd
        safe = shlex.quote(partial)

        def _run():
            # compgen is a bash builtin — must invoke via bash -c
            cmd = f'bash -c "compgen -f -- {safe}" 2>/dev/null'
            out, rc = self._sys.run_terminal_command(cmd, cwd)
            if rc == 0 and out.strip():
                return out.strip().splitlines()
            # Fallback: ls -d (works in any POSIX shell)
            cmd = f"ls -1d {safe}* 2>/dev/null"
            out, rc = self._sys.run_terminal_command(cmd, cwd)
            if rc == 0 and out.strip():
                return out.strip().splitlines()
            return []

        worker = DockerWorker(fn=_run)
        worker.signals.result.connect(self.completions_ready.emit)
        self._pool.start(worker)
