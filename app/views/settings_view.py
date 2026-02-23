from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.constants import APP_NAME, APP_VERSION, DATA_DIR, DB_PATH
from app.controllers.settings_controller import SettingsController

if TYPE_CHECKING:
    from app.controllers.server_controller import ServerController
    from app.services.connection_manager import ConnectionManager


class SettingsView(QWidget):
    """Settings page with grouped configuration sections."""

    def __init__(
        self,
        settings_controller: SettingsController,
        server_controller: ServerController,
        connection_manager: ConnectionManager,
        parent=None,
    ):
        super().__init__(parent)
        self._ctrl = settings_controller
        self._server_ctrl = server_controller
        self._cm = connection_manager
        self._init_ui()
        self._load_settings()

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(16)

        # Header
        header = QLabel("\u2699  Settings")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "padding: 0 0 4px 0;"
        )
        layout.addWidget(header)

        layout.addWidget(self._build_general_section())
        layout.addWidget(self._build_connection_section())
        layout.addWidget(self._build_terminal_section())
        layout.addWidget(self._build_data_section())
        layout.addWidget(self._build_desktop_section())
        layout.addWidget(self._build_about_section())
        layout.addStretch()

        scroll.setWidget(container)

    # ── General ───────────────────────────────────────────────

    def _build_general_section(self) -> QGroupBox:
        group = QGroupBox("General")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Theme
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Theme:"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["Dark"])
        self._theme_combo.setEnabled(False)
        self._theme_combo.setFixedWidth(160)
        row1.addWidget(self._theme_combo)
        row1.addStretch()
        layout.addLayout(row1)

        # Polling speed
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Polling speed:"))
        self._poll_combo = QComboBox()
        self._poll_combo.addItems(["Slow (0.5x)", "Normal (1x)", "Fast (2x)"])
        self._poll_combo.setFixedWidth(160)
        self._poll_combo.currentIndexChanged.connect(self._on_poll_changed)
        row2.addWidget(self._poll_combo)
        row2.addStretch()
        layout.addLayout(row2)

        # Confirm before kill
        self._confirm_kill_cb = QCheckBox("Confirm before killing processes")
        self._confirm_kill_cb.toggled.connect(self._on_confirm_kill_changed)
        layout.addWidget(self._confirm_kill_cb)

        return group

    # ── Connection ────────────────────────────────────────────

    def _build_connection_section(self) -> QGroupBox:
        group = QGroupBox("Connection")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Default SSH auth
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Default SSH auth:"))
        self._ssh_auth_combo = QComboBox()
        self._ssh_auth_combo.addItems(["SSH Key", "Password"])
        self._ssh_auth_combo.setFixedWidth(160)
        self._ssh_auth_combo.currentIndexChanged.connect(self._on_ssh_auth_changed)
        row1.addWidget(self._ssh_auth_combo)
        row1.addStretch()
        layout.addLayout(row1)

        # Auto-connect last server
        self._auto_connect_cb = QCheckBox("Auto-connect to last server on startup")
        self._auto_connect_cb.toggled.connect(self._on_auto_connect_changed)
        layout.addWidget(self._auto_connect_cb)

        return group

    # ── Terminal ──────────────────────────────────────────────

    def _build_terminal_section(self) -> QGroupBox:
        group = QGroupBox("Terminal")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        row = QHBoxLayout()
        row.addWidget(QLabel("Default font size:"))
        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 24)
        self._font_spin.setFixedWidth(80)
        self._font_spin.valueChanged.connect(self._on_font_size_changed)
        row.addWidget(self._font_spin)
        row.addStretch()
        layout.addLayout(row)

        return group

    # ── Data Management ───────────────────────────────────────

    def _build_data_section(self) -> QGroupBox:
        group = QGroupBox("Data Management")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # Export row
        export_row = QHBoxLayout()
        export_row.setSpacing(8)
        export_all_btn = QPushButton("\U0001F4E4  Export All Servers")
        export_all_btn.clicked.connect(self._on_export_all)
        export_row.addWidget(export_all_btn)

        export_sel_btn = QPushButton("\U0001F4E4  Export Selected Server")
        export_sel_btn.clicked.connect(self._on_export_selected)
        export_row.addWidget(export_sel_btn)
        export_row.addStretch()
        layout.addLayout(export_row)

        # Import row
        import_row = QHBoxLayout()
        import_row.setSpacing(8)
        import_btn = QPushButton("\U0001F4E5  Import Servers from JSON")
        import_btn.clicked.connect(self._on_import)
        import_row.addWidget(import_btn)
        import_row.addStretch()
        layout.addLayout(import_row)

        # Separator
        sep = QLabel("")
        sep.setFixedHeight(8)
        layout.addWidget(sep)

        # Reset
        reset_btn = QPushButton("\U0001F5D1  Reset & Reinitialize App")
        reset_btn.setStyleSheet(
            "QPushButton { background-color: #5a1d1d; color: #f48771;"
            " border: 1px solid #f48771; padding: 8px 16px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #6b2020; }"
        )
        reset_btn.clicked.connect(self._on_reset)
        reset_row = QHBoxLayout()
        reset_row.addWidget(reset_btn)
        reset_row.addStretch()
        layout.addLayout(reset_row)

        return group

    # ── Desktop Integration ───────────────────────────────────

    def _build_desktop_section(self) -> QGroupBox:
        group = QGroupBox("Desktop Integration (AppImage)")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(12)

        # AppImage path
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("AppImage path:"))
        self._appimage_input = QLineEdit()
        self._appimage_input.setPlaceholderText("/path/to/QuantumHub.AppImage")
        detected = self._ctrl.get_appimage_path()
        if detected:
            self._appimage_input.setText(detected)
        path_row.addWidget(self._appimage_input)
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse_appimage)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        add_menu_btn = QPushButton("\u2795  Add to App Menu")
        add_menu_btn.clicked.connect(self._on_add_to_menu)
        btn_row.addWidget(add_menu_btn)

        remove_menu_btn = QPushButton("\u2796  Remove from App Menu")
        remove_menu_btn.clicked.connect(self._on_remove_from_menu)
        btn_row.addWidget(remove_menu_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Status
        self._desktop_status = QLabel()
        self._desktop_status.setStyleSheet("color: #888888; font-size: 11px;")
        self._update_desktop_status()
        layout.addWidget(self._desktop_status)

        return group

    # ── About ─────────────────────────────────────────────────

    def _build_about_section(self) -> QGroupBox:
        group = QGroupBox("About")
        group.setObjectName("settingsGroup")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        name_lbl = QLabel(f"{APP_NAME} v{APP_VERSION}")
        name_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0;")
        layout.addWidget(name_lbl)

        data_lbl = QLabel(f"Data directory: {DATA_DIR}")
        data_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(data_lbl)

        db_lbl = QLabel(f"Database: {DB_PATH.name}")
        db_lbl.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(db_lbl)

        return group

    # ── Load / Save ───────────────────────────────────────────

    def _load_settings(self) -> None:
        settings = self._ctrl.get_all_settings()

        # Polling speed
        mult = settings.get("poll_multiplier", "1.0")
        poll_map = {"0.5": 0, "1.0": 1, "2.0": 2}
        self._poll_combo.setCurrentIndex(poll_map.get(mult, 1))

        # Confirm before kill
        self._confirm_kill_cb.setChecked(
            settings.get("confirm_before_kill", "True") == "True"
        )

        # SSH auth
        auth = settings.get("default_ssh_auth", "key")
        self._ssh_auth_combo.setCurrentIndex(0 if auth == "key" else 1)

        # Auto-connect
        self._auto_connect_cb.setChecked(
            settings.get("auto_connect_last_server", "False") == "True"
        )

        # Terminal font size
        size = int(settings.get("terminal_font_size", "12"))
        self._font_spin.setValue(size)

    def _on_poll_changed(self, index: int) -> None:
        values = ["0.5", "1.0", "2.0"]
        if 0 <= index < len(values):
            self._ctrl.set_setting("poll_multiplier", values[index])

    def _on_confirm_kill_changed(self, checked: bool) -> None:
        self._ctrl.set_setting("confirm_before_kill", str(checked))

    def _on_ssh_auth_changed(self, index: int) -> None:
        self._ctrl.set_setting("default_ssh_auth", "key" if index == 0 else "password")

    def _on_auto_connect_changed(self, checked: bool) -> None:
        self._ctrl.set_setting("auto_connect_last_server", str(checked))

    def _on_font_size_changed(self, value: int) -> None:
        self._ctrl.set_setting("terminal_font_size", str(value))

    # ── Export / Import ───────────────────────────────────────

    def _on_export_all(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export All Servers", "servers.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            count = self._ctrl.export_to_file(path)
            QMessageBox.information(
                self, "Export", f"Exported {count} server(s) to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _on_export_selected(self) -> None:
        server = self._cm.active_server
        if server is None:
            QMessageBox.warning(
                self,
                "Export",
                "No remote server selected.\nSelect a server from the sidebar first.",
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {server.name}",
            f"{server.name}.json",
            "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            self._ctrl.export_to_file(path, server_ids=[server.id])
            QMessageBox.information(
                self, "Export", f"Exported '{server.name}' to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Servers", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            imported, skipped = self._ctrl.import_from_file(path)
            msg = f"Imported: {imported} server(s)"
            if skipped:
                msg += f"\nSkipped: {skipped} duplicate(s)"
            QMessageBox.information(self, "Import", msg)
            if imported > 0:
                self._server_ctrl.servers_changed.emit()
        except json.JSONDecodeError:
            QMessageBox.critical(
                self, "Import Error", "Invalid JSON file."
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    # ── Reset ─────────────────────────────────────────────────

    def _on_reset(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Reset App",
            "This will delete ALL data (servers, history, settings) "
            "and restart the application.\n\n"
            "Are you sure?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        reply2 = QMessageBox.warning(
            self,
            "Confirm Reset",
            "This action is IRREVERSIBLE.\n\n"
            "All data will be permanently deleted.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply2 != QMessageBox.StandardButton.Yes:
            return

        self._ctrl.reset_database()
        # Restart the application
        subprocess.Popen([sys.executable] + sys.argv)
        from PyQt6.QtWidgets import QApplication

        QApplication.instance().quit()

    # ── Desktop Integration ───────────────────────────────────

    def _on_browse_appimage(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select AppImage", "", "AppImage (*.AppImage);;All Files (*)"
        )
        if path:
            self._appimage_input.setText(path)

    def _on_add_to_menu(self) -> None:
        appimage_path = self._appimage_input.text().strip()
        if not appimage_path:
            QMessageBox.warning(
                self,
                "Desktop Integration",
                "Please specify the AppImage path first.",
            )
            return
        if not os.path.isfile(appimage_path):
            QMessageBox.warning(
                self,
                "Desktop Integration",
                f"File not found:\n{appimage_path}",
            )
            return
        try:
            self._ctrl.create_desktop_file(appimage_path)
            self._update_desktop_status()
            QMessageBox.information(
                self,
                "Desktop Integration",
                f"{APP_NAME} has been added to the application menu.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_remove_from_menu(self) -> None:
        if self._ctrl.remove_desktop_file():
            self._update_desktop_status()
            QMessageBox.information(
                self,
                "Desktop Integration",
                f"{APP_NAME} has been removed from the application menu.",
            )
        else:
            QMessageBox.information(
                self,
                "Desktop Integration",
                "Desktop file not found. Nothing to remove.",
            )

    def _update_desktop_status(self) -> None:
        if self._ctrl.desktop_file_exists():
            path = self._ctrl.desktop_file_path()
            self._desktop_status.setText(f"Status: Installed ({path})")
            self._desktop_status.setStyleSheet(
                "color: #89d185; font-size: 11px;"
            )
        else:
            self._desktop_status.setText("Status: Not installed")
            self._desktop_status.setStyleSheet(
                "color: #888888; font-size: 11px;"
            )
