from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.controllers.users_controller import UsersController
from app.views.toast import show_toast


# ── Dialogs ────────────────────────────────────────────────────────


class _AddUserDialog(QDialog):
    """Dialog to add a new system user."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._username = QLineEdit()
        self._username.setPlaceholderText("username")
        self._home = QLineEdit()
        self._home.setPlaceholderText("/home/username (optional)")
        self._shell = QComboBox()
        self._shell.addItems(["/bin/bash", "/bin/sh", "/bin/zsh", "/usr/sbin/nologin"])
        self._shell.setEditable(True)
        self._groups = QLineEdit()
        self._groups.setPlaceholderText("group1,group2 (optional)")

        form.addRow("Username:", self._username)
        form.addRow("Home:", self._home)
        form.addRow("Shell:", self._shell)
        form.addRow("Groups:", self._groups)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "username": self._username.text().strip(),
            "home": self._home.text().strip() or None,
            "shell": self._shell.currentText().strip() or None,
            "groups": self._groups.text().strip() or None,
        }


class _EditUserDialog(QDialog):
    """Dialog to modify an existing user (shell, groups)."""

    def __init__(self, user: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit User — {user['username']}")
        self.setMinimumWidth(400)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._shell = QComboBox()
        self._shell.addItems(["/bin/bash", "/bin/sh", "/bin/zsh", "/usr/sbin/nologin"])
        self._shell.setEditable(True)
        self._shell.setCurrentText(user.get("shell", "/bin/bash"))

        self._groups = QLineEdit()
        self._groups.setPlaceholderText("group1,group2 (optional)")

        form.addRow("Shell:", self._shell)
        form.addRow("Groups:", self._groups)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        return {
            "shell": self._shell.currentText().strip() or None,
            "groups": self._groups.text().strip() or None,
        }


class _ChangePasswordDialog(QDialog):
    """Dialog to change a user's password."""

    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Change Password — {username}")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("New password")
        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm.setPlaceholderText("Confirm password")

        form.addRow("Password:", self._password)
        form.addRow("Confirm:", self._confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self._password.text():
            QMessageBox.warning(self, "Validation", "Password cannot be empty.")
            return
        if self._password.text() != self._confirm.text():
            QMessageBox.warning(self, "Validation", "Passwords do not match.")
            return
        self.accept()

    def get_password(self) -> str:
        return self._password.text()


class _AddGroupDialog(QDialog):
    """Dialog to add a new group."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Group")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name = QLineEdit()
        self._name.setPlaceholderText("groupname")
        self._gid = QSpinBox()
        self._gid.setRange(0, 65534)
        self._gid.setSpecialValueText("Auto")
        self._gid.setValue(0)

        form.addRow("Name:", self._name)
        form.addRow("GID:", self._gid)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self) -> dict:
        gid = self._gid.value() if self._gid.value() > 0 else None
        return {"name": self._name.text().strip(), "gid": gid}


class _EditGroupDialog(QDialog):
    """Dialog to modify an existing group (rename, change GID)."""

    def __init__(self, group: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Group — {group['name']}")
        self.setMinimumWidth(350)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._new_name = QLineEdit()
        self._new_name.setText(group["name"])
        self._new_name.setPlaceholderText("New name (leave unchanged to keep)")

        self._gid = QSpinBox()
        self._gid.setRange(0, 65534)
        self._gid.setSpecialValueText("Unchanged")
        self._gid.setValue(0)

        form.addRow("Name:", self._new_name)
        form.addRow("GID:", self._gid)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._original_name = group["name"]

    def get_data(self) -> dict:
        new_name = self._new_name.text().strip()
        if new_name == self._original_name:
            new_name = None
        gid = self._gid.value() if self._gid.value() > 0 else None
        return {"new_name": new_name, "gid": gid}


class _GroupMemberDialog(QDialog):
    """Dialog to add/remove a user to/from a group."""

    def __init__(self, title: str, label: str, users: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(300)
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._user_combo = QComboBox()
        self._user_combo.setEditable(True)
        self._user_combo.addItems(users)
        form.addRow(label, self._user_combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_username(self) -> str:
        return self._user_combo.currentText().strip()


# ── View ───────────────────────────────────────────────────────────


class UsersView(QWidget):
    """Users and Groups management view."""

    USER_COLUMNS = ["Username", "UID", "GID", "Home", "Shell", "GECOS"]
    GROUP_COLUMNS = ["Name", "GID", "Members"]

    def __init__(self, controller: UsersController, parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._init_ui()
        self._connect_signals()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        header = QPushButton("\U0001F465  Users & Groups")
        header.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #e0e0e0;"
            "background: transparent; border: none; text-align: left; padding: 0;"
        )
        header.setEnabled(False)
        layout.addWidget(header)

        # Tabs
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # ── Users tab ──────────────────────────────────────────
        users_widget = QWidget()
        users_layout = QVBoxLayout(users_widget)
        users_layout.setContentsMargins(0, 8, 0, 0)

        users_toolbar = QHBoxLayout()
        users_toolbar.setSpacing(6)
        self._add_user_btn = QPushButton("\u2795  Add User")
        self._add_user_btn.clicked.connect(self._on_add_user)
        self._edit_user_btn = QPushButton("\u270F  Edit")
        self._edit_user_btn.clicked.connect(self._on_edit_user)
        self._passwd_btn = QPushButton("\U0001F511  Password")
        self._passwd_btn.clicked.connect(self._on_change_password)
        self._del_user_btn = QPushButton("\U0001F5D1  Delete")
        self._del_user_btn.clicked.connect(self._on_delete_user)
        self._refresh_users_btn = QPushButton("\U0001F504  Refresh")
        self._refresh_users_btn.clicked.connect(self._ctrl.refresh_users)
        users_toolbar.addWidget(self._add_user_btn)
        users_toolbar.addWidget(self._edit_user_btn)
        users_toolbar.addWidget(self._passwd_btn)
        users_toolbar.addWidget(self._del_user_btn)
        users_toolbar.addWidget(self._refresh_users_btn)
        users_toolbar.addStretch()
        users_layout.addLayout(users_toolbar)

        self._user_table = QTableWidget()
        self._user_table.setColumnCount(len(self.USER_COLUMNS))
        self._user_table.setHorizontalHeaderLabels(self.USER_COLUMNS)
        self._user_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._user_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._user_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._user_table.horizontalHeader().setStretchLastSection(True)
        self._user_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._user_table.setAlternatingRowColors(True)
        self._user_table.verticalHeader().setVisible(False)
        self._user_table.setShowGrid(False)
        self._user_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._user_table.customContextMenuRequested.connect(self._show_user_context_menu)
        users_layout.addWidget(self._user_table)
        self._tabs.addTab(users_widget, "\U0001F464  Users")

        # ── Groups tab ─────────────────────────────────────────
        groups_widget = QWidget()
        groups_layout = QVBoxLayout(groups_widget)
        groups_layout.setContentsMargins(0, 8, 0, 0)

        groups_toolbar = QHBoxLayout()
        groups_toolbar.setSpacing(6)
        self._add_group_btn = QPushButton("\u2795  Add Group")
        self._add_group_btn.clicked.connect(self._on_add_group)
        self._edit_group_btn = QPushButton("\u270F  Edit")
        self._edit_group_btn.clicked.connect(self._on_edit_group)
        self._del_group_btn = QPushButton("\U0001F5D1  Delete")
        self._del_group_btn.clicked.connect(self._on_delete_group)
        self._add_member_btn = QPushButton("\U0001F464+  Add Member")
        self._add_member_btn.clicked.connect(self._on_add_member)
        self._rm_member_btn = QPushButton("\U0001F464\u2212  Remove Member")
        self._rm_member_btn.clicked.connect(self._on_remove_member)
        self._refresh_groups_btn = QPushButton("\U0001F504  Refresh")
        self._refresh_groups_btn.clicked.connect(self._ctrl.refresh_groups)
        groups_toolbar.addWidget(self._add_group_btn)
        groups_toolbar.addWidget(self._edit_group_btn)
        groups_toolbar.addWidget(self._del_group_btn)
        groups_toolbar.addWidget(self._add_member_btn)
        groups_toolbar.addWidget(self._rm_member_btn)
        groups_toolbar.addWidget(self._refresh_groups_btn)
        groups_toolbar.addStretch()
        groups_layout.addLayout(groups_toolbar)

        self._group_table = QTableWidget()
        self._group_table.setColumnCount(len(self.GROUP_COLUMNS))
        self._group_table.setHorizontalHeaderLabels(self.GROUP_COLUMNS)
        self._group_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._group_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._group_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._group_table.horizontalHeader().setStretchLastSection(True)
        self._group_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._group_table.setAlternatingRowColors(True)
        self._group_table.verticalHeader().setVisible(False)
        self._group_table.setShowGrid(False)
        self._group_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._group_table.customContextMenuRequested.connect(self._show_group_context_menu)
        groups_layout.addWidget(self._group_table)
        self._tabs.addTab(groups_widget, "\U0001F465  Groups")

        self._users: list[dict] = []
        self._groups: list[dict] = []

    def _connect_signals(self) -> None:
        self._ctrl.users_loaded.connect(self._populate_users)
        self._ctrl.groups_loaded.connect(self._populate_groups)
        self._ctrl.operation_success.connect(
            lambda msg: show_toast(self.window(), msg)
        )
        self._ctrl.operation_error.connect(
            lambda msg: QMessageBox.warning(self, "Error", msg)
        )

    # ── Populate tables ────────────────────────────────────────

    def _populate_users(self, users: list[dict]) -> None:
        self._users = users
        self._user_table.setRowCount(len(users))
        for row, u in enumerate(users):
            self._user_table.setItem(row, 0, QTableWidgetItem(u["username"]))
            self._user_table.setItem(row, 1, QTableWidgetItem(str(u["uid"])))
            self._user_table.setItem(row, 2, QTableWidgetItem(str(u["gid"])))
            self._user_table.setItem(row, 3, QTableWidgetItem(u["home"]))
            self._user_table.setItem(row, 4, QTableWidgetItem(u["shell"]))
            self._user_table.setItem(row, 5, QTableWidgetItem(u["gecos"]))
        self._user_table.resizeColumnsToContents()

    def _populate_groups(self, groups: list[dict]) -> None:
        self._groups = groups
        self._group_table.setRowCount(len(groups))
        for row, g in enumerate(groups):
            self._group_table.setItem(row, 0, QTableWidgetItem(g["name"]))
            self._group_table.setItem(row, 1, QTableWidgetItem(str(g["gid"])))
            self._group_table.setItem(row, 2, QTableWidgetItem(g["members"]))
        self._group_table.resizeColumnsToContents()

    # ── Helpers ────────────────────────────────────────────────

    def _selected_user(self) -> dict | None:
        row = self._user_table.currentRow()
        if row < 0 or row >= len(self._users):
            return None
        return self._users[row]

    def _selected_group(self) -> dict | None:
        row = self._group_table.currentRow()
        if row < 0 or row >= len(self._groups):
            return None
        return self._groups[row]

    def _user_names(self) -> list[str]:
        return [u["username"] for u in self._users]

    # ── User actions ───────────────────────────────────────────

    def _on_add_user(self) -> None:
        dialog = _AddUserDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["username"]:
                self._ctrl.add_user(**data)
            else:
                QMessageBox.warning(self, "Validation", "Username is required.")

    def _on_edit_user(self) -> None:
        user = self._selected_user()
        if not user:
            return
        dialog = _EditUserDialog(user, self)
        if dialog.exec():
            data = dialog.get_data()
            if data["shell"] or data["groups"]:
                self._ctrl.modify_user(user["username"], **data)

    def _on_change_password(self) -> None:
        user = self._selected_user()
        if not user:
            return
        dialog = _ChangePasswordDialog(user["username"], self)
        if dialog.exec():
            self._ctrl.change_password(user["username"], dialog.get_password())

    def _on_delete_user(self) -> None:
        user = self._selected_user()
        if not user:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Delete user '{user['username']}'?\nThis requires sudo."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_user(user["username"], remove_home=False)

    # ── Group actions ──────────────────────────────────────────

    def _on_add_group(self) -> None:
        dialog = _AddGroupDialog(self)
        if dialog.exec():
            data = dialog.get_data()
            if data["name"]:
                self._ctrl.add_group(**data)
            else:
                QMessageBox.warning(self, "Validation", "Group name is required.")

    def _on_edit_group(self) -> None:
        group = self._selected_group()
        if not group:
            return
        dialog = _EditGroupDialog(group, self)
        if dialog.exec():
            data = dialog.get_data()
            if data["new_name"] or data["gid"]:
                self._ctrl.modify_group(group["name"], **data)

    def _on_delete_group(self) -> None:
        group = self._selected_group()
        if not group:
            return
        reply = QMessageBox.question(
            self, "Confirm", f"Delete group '{group['name']}'?\nThis requires sudo."
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._ctrl.delete_group(group["name"])

    def _on_add_member(self) -> None:
        group = self._selected_group()
        if not group:
            return
        dialog = _GroupMemberDialog(
            f"Add Member to '{group['name']}'",
            "User:",
            self._user_names(),
            self,
        )
        if dialog.exec():
            username = dialog.get_username()
            if username:
                self._ctrl.add_user_to_group(username, group["name"])

    def _on_remove_member(self) -> None:
        group = self._selected_group()
        if not group:
            return
        members = [m.strip() for m in group["members"].split(",") if m.strip()]
        if not members:
            QMessageBox.information(self, "Info", "This group has no members.")
            return
        dialog = _GroupMemberDialog(
            f"Remove Member from '{group['name']}'",
            "User:",
            members,
            self,
        )
        if dialog.exec():
            username = dialog.get_username()
            if username:
                self._ctrl.remove_user_from_group(username, group["name"])

    # ── Context menus ──────────────────────────────────────────

    def _show_user_context_menu(self, pos) -> None:
        if self._user_table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u270F  Edit User", self, triggered=self._on_edit_user))
        menu.addAction(QAction("\U0001F511  Change Password", self, triggered=self._on_change_password))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Delete User", self, triggered=self._on_delete_user))
        menu.exec(self._user_table.viewport().mapToGlobal(pos))

    def _show_group_context_menu(self, pos) -> None:
        if self._group_table.currentRow() < 0:
            return
        menu = QMenu(self)
        menu.addAction(QAction("\u270F  Edit Group", self, triggered=self._on_edit_group))
        menu.addAction(QAction("\U0001F464+  Add Member", self, triggered=self._on_add_member))
        menu.addAction(QAction("\U0001F464\u2212  Remove Member", self, triggered=self._on_remove_member))
        menu.addSeparator()
        menu.addAction(QAction("\U0001F5D1  Delete Group", self, triggered=self._on_delete_group))
        menu.exec(self._group_table.viewport().mapToGlobal(pos))
