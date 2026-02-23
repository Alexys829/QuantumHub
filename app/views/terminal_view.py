from __future__ import annotations

import html
import re
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QKeySequence,
    QShortcut,
    QTextCursor,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.database import Database

if TYPE_CHECKING:
    from app.controllers.terminal_controller import TerminalController
    from app.services.connection_manager import ConnectionManager
    from app.services.system_service import SystemService

# ── ANSI Color Parser ────────────────────────────────────────

_ANSI_RE = re.compile(r"\033\[([0-9;]*)m")

_ANSI_COLORS = {
    "30": "#1e1e1e", "31": "#f85149", "32": "#2ea043", "33": "#d29922",
    "34": "#58a6ff", "35": "#bc3fbc", "36": "#39c5cf", "37": "#cccccc",
    "90": "#6e7681", "91": "#ff7b72", "92": "#3fb950", "93": "#d2a82f",
    "94": "#79c0ff", "95": "#d2a8ff", "96": "#56d4dd", "97": "#ffffff",
}


def _build_style(fg: str | None, bg: str | None, bold: bool, italic: bool, underline: bool) -> str:
    parts = [f"color:{fg or '#00ff41'}"]
    if bold:
        parts.append("font-weight:bold")
    if italic:
        parts.append("font-style:italic")
    if underline:
        parts.append("text-decoration:underline")
    if bg:
        parts.append(f"background-color:{bg}")
    return ";".join(parts)


def ansi_to_html(text: str) -> str:
    """Convert ANSI escape codes to HTML spans.

    Every text segment gets an explicit inline color so we never
    depend on Qt CSS cascade (which ignores specificity).
    """
    escaped = html.escape(text)
    result: list[str] = []
    pos = 0
    fg: str | None = None
    bg: str | None = None
    bold = italic = underline = False

    for m in _ANSI_RE.finditer(escaped):
        seg = escaped[pos:m.start()]
        if seg:
            st = _build_style(fg, bg, bold, italic, underline)
            result.append(f'<span style="{st}">{seg}</span>')
        pos = m.end()

        codes = m.group(1).split(";") if m.group(1) else ["0"]
        for code in codes:
            code = code.lstrip("0") or "0"
            if code == "0" or code == "":
                fg = bg = None
                bold = italic = underline = False
            elif code == "1":
                bold = True
            elif code == "3":
                italic = True
            elif code == "4":
                underline = True
            elif code in _ANSI_COLORS:
                fg = _ANSI_COLORS[code]
            elif code.startswith("4") and len(code) == 2:
                bg_code = "3" + code[1]
                if bg_code in _ANSI_COLORS:
                    bg = _ANSI_COLORS[bg_code]

    seg = escaped[pos:]
    if seg:
        st = _build_style(fg, bg, bold, italic, underline)
        result.append(f'<span style="{st}">{seg}</span>')

    return "".join(result)


# ── TerminalInput (multi-line) ───────────────────────────────


