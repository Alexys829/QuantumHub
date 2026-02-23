from __future__ import annotations

import logging

from app.services.docker_service import DockerService
from app.services.ssh_tunnel_service import SSHTunnelService

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages the active Docker connection (local or one remote at a time).

    For remote connections, creates an SSH tunnel that runs
    'docker system dial-stdio' on the remote host, then connects
    docker-py to the local TCP endpoint of the tunnel.
    """

    def __init__(self):
        self._tunnel_service = SSHTunnelService()
        self._docker_service: DockerService | None = None
        self._active_server = None  # None = local

    @property
    def docker(self) -> DockerService:
        if self._docker_service is None:
            raise RuntimeError("No active connection.")
        return self._docker_service

    @property
    def active_server(self):
        return self._active_server

    @property
    def is_local(self) -> bool:
        return self._active_server is None

    @property
    def is_connected(self) -> bool:
        return self._docker_service is not None

    @property
    def ssh_client(self):
        """Return the active Paramiko SSHClient for the current remote connection, or None."""
        if self._active_server is None or self._active_server.id is None:
            return None
        tunnel = self._tunnel_service._tunnels.get(self._active_server.id)
        if tunnel and tunnel.is_active:
            return tunnel.ssh_client
        return None

    def connect_local(self) -> None:
        self.disconnect()
        svc = DockerService()
        svc.connect()
        self._docker_service = svc
        self._active_server = None
        logger.info("Connected to local Docker.")

    def connect_remote(self, server) -> None:
        """Open SSH tunnel to server, then connect docker-py through it."""
        self.disconnect()
        tunnel_info = self._tunnel_service.open_tunnel(server)
        svc = DockerService()
        svc.connect(base_url=tunnel_info.docker_base_url)
        self._docker_service = svc
        self._active_server = server
        logger.info("Connected to remote Docker on %s.", server.name)

    def disconnect(self) -> None:
        if self._docker_service:
            self._docker_service.disconnect()
            self._docker_service = None
        if self._active_server and self._active_server.id:
            self._tunnel_service.close_tunnel(self._active_server.id)
        self._active_server = None

    def shutdown(self) -> None:
        self.disconnect()
        self._tunnel_service.close_all()
