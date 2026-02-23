from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum, auto

from PyQt6.QtCore import QThread, pyqtSignal

from app.services.file_transfer_service import FileTransferService


class TransferDirection(Enum):
    UPLOAD = auto()
    DOWNLOAD = auto()


@dataclass
class TransferRequest:
    source_path: str
    dest_path: str
    is_directory: bool
    direction: TransferDirection


class FileTransferWorker(QThread):
    """QThread for file transfers with continuous progress signals."""

    # file_name, bytes_done, bytes_total, files_done, files_total
    progress = pyqtSignal(str, int, int, int, int)
    # request, error_message (empty string = success)
    transfer_finished = pyqtSignal(object, str)

    def __init__(self, service: FileTransferService, request: TransferRequest,
                 parent=None):
        super().__init__(parent)
        self._service = service
        self._request = request
        self._cancelled = False
        self._files_done = 0
        self._files_total = 0
        self._current_file = ""

    def run(self) -> None:
        req = self._request
        try:
            if req.is_directory:
                self._files_total = self._count_files(req.source_path, req.direction)
            else:
                self._files_total = 1

            if req.direction == TransferDirection.UPLOAD:
                if req.is_directory:
                    self._upload_directory(req.source_path, req.dest_path)
                else:
                    self._current_file = os.path.basename(req.source_path)
                    self._service.upload_file(
                        req.source_path, req.dest_path,
                        progress_callback=self._on_progress,
                    )
                    self._files_done = 1
                    self.progress.emit(self._current_file, 1, 1,
                                       self._files_done, self._files_total)
            else:
                if req.is_directory:
                    self._download_directory(req.source_path, req.dest_path)
                else:
                    self._current_file = os.path.basename(req.source_path)
                    self._service.download_file(
                        req.source_path, req.dest_path,
                        progress_callback=self._on_progress,
                    )
                    self._files_done = 1
                    self.progress.emit(self._current_file, 1, 1,
                                       self._files_done, self._files_total)

            if self._cancelled:
                self.transfer_finished.emit(req, "Transfer cancelled")
            else:
                self.transfer_finished.emit(req, "")
        except Exception as e:
            self.transfer_finished.emit(req, str(e))

    def cancel(self) -> None:
        self._cancelled = True

    def _on_progress(self, bytes_done: int, bytes_total: int) -> None:
        if self._cancelled:
            raise InterruptedError("Transfer cancelled")
        self.progress.emit(self._current_file, bytes_done, bytes_total,
                           self._files_done, self._files_total)

    def _count_files(self, path: str, direction: TransferDirection) -> int:
        count = 0
        if direction == TransferDirection.UPLOAD:
            for _root, _dirs, files in os.walk(path):
                count += len(files)
        else:
            # For remote directories we can't easily walk, estimate 1
            if self._service._cm.is_local:
                for _root, _dirs, files in os.walk(path):
                    count += len(files)
            else:
                count = 1
        return max(count, 1)

    def _upload_directory(self, local_path: str, remote_path: str) -> None:
        from pathlib import PurePosixPath

        self._service.create_server_directory(remote_path)
        for root, dirs, files in os.walk(local_path):
            if self._cancelled:
                return
            rel = os.path.relpath(root, local_path)
            if self._service._cm.is_local:
                from pathlib import Path
                remote_root = str(Path(remote_path) / rel) if rel != "." else remote_path
            else:
                remote_root = str(PurePosixPath(remote_path) / rel) if rel != "." else remote_path
            for d in dirs:
                if self._service._cm.is_local:
                    from pathlib import Path
                    self._service.create_server_directory(str(Path(remote_root) / d))
                else:
                    self._service.create_server_directory(
                        str(PurePosixPath(remote_root) / d)
                    )
            for f in files:
                if self._cancelled:
                    return
                self._current_file = f
                src = os.path.join(root, f)
                if self._service._cm.is_local:
                    from pathlib import Path
                    dst = str(Path(remote_root) / f)
                else:
                    dst = str(PurePosixPath(remote_root) / f)
                self._service.upload_file(src, dst, progress_callback=self._on_progress)
                self._files_done += 1
                self.progress.emit(f, 1, 1, self._files_done, self._files_total)

    def _download_directory(self, remote_path: str, local_path: str) -> None:
        if self._service._cm.is_local:
            self._download_local_dir(remote_path, local_path)
        else:
            self._download_remote_dir(remote_path, local_path)

    def _download_local_dir(self, src: str, dst: str) -> None:
        from pathlib import Path
        Path(dst).mkdir(parents=True, exist_ok=True)
        for root, dirs, files in os.walk(src):
            if self._cancelled:
                return
            rel = os.path.relpath(root, src)
            dst_root = os.path.join(dst, rel) if rel != "." else dst
            for d in dirs:
                os.makedirs(os.path.join(dst_root, d), exist_ok=True)
            for f in files:
                if self._cancelled:
                    return
                self._current_file = f
                s = os.path.join(root, f)
                d = os.path.join(dst_root, f)
                self._service.download_file(s, d, progress_callback=self._on_progress)
                self._files_done += 1
                self.progress.emit(f, 1, 1, self._files_done, self._files_total)

    def _download_remote_dir(self, remote_path: str, local_path: str) -> None:
        from pathlib import Path, PurePosixPath
        import stat as stat_mod

        Path(local_path).mkdir(parents=True, exist_ok=True)
        sftp = self._service._get_sftp()
        try:
            self._sftp_walk_download(sftp, remote_path, local_path)
        finally:
            sftp.close()

    def _sftp_walk_download(self, sftp, remote_path: str, local_path: str) -> None:
        import stat as stat_mod
        from pathlib import PurePosixPath

        os.makedirs(local_path, exist_ok=True)
        for attr in sftp.listdir_attr(remote_path):
            if self._cancelled:
                return
            remote_child = str(PurePosixPath(remote_path) / attr.filename)
            local_child = os.path.join(local_path, attr.filename)
            is_dir = stat_mod.S_ISDIR(attr.st_mode) if attr.st_mode else False
            if is_dir:
                self._sftp_walk_download(sftp, remote_child, local_child)
            else:
                self._current_file = attr.filename
                sftp.get(remote_child, local_child, callback=self._on_progress)
                self._files_done += 1
                self.progress.emit(attr.filename, 1, 1,
                                   self._files_done, self._files_total)
