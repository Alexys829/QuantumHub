from __future__ import annotations

import time

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.constants import (
    APP_NAME,
    APP_POLL_INTERVAL_MS,
    CONTAINER_POLL_INTERVAL_MS,
    PROCESS_POLL_INTERVAL_MS,
    SERVICE_POLL_INTERVAL_MS,
)
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
    GUIDE_VIEW_INDEX,
)
from app.controllers.application_controller import ApplicationController
from app.controllers.file_transfer_controller import FileTransferController
from app.controllers.apt_repo_controller import AptRepoController
from app.controllers.compose_controller import ComposeController
from app.controllers.container_controller import ContainerController
from app.controllers.cron_controller import CronController
from app.controllers.disk_controller import DiskController
from app.controllers.firewall_controller import FirewallController
from app.controllers.hosts_controller import HostsController
from app.controllers.image_controller import ImageController
from app.controllers.journal_controller import JournalController
from app.controllers.network_config_controller import NetworkConfigController
from app.controllers.network_controller import NetworkController
from app.controllers.network_tools_controller import NetworkToolsController
from app.controllers.package_controller import PackageController
from app.controllers.process_controller import ProcessController
from app.controllers.registry_controller import RegistryController
from app.controllers.server_controller import ServerController
from app.controllers.service_controller import ServiceController
from app.controllers.settings_controller import SettingsController
from app.controllers.startup_controller import StartupController
from app.controllers.system_controller import SystemController
from app.controllers.users_controller import UsersController
from app.controllers.vm_controller import VmController
from app.controllers.volume_controller import VolumeController
from app.services.connection_manager import ConnectionManager
from app.services.file_transfer_service import FileTransferService
from app.services.system_service import SystemService
from app.services.vm_service import VmService
from app.views.applications_view import ApplicationsView
from app.views.apt_repos_view import AptReposView
from app.views.compose_view import ComposeView
from app.views.containers_view import ContainersView
from app.views.cron_view import CronView
from app.views.disk_usage_view import DiskUsageView
from app.views.file_transfer_view import FileTransferView
from app.views.dashboard_view import DashboardView
from app.views.firewall_view import FirewallView
from app.views.hosts_view import HostsView
from app.views.images_view import ImagesView
from app.views.journal_view import JournalView
from app.views.network_config_view import NetworkConfigView
from app.views.network_tools_view import NetworkToolsView
from app.views.networks_view import NetworksView
from app.views.packages_view import PackagesView
from app.views.processes_view import ProcessesView
from app.views.registry_view import RegistryView
from app.views.services_view import ServicesView
from app.views.settings_view import SettingsView
from app.views.sidebar import Sidebar
from app.views.startup_view import StartupView
from app.views.terminal_view import TerminalTabWidget
from app.views.users_view import UsersView
from app.views.guide_view import GuideView
from app.views.vm_view import VmView
from app.views.volumes_view import VolumesView


