from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from app.constants import APP_NAME, DATA_DIR, DB_PATH
from app.models.database import Database
from app.models.server import Server, ServerRepository


class SettingsController(QObject):
    """Business logic for the Settings page."""

    settings_changed = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._db = Database.instance()
        self._repo = ServerRepository()

    # ── Settings CRUD ─────────────────────────────────────────

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        return self._db.get_setting(key, default)

    def set_setting(self, key: str, value: str) -> None:
        self._db.set_setting(key, value)
        self.settings_changed.emit()

    def get_all_settings(self) -> dict[str, str]:
        return self._db.get_all_settings()

    # ── Export ────────────────────────────────────────────────

    def export_servers(self, server_ids: list[int] | None = None) -> dict:
        """Build export dict. If server_ids is None, export all."""
        servers = self._repo.get_all()
        if server_ids is not None:
            servers = [s for s in servers if s.id in server_ids]
        return {
            "app": APP_NAME,
            "version": "1",
            "servers": [s.to_export_dict() for s in servers],
        }

    def export_to_file(self, path: str, server_ids: list[int] | None = None) -> int:
        """Export servers to JSON file. Returns count exported."""
        data = self.export_servers(server_ids)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return len(data["servers"])

    # ── Import ────────────────────────────────────────────────

    def import_from_file(self, path: str) -> tuple[int, int]:
        """Import servers from JSON. Returns (imported_count, skipped_count)."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        server_list = data.get("servers", [])
        imported = 0
        skipped = 0
        for entry in server_list:
            name = entry.get("name", "")
            host = entry.get("host", "")
            if not name or not host:
                skipped += 1
                continue
            if self._repo.exists(name, host):
                skipped += 1
                continue
            server = Server.from_import_dict(entry)
            self._repo.create(server)
            imported += 1
        return imported, skipped

    # ── Reset ─────────────────────────────────────────────────

    def reset_database(self) -> None:
        """Close DB and delete the file. Caller must restart the app."""
        self._db.close()
        Database.delete_database()

    # ── Desktop file (.desktop) ───────────────────────────────

    @staticmethod
    def get_appimage_path() -> str | None:
        """Try to detect the running AppImage path from environment."""
        return os.environ.get("APPIMAGE")

    @staticmethod
    def desktop_file_path() -> Path:
        return (
            Path.home()
            / ".local"
            / "share"
            / "applications"
            / f"{APP_NAME.lower()}.desktop"
        )

    def create_desktop_file(self, appimage_path: str) -> None:
        """Write a .desktop file for the app."""
        desktop_content = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Docker and Server Management GUI\n"
            f"Exec={appimage_path}\n"
            "Terminal=false\n"
            "Categories=Development;System;Utility;\n"
            "Keywords=docker;server;ssh;containers;\n"
            f"StartupWMClass={APP_NAME.lower()}\n"
        )
        desktop_path = self.desktop_file_path()
        desktop_path.parent.mkdir(parents=True, exist_ok=True)
        desktop_path.write_text(desktop_content)
        os.chmod(str(desktop_path), 0o755)

    def remove_desktop_file(self) -> bool:
        """Remove the .desktop file. Returns True if removed."""
        path = self.desktop_file_path()
        if path.exists():
            path.unlink()
            return True
        return False

    def desktop_file_exists(self) -> bool:
        return self.desktop_file_path().exists()

    # ── Info ──────────────────────────────────────────────────

    @staticmethod
    def data_dir() -> str:
        return str(DATA_DIR)

    @staticmethod
    def db_path() -> str:
        return str(DB_PATH)
