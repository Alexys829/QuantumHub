from __future__ import annotations

import os
from pathlib import PurePosixPath

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.services.file_transfer_service import FileTransferService
from app.workers.docker_worker import DockerWorker
from app.workers.file_transfer_worker import (
    FileTransferWorker,
    TransferDirection,
    TransferRequest,
)


class FileTransferController(QObject):
    # Listing signals
    local_directory_listed = pyqtSignal(list)
    server_directory_listed = pyqtSignal(list)

    # Transfer signals
    transfer_started = pyqtSignal(str)
    transfer_progress = pyqtSignal(str, int, int, int, int)
    transfer_complete = pyqtSignal(str)
    transfer_error = pyqtSignal(str)

    # File operation signals
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, service: FileTransferService, parent=None):
        super().__init__(parent)
        self._service = service
        self._pool = QThreadPool.globalInstance()
        self._worker: FileTransferWorker | None = None

    # ── listing ─────────────────────────────────────────────

    def refresh_local_directory(self, path: str) -> None:
        def _fetch():
            return self._service.list_local_directory(path)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.local_directory_listed.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_server_directory(self, path: str) -> None:
        def _fetch():
            return self._service.list_server_directory(path)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.server_directory_listed.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def get_local_home(self) -> str:
        return self._service.get_local_home()

    def get_server_home(self) -> str:
        return self._service.get_server_home()

    # ── transfer ────────────────────────────────────────────

    def upload(self, local_path: str, server_dir: str, is_dir: bool) -> None:
        if self._worker and self._worker.isRunning():
            self.transfer_error.emit("A transfer is already in progress")
            return

        name = os.path.basename(local_path)
        if self._service._cm.is_local:
            dest = os.path.join(server_dir, name)
        else:
            dest = str(PurePosixPath(server_dir) / name)

        req = TransferRequest(
            source_path=local_path,
            dest_path=dest,
            is_directory=is_dir,
            direction=TransferDirection.UPLOAD,
        )
        self._start_transfer(req)

    def download(self, server_path: str, local_dir: str, is_dir: bool) -> None:
        if self._worker and self._worker.isRunning():
            self.transfer_error.emit("A transfer is already in progress")
            return

        name = os.path.basename(server_path)
        dest = os.path.join(local_dir, name)

        req = TransferRequest(
            source_path=server_path,
            dest_path=dest,
            is_directory=is_dir,
            direction=TransferDirection.DOWNLOAD,
        )
        self._start_transfer(req)

    def cancel_transfer(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()

    def _start_transfer(self, req: TransferRequest) -> None:
        direction = "Uploading" if req.direction == TransferDirection.UPLOAD else "Downloading"
        name = os.path.basename(req.source_path)
        self.transfer_started.emit(f"{direction} {name}...")

        self._worker = FileTransferWorker(self._service, req, parent=self)
        self._worker.progress.connect(self.transfer_progress.emit)
        self._worker.transfer_finished.connect(self._on_transfer_finished)
        self._worker.start()

    def _on_transfer_finished(self, req: TransferRequest, error: str) -> None:
        self._worker = None
        if error:
            self.transfer_error.emit(error)
        else:
            name = os.path.basename(req.source_path)
            self.transfer_complete.emit(f"Transfer complete: {name}")

    # ── file operations ─────────────────────────────────────

    def create_directory_local(self, path: str) -> None:
        def _op():
            self._service.create_local_directory(path)
            return f"Created: {os.path.basename(path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def create_directory_server(self, path: str) -> None:
        def _op():
            self._service.create_server_directory(path)
            return f"Created: {os.path.basename(path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def delete_local(self, path: str) -> None:
        def _op():
            self._service.delete_local_path(path)
            return f"Deleted: {os.path.basename(path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def delete_server(self, path: str) -> None:
        def _op():
            self._service.delete_server_path(path)
            return f"Deleted: {os.path.basename(path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def rename_local(self, old_path: str, new_path: str) -> None:
        def _op():
            self._service.rename_local_path(old_path, new_path)
            return f"Renamed to: {os.path.basename(new_path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def rename_server(self, old_path: str, new_path: str) -> None:
        def _op():
            self._service.rename_server_path(old_path, new_path)
            return f"Renamed to: {os.path.basename(new_path)}"

        worker = DockerWorker(fn=_op)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)
