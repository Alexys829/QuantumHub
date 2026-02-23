from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.server_controller import ServerController
from app.controllers.vm_controller import VmController
from app.models.server import Server
from app.views.server_dialog import ServerDialog
from app.views.toast import show_toast

# VM state colors
_STATE_COLORS = {
    "running": QColor("#2ea043"),
    "paused": QColor("#d29922"),
    "shut off": QColor("#8b949e"),
    "crashed": QColor("#f85149"),
    "pmsuspended": QColor("#d29922"),
    "idle": QColor("#58a6ff"),
    "in shutdown": QColor("#d29922"),
}


def _make_table(columns: list[str]) -> QTableWidget:
    """Create a consistently-styled QTableWidget."""
    table = QTableWidget()
    table.setColumnCount(len(columns))
    table.setHorizontalHeaderLabels(columns)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setStretchLastSection(True)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents
    )
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    return table


class VmView(QWidget):
    """Virtual-machine management view: table + details + snapshots."""

    COLUMNS = ["Name", "State", "IP", "vCPUs", "Memory", "Autostart", "ID"]

    def __init__(self, controller: VmController, server_controller: ServerController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._server_ctrl = server_controller
        self._selected_vm: str | None = None
        self._init_ui()
        self._connect_signals()

    # ── UI setup ─────────────────────────────────────────────

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header = QLabel("\U0001F5A5  Virtual Machines")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._start_btn = QPushButton("\u25B6  Start")
        self._shutdown_btn = QPushButton("\u23F9  Shutdown")
        self._forceoff_btn = QPushButton("\U0001F480  Force Off")
        self._reboot_btn = QPushButton("\U0001F504  Reboot")
        self._suspend_btn = QPushButton("\u23F8  Suspend")
        self._resume_btn = QPushButton("\u25B6  Resume")
        self._autostart_btn = QPushButton("\u2699  Autostart")
        self._delete_btn = QPushButton("\U0001F5D1  Delete")
        self._export_btn = QPushButton("\U0001F4E4  Export")
        self._import_btn = QPushButton("\U0001F4E5  Import")
        self._clone_btn = QPushButton("\U0001F4CB  Clone")
        self._refresh_btn = QPushButton("\U0001F504  Refresh")

        for btn in (
            self._start_btn,
            self._shutdown_btn,
            self._forceoff_btn,
            self._reboot_btn,
            self._suspend_btn,
            self._resume_btn,
            self._autostart_btn,
            self._delete_btn,
            self._export_btn,
            self._import_btn,
            self._clone_btn,
        ):
            toolbar.addWidget(btn)
        toolbar.addStretch()
        toolbar.addWidget(self._refresh_btn)
        layout.addLayout(toolbar)

        # Splitter: VM table on top, details+snapshots on bottom
        splitter = QSplitter(Qt.Orientation.Vertical)

        # ── VM table ──
        self._table = _make_table(self.COLUMNS)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._show_context_menu)
        self._table.currentCellChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._table)

        # ── Bottom panel: details + snapshots ──
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(8)

        # Details section
        self._details_header = QLabel("Details")
        self._details_header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0;"
        )
        bottom_layout.addWidget(self._details_header)

        details_row = QHBoxLayout()
        details_row.setSpacing(8)

        # Disks mini-table
        disks_frame = self._make_detail_frame("Disks")
        self._disks_table = _make_table(["Target", "Source", "Type", "Device"])
        disks_frame.layout().addWidget(self._disks_table)
        details_row.addWidget(disks_frame)

        # Interfaces mini-table
        ifaces_frame = self._make_detail_frame("Interfaces")
        self._ifaces_table = _make_table(
            ["Interface", "Type", "Source", "Model", "MAC"]
        )
        ifaces_frame.layout().addWidget(self._ifaces_table)
        details_row.addWidget(ifaces_frame)

        # IP Addresses mini-table
        addr_frame = self._make_detail_frame("IP Addresses")
        self._addr_table = _make_table(["Interface", "Protocol", "Address"])
        addr_frame.layout().addWidget(self._addr_table)
        details_row.addWidget(addr_frame)

        # Memory stats mini-table
        mem_frame = self._make_detail_frame("Memory")
        self._mem_table = _make_table(["Stat", "Value"])
        mem_frame.layout().addWidget(self._mem_table)
        details_row.addWidget(mem_frame)

        bottom_layout.addLayout(details_row)

        # Snapshots section
        snap_header_row = QHBoxLayout()
        self._snap_header = QLabel("Snapshots")
        self._snap_header.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e0e0e0;"
        )
        snap_header_row.addWidget(self._snap_header)
        snap_header_row.addStretch()

        self._snap_create_btn = QPushButton("\u2795  Create")
        self._snap_revert_btn = QPushButton("\U0001F504  Revert")
        self._snap_delete_btn = QPushButton("\U0001F5D1  Delete")
        for btn in (self._snap_create_btn, self._snap_revert_btn, self._snap_delete_btn):
            snap_header_row.addWidget(btn)
        bottom_layout.addLayout(snap_header_row)

        self._snap_table = _make_table(["Name", "Date", "State", "Parent"])
        bottom_layout.addWidget(self._snap_table)

        splitter.addWidget(bottom)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)

    @staticmethod
    def _make_detail_frame(title: str) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "QFrame { border: 1px solid #333333; border-radius: 4px; }"
        )
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(6, 4, 6, 4)
        vbox.setSpacing(4)
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: bold; color: #bbbbbb; border: none;")
        vbox.addWidget(lbl)
        return frame

    # ── Signal wiring ────────────────────────────────────────

    def _connect_signals(self) -> None:
        # Controller → view
        self._ctrl.vms_loaded.connect(self._populate_table)
        self._ctrl.vm_details_loaded.connect(self._populate_details)
        self._ctrl.snapshots_loaded.connect(self._populate_snapshots)
        self._ctrl.operation_success.connect(
            lambda msg: show_toast(self.window(), msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

        # Toolbar buttons
        self._start_btn.clicked.connect(self._on_start)
        self._shutdown_btn.clicked.connect(self._on_shutdown)
        self._forceoff_btn.clicked.connect(self._on_force_off)
        self._reboot_btn.clicked.connect(self._on_reboot)
        self._suspend_btn.clicked.connect(self._on_suspend)
        self._resume_btn.clicked.connect(self._on_resume)
        self._autostart_btn.clicked.connect(self._on_autostart)
        self._delete_btn.clicked.connect(self._on_delete)
        self._export_btn.clicked.connect(self._on_export)
        self._import_btn.clicked.connect(self._on_import)
        self._clone_btn.clicked.connect(self._on_clone)
        self._refresh_btn.clicked.connect(self._ctrl.refresh_vms)

        # Snapshot buttons
        self._snap_create_btn.clicked.connect(self._on_snap_create)
        self._snap_revert_btn.clicked.connect(self._on_snap_revert)
        self._snap_delete_btn.clicked.connect(self._on_snap_delete)

    # ── Table population ─────────────────────────────────────

    def _populate_table(self, vms: list[dict]) -> None:
        self._table.setUpdatesEnabled(False)
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(vms))
        for row, vm in enumerate(vms):
            self._table.setItem(row, 0, QTableWidgetItem(vm["name"]))

            state = vm["state"]
            state_item = QTableWidgetItem(f"  {state}")
            color = _STATE_COLORS.get(state, QColor("#8b949e"))
            state_item.setForeground(color)
            self._table.setItem(row, 1, state_item)

            self._table.setItem(row, 2, QTableWidgetItem(vm.get("ip", "-")))

            self._table.setItem(row, 3, QTableWidgetItem(str(vm["vcpus"])))

            mem = vm["memory_mib"]
            if mem >= 1024:
                mem_str = f"{mem / 1024:.1f} GiB"
            else:
                mem_str = f"{mem} MiB"
            self._table.setItem(row, 4, QTableWidgetItem(mem_str))

            self._table.setItem(row, 5, QTableWidgetItem(vm["autostart"]))

            vm_id = vm["id"]
            self._table.setItem(row, 6, QTableWidgetItem(str(vm_id)))

        self._table.setSortingEnabled(True)
        self._table.setUpdatesEnabled(True)

    def _populate_details(self, details: dict) -> None:
        # Disks
        disks = details.get("disks", [])
        self._disks_table.setRowCount(len(disks))
        for row, d in enumerate(disks):
            self._disks_table.setItem(row, 0, QTableWidgetItem(d.get("target", "")))
            self._disks_table.setItem(row, 1, QTableWidgetItem(d.get("source", "")))
            self._disks_table.setItem(row, 2, QTableWidgetItem(d.get("type", "")))
            self._disks_table.setItem(row, 3, QTableWidgetItem(d.get("device", "")))

        # Interfaces
        ifaces = details.get("interfaces", [])
        self._ifaces_table.setRowCount(len(ifaces))
        for row, iface in enumerate(ifaces):
            self._ifaces_table.setItem(
                row, 0, QTableWidgetItem(iface.get("interface", ""))
            )
            self._ifaces_table.setItem(
                row, 1, QTableWidgetItem(iface.get("type", ""))
            )
            self._ifaces_table.setItem(
                row, 2, QTableWidgetItem(iface.get("source", ""))
            )
            self._ifaces_table.setItem(
                row, 3, QTableWidgetItem(iface.get("model", ""))
            )
            self._ifaces_table.setItem(
                row, 4, QTableWidgetItem(iface.get("mac", ""))
            )

        # IP Addresses
        addresses = details.get("addresses", [])
        self._addr_table.setRowCount(len(addresses))
        for row, a in enumerate(addresses):
            self._addr_table.setItem(
                row, 0, QTableWidgetItem(a.get("interface", ""))
            )
            self._addr_table.setItem(
                row, 1, QTableWidgetItem(a.get("protocol", ""))
            )
            self._addr_table.setItem(
                row, 2, QTableWidgetItem(a.get("full", ""))
            )

        # Memory stats
        mem = details.get("memory", {})
        display_keys = ["actual", "rss", "unused", "available", "usable"]
        rows = [(k, mem[k]) for k in display_keys if k in mem]
        self._mem_table.setRowCount(len(rows))
        for row, (key, val_kib) in enumerate(rows):
            self._mem_table.setItem(row, 0, QTableWidgetItem(key))
            mib = val_kib // 1024
            if mib >= 1024:
                val_str = f"{mib / 1024:.1f} GiB"
            else:
                val_str = f"{mib} MiB"
            self._mem_table.setItem(row, 1, QTableWidgetItem(val_str))

    def _populate_snapshots(self, snapshots: list[dict]) -> None:
        self._snap_table.setRowCount(len(snapshots))
        for row, s in enumerate(snapshots):
            self._snap_table.setItem(row, 0, QTableWidgetItem(s.get("name", "")))
            self._snap_table.setItem(
                row, 1, QTableWidgetItem(s.get("creation_time", ""))
            )
            self._snap_table.setItem(row, 2, QTableWidgetItem(s.get("state", "")))
            self._snap_table.setItem(row, 3, QTableWidgetItem(s.get("parent", "")))

    # ── Selection handling ───────────────────────────────────

    def _selected_vm_name(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item else None

    def _selected_vm_state(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 1)
        return item.text().strip() if item else None

    def _selected_snapshot_name(self) -> str | None:
        row = self._snap_table.currentRow()
        if row < 0:
            return None
        item = self._snap_table.item(row, 0)
        return item.text() if item else None

    def _on_selection_changed(self, row: int, _col: int, _prev_row: int, _prev_col: int) -> None:
        name = self._selected_vm_name()
        if name and name != self._selected_vm:
            self._selected_vm = name
            self._details_header.setText(f"Details: {name}")
            self._snap_header.setText(f"Snapshots: {name}")
            self._ctrl.refresh_vm_details(name)
            self._ctrl.refresh_snapshots(name)

    # ── Context menu ─────────────────────────────────────────

    def _show_context_menu(self, pos) -> None:
        if self._table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u25B6  Start", self, triggered=self._on_start))
        menu.addAction(QAction("\u23F9  Shutdown", self, triggered=self._on_shutdown))
        menu.addAction(QAction("\U0001F480  Force Off", self, triggered=self._on_force_off))
        menu.addAction(QAction("\U0001F504  Reboot", self, triggered=self._on_reboot))
        menu.addSeparator()
        menu.addAction(QAction("\u23F8  Suspend", self, triggered=self._on_suspend))
        menu.addAction(QAction("\u25B6  Resume", self, triggered=self._on_resume))
        menu.addSeparator()
        menu.addAction(QAction("\u2699  Toggle Autostart", self, triggered=self._on_autostart))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F4E5  Import as Server", self, triggered=self._on_import_server))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F4E4  Export VM", self, triggered=self._on_export))
        menu.addAction(QAction("\U0001F4E5  Import VM", self, triggered=self._on_import))
        menu.addAction(QAction("\U0001F4CB  Clone VM", self, triggered=self._on_clone))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Delete", self, triggered=self._on_delete))
        menu.exec(self._table.viewport().mapToGlobal(pos))

    # ── VM actions ───────────────────────────────────────────

    def _on_start(self) -> None:
        name = self._selected_vm_name()
        if name:
            self._ctrl.start_vm(name)

    def _on_shutdown(self) -> None:
        name = self._selected_vm_name()
        if name:
            self._ctrl.shutdown_vm(name)

    def _on_force_off(self) -> None:
        name = self._selected_vm_name()
        if not name:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Force off VM '{name}'? This is like pulling the power plug."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.destroy_vm(name)

    def _on_reboot(self) -> None:
        name = self._selected_vm_name()
        if name:
            self._ctrl.reboot_vm(name)

    def _on_suspend(self) -> None:
        name = self._selected_vm_name()
        if name:
            self._ctrl.suspend_vm(name)

    def _on_resume(self) -> None:
        name = self._selected_vm_name()
        if name:
            self._ctrl.resume_vm(name)

    def _on_autostart(self) -> None:
        name = self._selected_vm_name()
        if not name:
            return
        row = self._table.currentRow()
        current = self._table.item(row, 5).text().strip().lower() if self._table.item(row, 5) else ""
        enable = current != "enable"
        self._ctrl.set_autostart(name, enable)

    def _on_delete(self) -> None:
        name = self._selected_vm_name()
        if not name:
            return
        reply = QMessageBox.question(
            self,
            "Confirm",
            f"Delete VM '{name}'?\n\nThis will undefine the VM and remove "
            "managed save files and snapshot metadata.",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_vm(name)

    def _on_export(self) -> None:
        name = self._selected_vm_name()
        if not name:
            return
        output_dir = QFileDialog.getExistingDirectory(
            self, f"Export VM '{name}' - Select Output Directory"
        )
        if output_dir:
            self._ctrl.export_vm(name, output_dir)

    def _on_import(self) -> None:
        xml_path, _ = QFileDialog.getOpenFileName(
            self, "Import VM - Select XML File", "", "XML Files (*.xml);;All Files (*)"
        )
        if xml_path:
            self._ctrl.import_vm(xml_path)

    def _on_clone(self) -> None:
        name = self._selected_vm_name()
        if not name:
            return
        new_name, ok = QInputDialog.getText(
            self, "Clone VM", f"New name for clone of '{name}':"
        )
        if ok and new_name.strip():
            self._ctrl.clone_vm(name, new_name.strip())

    def _on_import_server(self) -> None:
        """Open ServerDialog pre-filled with the VM's name and IP address."""
        row = self._table.currentRow()
        if row < 0:
            return
        vm_name = self._table.item(row, 0).text()
        vm_ip = self._table.item(row, 2).text().strip()

        if not vm_ip or vm_ip == "-":
            QMessageBox.warning(
                self,
                "Import as Server",
                f"VM '{vm_name}' has no IP address.\n"
                "The VM must be running with a network interface to import it.",
            )
            return

        # Use first IP if multiple
        first_ip = vm_ip.split(",")[0].strip()

        server = Server(name=vm_name, host=first_ip, username="root")
        dialog = ServerDialog(server=server, parent=self)
        dialog.setWindowTitle("\U0001F4E5  Import VM as Server")
        if dialog.exec():
            new_server = dialog.get_server()
            if new_server.name and new_server.host and new_server.username:
                self._server_ctrl.add_server(new_server)
                QMessageBox.information(
                    self,
                    "Import as Server",
                    f"Server '{new_server.name}' added successfully.",
                )
            else:
                QMessageBox.warning(
                    self, "Validation", "Name, Host, and Username are required."
                )

    # ── Snapshot actions ─────────────────────────────────────

    def _on_snap_create(self) -> None:
        vm_name = self._selected_vm_name()
        if not vm_name:
            return
        snap_name, ok = QInputDialog.getText(
            self, "Create Snapshot", f"Snapshot name for '{vm_name}':"
        )
        if ok and snap_name.strip():
            self._ctrl.create_snapshot(vm_name, snap_name.strip())

    def _on_snap_revert(self) -> None:
        vm_name = self._selected_vm_name()
        snap_name = self._selected_snapshot_name()
        if not vm_name or not snap_name:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Revert VM '{vm_name}' to snapshot '{snap_name}'?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.revert_snapshot(vm_name, snap_name)

    def _on_snap_delete(self) -> None:
        vm_name = self._selected_vm_name()
        snap_name = self._selected_snapshot_name()
        if not vm_name or not snap_name:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Delete snapshot '{snap_name}' of VM '{vm_name}'?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_snapshot(vm_name, snap_name)
