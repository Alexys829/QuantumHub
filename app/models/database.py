from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

from app.constants import DB_PATH, DATA_DIR


class Database:
    """Singleton SQLite connection manager with schema migration."""

    _instance: Database | None = None

    def __init__(self, db_path: Path = DB_PATH):
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None

    @classmethod
    def instance(cls) -> Database:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def connect(self) -> sqlite3.Connection:
        if self._connection is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            # One-time migration from old path
            old_db = Path(os.path.expanduser("~/.local/share/dockergui/servers.db"))
            if old_db.exists() and not self._db_path.exists():
                shutil.copy2(str(old_db), str(self._db_path))
            self._connection = sqlite3.connect(str(self._db_path))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._migrate()
        return self._connection

    def close(self) -> None:
        if self._connection:
            self._connection.close()
            self._connection = None

    @staticmethod
    def delete_database() -> None:
        """Delete the database file. Caller must restart the app."""
        if DB_PATH.exists():
            os.remove(DB_PATH)

    def _migrate(self) -> None:
        conn = self._connection
        conn.execute("""
            CREATE TABLE IF NOT EXISTS servers (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT    NOT NULL,
                host        TEXT    NOT NULL,
                port        INTEGER NOT NULL DEFAULT 22,
                username    TEXT    NOT NULL,
                auth_method TEXT    NOT NULL DEFAULT 'key',
                key_path    TEXT,
                password    TEXT,
                docker_port INTEGER NOT NULL DEFAULT 2375,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS command_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id  INTEGER,
                command    TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (server_id) REFERENCES servers(id) ON DELETE CASCADE
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS quick_commands (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                label   TEXT NOT NULL,
                command TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.commit()
        self._seed_quick_commands()
        self._seed_default_settings()

    def _seed_quick_commands(self) -> None:
        """Populate default quick commands if the table is empty."""
        conn = self._connection
        count = conn.execute("SELECT COUNT(*) FROM quick_commands").fetchone()[0]
        if count == 0:
            defaults = [
                ("ip addr", "ip addr"),
                ("apt update", "sudo apt update"),
                ("apt upgrade", "sudo apt upgrade"),
            ]
            conn.executemany(
                "INSERT INTO quick_commands (label, command) VALUES (?, ?)",
                defaults,
            )
            conn.commit()

    def _seed_default_settings(self) -> None:
        """Populate default settings if the table is empty."""
        conn = self._connection
        count = conn.execute("SELECT COUNT(*) FROM settings").fetchone()[0]
        if count == 0:
            defaults = {
                "theme": "dark",
                "poll_multiplier": "1.0",
                "default_ssh_auth": "key",
                "terminal_font_size": "12",
                "confirm_before_kill": "True",
                "auto_connect_last_server": "False",
                "last_connected_server_id": "",
            }
            conn.executemany(
                "INSERT INTO settings (key, value) VALUES (?, ?)",
                list(defaults.items()),
            )
            conn.commit()

    # ── Settings ──────────────────────────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        conn = self.connect()
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()

    def get_all_settings(self) -> dict[str, str]:
        conn = self.connect()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    # ── Command History ──────────────────────────────────────

    def add_history(self, server_id: int | None, command: str) -> None:
        conn = self.connect()
        conn.execute(
            "INSERT INTO command_history (server_id, command) VALUES (?, ?)",
            (server_id, command),
        )
        conn.commit()

    def get_history(self, server_id: int | None, limit: int = 500) -> list[str]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT command FROM command_history "
            "WHERE server_id IS ? ORDER BY id ASC LIMIT ?",
            (server_id, limit),
        ).fetchall()
        return [r["command"] for r in rows]

    # ── Quick Commands ───────────────────────────────────────

    def get_quick_commands(self) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT id, label, command FROM quick_commands ORDER BY id"
        ).fetchall()
        return [{"id": r["id"], "label": r["label"], "command": r["command"]} for r in rows]

    def add_quick_command(self, label: str, command: str) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO quick_commands (label, command) VALUES (?, ?)",
            (label, command),
        )
        conn.commit()
        return cur.lastrowid

    def update_quick_command(self, cmd_id: int, label: str, command: str) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE quick_commands SET label=?, command=? WHERE id=?",
            (label, command, cmd_id),
        )
        conn.commit()

    def delete_quick_command(self, cmd_id: int) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM quick_commands WHERE id = ?", (cmd_id,))
        conn.commit()
