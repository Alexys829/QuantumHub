from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from app.models.server import Server, ServerRepository


class ServerController(QObject):
    """CRUD operations for saved servers."""

    servers_changed = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._repo = ServerRepository()

    def get_all_servers(self) -> list[Server]:
        return self._repo.get_all()

    def get_server(self, server_id: int) -> Server | None:
        return self._repo.get_by_id(server_id)

    def add_server(self, server: Server) -> Server:
        created = self._repo.create(server)
        self.servers_changed.emit()
        return created

    def update_server(self, server: Server) -> None:
        self._repo.update(server)
        self.servers_changed.emit()

    def delete_server(self, server_id: int) -> None:
        self._repo.delete(server_id)
        self.servers_changed.emit()