class _SudoPasswordDialog(QDialog):
    """Dialog to ask for the sudo password."""

    def __init__(self, parent=None, message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("\U0001F512  Sudo Password")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 16, 20, 16)

        if not message:
            message = (
                "Inserisci la password sudo per le operazioni amministrative "
                "(hosts, rete, pacchetti, servizi, ecc.).\n\n"
                "La password viene conservata solo in memoria — "
                "mai salvata su disco."
            )
        info = QLabel(message)
        info.setStyleSheet("color: #bbbbbb;")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setPlaceholderText("Password")
        layout.addWidget(self._password_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._password_input.returnPressed.connect(self.accept)

    def get_password(self) -> str:
        return self._password_input.text()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"\U0001F5A5 {APP_NAME}")
        self.setMinimumSize(1150, 700)

        # -- Services --
        self._conn_manager = ConnectionManager()
        self._system_service = SystemService(self._conn_manager)
        self._file_transfer_service = FileTransferService(self._conn_manager)

        # -- Controllers --
        self._container_ctrl = ContainerController(self._conn_manager, self)
        self._image_ctrl = ImageController(self._conn_manager, self)
        self._volume_ctrl = VolumeController(self._conn_manager, self)
        self._network_ctrl = NetworkController(self._conn_manager, self)
        self._compose_ctrl = ComposeController(self._conn_manager, self)
        self._server_ctrl = ServerController(self)
        self._system_ctrl = SystemController(self._system_service, self)
        self._process_ctrl = ProcessController(self._system_service, self)
        self._app_ctrl = ApplicationController(self._system_service, self)
        self._service_ctrl = ServiceController(self._system_service, self)
        self._package_ctrl = PackageController(self._system_service, self)
        self._hosts_ctrl = HostsController(self._system_service, self)
        self._netcfg_ctrl = NetworkConfigController(self._system_service, self)
        self._apt_repo_ctrl = AptRepoController(self._system_service, self)
        self._startup_ctrl = StartupController(self._system_service, self)
        self._firewall_ctrl = FirewallController(self._system_service, self)
        self._nettools_ctrl = NetworkToolsController(self._system_service, self)
        self._settings_ctrl = SettingsController(self)
        self._file_transfer_ctrl = FileTransferController(self._file_transfer_service, self)
        self._vm_service = VmService(self._system_service)
        self._vm_ctrl = VmController(self._vm_service, self)
        self._journal_ctrl = JournalController(self._system_service, self)
        self._cron_ctrl = CronController(self._system_service, self)
        self._users_ctrl = UsersController(self._system_service, self)
        self._disk_ctrl = DiskController(self._system_service, self)
        self._registry_ctrl = RegistryController(self._conn_manager, self)

        # -- Central layout --
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar(
            server_controller=self._server_ctrl,
            connection_manager=self._conn_manager,
            parent=self,
        )
        self._sidebar.setFixedWidth(230)
        main_layout.addWidget(self._sidebar)

        # Content area — 26 pages (indices 0-25)
        self._stack = QStackedWidget()

        # SERVER views (0-3, 9)
        self._dashboard_view = DashboardView(self._system_ctrl, self)
        self._terminal_tabs = TerminalTabWidget(
            self._system_service, self._conn_manager, self
        )
        self._processes_view = ProcessesView(self._process_ctrl, self)
        self._services_view = ServicesView(self._service_ctrl, self)

        # DOCKER views (4-8)
        self._containers_view = ContainersView(self._container_ctrl, self._conn_manager, self)
        self._images_view = ImagesView(self._image_ctrl, self)
        self._volumes_view = VolumesView(self._volume_ctrl, self)
        self._networks_view = NetworksView(self._network_ctrl, self)
        self._compose_view = ComposeView(self._compose_ctrl, self)

        # SERVER view (9)
        self._applications_view = ApplicationsView(self._app_ctrl, self)

        # Settings view (10)
        self._settings_view = SettingsView(
            self._settings_ctrl, self._server_ctrl, self._conn_manager, self
        )

        # Packages view (11)
        self._packages_view = PackagesView(self._package_ctrl, self)

        # SYSTEM views (12-17)
        self._hosts_view = HostsView(self._hosts_ctrl, self)
        self._netcfg_view = NetworkConfigView(self._netcfg_ctrl, self)
        self._apt_repos_view = AptReposView(self._apt_repo_ctrl, self)
        self._startup_view = StartupView(self._startup_ctrl, self)
        self._firewall_view = FirewallView(self._firewall_ctrl, self)
        self._nettools_view = NetworkToolsView(self._nettools_ctrl, self)

        # File Transfer view (18)
        self._file_transfer_view = FileTransferView(
            self._file_transfer_ctrl, self._conn_manager, self
        )

        # VM view (19)
        self._vm_view = VmView(self._vm_ctrl, self._server_ctrl, self)

        # Guide view (20)
        self._guide_view = GuideView(self)

        # New views (21-25)
        self._journal_view = JournalView(self._journal_ctrl, self)
        self._cron_view = CronView(self._cron_ctrl, self)
        self._users_view = UsersView(self._users_ctrl, self)
        self._disk_usage_view = DiskUsageView(self._disk_ctrl, self)
        self._registry_view = RegistryView(self._registry_ctrl, self)

        # Set connection manager on images view for build feature
        self._images_view.set_connection_manager(self._conn_manager)

        self._stack.addWidget(self._dashboard_view)    # 0
        self._stack.addWidget(self._terminal_tabs)     # 1
        self._stack.addWidget(self._processes_view)    # 2
        self._stack.addWidget(self._services_view)     # 3
        self._stack.addWidget(self._containers_view)   # 4
        self._stack.addWidget(self._images_view)       # 5
        self._stack.addWidget(self._volumes_view)      # 6
        self._stack.addWidget(self._networks_view)     # 7
        self._stack.addWidget(self._compose_view)      # 8
        self._stack.addWidget(self._applications_view) # 9
        self._stack.addWidget(self._settings_view)     # 10
        self._stack.addWidget(self._packages_view)     # 11
        self._stack.addWidget(self._hosts_view)        # 12
        self._stack.addWidget(self._netcfg_view)       # 13
        self._stack.addWidget(self._apt_repos_view)    # 14
        self._stack.addWidget(self._startup_view)      # 15
        self._stack.addWidget(self._firewall_view)     # 16
        self._stack.addWidget(self._nettools_view)     # 17
        self._stack.addWidget(self._file_transfer_view) # 18
        self._stack.addWidget(self._vm_view)             # 19
        self._stack.addWidget(self._guide_view)          # 20
        self._stack.addWidget(self._journal_view)        # 21
        self._stack.addWidget(self._cron_view)           # 22
        self._stack.addWidget(self._users_view)          # 23
        self._stack.addWidget(self._disk_usage_view)     # 24
        self._stack.addWidget(self._registry_view)       # 25

        main_layout.addWidget(self._stack)
        self.setCentralWidget(central)

        # -- Status bar --
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        self._sudo_btn = QPushButton("\U0001F512")
        self._sudo_btn.setFixedSize(30, 24)
        self._sudo_btn.setToolTip("Sudo: non autenticato (clicca per impostare)")
        self._sudo_btn.setStyleSheet(
            "QPushButton { border: none; background: transparent;"
            " font-size: 14px; padding: 0 4px; }"
            "QPushButton:hover { background-color: #3a3a3a; border-radius: 3px; }"
        )
        self._sudo_btn.clicked.connect(self._on_change_sudo_password)
        status_bar.addPermanentWidget(self._sudo_btn)

        self._conn_label = QLabel()
        self._conn_label.setStyleSheet("padding: 0 8px;")
        status_bar.addPermanentWidget(self._conn_label)

        # -- Sudo password (session-only, never persisted) --
        self._local_sudo_password: str | None = None

        # -- Signals --
        self._sidebar.view_changed.connect(self._on_view_changed)
        self._sidebar.connection_changed.connect(self._on_connection_changed)

        # -- Polling timer --
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._poll_active_view)
        self._poll_timer.setInterval(CONTAINER_POLL_INTERVAL_MS)
        self._last_poll: dict[int, float] = {}  # view_idx → last poll timestamp

        # -- Intercept "sudo password not set" from all controllers --
        sudo_controllers = [
            self._service_ctrl, self._package_ctrl, self._hosts_ctrl,
            self._netcfg_ctrl, self._apt_repo_ctrl, self._startup_ctrl,
            self._firewall_ctrl, self._nettools_ctrl, self._process_ctrl,
            self._app_ctrl, self._system_ctrl,
            self._cron_ctrl, self._users_ctrl,
        ]
        for ctrl in sudo_controllers:
            if hasattr(ctrl, "operation_error"):
                ctrl.operation_error.connect(self._handle_sudo_error)

        # -- Auto-connect local --
        self._try_connect_local()

    def _try_connect_local(self) -> None:
        # Hide power buttons on localhost
        self._dashboard_view.set_power_buttons_visible(False)
        # Always load dashboard (system info works without Docker)
        self._system_ctrl.refresh_system_info()
        self._system_ctrl.refresh_ports()
        self._system_ctrl.refresh_interface_ips()
        self._system_ctrl.start_metrics_polling()

        try:
            self._conn_manager.connect_local()
            self._update_connection_status()
            self._poll_timer.start()
        except Exception as e:
            self.statusBar().showMessage(f"Localhost unavailable: {e}")
            self._conn_label.setText("\u26A0  Disconnected (Docker)")
            self._update_connection_status()

    def _on_view_changed(self, index: int) -> None:
        old_index = self._stack.currentIndex()
        self._stack.setCurrentIndex(index)

        # Stop metrics polling when leaving Dashboard
        if old_index == 0 and index != 0:
            self._system_ctrl.stop_metrics_polling()

        # Start metrics polling when entering Dashboard
        if index == 0:
            self._system_ctrl.refresh_system_info()
            self._system_ctrl.refresh_ports()
            self._system_ctrl.refresh_interface_ips()
            self._system_ctrl.start_metrics_polling()

        # Static views: refresh on first entry only (no auto-polling)
        if index == PACKAGES_VIEW_INDEX:
            if not getattr(self, "_packages_loaded", False):
                self._packages_loaded = True
                self._package_ctrl.refresh_packages()
        elif index == HOSTS_VIEW_INDEX:
            if not getattr(self, "_hosts_loaded", False):
                self._hosts_loaded = True
                self._hosts_ctrl.load_hosts()
        elif index == NETWORK_VIEW_INDEX:
            if not getattr(self, "_netcfg_loaded", False):
                self._netcfg_loaded = True
                self._netcfg_ctrl.check_nm()
                self._netcfg_ctrl.refresh_connections()
                self._load_mac_addresses()
        elif index == FIREWALL_VIEW_INDEX:
            if not getattr(self, "_firewall_loaded", False):
                self._firewall_loaded = True
                self._firewall_ctrl.refresh_rules()
        elif index == APT_REPOS_VIEW_INDEX:
            if not getattr(self, "_apt_repos_loaded", False):
                self._apt_repos_loaded = True
                self._apt_repo_ctrl.refresh_repos()
        elif index == STARTUP_VIEW_INDEX:
            if not getattr(self, "_startup_loaded", False):
                self._startup_loaded = True
                self._startup_ctrl.refresh_entries()
        elif index == FILE_TRANSFER_VIEW_INDEX:
            if not getattr(self, "_file_transfer_loaded", False):
                self._file_transfer_loaded = True
                self._file_transfer_view.load_initial()
        elif index == VM_VIEW_INDEX:
            if not getattr(self, "_vm_loaded", False):
                self._vm_loaded = True
                self._vm_ctrl.refresh_vms()
        elif index == JOURNAL_VIEW_INDEX:
            if not getattr(self, "_journal_loaded", False):
                self._journal_loaded = True
                self._journal_ctrl.refresh_units()
                self._journal_ctrl.refresh_logs()
        elif index == CRON_VIEW_INDEX:
            if not getattr(self, "_cron_loaded", False):
                self._cron_loaded = True
                self._cron_ctrl.refresh_cron()
        elif index == USERS_VIEW_INDEX:
            if not getattr(self, "_users_loaded", False):
                self._users_loaded = True
                self._users_ctrl.refresh_users()
                self._users_ctrl.refresh_groups()
        elif index == DISK_USAGE_VIEW_INDEX:
            if not getattr(self, "_disk_loaded", False):
                self._disk_loaded = True
                self._disk_ctrl.refresh_disk()

        # Force immediate refresh on view switch (reset throttle)
        self._last_poll.pop(index, None)

        self._poll_active_view()

    def _on_connection_changed(self) -> None:
        self._update_connection_status()
        self._terminal_tabs.reset_all_sessions()
        self._dashboard_view.reset_network_state()
        self._dashboard_view.set_power_buttons_visible(
            not self._conn_manager.is_local
        )
        self._packages_loaded = False
        self._hosts_loaded = False
        self._netcfg_loaded = False
        self._firewall_loaded = False
        self._apt_repos_loaded = False
        self._startup_loaded = False
        self._file_transfer_loaded = False
        self._vm_loaded = False
        self._journal_loaded = False
        self._cron_loaded = False
        self._users_loaded = False
        self._disk_loaded = False
        self._file_transfer_view.reset()

        # Set sudo password for the new connection
        if self._conn_manager.is_local:
            self._system_service.sudo_password = self._local_sudo_password
            self._update_sudo_status(self._local_sudo_password is not None)
        elif self._conn_manager.active_server:
            server = self._conn_manager.active_server
            if server.password:
                # Password-auth servers: reuse SSH password as sudo password
                self._system_service.sudo_password = server.password
                self._update_sudo_status(True)
            else:
                # Key-auth servers: sudo will be prompted on demand
                self._system_service.sudo_password = None
                self._update_sudo_status(False)

        # Refresh dashboard info for new server
        if self._stack.currentIndex() == 0:
            self._system_ctrl.stop_metrics_polling()
            self._system_ctrl.refresh_system_info()
            self._system_ctrl.refresh_ports()
            self._system_ctrl.refresh_interface_ips()
            self._system_ctrl.start_metrics_polling()

        self._poll_active_view()

    def _update_connection_status(self) -> None:
        if self._conn_manager.is_local:
            name = "\U0001F4BB  Localhost"
        elif self._conn_manager.active_server:
            name = f"\U0001F5A5  {self._conn_manager.active_server.name}"
        else:
            name = "\u26A0  Disconnected"
        self._conn_label.setText(name)
        self.statusBar().showMessage(f"Connected to: {name}", 3000)

    # ── Sudo password management ──────────────────────────────

    def _handle_sudo_error(self, error_msg: str) -> None:
        """Intercept 'sudo password not set' errors and prompt for password."""
        if "sudo password not set" not in error_msg:
            return
        if self._ask_sudo_password(
            "Questa operazione richiede privilegi sudo.\n\n"
            "Inserisci la password sudo per continuare.\n"
            "La password viene conservata solo in memoria."
        ):
            self.statusBar().showMessage(
                "\U0001F513  Password sudo impostata — riprova l'operazione",
                5000,
            )

    def _ask_sudo_password(self, message: str = "") -> bool:
        """Show dialog to ask for sudo password. Returns True if set."""
        dialog = _SudoPasswordDialog(parent=self, message=message)
        if dialog.exec():
            password = dialog.get_password()
            if password:
                # Validate the password with a quick sudo test
                _, _, rc = self._system_service._run_command(
                    "sudo -S true",
                    timeout=10,
                    stdin_data=password + "\n",
                )
                if rc == 0:
                    self._system_service.sudo_password = password
                    if self._conn_manager.is_local:
                        self._local_sudo_password = password
                    self._update_sudo_status(True)
                    self.statusBar().showMessage(
                        "\U0001F513  Password sudo impostata", 3000
                    )
                    return True
                else:
                    # Wrong password — retry
                    return self._ask_sudo_password(
                        "\u26A0  Password errata. Riprova."
                    )
        return False

    def _on_change_sudo_password(self) -> None:
        """Handle click on the lock button in the status bar."""
        self._ask_sudo_password()

    def _update_sudo_status(self, has_password: bool) -> None:
        if has_password:
            self._sudo_btn.setText("\U0001F513")  # unlocked
            self._sudo_btn.setToolTip(
                "Sudo: autenticato (clicca per cambiare)"
            )
        else:
            self._sudo_btn.setText("\U0001F512")  # locked
            self._sudo_btn.setToolTip(
                "Sudo: non autenticato (clicca per impostare)"
            )

    def _load_mac_addresses(self) -> None:
        """Fetch MAC addresses in background and pass to the network view."""
        from app.workers.docker_worker import DockerWorker
        from PyQt6.QtCore import QThreadPool

        def _fetch():
            return self._system_service.get_interface_macs()

        worker = DockerWorker(fn=_fetch)
        worker.signals.result.connect(self._netcfg_view.set_mac_map)
        QThreadPool.globalInstance().start(worker)

    def _poll_active_view(self) -> None:
        idx = self._stack.currentIndex()

        # SERVER views (0-3, 9): work without Docker
        if idx == 0:
            pass  # Dashboard uses its own polling worker
        elif idx == 1:
            pass  # Terminal is interactive, no polling
        elif idx == 2:
            if self._throttle_ok(2, PROCESS_POLL_INTERVAL_MS):
                self._process_ctrl.refresh_processes()
        elif idx == 3:
            if self._throttle_ok(3, SERVICE_POLL_INTERVAL_MS):
                self._service_ctrl.refresh_services()
        elif idx == 9:
            if self._throttle_ok(9, APP_POLL_INTERVAL_MS):
                self._app_ctrl.refresh_applications()
        # DOCKER views (4-8): require Docker connection
        elif self._conn_manager.is_connected:
            if idx == 4:
                self._container_ctrl.refresh_containers()
            elif idx == 5:
                self._image_ctrl.refresh_images()
            elif idx == 6:
                self._volume_ctrl.refresh_volumes()
            elif idx == 7:
                self._network_ctrl.refresh_networks()
            elif idx == 8:
                self._compose_ctrl.refresh_projects()

    def _throttle_ok(self, view_idx: int, interval_ms: int) -> bool:
        """Return True if enough time has passed since the last poll for *view_idx*."""
        now = time.monotonic()
        last = self._last_poll.get(view_idx, 0.0)
        if now - last >= interval_ms / 1000.0:
            self._last_poll[view_idx] = now
            return True
        return False

    def closeEvent(self, event) -> None:
        self._poll_timer.stop()
        self._system_ctrl.stop_metrics_polling(wait=True)
        self._conn_manager.shutdown()
        from app.models.database import Database

        Database.instance().close()
        super().closeEvent(event)
