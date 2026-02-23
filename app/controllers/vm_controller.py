from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal

from app.workers.docker_worker import DockerWorker

if TYPE_CHECKING:
    from app.services.vm_service import VmService


class VmController(QObject):
    """Controller for libvirt/KVM/QEMU virtual-machine management."""

    vms_loaded = pyqtSignal(list)
    vm_details_loaded = pyqtSignal(dict)       # {disks, interfaces, memory}
    snapshots_loaded = pyqtSignal(list)
    operation_success = pyqtSignal(str)
    operation_error = pyqtSignal(str)

    def __init__(self, vm_service: VmService, parent=None):
        super().__init__(parent)
        self._svc = vm_service
        self._pool = QThreadPool.globalInstance()
        self._busy = False

    # ── Refresh ──────────────────────────────────────────────

    def refresh_vms(self) -> None:
        if self._busy:
            return
        self._busy = True

        def _fetch():
            return self._svc.get_vms()

        worker = DockerWorker(fn=_fetch)

        def _done():
            self._busy = False

        worker.signals.result.connect(self.vms_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(_done)
        self._pool.start(worker)

    def refresh_vm_details(self, name: str) -> None:
        def _fetch():
            disks = self._svc.get_vm_disks(name)
            interfaces = self._svc.get_vm_interfaces(name)
            memory = self._svc.get_vm_memory_stats(name)
            addresses = self._svc.get_vm_addresses(name)
            return {
                "disks": disks,
                "interfaces": interfaces,
                "memory": memory,
                "addresses": addresses,
            }

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.vm_details_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    def refresh_snapshots(self, name: str) -> None:
        def _fetch():
            return self._svc.get_snapshots(name)

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self.snapshots_loaded.emit)
        worker.signals.error.connect(self.operation_error.emit)
        self._pool.start(worker)

    # ── Lifecycle actions ────────────────────────────────────

    def _run_action(self, fn, success_msg: str) -> None:
        def _act():
            output, rc = fn()
            if rc != 0:
                raise RuntimeError(output or success_msg.replace("succeeded", "failed"))
            return success_msg

        worker = DockerWorker(fn=_act)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_vms)
        self._pool.start(worker)

    def start_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_start(name), f"Start {name} succeeded"
        )

    def shutdown_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_shutdown(name), f"Shutdown {name} succeeded"
        )

    def destroy_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_destroy(name), f"Force off {name} succeeded"
        )

    def reboot_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_reboot(name), f"Reboot {name} succeeded"
        )

    def suspend_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_suspend(name), f"Suspend {name} succeeded"
        )

    def resume_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_resume(name), f"Resume {name} succeeded"
        )

    def delete_vm(self, name: str) -> None:
        self._run_action(
            lambda: self._svc.vm_undefine(name), f"Delete {name} succeeded"
        )

    def set_autostart(self, name: str, enable: bool) -> None:
        label = "enable" if enable else "disable"
        self._run_action(
            lambda: self._svc.vm_set_autostart(name, enable),
            f"Autostart {label} for {name} succeeded",
        )

    # ── Snapshot actions ─────────────────────────────────────

    def create_snapshot(self, vm_name: str, snap_name: str) -> None:
        def _act():
            output, rc = self._svc.create_snapshot(vm_name, snap_name)
            if rc != 0:
                raise RuntimeError(output or f"Failed to create snapshot {snap_name}")
            return f"Snapshot {snap_name} created"

        worker = DockerWorker(fn=_act)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: self.refresh_snapshots(vm_name))
        self._pool.start(worker)

    def revert_snapshot(self, vm_name: str, snap_name: str) -> None:
        def _act():
            output, rc = self._svc.revert_snapshot(vm_name, snap_name)
            if rc != 0:
                raise RuntimeError(output or f"Failed to revert to {snap_name}")
            return f"Reverted to snapshot {snap_name}"

        worker = DockerWorker(fn=_act)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(self.refresh_vms)
        self._pool.start(worker)

    def delete_snapshot(self, vm_name: str, snap_name: str) -> None:
        def _act():
            output, rc = self._svc.delete_snapshot(vm_name, snap_name)
            if rc != 0:
                raise RuntimeError(output or f"Failed to delete snapshot {snap_name}")
            return f"Snapshot {snap_name} deleted"

        worker = DockerWorker(fn=_act)
        worker.signals.result.connect(self.operation_success.emit)
        worker.signals.error.connect(self.operation_error.emit)
        worker.signals.finished.connect(lambda: self.refresh_snapshots(vm_name))
        self._pool.start(worker)

    # ── Export / Import / Clone ───────────────────────────────

    def export_vm(self, name: str, output_dir: str) -> None:
        self._run_action(
            lambda: self._svc.export_vm(name, output_dir),
            f"Export {name} succeeded",
        )

    def import_vm(self, xml_path: str) -> None:
        self._run_action(
            lambda: self._svc.import_vm(xml_path),
            f"Import from {xml_path} succeeded",
        )

    def clone_vm(self, name: str, new_name: str) -> None:
        self._run_action(
            lambda: self._svc.clone_vm(name, new_name),
            f"Clone {name} -> {new_name} succeeded",
        )
