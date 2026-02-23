from __future__ import annotations

import json
import logging
import shlex
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


class ComposeService:
    """Runs `docker compose` commands locally or via SSH on a remote host."""

    def __init__(self, connection_manager: ConnectionManager):
        self._cm = connection_manager

    def _run_compose(
        self, args: list[str], timeout: int = 60
    ) -> tuple[str, str, int]:
        """Execute a docker compose command and return (stdout, stderr, returncode)."""
        cmd_parts = ["docker", "compose"] + args

        ssh = self._cm.ssh_client
        if ssh is not None:
            # Remote: run via SSH
            cmd_str = " ".join(shlex.quote(p) for p in cmd_parts)
            logger.info("Remote compose: %s", cmd_str)
            transport = ssh.get_transport()
            if transport is None or not transport.is_active():
                raise RuntimeError("SSH transport is not active")
            channel = transport.open_session()
            channel.settimeout(timeout)
            channel.exec_command(cmd_str)

            stdout_chunks = []
            stderr_chunks = []
            while True:
                if channel.recv_ready():
                    data = channel.recv(65536)
                    if data:
                        stdout_chunks.append(data.decode("utf-8", errors="replace"))
                if channel.recv_stderr_ready():
                    data = channel.recv_stderr(65536)
                    if data:
                        stderr_chunks.append(data.decode("utf-8", errors="replace"))
                if channel.exit_status_ready():
                    # Drain remaining
                    while channel.recv_ready():
                        data = channel.recv(65536)
                        if data:
                            stdout_chunks.append(data.decode("utf-8", errors="replace"))
                    while channel.recv_stderr_ready():
                        data = channel.recv_stderr(65536)
                        if data:
                            stderr_chunks.append(data.decode("utf-8", errors="replace"))
                    break

            rc = channel.recv_exit_status()
            channel.close()
            return "".join(stdout_chunks), "".join(stderr_chunks), rc
        else:
            # Local: subprocess
            logger.info("Local compose: %s", " ".join(cmd_parts))
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode

    def list_projects(self) -> list[dict]:
        """List active compose projects."""
        stdout, stderr, rc = self._run_compose(["ls", "--format", "json"])
        if rc != 0:
            raise RuntimeError(f"docker compose ls failed: {stderr.strip()}")
        if not stdout.strip():
            return []
        try:
            data = json.loads(stdout)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            logger.warning("Failed to parse compose ls output: %s", stdout[:200])
            return []

    def project_services(self, project_name: str) -> list[dict]:
        """List services for a compose project."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "ps", "--format", "json"]
        )
        if rc != 0:
            raise RuntimeError(f"docker compose ps failed: {stderr.strip()}")
        if not stdout.strip():
            return []
        try:
            # docker compose ps --format json outputs one JSON object per line
            services = []
            for line in stdout.strip().splitlines():
                line = line.strip()
                if line:
                    services.append(json.loads(line))
            return services
        except json.JSONDecodeError:
            logger.warning("Failed to parse compose ps output: %s", stdout[:200])
            return []

    def up(self, project_name: str) -> str:
        """Start a compose project (detached)."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "up", "-d"], timeout=120
        )
        if rc != 0:
            raise RuntimeError(f"docker compose up failed: {stderr.strip()}")
        return stdout + stderr

    def down(self, project_name: str) -> str:
        """Stop and remove a compose project."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "down"], timeout=120
        )
        if rc != 0:
            raise RuntimeError(f"docker compose down failed: {stderr.strip()}")
        return stdout + stderr

    def restart(self, project_name: str) -> str:
        """Restart a compose project."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "restart"], timeout=120
        )
        if rc != 0:
            raise RuntimeError(f"docker compose restart failed: {stderr.strip()}")
        return stdout + stderr

    def pull(self, project_name: str) -> str:
        """Pull images for a compose project."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "pull"], timeout=300
        )
        if rc != 0:
            raise RuntimeError(f"docker compose pull failed: {stderr.strip()}")
        return stdout + stderr

    def logs(self, project_name: str, tail: int = 200) -> str:
        """Get logs for a compose project."""
        stdout, stderr, rc = self._run_compose(
            ["-p", project_name, "logs", "--tail", str(tail), "--no-color"]
        )
        if rc != 0:
            raise RuntimeError(f"docker compose logs failed: {stderr.strip()}")
        return stdout
