"""AutoHotkey-style automation editor: hotkeys, hotstrings and .ahk import."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QTabWidget, QWidget, QPlainTextEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QFileDialog, QMessageBox
)

from services.automation_service import ACTIONS, ACTION_INFO, action_label, parse_ahk
from services.hotkey_service import parse_hotkey
from styles import dialog_style

_QT_MODS = [(Qt.KeyboardModifier.ControlModifier, "Ctrl"), (Qt.KeyboardModifier.AltModifier, "Alt"),
            (Qt.KeyboardModifier.ShiftModifier, "Shift"), (Qt.KeyboardModifier.MetaModifier, "Win")]
_MOD_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta,
             Qt.Key.Key_AltGr, Qt.Key.Key_Super_L, Qt.Key.Key_Super_R}


class HotkeyEdit(QLineEdit):
    """Click, then press the shortcut. Backspace/Delete alone clears it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Click here and press a shortcut…")
        self.setReadOnly(True)

    def keyPressEvent(self, event):
        key = event.key()
        mods = event.modifiers()
        if key in _MOD_KEYS:
            return
        names = [name for flag, name in _QT_MODS if mods & flag]
        if not names and key in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete, Qt.Key.Key_Escape):
            self.clear()
            return
        key_name = QKeySequence(key).toString(QKeySequence.SequenceFormat.PortableText)
        if not key_name:
            return
        key_name = key_name.replace(" ", "_")
        self.setText("+".join(names + [key_name]))


class MacroEditor(QDialog):
    def __init__(self, theme, macro=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit automation")
        self.setStyleSheet(dialog_style(theme))
        self.setMinimumWidth(460)
        macro = dict(macro or {"name": "", "hotkey": "", "action": "run", "arg": "", "enabled": True})
        self.macro = macro

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Name"))
        self.name = QLineEdit(macro.get("name", ""))
        lay.addWidget(self.name)

        lay.addWidget(QLabel("Hotkey (optional — you can also run it from the island)"))
        hk_row = QHBoxLayout()
        self.hotkey = HotkeyEdit()
        self.hotkey.setText(macro.get("hotkey", ""))
        hk_row.addWidget(self.hotkey, 1)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.hotkey.clear)
        hk_row.addWidget(clear)
        lay.addLayout(hk_row)

        lay.addWidget(QLabel("Action"))
        self.action = QComboBox()
        group = None
        for key, label, grp, _ in ACTIONS:
            if grp != group:
                if group is not None:
                    self.action.insertSeparator(self.action.count())
                group = grp
            self.action.addItem(f"{grp} · {label}", key)
        idx = self.action.findData(macro.get("action", "run"))
        self.action.setCurrentIndex(max(0, idx))
        self.action.currentIndexChanged.connect(self._on_action)
        lay.addWidget(self.action)

        self.arg_label = QLabel()
        self.arg_label.setWordWrap(True)
        lay.addWidget(self.arg_label)
        arg_row = QHBoxLayout()
        self.arg = QPlainTextEdit(str(macro.get("arg", "")))
        self.arg.setFixedHeight(70)
        arg_row.addWidget(self.arg, 1)
        self.browse = QPushButton("Browse…")
        self.browse.clicked.connect(self._browse)
        arg_row.addWidget(self.browse, alignment=Qt.AlignmentFlag.AlignTop)
        lay.addLayout(arg_row)

        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(macro.get("enabled", True))
        lay.addWidget(self.enabled)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        lay.addLayout(btns)
        self._on_action()

    def _on_action(self):
        key = self.action.currentData()
        hint = ACTION_INFO.get(key, ("", "", None))[2]
        self.arg_label.setText(hint or "No argument needed.")
        self.arg.setEnabled(hint is not None)
        self.browse.setVisible(key in ("run", "ahk"))

    def _browse(self):
        filt = "AutoHotkey scripts (*.ahk);;All files (*)" if self.action.currentData() == "ahk" else "All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Choose file", "", filt)
        if path:
            self.arg.setPlainText(path)

    def _accept(self):
        hotkey = self.hotkey.text().strip()
        if hotkey and parse_hotkey(hotkey) is None:
            QMessageBox.warning(self, "Invalid hotkey",
                                f"'{hotkey}' can't be used as a global hotkey.\n"
                                "Letters, digits and Space need Ctrl, Alt, Shift or Win.")
            return
        key = self.action.currentData()
        name = self.name.text().strip() or action_label(key)
        self.macro = {"name": name, "hotkey": hotkey, "action": key,
                      "arg": self.arg.toPlainText() if self.arg.isEnabled() else "",
                      "enabled": self.enabled.isChecked()}
        self.accept()