class TerminalInput(QPlainTextEdit):
    """Multi-line input with history, tab completion, and auto-resize."""

    execute_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._history: list[str] = []
        self._history_idx = -1
        self._ctrl: TerminalController | None = None
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setTabChangesFocus(False)
        self.textChanged.connect(self._update_height)
        self._update_height()

    def set_controller(self, ctrl: TerminalController) -> None:
        self._ctrl = ctrl

    def set_history(self, cmds: list[str]) -> None:
        self._history = list(cmds)
        self._history_idx = -1

    def add_history(self, cmd: str) -> None:
        if cmd and (not self._history or self._history[-1] != cmd):
            self._history.append(cmd)
        self._history_idx = -1

    # ── QLineEdit-compatible API ──

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, t: str) -> None:
        self.setPlainText(t)
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(c)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._update_height()

    # ── Key handling ──

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()

        # Enter / Return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self.textCursor().insertText("\n")  # hard newline
            elif self.toPlainText().strip():
                self.execute_requested.emit()
            return

        # Up → history when on first line or single line
        if key == Qt.Key.Key_Up:
            cur = self.textCursor()
            if self.document().blockCount() == 1 or cur.blockNumber() == 0:
                if self._history:
                    if self._history_idx == -1:
                        self._history_idx = len(self._history) - 1
                    elif self._history_idx > 0:
                        self._history_idx -= 1
                    self.setText(self._history[self._history_idx])
                return
            # multi-line: move cursor normally
            super().keyPressEvent(event)
            return

        # Down → history when on last line or single line
        if key == Qt.Key.Key_Down:
            cur = self.textCursor()
            last = self.document().blockCount() - 1
            if self.document().blockCount() == 1 or cur.blockNumber() == last:
                if self._history_idx != -1:
                    if self._history_idx < len(self._history) - 1:
                        self._history_idx += 1
                        self.setText(self._history[self._history_idx])
                    else:
                        self._history_idx = -1
                        self.clear()
                return
            super().keyPressEvent(event)
            return

        # Tab → completion
        if key == Qt.Key.Key_Tab:
            if self._ctrl and self.toPlainText().strip():
                self._ctrl.tab_complete(self.toPlainText())
            return

        # Ctrl+C → cancel
        if key == Qt.Key.Key_C and (mods & Qt.KeyboardModifier.ControlModifier):
            if self._ctrl:
                self._ctrl.cancel_command()
            return

        super().keyPressEvent(event)

    # ── Auto-resize ──

    def _update_height(self) -> None:
        text = self.toPlainText()
        lines = max(1, text.count("\n") + 1)
        lines = min(lines, 5)
        lh = self.fontMetrics().lineSpacing()
        # border (2) + document margin (~8) + QSS padding (16)
        self.setFixedHeight(lines * lh + 26)


# ── Search Bar ───────────────────────────────────────────────


class SearchBar(QWidget):
    """Inline search bar for terminal output."""

    def __init__(self, text_edit: QTextEdit, parent=None):
        super().__init__(parent)
        self._text_edit = text_edit
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search...")
        self._input.setObjectName("terminalSearchInput")
        self._input.textChanged.connect(self._on_search)
        self._input.returnPressed.connect(self.find_next)
        layout.addWidget(self._input)

        prev_btn = QPushButton("Prev")
        prev_btn.setFixedHeight(28)
        prev_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        prev_btn.clicked.connect(self.find_prev)
        layout.addWidget(prev_btn)

        next_btn = QPushButton("Next")
        next_btn.setFixedHeight(28)
        next_btn.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        next_btn.clicked.connect(self.find_next)
        layout.addWidget(next_btn)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet("color: #888888; font-size: 11px; min-width: 60px;")
        layout.addWidget(self._count_lbl)

        close_btn = QPushButton("X")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("padding: 2px; font-size: 12px; font-weight: bold;")
        close_btn.clicked.connect(self.close_bar)
        layout.addWidget(close_btn)

    def toggle(self) -> None:
        if self.isVisible():
            self.close_bar()
        else:
            self.setVisible(True)
            self._input.setFocus()
            self._input.selectAll()

    def close_bar(self) -> None:
        self.setVisible(False)
        self._clear_highlights()
        self._count_lbl.setText("")

    def find_next(self) -> None:
        text = self._input.text()
        if text:
            self._text_edit.find(text)

    def find_prev(self) -> None:
        text = self._input.text()
        if text:
            from PyQt6.QtGui import QTextDocument
            self._text_edit.find(text, QTextDocument.FindFlag.FindBackward)

    def _on_search(self, text: str) -> None:
        self._clear_highlights()
        if not text:
            self._count_lbl.setText("")
            return
        self._highlight_all(text)

    def _highlight_all(self, text: str) -> None:
        selections = []
        doc = self._text_edit.document()
        cursor = QTextCursor(doc)

        while True:
            cursor = doc.find(text, cursor)
            if cursor.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor("#664d00"))
            sel.format.setForeground(QColor("#ffffff"))
            sel.cursor = cursor
            selections.append(sel)

        self._text_edit.setExtraSelections(selections)
        count = len(selections)
        self._count_lbl.setText(f"{count} found" if count else "No match")
        if count:
            self._text_edit.moveCursor(QTextCursor.MoveOperation.Start)
            self._text_edit.find(text)

    def _clear_highlights(self) -> None:
        self._text_edit.setExtraSelections([])

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_bar()
            return
        super().keyPressEvent(event)


