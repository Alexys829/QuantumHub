from __future__ import annotations

import logging
import select
import socket
import threading
from dataclasses import dataclass, field

import paramiko

from app.constants import TUNNEL_LOCAL_BIND_HOST

logger = logging.getLogger(__name__)


@dataclass
class TunnelInfo:
    """Holds tunnel state for one remote server."""

    server_id: int
    local_port: int
    ssh_client: paramiko.SSHClient | None = None
    server_socket: socket.socket | None = None
    thread: threading.Thread | None = None
    _active: bool = field(default=False, repr=False)

    @property
    def docker_base_url(self) -> str:
        return f"tcp://{TUNNEL_LOCAL_BIND_HOST}:{self.local_port}"

    @property
    def is_active(self) -> bool:
        if not self._active or not self.ssh_client:
            return False
        transport = self.ssh_client.get_transport()
        return transport is not None and transport.is_active()


def _forward_dial_stdio(
    local_socket: socket.socket,
    ssh_client: paramiko.SSHClient,
    tunnel_info: TunnelInfo,
) -> None:
    """Accept local TCP connections and forward each via 'docker system dial-stdio'."""
    local_socket.settimeout(1.0)
    while tunnel_info._active:
        try:
            client_sock, _ = local_socket.accept()
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            transport = ssh_client.get_transport()
            if transport is None or not transport.is_active():
                logger.error("SSH transport is no longer active")
                client_sock.close()
                break
            channel = transport.open_session()
            channel.exec_command("docker system dial-stdio")
        except Exception as e:
            logger.error("Failed to open SSH session: %s", e)
            client_sock.close()
            continue

        relay = threading.Thread(
            target=_relay_data,
            args=(client_sock, channel),
            daemon=True,
        )
        relay.start()


def _relay_data(sock: socket.socket, channel: paramiko.Channel) -> None:
    """Bidirectional relay between a local socket and an SSH channel."""
    try:
        while True:
            r, _, _ = select.select([sock, channel], [], [], 10.0)
            if not r:
                # Check if channel is still open
                if channel.closed or channel.exit_status_ready():
                    break
                continue
            if sock in r:
                data = sock.recv(65536)
                if not data:
                    break
                channel.sendall(data)
            if channel in r:
                data = channel.recv(65536)
                if not data:
                    break
                sock.sendall(data)
    except Exception:
        pass
    finally:
        try:
            channel.close()
        except Exception:
            pass
        try:
            sock.close()
        except Exception:
            pass


class SSHTunnelService:
    """Creates SSH tunnels to remote Docker daemons using 'docker system dial-stdio'."""

    def __init__(self):
        self._tunnels: dict[int, TunnelInfo] = {}

    def open_tunnel(self, server) -> TunnelInfo:
        """Open an SSH tunnel to the given server.

        For each incoming local TCP connection, opens an SSH session
        running 'docker system dial-stdio' on the remote host,
        effectively proxying Docker API over SSH.
        """
        if server.id in self._tunnels:
            existing = self._tunnels[server.id]
            if existing.is_active:
                return existing
            self._cleanup_tunnel(existing)
            self._tunnels.pop(server.id)

        # Create SSH client
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs: dict = {
            "hostname": server.host,
            "port": server.port,
            "username": server.username,
        }
        if server.auth_method == "key" and server.key_path:
            connect_kwargs["key_filename"] = server.key_path
        elif server.auth_method == "password" and server.password:
            connect_kwargs["password"] = server.password

        ssh.connect(**connect_kwargs)
        logger.info("SSH connected to %s@%s:%d", server.username, server.host, server.port)

        # Bind a local TCP socket on a random free port
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((TUNNEL_LOCAL_BIND_HOST, 0))
        server_socket.listen(5)
        local_port = server_socket.getsockname()[1]

        info = TunnelInfo(
            server_id=server.id,
            local_port=local_port,
            ssh_client=ssh,
            server_socket=server_socket,
            _active=True,
        )

        # Start forwarding thread
        thread = threading.Thread(
            target=_forward_dial_stdio,
            args=(server_socket, ssh, info),
            daemon=True,
        )
        thread.start()
        info.thread = thread

        self._tunnels[server.id] = info
        logger.info(
            "Tunnel opened: docker system dial-stdio via %s -> localhost:%d",
            server.host,
            info.local_port,
        )
        return info

    def close_tunnel(self, server_id: int) -> None:
        info = self._tunnels.pop(server_id, None)
        if info:
            self._cleanup_tunnel(info)
            logger.info("Tunnel closed for server_id=%d", server_id)

    def close_all(self) -> None:
        for server_id in list(self._tunnels.keys()):
            self.close_tunnel(server_id)

    def is_active(self, server_id: int) -> bool:
        info = self._tunnels.get(server_id)
        return info is not None and info.is_active

    @staticmethod
    def _cleanup_tunnel(info: TunnelInfo) -> None:
        info._active = False
        if info.server_socket:
            try:
                info.server_socket.close()
            except Exception:
                pass
        if info.ssh_client:
            try:
                info.ssh_client.close()
            except Exception:
                pass
        if info.thread and info.thread.is_alive():
            info.thread.join(timeout=3)
