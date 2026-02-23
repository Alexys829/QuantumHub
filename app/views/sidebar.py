from __future__ import annotations

from PyQt6.QtCore import Qt, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.workers.docker_worker import DockerWorker

from app.controllers.server_controller import ServerController
from app.services.connection_manager import ConnectionManager
from app.views.server_dialog import ServerDialog


class _CollapsibleSection(QWidget):
    """A header that toggles visibility of child buttons."""

    def __init__(self, title: str, expanded: bool = True, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._expanded = expanded
        self._header = QPushButton()
        self._header.setObjectName("sectionHeader")
        self._header.setCheckable(False)
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.clicked.connect(self._toggle)
        layout.addWidget(self._header)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(2)
        layout.addWidget(self._container)

        self._title = title
        self._update_header()
        self._container.setVisible(self._expanded)

    def _update_header(self) -> None:
        arrow = "\u25BC" if self._expanded else "\u25B6"
        self._header.setText(f"{arrow}  {self._title}")

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._container.setVisible(self._expanded)
        self._update_header()

    def add_button(self, btn: QPushButton) -> None:
        self._container_layout.addWidget(btn)


class Sidebar(QWidget):
    """Left sidebar: server selector + collapsible tree navigation."""

    view_changed = pyqtSignal(int)
    connection_changed = pyqtSignal()

    def __init__(
        self,
        server_controller: ServerController,
        connection_manager: ConnectionManager,
        parent=None,
    ):
        super().__init__(parent)
        self._server_ctrl = server_controller
        self._conn_manager = connection_manager
        self.setObjectName("sidebar")
        self._init_ui()
        self._load_servers()
        self._server_ctrl.servers_changed.connect(self._load_servers)

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Scroll area for the entire sidebar
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setObjectName("sidebarScroll")
        outer.addWidget(scroll)

        container = QWidget()
        container.setObjectName("sidebarInner")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 14, 10, 14)
        layout.setSpacing(6)

        # -- App title --
        from app.constants import APP_NAME
        title = QLabel(f"\U0001F5A5  {APP_NAME}")
        title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #e0e0e0;"
            "padding: 4px 0 10px 0;"
        )
        layout.addWidget(title)

        # -- Server section header + buttons --
        server_header_row = QHBoxLayout()
        server_header_row.setSpacing(2)
        server_header = QLabel("\U0001F5A5  SERVERS")
        server_header.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #888888;"
            "letter-spacing: 1px; padding: 6px 0 3px 2px;"
        )
        server_header_row.addWidget(server_header)
        server_header_row.addStretch()

        # Icon-only buttons aligned right
        add_btn = QPushButton("\u2795")
        add_btn.setObjectName("serverMiniBtn")
        add_btn.setFixedSize(26, 24)
        add_btn.setToolTip("Add server")
        add_btn.clicked.connect(self._on_add_server)

        edit_btn = QPushButton("\u270F")
        edit_btn.setObjectName("serverMiniBtn")
        edit_btn.setFixedSize(26, 24)
        edit_btn.setToolTip("Edit server")
        edit_btn.clicked.connect(self._on_edit_server)

        del_btn = QPushButton("\u2796")
        del_btn.setObjectName("serverMiniBtn")
        del_btn.setFixedSize(26, 24)
        del_btn.setToolTip("Delete server")
        del_btn.clicked.connect(self._on_delete_server)

        server_header_row.addWidget(add_btn)
        server_header_row.addWidget(edit_btn)
        server_header_row.addWidget(del_btn)
        layout.addLayout(server_header_row)

        # -- Server list --
        self._server_list = QListWidget()
        self._server_list.setMaximumHeight(180)
        self._server_list.itemClicked.connect(self._on_server_clicked)
        layout.addWidget(self._server_list)

        layout.addSpacing(10)

        # -- Navigation: collapsible sections --
        self._nav_buttons: list[QPushButton] = []

        from app.constants import (
            APT_REPOS_VIEW_INDEX,
            CRON_VIEW_INDEX,
            DISK_USAGE_VIEW_INDEX,
            FILE_TRANSFER_VIEW_INDEX,
            FIREWALL_VIEW_INDEX,
            HOSTS_VIEW_INDEX,
            JOURNAL_VIEW_INDEX,
            NETWORK_TOOLS_VIEW_INDEX,
            NETWORK_VIEW_INDEX,
            PACKAGES_VIEW_INDEX,
            REGISTRY_VIEW_INDEX,
            STARTUP_VIEW_INDEX,
            USERS_VIEW_INDEX,
            VM_VIEW_INDEX,
        )

        # SERVER section (monitoring, expanded by default)
        self._server_section = _CollapsibleSection(
            "\U0001F5A5  SERVER", expanded=True
        )
        server_nav_items = [
            ("\U0001F4CA  Dashboard", 0),
            ("\U0001F4BB  Terminal", 1),
            ("\u2699  Processes", 2),
            ("\U0001F4F1  Applications", 9),
            ("\U0001F4C2  File Transfer", FILE_TRANSFER_VIEW_INDEX),
        ]
        for label, idx in server_nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("view_index", idx)
            btn.clicked.connect(
                lambda checked, i=idx: self._on_nav_clicked(i)
            )
            self._server_section.add_button(btn)
            self._nav_buttons.append(btn)
        layout.addWidget(self._server_section)

        layout.addSpacing(4)

        # SYSTEM section (configuration, collapsed by default)
        self._system_section = _CollapsibleSection(
            "\U0001F527  SYSTEM", expanded=False
        )
        system_nav_items = [
            ("\U0001F527  Services", 3),
            ("\U0001F4E6  Packages", PACKAGES_VIEW_INDEX),
            ("\U0001F4DD  Hosts File", HOSTS_VIEW_INDEX),
            ("\U0001F310  Network", NETWORK_VIEW_INDEX),
            ("\U0001F6E1  Firewall", FIREWALL_VIEW_INDEX),
            ("\U0001F527  Net Tools", NETWORK_TOOLS_VIEW_INDEX),
            ("\U0001F4CB  APT Repos", APT_REPOS_VIEW_INDEX),
            ("\U0001F680  Startup", STARTUP_VIEW_INDEX),
            ("\U0001F4CB  System Logs", JOURNAL_VIEW_INDEX),
            ("\u23F0  Cron Jobs", CRON_VIEW_INDEX),
            ("\U0001F465  Users", USERS_VIEW_INDEX),
            ("\U0001F4BE  Disk Usage", DISK_USAGE_VIEW_INDEX),
        ]
        for label, idx in system_nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("view_index", idx)
            btn.clicked.connect(
                lambda checked, i=idx: self._on_nav_clicked(i)
            )
            self._system_section.add_button(btn)
            self._nav_buttons.append(btn)
        layout.addWidget(self._system_section)

        layout.addSpacing(4)

        # DOCKER section (collapsed by default)
        self._docker_section = _CollapsibleSection(
            "\U0001F433  DOCKER", expanded=False
        )
        docker_nav_items = [
            ("\u25B6  Containers", 4),
            ("\U0001F4BF  Images", 5),
            ("\U0001F4BE  Volumes", 6),
            ("\U0001F310  Networks", 7),
            ("\U0001F4E6  Compose", 8),
            ("\U0001F50D  Registry", REGISTRY_VIEW_INDEX),
        ]
        for label, idx in docker_nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("view_index", idx)
            btn.clicked.connect(
                lambda checked, i=idx: self._on_nav_clicked(i)
            )
            self._docker_section.add_button(btn)
            self._nav_buttons.append(btn)
        layout.addWidget(self._docker_section)

        layout.addSpacing(4)

        # VIRTUALIZATION section (collapsed by default)
        self._virt_section = _CollapsibleSection(
            "\U0001F5A5  VIRTUALIZATION", expanded=False
        )
        virt_nav_items = [
            ("\U0001F5A5  Virtual Machines", VM_VIEW_INDEX),
        ]
        for label, idx in virt_nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setProperty("view_index", idx)
            btn.clicked.connect(
                lambda checked, i=idx: self._on_nav_clicked(i)
            )
            self._virt_section.add_button(btn)
            self._nav_buttons.append(btn)
        layout.addWidget(self._virt_section)

        self._nav_buttons[0].setChecked(True)

        layout.addStretch()

        # -- Settings button --
        from app.constants import SETTINGS_VIEW_INDEX, GUIDE_VIEW_INDEX
        settings_btn = QPushButton("\u2699  Settings")
        settings_btn.setCheckable(True)
        settings_btn.setProperty("view_index", SETTINGS_VIEW_INDEX)
        settings_btn.clicked.connect(
            lambda checked: self._on_nav_clicked(SETTINGS_VIEW_INDEX)
        )
        settings_btn.setObjectName("settingsNavBtn")
        layout.addWidget(settings_btn)
        self._nav_buttons.append(settings_btn)

        # -- Guide button --
        guide_btn = QPushButton("\u2139  Guide")
        guide_btn.setCheckable(True)
        guide_btn.setProperty("view_index", GUIDE_VIEW_INDEX)
        guide_btn.clicked.connect(
            lambda checked: self._on_nav_clicked(GUIDE_VIEW_INDEX)
        )
        guide_btn.setObjectName("settingsNavBtn")
        layout.addWidget(guide_btn)
        self._nav_buttons.append(guide_btn)

        # -- Version label --
        from app.constants import APP_VERSION
        ver = QLabel(f"v{APP_VERSION}")
        ver.setStyleSheet("color: #555555; font-size: 11px; padding: 4px;")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver)

        scroll.setWidget(container)

        self.setStyleSheet(
            "#sidebar { background-color: #252526; border-right: 1px solid #333333; }"
            "#sidebarScroll { background: transparent; }"
            "#sidebarInner { background: transparent; }"
            "#sidebar QPushButton { text-align: left; padding: 8px 12px; border: none;"
            "  color: #bbbbbb; background: transparent; border-radius: 5px; font-size: 13px; }"
            "#sidebar QPushButton:checked { background-color: #094771; color: #ffffff; }"
            "#sidebar QPushButton:hover { background-color: #2a2d2e; color: #ffffff; }"
            "#sectionHeader { font-size: 11px; font-weight: 600; color: #888888;"
            "  letter-spacing: 1px; padding: 6px 2px 3px 2px; border-radius: 4px;"
            "  text-align: left; }"
            "#sectionHeader:hover { color: #bbbbbb; background-color: #2a2d2e; }"
            "QPushButton#serverMiniBtn { padding: 2px; border: none; background: transparent;"
            "  color: #888888; font-size: 12px; border-radius: 3px; min-width: 0; }"
            "QPushButton#serverMiniBtn:hover { background-color: #3a3a3a; color: #e0e0e0; }"
            "QPushButton#settingsNavBtn { border-top: 1px solid #333333;"
            "  margin-top: 4px; padding-top: 10px; }"
        )

    def _load_servers(self) -> None:
        self._server_list.clear()
        local_item = QListWidgetItem("\U0001F4BB  Localhost")
        local_item.setData(Qt.ItemDataRole.UserRole, None)
        self._server_list.addItem(local_item)
        self._server_list.setCurrentItem(local_item)

        for server in self._server_ctrl.get_all_servers():
            item = QListWidgetItem(f"\U0001F5A5  {server.name}")
            item.setData(Qt.ItemDataRole.UserRole, server.id)
            self._server_list.addItem(item)

    def _on_server_clicked(self, item: QListWidgetItem) -> None:
        server_id = item.data(Qt.ItemDataRole.UserRole)
        if server_id is None:
            try:
                self._conn_manager.connect_local()
                self.connection_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, "Connection Error", str(e))
        else:
            server = self._server_ctrl.get_server(server_id)
            if server:
                self._connect_remote_async(server)

    def _connect_remote_async(self, server) -> None:
        """Connect to a remote server in a background thread with a loading dialog."""
        self._loading = QDialog(self, Qt.WindowType.FramelessWindowHint)
        self._loading.setModal(True)
        self._loading.setFixedSize(260, 80)
        self._loading.setStyleSheet(
            "QDialog { background-color: #2d2d2d; border: 1px solid #555555;"
            " border-radius: 10px; }"
        )
        lbl = QLabel(f"  Connecting to {server.name}...")
        lbl.setStyleSheet("color: #e0e0e0; font-size: 13px;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dlg_layout = QVBoxLayout(self._loading)
        dlg_layout.addWidget(lbl)

        def _connect():
            self._conn_manager.connect_remote(server)

        worker = DockerWorker(fn=_connect)
        worker.signals.result.connect(self._on_remote_connected)
        worker.signals.error.connect(self._on_remote_error)
        QThreadPool.globalInstance().start(worker)

        self._loading.exec()

    def _on_remote_connected(self, _result) -> None:
        if self._loading:
            self._loading.accept()
            self._loading = None
        self.connection_changed.emit()

    def _on_remote_error(self, error_msg: str) -> None:
        if self._loading:
            self._loading.reject()
            self._loading = None
        QMessageBox.critical(self, "Connection Error", error_msg)

    def _on_nav_clicked(self, index: int) -> None:
        for btn in self._nav_buttons:
            btn.setChecked(btn.property("view_index") == index)
        self.view_changed.emit(index)

    def _on_add_server(self) -> None:
        dialog = ServerDialog(parent=self)
        if dialog.exec():
            server = dialog.get_server()
            if server.name and server.host and server.username:
                self._server_ctrl.add_server(server)
            else:
                QMessageBox.warning(
                    self, "Validation", "Name, Host, and Username are required."
                )

    def _on_edit_server(self) -> None:
        item = self._server_list.currentItem()
        if not item:
            return
        server_id = item.data(Qt.ItemDataRole.UserRole)
        if server_id is None:
            return
        server = self._server_ctrl.get_server(server_id)
        if server:
            dialog = ServerDialog(server=server, parent=self)
            if dialog.exec():
                self._server_ctrl.update_server(dialog.get_server())

    def _on_delete_server(self) -> None:
        item = self._server_list.currentItem()
        if not item:
            return
        server_id = item.data(Qt.ItemDataRole.UserRole)
        if server_id is None:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Delete server '{item.text().strip()}'?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            if (
                self._conn_manager.active_server
                and self._conn_manager.active_server.id == server_id
            ):
                self._conn_manager.connect_local()
                self.connection_changed.emit()
            self._server_ctrl.delete_server(server_id)
