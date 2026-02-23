from __future__ import annotations

import logging
from typing import Any

import docker
from docker.models.containers import Container
from docker.models.images import Image
from docker.models.networks import Network
from docker.models.volumes import Volume

from app.constants import LOCAL_DOCKER_SOCKET

logger = logging.getLogger(__name__)


class DockerService:
    """Wraps docker-py DockerClient. One instance per connection."""

    def __init__(self):
        self._client: docker.DockerClient | None = None

    def connect(self, base_url: str = LOCAL_DOCKER_SOCKET) -> None:
        """Connect to Docker daemon at the given URL (local socket or TCP)."""
        self._client = docker.DockerClient(base_url=base_url, timeout=10)
        self._client.ping()
        logger.info("Docker connected: %s", base_url)

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    @property
    def client(self) -> docker.DockerClient:
        if self._client is None:
            raise RuntimeError("DockerService not connected.")
        return self._client

    # -- Containers -------------------------------------------------------

    def list_containers(self, all: bool = True) -> list[Container]:
        return self.client.containers.list(all=all)

    def get_container(self, container_id: str) -> Container:
        return self.client.containers.get(container_id)

    def start_container(self, container_id: str) -> None:
        self.client.containers.get(container_id).start()

    def stop_container(self, container_id: str, timeout: int = 10) -> None:
        self.client.containers.get(container_id).stop(timeout=timeout)

    def restart_container(self, container_id: str, timeout: int = 10) -> None:
        self.client.containers.get(container_id).restart(timeout=timeout)

    def kill_container(self, container_id: str, signal: str = "SIGKILL") -> None:
        self.client.containers.get(container_id).kill(signal=signal)

    def remove_container(self, container_id: str, force: bool = False) -> None:
        self.client.containers.get(container_id).remove(force=force)

    def container_logs(
        self, container_id: str, tail: int = 200, stream: bool = False
    ) -> Any:
        return self.client.containers.get(container_id).logs(
            tail=tail, stream=stream, timestamps=True
        )

    def container_stats(self, container_id: str, stream: bool = False) -> Any:
        return self.client.containers.get(container_id).stats(
            stream=stream, decode=True
        )

    # -- Images -----------------------------------------------------------

    def list_images(self) -> list[Image]:
        return self.client.images.list()

    def pull_image(self, repository: str, tag: str = "latest") -> Image:
        return self.client.images.pull(repository, tag=tag)

    def remove_image(self, image_id: str, force: bool = False) -> None:
        self.client.images.remove(image_id, force=force)

    def build_image(self, path: str, tag: str, **kwargs) -> tuple:
        return self.client.images.build(path=path, tag=tag, **kwargs)

    # -- Volumes ----------------------------------------------------------

    def list_volumes(self) -> list[Volume]:
        return self.client.volumes.list()

    def create_volume(self, name: str, **kwargs) -> Volume:
        return self.client.volumes.create(name=name, **kwargs)

    def remove_volume(self, volume_name: str, force: bool = False) -> None:
        self.client.volumes.get(volume_name).remove(force=force)

    def inspect_volume(self, volume_name: str) -> dict:
        return self.client.volumes.get(volume_name).attrs

    # -- Networks ---------------------------------------------------------

    def list_networks(self) -> list[Network]:
        return self.client.networks.list()

    def create_network(
        self, name: str, driver: str = "bridge", **kwargs
    ) -> Network:
        return self.client.networks.create(name, driver=driver, **kwargs)

    def remove_network(self, network_id: str) -> None:
        self.client.networks.get(network_id).remove()

    def inspect_network(self, network_id: str) -> dict:
        return self.client.networks.get(network_id).attrs

    # -- Exec -------------------------------------------------------------

    def exec_run(self, container_id: str, cmd: str) -> tuple[int, str]:
        """Run a command inside a container and return (exit_code, output)."""
        container = self.client.containers.get(container_id)
        result = container.exec_run(cmd, demux=False)
        output = result.output.decode("utf-8", errors="replace") if result.output else ""
        return result.exit_code, output

    # -- Search -----------------------------------------------------------

    def search_images(self, term: str, limit: int = 25) -> list[dict]:
        """Search Docker Hub for images."""
        return self.client.images.search(term, limit=limit)

    # -- System -----------------------------------------------------------

    def info(self) -> dict:
        return self.client.info()

    def disk_usage(self) -> dict:
        return self.client.df()