class AutomationDialog(QDialog):
    def __init__(self, theme, automation_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.service = automation_service
        self.macros = [dict(m) for m in automation_service.macros]
        self.hotstrings = [dict(h) for h in automation_service.hotstrings]

        self.setWindowTitle("Automations — hotkeys, hotstrings & AutoHotkey")
        self.resize(720, 520)
        self.setStyleSheet(dialog_style(theme))

        lay = QVBoxLayout(self)
        title = QLabel("⌨️ Automations")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme['accent']};")
        lay.addWidget(title)
        sub = QLabel("AutoHotkey-style shortcuts that work in every app. "
                     "Hotkeys run actions; hotstrings expand text as you type.")
        sub.setStyleSheet(f"color: {theme['text_secondary']};")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_hotkeys_tab(), "⌨️ Hotkeys")
        self.tabs.addTab(self._build_hotstrings_tab(), "✍️ Hotstrings")
        self.tabs.addTab(self._build_import_tab(), "📥 Import .ahk")
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setStyleSheet(f"background: {theme['accent']}; color: {theme['bg_color']}; border: none;")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)

        self._fill_macros()
        self._fill_hotstrings()

    # ----------------------------------------------------------- Hotkeys
    def _build_hotkeys_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.macro_table = QTableWidget(0, 4)
        self.macro_table.setHorizontalHeaderLabels(["On", "Name", "Hotkey", "Action"])
        hdr = self.macro_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.macro_table.verticalHeader().setVisible(False)
        self.macro_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.macro_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.macro_table.cellDoubleClicked.connect(lambda r, c: self._edit_macro(r))
        self.macro_table.itemChanged.connect(self._on_macro_item_changed)
        lay.addWidget(self.macro_table)

        row = QHBoxLayout()
        for text, fn in (("＋ Add", self._add_macro), ("Edit", lambda: self._edit_macro(self.macro_table.currentRow())),
                         ("Delete", self._delete_macro), ("▶ Test run", self._test_macro)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.macro_status = QLabel("")
        self.macro_status.setStyleSheet(f"color: {self.theme['warning']};")
        row.addWidget(self.macro_status)
        lay.addLayout(row)
        return w

    def _fill_macros(self):
        self.macro_table.blockSignals(True)
        self.macro_table.setRowCount(len(self.macros))
        for r, m in enumerate(self.macros):
            on = QTableWidgetItem()
            on.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            on.setCheckState(Qt.CheckState.Checked if m.get("enabled", True) else Qt.CheckState.Unchecked)
            self.macro_table.setItem(r, 0, on)
            self.macro_table.setItem(r, 1, QTableWidgetItem(m.get("name", "")))
            hk = m.get("hotkey", "") or "—"
            err = self.service.status.get(m.get("hotkey", ""))
            hk_item = QTableWidgetItem(("⚠️ " if err else "") + hk)
            if err:
                hk_item.setToolTip(err)
            self.macro_table.setItem(r, 2, hk_item)
            arg = str(m.get("arg", "") or "").replace("\n", " ")
            desc = action_label(m.get("action", "")) + (f": {arg[:40]}" if arg else "")
            self.macro_table.setItem(r, 3, QTableWidgetItem(desc))
        self.macro_table.blockSignals(False)
        conflicts = len(self.service.status)
        self.macro_status.setText(f"⚠️ {conflicts} hotkey(s) taken by another app" if conflicts else "")

    def _on_macro_item_changed(self, item):
        if item.column() == 0 and 0 <= item.row() < len(self.macros):
            self.macros[item.row()]["enabled"] = item.checkState() == Qt.CheckState.Checked

    def _add_macro(self):
        dlg = MacroEditor(self.theme, None, self)
        if dlg.exec():
            self.macros.append(dlg.macro)
            self._fill_macros()

    def _edit_macro(self, row):
        if not 0 <= row < len(self.macros):
            return
        dlg = MacroEditor(self.theme, self.macros[row], self)
        if dlg.exec():
            self.macros[row] = dlg.macro
            self._fill_macros()

    def _delete_macro(self):
        row = self.macro_table.currentRow()
        if 0 <= row < len(self.macros):
            self.macros.pop(row)
            self._fill_macros()

    def _test_macro(self):
        row = self.macro_table.currentRow()
        if 0 <= row < len(self.macros):
            self.service.run_macro(self.macros[row])

    # -------------------------------------------------------- Hotstrings
    def _build_hotstrings_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        self.chk_hs = QCheckBox("Enable hotstrings (type the trigger, then Space / Enter / Tab)")
        self.chk_hs.setChecked(self.service.hotstrings_enabled)
        lay.addWidget(self.chk_hs)
        self.hs_table = QTableWidget(0, 4)
        self.hs_table.setHorizontalHeaderLabels(["On", "Trigger", "Replacement", "Instant"])
        hdr = self.hs_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.hs_table.verticalHeader().setVisible(False)
        lay.addWidget(self.hs_table)
        tip = QLabel("Tokens: {date} {time} {datetime} {clipboard}. “Instant” fires without "
                     "waiting for Space. Only the current word is ever held in memory.")
        tip.setWordWrap(True)
        tip.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 10px;")
        lay.addWidget(tip)
        row = QHBoxLayout()
        add = QPushButton("＋ Add")
        add.clicked.connect(self._add_hotstring)
        rem = QPushButton("Delete")
        rem.clicked.connect(self._delete_hotstring)
        row.addWidget(add)
        row.addWidget(rem)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _check_item(self, checked):
        it = QTableWidgetItem()
        it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        return it

    def _fill_hotstrings(self):
        self.hs_table.setRowCount(len(self.hotstrings))
        for r, h in enumerate(self.hotstrings):
            self.hs_table.setItem(r, 0, self._check_item(h.get("enabled", True)))
            self.hs_table.setItem(r, 1, QTableWidgetItem(h.get("trigger", "")))
            self.hs_table.setItem(r, 2, QTableWidgetItem(h.get("replacement", "").replace("\n", "\\n")))
            self.hs_table.setItem(r, 3, self._check_item(h.get("instant", False)))

    def _read_hotstrings(self):
        items = []
        for r in range(self.hs_table.rowCount()):
            trig = (self.hs_table.item(r, 1).text() if self.hs_table.item(r, 1) else "").strip()
            if not trig or " " in trig:
                continue
            repl = self.hs_table.item(r, 2).text() if self.hs_table.item(r, 2) else ""
            items.append({
                "trigger": trig,
                "replacement": repl.replace("\\n", "\n"),
                "instant": self.hs_table.item(r, 3).checkState() == Qt.CheckState.Checked,
                "enabled": self.hs_table.item(r, 0).checkState() == Qt.CheckState.Checked,
            })
        return items

    def _add_hotstring(self):
        self.hotstrings = self._read_hotstrings() + [
            {"trigger": ";new", "replacement": "", "instant": False, "enabled": True}]
        self._fill_hotstrings()
        r = self.hs_table.rowCount() - 1
        self.hs_table.setCurrentCell(r, 1)
        self.hs_table.editItem(self.hs_table.item(r, 1))

    def _delete_hotstring(self):
        row = self.hs_table.currentRow()
        if row >= 0:
            self.hs_table.removeRow(row)

    # ------------------------------------------------------------ Import
    def _build_import_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        info = QLabel("Paste an AutoHotkey script (v1 or v2) or open a .ahk file. Simple hotkeys "
                      "(Run, Send, remaps, AlwaysOnTop, Win…) and one-line hotstrings are converted. "
                      "For complex scripts, add a “Run AutoHotkey script” action instead.")
        info.setWordWrap(True)
        lay.addWidget(info)
        self.ahk_text = QPlainTextEdit()
        self.ahk_text.setPlaceholderText("^!e::Run \"explorer.exe\"\n#n::Run notepad\n::btw::by the way\n:*:@@::me@example.com\nCapsLock::Esc")
        lay.addWidget(self.ahk_text, 1)
        row = QHBoxLayout()
        openb = QPushButton("Open .ahk file…")
        openb.clicked.connect(self._open_ahk)
        imp = QPushButton("Convert && add")
        imp.clicked.connect(self._import)
        row.addWidget(openb)
        row.addWidget(imp)
        row.addStretch()
        lay.addLayout(row)
        self.import_result = QLabel("")
        self.import_result.setWordWrap(True)
        lay.addWidget(self.import_result)
        return w

    def _open_ahk(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open AutoHotkey script", "", "AutoHotkey (*.ahk);;All files (*)")
        if path:
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                    self.ahk_text.setPlainText(f.read())
            except OSError as e:
                QMessageBox.warning(self, "Could not open", str(e))

    def _import(self):
        macros, hotstrings, skipped = parse_ahk(self.ahk_text.toPlainText())
        have_keys = {m.get("hotkey", "").lower() for m in self.macros}
        new_m = [m for m in macros if m["hotkey"].lower() not in have_keys]
        current_hs = self._read_hotstrings()
        have_trig = {h["trigger"] for h in current_hs}
        new_h = [h for h in hotstrings if h["trigger"] not in have_trig]
        self.macros += new_m
        self.hotstrings = current_hs + new_h
        self._fill_macros()
        self._fill_hotstrings()
        msg = f"✅ Added {len(new_m)} hotkey(s) and {len(new_h)} hotstring(s). Click Save to activate."
        if skipped:
            preview = "\n".join(s.strip() for s in skipped[:5])
            msg += f"\n⚠️ Skipped {len(skipped)} line(s) that need real AutoHotkey:\n{preview}"
        self.import_result.setText(msg)

    # -------------------------------------------------------------- Save
    def _save(self):
        self.service.config.set("hotstrings_enabled", self.chk_hs.isChecked())
        self.service.config.set("hotstrings", self._read_hotstrings())
        self.service.save_macros(self.macros)  # also re-applies everything
        if self.service.status:
            self._fill_macros()
            QMessageBox.information(self, "Some hotkeys are taken",
                                    "These hotkeys are already used by Windows or another app:\n\n" +
                                    "\n".join(f"• {k}" for k in self.service.status))
        self.accept()