# ── Zoom sizes ───────────────────────────────────────────────

_ZOOM_SIZES = [8, 9, 10, 11, 12, 13, 14, 16, 18, 20, 24]


# ── Terminal View ────────────────────────────────────────────


class TerminalView(QWidget):
    """Terminal emulator view with ANSI colors, search, tab completion, and more."""

    cwd_changed = pyqtSignal(str)

    def __init__(self, controller: "TerminalController", parent=None):
        super().__init__(parent)
        self._ctrl = controller
        self._font_size = 12
        self._prompt_str = "$"
        self._busy = False
        self._init_ui()
        self._connect_signals()

    @property
    def controller(self) -> "TerminalController":
        return self._ctrl

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ── Quick actions (from DB only) ───────────────────
        self._quick_row = QHBoxLayout()
        self._quick_row.setSpacing(4)
        layout.addLayout(self._quick_row)
        self._rebuild_quick_actions()

        # ── Search bar (hidden by default) ──────────────
        self._output = QTextEdit()
        self._search_bar = SearchBar(self._output, self)
        layout.addWidget(self._search_bar)

        # ── Output area ─────────────────────────────────
        self._output.setObjectName("terminalOutput")
        self._output.setReadOnly(True)
        self._output.document().setMaximumBlockCount(5000)
        self._output.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._output.customContextMenuRequested.connect(self._output_context_menu)
        layout.addWidget(self._output)

        # ── Input row ───────────────────────────────────
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._prompt_label = QLabel("$")
        self._prompt_label.setStyleSheet(
            "color: #00ff41; font-size: 12px; font-weight: bold; padding: 0 2px;"
        )
        input_row.addWidget(self._prompt_label, 0, Qt.AlignmentFlag.AlignTop)

        self._input = TerminalInput()
        self._input.set_controller(self._ctrl)
        self._input.setObjectName("terminalInput")
        self._input.setPlaceholderText("Type a command... (Shift+Enter for newline)")
        self._input.execute_requested.connect(self._on_execute)

        # Apply font after both output and input exist
        self._apply_font()
        input_row.addWidget(self._input)

        paste_btn = QPushButton("\U0001F4CB Paste")
        paste_btn.setStyleSheet("padding: 4px 10px; font-size: 11px;")
        paste_btn.clicked.connect(self._on_paste)
        input_row.addWidget(paste_btn, 0, Qt.AlignmentFlag.AlignTop)

        layout.addLayout(input_row)

        # ── Bottom bar ──────────────────────────────────
        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(8)

        info_btn = QPushButton("\u2139 Info")
        info_btn.setObjectName("terminalBottomBtn")
        info_btn.setFixedHeight(28)
        info_btn.clicked.connect(self._on_info)
        bottom_bar.addWidget(info_btn)

        clear_btn = QPushButton("\U0001F5D1 Clear")
        clear_btn.setObjectName("terminalBottomBtn")
        clear_btn.setFixedHeight(28)
        clear_btn.clicked.connect(self._on_clear)
        bottom_bar.addWidget(clear_btn)

        bottom_bar.addStretch()

        self._cwd_label = QLabel(f"cwd: {self._ctrl.cwd}")
        self._cwd_label.setStyleSheet("color: #888888; font-size: 11px;")
        bottom_bar.addWidget(self._cwd_label)

        bottom_bar.addStretch()

        # Zoom dropdown
        zoom_label = QLabel("Zoom:")
        zoom_label.setStyleSheet("color: #888888; font-size: 11px;")
        bottom_bar.addWidget(zoom_label)

        self._zoom_combo = QComboBox()
        self._zoom_combo.setObjectName("zoomCombo")
        for size in _ZOOM_SIZES:
            self._zoom_combo.addItem(f"{size}px", size)
        # Set default to 12
        default_idx = _ZOOM_SIZES.index(12)
        self._zoom_combo.setCurrentIndex(default_idx)
        self._zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        bottom_bar.addWidget(self._zoom_combo)

        layout.addLayout(bottom_bar)

        # ── Keyboard shortcuts ──────────────────────────
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self._search_bar.toggle)
        QShortcut(QKeySequence("Ctrl++"), self, activated=self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, activated=self._zoom_in)
        QShortcut(QKeySequence("Ctrl+-"), self, activated=self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self._zoom_reset)

    def _connect_signals(self) -> None:
        self._ctrl.command_output.connect(self._append_output)
        self._ctrl.command_error.connect(self._append_error)
        self._ctrl.cwd_changed.connect(self._on_cwd_changed)
        self._ctrl.prompt_changed.connect(self._on_prompt_changed)
        self._ctrl.sudo_password_needed.connect(self._on_sudo_password_needed)
        self._ctrl.command_started.connect(self._on_command_started)
        self._ctrl.command_finished.connect(self._on_command_finished)
        self._ctrl.completions_ready.connect(self._on_completions)
        self._ctrl.history_loaded.connect(self._on_history_loaded)

    # ── Execute ──────────────────────────────────────────

    def _on_execute(self) -> None:
        cmd = self._input.text().strip()
        if not cmd:
            return
        self._input.add_history(cmd)
        self._append_html(
            f'<span style="color:#00ff41;font-weight:bold">'
            f'{html.escape(self._prompt_str)} $ </span>'
            f'<span style="color:#e0e0e0">{html.escape(cmd)}</span>'
        )
        self._ctrl.execute_command(cmd)
        self._input.clear()

    def _run_quick(self, cmd: str) -> None:
        if self._busy:
            return
        self._input.setText(cmd)
        self._on_execute()

    def _rebuild_quick_actions(self) -> None:
        """Clear and rebuild quick action buttons from DB."""
        while self._quick_row.count():
            item = self._quick_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        for qc in Database.instance().get_quick_commands():
            btn = QPushButton(qc["label"])
            btn.setObjectName("quickAction")
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, c=qc["command"]: self._run_quick(c))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, b=btn, qid=qc["id"], qlbl=qc["label"], qcmd=qc["command"]: (
                    self._quick_cmd_context_menu(b, qid, qlbl, qcmd, pos)
                )
            )
            self._quick_row.addWidget(btn)

        add_btn = QPushButton("+")
        add_btn.setObjectName("quickAction")
        add_btn.setFixedHeight(26)
        add_btn.setFixedWidth(30)
        add_btn.setToolTip("Add custom command")
        add_btn.clicked.connect(self._add_quick_command)
        self._quick_row.addWidget(add_btn)

        self._quick_row.addStretch()

    def _add_quick_command(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Quick Command")
        dialog.setMinimumWidth(350)
        form = QFormLayout(dialog)

        label_input = QLineEdit()
        label_input.setPlaceholderText("e.g. Docker PS")
        form.addRow("Label:", label_input)

        cmd_input = QLineEdit()
        cmd_input.setPlaceholderText("e.g. docker ps -a")
        form.addRow("Command:", cmd_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            label = label_input.text().strip()
            cmd = cmd_input.text().strip()
            if label and cmd:
                Database.instance().add_quick_command(label, cmd)
                self._rebuild_quick_actions()

    def _quick_cmd_context_menu(
        self, btn: QPushButton, cmd_id: int, label: str, command: str, pos
    ) -> None:
        menu = QMenu(self)
        edit_action = menu.addAction("Edit")
        delete_action = menu.addAction("Delete")
        action = menu.exec(btn.mapToGlobal(pos))
        if action == edit_action:
            self._edit_quick_command(cmd_id, label, command)
        elif action == delete_action:
            reply = QMessageBox.question(
                self,
                "Delete Quick Command",
                f'Delete "{label}"?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                Database.instance().delete_quick_command(cmd_id)
                self._rebuild_quick_actions()

    def _edit_quick_command(self, cmd_id: int, old_label: str, old_command: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Quick Command")
        dialog.setMinimumWidth(350)
        form = QFormLayout(dialog)

        label_input = QLineEdit(old_label)
        form.addRow("Label:", label_input)

        cmd_input = QLineEdit(old_command)
        form.addRow("Command:", cmd_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            label = label_input.text().strip()
            cmd = cmd_input.text().strip()
            if label and cmd:
                Database.instance().update_quick_command(cmd_id, label, cmd)
                self._rebuild_quick_actions()

    # ── Output helpers ───────────────────────────────────

    def _append_html(self, html_str: str) -> None:
        self._output.append(html_str)
        self._output.verticalScrollBar().setValue(
            self._output.verticalScrollBar().maximum()
        )

    def _append_output(self, text: str) -> None:
        lines = text.split("\n")
        for line in lines:
            self._append_html(
                f'<pre style="margin:0;white-space:pre-wrap">{ansi_to_html(line)}</pre>'
            )

    def _append_error(self, text: str) -> None:
        self._append_html(
            f'<span style="color:#f85149;font-weight:bold">[ERROR] '
            f'{html.escape(text)}</span>'
        )

    # ── Busy state ───────────────────────────────────────

    def _on_command_started(self) -> None:
        self._busy = True
        self._input.setEnabled(False)
        self._prompt_label.setText("\u23F3")
        self._prompt_label.setStyleSheet(
            "color: #d29922; font-size: 12px; font-weight: bold; padding: 0 2px;"
        )

    def _on_command_finished(self) -> None:
        self._busy = False
        self._input.setEnabled(True)
        self._input.setFocus()
        self._prompt_label.setText("$")
        self._prompt_label.setStyleSheet(
            "color: #00ff41; font-size: 12px; font-weight: bold; padding: 0 2px;"
        )

    # ── Prompt / CWD ─────────────────────────────────────

    def _on_cwd_changed(self, cwd: str) -> None:
        self._cwd_label.setText(f"cwd: {cwd}")
        self.cwd_changed.emit(cwd)

    def _on_prompt_changed(self, prompt: str) -> None:
        self._prompt_str = prompt

    # ── Tab Completion ───────────────────────────────────

    def _on_completions(self, completions: list[str]) -> None:
        if not completions:
            return
        if len(completions) == 1:
            # Auto-complete: replace the last word
            text = self._input.text()
            parts = text.rsplit(None, 1)
            if len(parts) > 1:
                self._input.setText(f"{parts[0]} {completions[0]}")
            else:
                self._input.setText(completions[0])
        else:
            # Show all completions in output
            cols = "   ".join(completions[:50])
            self._append_html(
                f'<span style="color:#888888">{html.escape(cols)}</span>'
            )

    # ── Persistent History ───────────────────────────────

    def _on_history_loaded(self, cmds: list[str]) -> None:
        self._input.set_history(cmds)

    # ── Zoom ─────────────────────────────────────────────

    def _on_zoom_changed(self, index: int) -> None:
        size = self._zoom_combo.itemData(index)
        if size is not None:
            self._font_size = size
            self._apply_font()

    def _zoom_in(self) -> None:
        idx = self._zoom_combo.currentIndex()
        if idx < self._zoom_combo.count() - 1:
            self._zoom_combo.setCurrentIndex(idx + 1)

    def _zoom_out(self) -> None:
        idx = self._zoom_combo.currentIndex()
        if idx > 0:
            self._zoom_combo.setCurrentIndex(idx - 1)

    def _zoom_reset(self) -> None:
        default_idx = _ZOOM_SIZES.index(12)
        self._zoom_combo.setCurrentIndex(default_idx)

    def _apply_font(self) -> None:
        mono = QFont("JetBrains Mono", self._font_size)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._output.setFont(mono)
        self._input.setFont(mono)

    # ── Paste / Other ─────────────────────────────────────

    def _on_paste(self) -> None:
        self._input.paste()
        self._input.setFocus()

    def _on_info(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Terminal - Info")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(
            "<h3>Keyboard Shortcuts</h3>"
            "<table cellpadding='4'>"
            "<tr><td><b>Enter</b></td><td>Execute command</td></tr>"
            "<tr><td><b>Shift+Enter</b></td><td>New line (multi-line input)</td></tr>"
            "<tr><td><b>Up / Down</b></td><td>Command history</td></tr>"
            "<tr><td><b>Tab</b></td><td>File/directory autocomplete</td></tr>"
            "<tr><td><b>Ctrl+C</b></td><td>Cancel running command</td></tr>"
            "<tr><td><b>Ctrl+F</b></td><td>Search in output</td></tr>"
            "<tr><td><b>Ctrl+V</b></td><td>Paste from clipboard</td></tr>"
            "<tr><td><b>Ctrl+Plus</b></td><td>Zoom in</td></tr>"
            "<tr><td><b>Ctrl+Minus</b></td><td>Zoom out</td></tr>"
            "<tr><td><b>Ctrl+0</b></td><td>Reset zoom</td></tr>"
            "</table>"
            "<h3>Tabs</h3>"
            "<ul>"
            "<li><b>+</b> button &mdash; open a new terminal tab</li>"
            "<li><b>Right-click</b> on tab &mdash; Rename, Detach or Close</li>"
            "<li><b>Detach</b> &mdash; move tab to a floating window</li>"
            "<li>Close the floating window to reattach the tab</li>"
            "</ul>"
            "<h3>Quick Commands</h3>"
            "<ul>"
            "<li>Click a quick command button to execute it</li>"
            "<li><b>+</b> button &mdash; add a new custom command</li>"
            "<li><b>Right-click</b> on any command &mdash; Edit or Delete</li>"
            "</ul>"
            "<h3>Sudo</h3>"
            "<ul>"
            "<li>SSH password is used automatically for sudo</li>"
            "<li>If the password is wrong or missing, a popup appears</li>"
            "<li>NOPASSWD sudoers rules are detected automatically</li>"
            "</ul>"
            "<h3>Features</h3>"
            "<ul>"
            "<li><b>Multi-tab</b> &mdash; independent terminal sessions</li>"
            "<li><b>Detachable tabs</b> &mdash; floating windows</li>"
            "<li><b>Multi-line input</b> &mdash; Shift+Enter for new lines</li>"
            "<li><b>Persistent history</b> &mdash; saved per server</li>"
            "<li><b>Tab completion</b> &mdash; file/directory autocomplete</li>"
            "<li><b>Search</b> &mdash; Ctrl+F to find text in output</li>"
            "<li><b>Zoom</b> &mdash; dropdown or Ctrl+/- shortcuts</li>"
            "<li><b>ANSI colors</b> &mdash; use <code>--color=always</code></li>"
            "</ul>"
        )
        msg.exec()

    def _on_clear(self) -> None:
        self._output.clear()

    def _output_context_menu(self, pos) -> None:
        menu = self._output.createStandardContextMenu()
        selected = self._output.textCursor().selectedText().strip()
        if selected:
            menu.addSeparator()
            run_action = menu.addAction("\u25B6  Run in Terminal")
            run_action.triggered.connect(lambda: self._run_selected(selected))
        menu.exec(self._output.viewport().mapToGlobal(pos))

    def _run_selected(self, text: str) -> None:
        cmd = text.replace("\u2029", "\n").strip()
        if cmd and not self._busy:
            self._input.setText(cmd)
            self._on_execute()

    def _on_sudo_password_needed(self, pending_cmd: str) -> None:
        password, ok = QInputDialog.getText(
            self,
            "sudo",
            "Password required for sudo:",
            QLineEdit.EchoMode.Password,
        )
        if ok and password:
            self._ctrl.set_sudo_password(password)
            self._ctrl.execute_command(pending_cmd)
        else:
            self._append_error("sudo: password not provided, command cancelled")


# ── Detached Terminal Window ─────────────────────────────────


class DetachedTerminal(QMainWindow):
    """Floating window for a detached terminal tab."""

    reattach_requested = pyqtSignal(object)

    def __init__(
        self,
        view: TerminalView,
        controller: "TerminalController",
        tab_widget: "TerminalTabWidget",
        title: str = "Terminal",
    ):
        super().__init__()
        self._view = view
        self._controller = controller
        self._tab_widget = tab_widget
        self.setWindowTitle(f"\U0001F4BB {title}")
        self.setMinimumSize(700, 450)
        self.resize(900, 550)
        self.setCentralWidget(view)
        view.show()
        self.reattach_requested.connect(tab_widget.reattach)

    @property
    def view(self) -> TerminalView:
        return self._view

    @property
    def controller(self) -> "TerminalController":
        return self._controller

    def closeEvent(self, event):
        self.reattach_requested.emit(self)
        event.ignore()


# ── Multi-Tab Terminal Widget ────────────────────────────────


class TerminalTabWidget(QWidget):
    """Container with a QTabWidget holding multiple TerminalView instances."""

    def __init__(
        self,
        system_service: "SystemService",
        connection_manager: "ConnectionManager",
        parent=None,
    ):
        super().__init__(parent)
        self._sys = system_service
        self._cm = connection_manager
        self._tab_counter = 0
        self._detached_windows: list[DetachedTerminal] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setObjectName("terminalTabs")
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.tabCloseRequested.connect(self.close_tab)

        # Style the tab bar
        tab_bar = self._tabs.tabBar()
        tab_bar.setObjectName("terminalTabBar")
        tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tab_bar.customContextMenuRequested.connect(self._tab_context_menu)

        # "+" corner button to add new tabs
        add_btn = QPushButton(" + ")
        add_btn.setObjectName("terminalAddTab")
        add_btn.setFixedHeight(26)
        add_btn.setToolTip("New terminal tab")
        add_btn.clicked.connect(self.add_tab)
        self._tabs.setCornerWidget(add_btn, Qt.Corner.TopRightCorner)

        layout.addWidget(self._tabs)

        # Create first tab
        self.add_tab()

    def add_tab(self) -> int:
        """Create a new terminal tab and return its index."""
        from app.controllers.terminal_controller import TerminalController

        self._tab_counter += 1
        title = f"Terminal {self._tab_counter}"

        ctrl = TerminalController(self._sys, self._cm, self)
        view = TerminalView(ctrl, self)
        ctrl.reset_session()

        idx = self._tabs.addTab(view, title)
        self._tabs.setCurrentIndex(idx)
        return idx

    def close_tab(self, index: int) -> None:
        """Close a tab (only if more than one tab remains)."""
        if self._tabs.count() <= 1:
            return
        view: TerminalView = self._tabs.widget(index)
        self._tabs.removeTab(index)
        view.deleteLater()

    def detach_tab(self, index: int) -> None:
        """Detach a tab into a floating window."""
        if self._tabs.count() <= 1:
            return
        view: TerminalView = self._tabs.widget(index)
        title = self._tabs.tabText(index)
        ctrl = view.controller
        self._tabs.removeTab(index)

        window = DetachedTerminal(view, ctrl, self, title)
        self._detached_windows.append(window)
        window.show()

    def reattach(self, window: DetachedTerminal) -> None:
        """Reattach a detached terminal window as a tab."""
        view = window.view
        title = window.windowTitle().replace("\U0001F4BB ", "")

        if window in self._detached_windows:
            self._detached_windows.remove(window)
        # Disconnect before closing so closeEvent doesn't re-trigger reattach
        window.reattach_requested.disconnect()

        # Take the central widget away before closing the window
        window.takeCentralWidget()
        window.close()
        window.deleteLater()

        # Re-parent into tab widget and show
        view.setParent(self._tabs)
        idx = self._tabs.addTab(view, title)
        self._tabs.setCurrentIndex(idx)
        view.show()

    def reset_all_sessions(self) -> None:
        """Reset sessions in all tabs and detached windows."""
        for i in range(self._tabs.count()):
            view: TerminalView = self._tabs.widget(i)
            view.controller.reset_session()
        for window in self._detached_windows:
            window.controller.reset_session()

    def _tab_context_menu(self, pos) -> None:
        """Right-click menu on tab bar."""
        tab_bar = self._tabs.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return

        menu = QMenu(self)
        rename_action = menu.addAction("Rename")
        detach_action = menu.addAction("Detach")
        close_action = menu.addAction("Close")

        if self._tabs.count() <= 1:
            detach_action.setEnabled(False)
            close_action.setEnabled(False)

        action = menu.exec(tab_bar.mapToGlobal(pos))
        if action == rename_action:
            self._rename_tab(index)
        elif action == detach_action:
            self.detach_tab(index)
        elif action == close_action:
            self.close_tab(index)

    def _rename_tab(self, index: int) -> None:
        old_title = self._tabs.tabText(index)
        new_title, ok = QInputDialog.getText(
            self, "Rename Tab", "New name:", text=old_title,
        )
        if ok and new_title.strip():
            self._tabs.setTabText(index, new_title.strip())
