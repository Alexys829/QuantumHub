from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QRunnable, QThread, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    """Signals emitted by DockerWorker."""

    started = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)
    result = pyqtSignal(object)


class DockerWorker(QRunnable):
    """Generic worker that runs a callable in QThreadPool.

    Usage:
        worker = DockerWorker(fn=some_blocking_function, arg1, kwarg1=val)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        QThreadPool.globalInstance().start(worker)
    """

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self) -> None:
        self.signals.started.emit()
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class LogStreamWorker(QThread):
    """Dedicated QThread for streaming container logs."""

    new_line = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, docker_service, container_id: str, tail: int = 100, parent=None):
        super().__init__(parent)
        self._docker_service = docker_service
        self._container_id = container_id
        self._tail = tail
        self._running = True

    def run(self) -> None:
        try:
            log_stream = self._docker_service.container_logs(
                self._container_id, tail=self._tail, stream=True
            )
            for chunk in log_stream:
                if not self._running:
                    break
                line = chunk.decode("utf-8", errors="replace").rstrip()
                if line:
                    self.new_line.emit(line)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self) -> None:
        self._running = False


class StatsWorker(QThread):
    """Streams container stats (CPU, memory) continuously."""

    stats_update = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, docker_service, container_id: str, parent=None):
        super().__init__(parent)
        self._docker_service = docker_service
        self._container_id = container_id
        self._running = True

    def run(self) -> None:
        try:
            stats_stream = self._docker_service.container_stats(
                self._container_id, stream=True
            )
            for stats in stats_stream:
                if not self._running:
                    break
                self.stats_update.emit(stats)
        except Exception as e:
            self.error.emit(str(e))

    def stop(self) -> None:
        self._running = False


class ExecWorker(QThread):
    """Runs a command inside a container and emits output."""

    output_received = pyqtSignal(str)
    error = pyqtSignal(str)
    finished_signal = pyqtSignal(int)  # exit code

    def __init__(self, docker_service, container_id: str, command: str, parent=None):
        super().__init__(parent)
        self._docker_service = docker_service
        self._container_id = container_id
        self._command = command

    def run(self) -> None:
        try:
            exit_code, output = self._docker_service.exec_run(
                self._container_id, self._command
            )
            if output:
                self.output_received.emit(output)
            self.finished_signal.emit(exit_code)
        except Exception as e:
            self.error.emit(str(e))


class BuildWorker(QThread):
    """Streams Docker image build output."""

    build_log = pyqtSignal(str)
    error = pyqtSignal(str)
    build_finished = pyqtSignal(str)  # image id or message

    def __init__(self, docker_service, path: str, tag: str, parent=None):
        super().__init__(parent)
        self._docker_service = docker_service
        self._path = path
        self._tag = tag

    def run(self) -> None:
        try:
            import json
            client = self._docker_service.client
            response = client.api.build(
                path=self._path, tag=self._tag, rm=True, decode=True
            )
            for chunk in response:
                if "stream" in chunk:
                    self.build_log.emit(chunk["stream"].rstrip())
                elif "error" in chunk:
                    self.error.emit(chunk["error"])
                    return
            self.build_finished.emit(f"Image '{self._tag}' built successfully.")
        except Exception as e:
            self.error.emit(str(e))
