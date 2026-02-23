from __future__ import annotations

from dataclasses import dataclass

from app.models.database import Database


@dataclass
class Server:
    """Represents a saved remote Docker server."""

    id: int | None = None
    name: str = ""
    host: str = ""
    port: int = 22
    username: str = ""
    auth_method: str = "key"  # "key" | "password"
    key_path: str | None = None
    password: str | None = None
    docker_port: int = 2375
    created_at: str | None = None
    updated_at: str | None = None

    def to_export_dict(self) -> dict:
        """Convert to a JSON-safe dict, excluding password and internal IDs."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "auth_method": self.auth_method,
            "key_path": self.key_path,
            "docker_port": self.docker_port,
        }

    @classmethod
    def from_import_dict(cls, data: dict) -> Server:
        """Create a Server from an imported JSON dict (password never imported)."""
        return cls(
            name=data.get("name", ""),
            host=data.get("host", ""),
            port=data.get("port", 22),
            username=data.get("username", ""),
            auth_method=data.get("auth_method", "key"),
            key_path=data.get("key_path"),
            password=None,
            docker_port=data.get("docker_port", 2375),
        )


class ServerRepository:
    """Data Access Object for Server CRUD operations."""

    def __init__(self, db: Database | None = None):
        self._db = db or Database.instance()

    def get_all(self) -> list[Server]:
        conn = self._db.connect()
        rows = conn.execute("SELECT * FROM servers ORDER BY name").fetchall()
        return [self._row_to_server(r) for r in rows]

    def get_by_id(self, server_id: int) -> Server | None:
        conn = self._db.connect()
        row = conn.execute(
            "SELECT * FROM servers WHERE id = ?", (server_id,)
        ).fetchone()
        return self._row_to_server(row) if row else None

    def create(self, server: Server) -> Server:
        conn = self._db.connect()
        cursor = conn.execute(
            """INSERT INTO servers
               (name, host, port, username, auth_method, key_path, password, docker_port)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                server.name,
                server.host,
                server.port,
                server.username,
                server.auth_method,
                server.key_path,
                server.password,
                server.docker_port,
            ),
        )
        conn.commit()
        server.id = cursor.lastrowid
        return server

    def update(self, server: Server) -> None:
        conn = self._db.connect()
        conn.execute(
            """UPDATE servers
               SET name=?, host=?, port=?, username=?, auth_method=?,
                   key_path=?, password=?, docker_port=?,
                   updated_at=datetime('now')
               WHERE id=?""",
            (
                server.name,
                server.host,
                server.port,
                server.username,
                server.auth_method,
                server.key_path,
                server.password,
                server.docker_port,
                server.id,
            ),
        )
        conn.commit()

    def delete(self, server_id: int) -> None:
        conn = self._db.connect()
        conn.execute("DELETE FROM servers WHERE id = ?", (server_id,))
        conn.commit()

    def exists(self, name: str, host: str) -> bool:
        """Check if a server with the same name+host already exists."""
        conn = self._db.connect()
        row = conn.execute(
            "SELECT COUNT(*) FROM servers WHERE name = ? AND host = ?",
            (name, host),
        ).fetchone()
        return row[0] > 0

    @staticmethod
    def _row_to_server(row) -> Server:
        return Server(
            id=row["id"],
            name=row["name"],
            host=row["host"],
            port=row["port"],
            username=row["username"],
            auth_method=row["auth_method"],
            key_path=row["key_path"],
            password=row["password"],
            docker_port=row["docker_port"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
