from __future__ import annotations

import logging
import os
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.services.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB


@dataclass
class FileEntry:
    name: str
    path: str
    is_dir: bool
    size: int
    modified: float
    permissions: str

    @property
    def modified_str(self) -> str:
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(self.modified, tz=timezone.utc).astimezone()
        return dt.strftime("%Y-%m-%d %H:%M")

    @property
    def size_human(self) -> str:
        if self.is_dir:
            return ""
        size = self.size
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if abs(size) < 1024:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class FileTransferService:
    def __init__(self, connection_manager: ConnectionManager):
        self._cm = connection_manager

    # ── helpers ──────────────────────────────────────────────

    def _get_sftp(self):
        ssh = self._cm.ssh_client
        if ssh is None:
            raise RuntimeError("No active SSH connection")
        return ssh.open_sftp()

    def _perm_str(self, mode: int) -> str:
        parts = []
        for who in (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR,
                     stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP,
                     stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH):
            parts.append("r" if who in (stat.S_IRUSR, stat.S_IRGRP, stat.S_IROTH) and mode & who else
                         "w" if who in (stat.S_IWUSR, stat.S_IWGRP, stat.S_IWOTH) and mode & who else
                         "x" if who in (stat.S_IXUSR, stat.S_IXGRP, stat.S_IXOTH) and mode & who else
                         "-")
        return "".join(parts)

    # ── listing ─────────────────────────────────────────────

    def list_local_directory(self, path: str) -> list[FileEntry]:
        entries: list[FileEntry] = []
        p = Path(path)
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            try:
                st = item.stat()
                entries.append(FileEntry(
                    name=item.name,
                    path=str(item),
                    is_dir=item.is_dir(),
                    size=st.st_size if not item.is_dir() else 0,
                    modified=st.st_mtime,
                    permissions=self._perm_str(st.st_mode),
                ))
            except PermissionError:
                entries.append(FileEntry(
                    name=item.name,
                    path=str(item),
                    is_dir=item.is_dir(),
                    size=0,
                    modified=0,
                    permissions="---------",
                ))
        return entries

    def list_remote_directory(self, path: str) -> list[FileEntry]:
        sftp = self._get_sftp()
        try:
            entries: list[FileEntry] = []
            for attr in sftp.listdir_attr(path):
                full = str(PurePosixPath(path) / attr.filename)
                is_dir = stat.S_ISDIR(attr.st_mode) if attr.st_mode else False
                entries.append(FileEntry(
                    name=attr.filename,
                    path=full,
                    is_dir=is_dir,
                    size=attr.st_size if attr.st_size and not is_dir else 0,
                    modified=attr.st_mtime if attr.st_mtime else 0,
                    permissions=self._perm_str(attr.st_mode) if attr.st_mode else "---------",
                ))
            entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
            return entries
        finally:
            sftp.close()

    def list_server_directory(self, path: str) -> list[FileEntry]:
        if self._cm.is_local:
            return self.list_local_directory(path)
        return self.list_remote_directory(path)

    # ── home dirs ───────────────────────────────────────────

    def get_local_home(self) -> str:
        return str(Path.home())

    def get_server_home(self) -> str:
        if self._cm.is_local:
            return str(Path.home())
        sftp = self._get_sftp()
        try:
            return sftp.normalize(".")
        finally:
            sftp.close()

    # ── upload (local → server) ─────────────────────────────

    def upload_file(self, local_path: str, remote_path: str,
                    progress_callback=None) -> None:
        if self._cm.is_local:
            self._copy_local(local_path, remote_path, progress_callback)
            return
        sftp = self._get_sftp()
        try:
            sftp.put(local_path, remote_path, callback=progress_callback)
        finally:
            sftp.close()

    def upload_directory(self, local_path: str, remote_path: str,
                         progress_callback=None) -> None:
        if self._cm.is_local:
            self._copy_local_dir(local_path, remote_path, progress_callback)
            return
        sftp = self._get_sftp()
        try:
            self._sftp_mkdir_p(sftp, remote_path)
            for root, dirs, files in os.walk(local_path):
                rel = os.path.relpath(root, local_path)
                remote_root = str(PurePosixPath(remote_path) / rel) if rel != "." else remote_path
                for d in dirs:
                    self._sftp_mkdir_p(sftp, str(PurePosixPath(remote_root) / d))
                for f in files:
                    src = os.path.join(root, f)
                    dst = str(PurePosixPath(remote_root) / f)
                    sftp.put(src, dst, callback=progress_callback)
        finally:
            sftp.close()

    # ── download (server → local) ───────────────────────────

    def download_file(self, remote_path: str, local_path: str,
                      progress_callback=None) -> None:
        if self._cm.is_local:
            self._copy_local(remote_path, local_path, progress_callback)
            return
        sftp = self._get_sftp()
        try:
            sftp.get(remote_path, local_path, callback=progress_callback)
        finally:
            sftp.close()

    def download_directory(self, remote_path: str, local_path: str,
                           progress_callback=None) -> None:
        if self._cm.is_local:
            self._copy_local_dir(remote_path, local_path, progress_callback)
            return
        sftp = self._get_sftp()
        try:
            self._sftp_download_dir(sftp, remote_path, local_path, progress_callback)
        finally:
            sftp.close()

    # ── server-side ops ─────────────────────────────────────

    def create_server_directory(self, path: str) -> None:
        if self._cm.is_local:
            Path(path).mkdir(parents=True, exist_ok=True)
            return
        sftp = self._get_sftp()
        try:
            self._sftp_mkdir_p(sftp, path)
        finally:
            sftp.close()

    def delete_server_path(self, path: str) -> None:
        if self._cm.is_local:
            self.delete_local_path(path)
            return
        sftp = self._get_sftp()
        try:
            self._sftp_rm_recursive(sftp, path)
        finally:
            sftp.close()

    def rename_server_path(self, old_path: str, new_path: str) -> None:
        if self._cm.is_local:
            self.rename_local_path(old_path, new_path)
            return
        sftp = self._get_sftp()
        try:
            sftp.rename(old_path, new_path)
        finally:
            sftp.close()

    # ── local-side ops ──────────────────────────────────────

    def create_local_directory(self, path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    def delete_local_path(self, path: str) -> None:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()

    def rename_local_path(self, old_path: str, new_path: str) -> None:
        Path(old_path).rename(new_path)

    # ── private helpers ─────────────────────────────────────

    def _copy_local(self, src: str, dst: str, callback=None) -> None:
        total = os.path.getsize(src)
        copied = 0
        with open(src, "rb") as fin, open(dst, "wb") as fout:
            while True:
                chunk = fin.read(CHUNK_SIZE)
                if not chunk:
                    break
                fout.write(chunk)
                copied += len(chunk)
                if callback:
                    callback(copied, total)

    def _copy_local_dir(self, src: str, dst: str, callback=None) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        dst_path.mkdir(parents=True, exist_ok=True)
        for root, dirs, files in os.walk(src):
            rel = os.path.relpath(root, src)
            dest_root = dst_path / rel if rel != "." else dst_path
            for d in dirs:
                (dest_root / d).mkdir(parents=True, exist_ok=True)
            for f in files:
                s = os.path.join(root, f)
                d = str(dest_root / f)
                self._copy_local(s, d, callback)

    def _sftp_mkdir_p(self, sftp, remote_path: str) -> None:
        parts = PurePosixPath(remote_path).parts
        current = ""
        for part in parts:
            current = current + "/" + part if current else part
            if current == "/":
                current = "/"
                continue
            if not current.startswith("/"):
                current = "/" + current
            try:
                sftp.stat(current)
            except FileNotFoundError:
                sftp.mkdir(current)

    def _sftp_rm_recursive(self, sftp, path: str) -> None:
        try:
            st = sftp.stat(path)
        except FileNotFoundError:
            return
        if stat.S_ISDIR(st.st_mode):
            for attr in sftp.listdir_attr(path):
                child = str(PurePosixPath(path) / attr.filename)
                if stat.S_ISDIR(attr.st_mode) if attr.st_mode else False:
                    self._sftp_rm_recursive(sftp, child)
                else:
                    sftp.remove(child)
            sftp.rmdir(path)
        else:
            sftp.remove(path)

    def _sftp_download_dir(self, sftp, remote_path: str, local_path: str,
                           callback=None) -> None:
        Path(local_path).mkdir(parents=True, exist_ok=True)
        for attr in sftp.listdir_attr(remote_path):
            remote_child = str(PurePosixPath(remote_path) / attr.filename)
            local_child = os.path.join(local_path, attr.filename)
            if stat.S_ISDIR(attr.st_mode) if attr.st_mode else False:
                self._sftp_download_dir(sftp, remote_child, local_child, callback)
            else:
                sftp.get(remote_child, local_child, callback=callback)
