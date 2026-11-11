"""🎨 Customize Island: choose what the pill shows, which tabs appear, your own
info items, and how/when the island is visible."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QComboBox,
    QCheckBox, QTabWidget, QWidget, QListWidget, QListWidgetItem, QAbstractItemView,
    QRadioButton, QButtonGroup, QSpinBox, QFormLayout, QMessageBox, QFrame
)

from config import ConfigManager
from modules.pill_idle import IdlePillWidget
from modules.tab_registry import TAB_REGISTRY, DEFAULT_TABS
from services.info_service import INFO_TYPES, INFO_TYPE_LABELS, PILL_BUILTINS, new_info_id
from styles import THEMES, dialog_style, get_theme


class PillPreview(QWidget):
    """Draws the pill background exactly like the island and hosts a real pill."""

    def __init__(self, theme, info_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.pill = IdlePillWidget(theme, self, info_service=info_service)
        self.setFixedHeight(44)

    def set_width(self, w):
        self.setFixedWidth(w + 8)
        self.pill.setGeometry(4, 4, w, 36)

    def set_theme(self, theme):
        self.theme = theme
        self.pill.update_theme(theme)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0, QColor(self.theme["pill_gradient_start"]))
        g.setColorAt(1, QColor(self.theme["pill_gradient_end"]))
        p.setBrush(QBrush(g))
        p.setPen(QPen(QColor(self.theme["border_color"]), 1.2))
        p.drawRoundedRect(1, 1, w - 2, h - 2, (h - 2) / 2, (h - 2) / 2)


class InfoItemEditor(QDialog):
    def __init__(self, theme, item=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Info item")
        self.setStyleSheet(dialog_style(theme))
        self.setMinimumWidth(440)
        item = dict(item or {"id": new_info_id(), "type": "world_clock", "label": "", "value": "", "interval": 60})
        self.item = item
        form = QFormLayout(self)
        self.type = QComboBox()
        for key, label, _ in INFO_TYPES:
            self.type.addItem(label, key)
        self.type.setCurrentIndex(max(0, self.type.findData(item.get("type"))))
        self.type.currentIndexChanged.connect(self._on_type)
        form.addRow("Type", self.type)
        self.label = QLineEdit(item.get("label", ""))
        self.label.setPlaceholderText("Short label, e.g. Riyadh, Exam, Weather")
        form.addRow("Label", self.label)
        self.value = QLineEdit(str(item.get("value", "")))
        form.addRow("Value", self.value)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        form.addRow("", self.hint)
        self.interval = QSpinBox()
        self.interval.setRange(5, 86400)
        self.interval.setSuffix(" s")
        self.interval.setValue(int(item.get("interval", 60) or 60))
        self.interval_label = QLabel("Refresh every")
        form.addRow(self.interval_label, self.interval)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("OK")
        ok.setDefault(True)
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)
        self._on_type()

    def _on_type(self):
        key = self.type.currentData()
        hint = next(h for k, _, h in INFO_TYPES if k == key)
        self.hint.setText(hint)
        self.value.setPlaceholderText(hint.split(", e.g.")[0])
        is_cmd = key == "command"
        self.interval.setVisible(is_cmd)
        self.interval_label.setVisible(is_cmd)

    def _accept(self):
        if not self.value.text().strip():
            QMessageBox.warning(self, "Missing value", "Please fill in the value.")
            return
        self.item = {"id": self.item["id"], "type": self.type.currentData(),
                     "label": self.label.text().strip(), "value": self.value.text().strip(),
                     "interval": self.interval.value()}
        self.accept()


class CustomizeDialog(QDialog):
    def __init__(self, theme, info_service, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.theme = theme
        self.info = info_service
        self.items = [dict(i) for i in info_service.items]
        self._original_items = [dict(i) for i in self.items]

        self.setWindowTitle("Customize Dynamic Island")
        self.resize(680, 690)
        self.setStyleSheet(dialog_style(theme))

        lay = QVBoxLayout(self)
        title = QLabel("🎨 Customize Island")
        title.setStyleSheet(f"font-size: 16px; font-weight: 700; color: {theme['accent']};")
        lay.addWidget(title)

        # Live preview of the compact pill
        prev_row = QHBoxLayout()
        prev_row.addStretch()
        self.preview = PillPreview(theme, info_service)
        prev_row.addWidget(self.preview)
        prev_row.addStretch()
        prev_frame = QFrame()
        prev_frame.setStyleSheet(f"QFrame {{ background: {theme['bg_secondary']}; border-radius: 10px; }}")
        pf = QVBoxLayout(prev_frame)
        pf.setContentsMargins(8, 10, 8, 10)
        pf.addLayout(prev_row)
        lay.addWidget(prev_frame)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_pill_tab(), "💊 Pill")
        self.tabs.addTab(self._build_tabs_tab(), "🗂️ Tabs")
        self.tabs.addTab(self._build_info_tab(), "ℹ️ Info")
        self.tabs.addTab(self._build_behavior_tab(), "👁️ Visibility")
        lay.addWidget(self.tabs, 1)

        btns = QHBoxLayout()
        reset = QPushButton("Reset to default look")
        reset.clicked.connect(self._reset)
        btns.addWidget(reset)
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setStyleSheet(f"background: {theme['accent']}; color: {theme['bg_color']}; border: none;")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        lay.addLayout(btns)
        self._update_preview()

    # --------------------------------------------------------------- Pill
    def _build_pill_tab(self):
        w = QWidget()
        form = QFormLayout(w)
        form.addRow(QLabel("Pick what the small pill shows. Live activities (timers, builds, alerts) "
                           "temporarily replace the middle."))
        self.slot_left, self.slot_center, self.slot_right = QComboBox(), QComboBox(), QComboBox()
        for combo in (self.slot_left, self.slot_center, self.slot_right):
            combo.currentIndexChanged.connect(self._update_preview)
        self._fill_slot_combos()
        form.addRow("Left", self.slot_left)
        form.addRow("Middle", self.slot_center)
        form.addRow("Right", self.slot_right)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(150, 420)
        self.width_spin.setSingleStep(10)
        self.width_spin.setSuffix(" px")
        self.width_spin.setValue(int(self.config.get("compact_width", 200)))
        self.width_spin.valueChanged.connect(self._update_preview)
        form.addRow("Pill width", self.width_spin)
        return w

    def _slot_choices(self):
        choices = list(PILL_BUILTINS)
        for item in self.items:
            name = item.get("label") or INFO_TYPE_LABELS.get(item.get("type"), "")
            choices.append((f"info:{item['id']}", f"ℹ️ {name} ({INFO_TYPE_LABELS.get(item.get('type'), '')})"))
        return choices

    def _fill_slot_combos(self, current=None):
        current = current or (self.config.get("pill_left", "ai_dot"),
                              self.config.get("pill_center", "clock"),
                              self.config.get("pill_right", "battery_icon"))
        for combo, cur in zip((self.slot_left, self.slot_center, self.slot_right), current):
            combo.blockSignals(True)
            combo.clear()
            for key, label in self._slot_choices():
                combo.addItem(label, key)
            idx = combo.findData(cur)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _current_slots(self):
        return (self.slot_left.currentData(), self.slot_center.currentData(), self.slot_right.currentData())

    def _update_preview(self):
        # Preview uses the items being edited, so temporarily expose them to the info service
        self.preview.set_width(self.width_spin.value())
        self.preview.pill.set_slots(*self._current_slots())
        theme_key = self.theme_combo.currentData() if hasattr(self, "theme_combo") else None
        if theme_key:
            self.preview.set_theme(get_theme(theme_key))

    # --------------------------------------------------------------- Tabs
    def _build_tabs_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Tick the tabs you want, drag (or use ↑ ↓) to reorder. "
                             "Hidden tabs are still reachable from hotkeys and menus."))
        self.tab_list = QListWidget()
        self.tab_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        visible = [k for k in self.config.get("tabs_visible", DEFAULT_TABS) if k in TAB_REGISTRY]
        ordered = visible + [k for k in TAB_REGISTRY if k not in visible]
        for key in ordered:
            icon, label, tip = TAB_REGISTRY[key]
            it = QListWidgetItem(f"{icon}  {label} — {tip}")
            it.setData(Qt.ItemDataRole.UserRole, key)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if key in visible else Qt.CheckState.Unchecked)
            self.tab_list.addItem(it)
        lay.addWidget(self.tab_list, 1)
        row = QHBoxLayout()
        up, down = QPushButton("↑ Up"), QPushButton("↓ Down")
        up.clicked.connect(lambda: self._move_tab(-1))
        down.clicked.connect(lambda: self._move_tab(1))
        row.addWidget(up)
        row.addWidget(down)
        row.addStretch()
        lay.addLayout(row)
        return w

    def _move_tab(self, step):
        row = self.tab_list.currentRow()
        new = row + step
        if row < 0 or not 0 <= new < self.tab_list.count():
            return
        it = self.tab_list.takeItem(row)
        self.tab_list.insertItem(new, it)
        self.tab_list.setCurrentRow(new)

    def _visible_tabs(self):
        keys = []
        for i in range(self.tab_list.count()):
            it = self.tab_list.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                keys.append(it.data(Qt.ItemDataRole.UserRole))
        return keys

    def _set_tab_checked(self, key, checked=True):
        for i in range(self.tab_list.count()):
            it = self.tab_list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == key:
                it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    # --------------------------------------------------------------- Info
    def _build_info_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Add your own info. Each item appears in the ℹ️ Info tab and can be "
                             "picked for the pill in the 💊 Pill tab."))
        self.info_list = QListWidget()
        self.info_list.itemDoubleClicked.connect(lambda _: self._edit_item())
        lay.addWidget(self.info_list, 1)
        row = QHBoxLayout()
        for text, fn in (("＋ Add", self._add_item), ("Edit", self._edit_item), ("Delete", self._delete_item)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        ex = QLabel("Ideas: World clock “Riyadh” = Asia/Riyadh · Countdown “Exam” = 2026-12-14 09:00 · "
                    "Command “Weather” = curl -s \"wttr.in/?format=%t+%C\" · Text “Today” = Call the bank")
        ex.setWordWrap(True)
        ex.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 10px;")
        lay.addWidget(ex)
        self._fill_info_list()
        return w

    def _fill_info_list(self):
        self.info_list.clear()
        for item in self.items:
            kind = INFO_TYPE_LABELS.get(item.get("type"), item.get("type"))
            self.info_list.addItem(f"{item.get('label') or '(no label)'}  ·  {kind}  ·  {item.get('value')}")

    def _items_changed(self):
        slots = self._current_slots()
        self._fill_info_list()
        self._fill_slot_combos(slots)
        self.info.save_items(self.items)  # so the preview / Info tab can show real values
        self._update_preview()

    def _add_item(self):
        dlg = InfoItemEditor(self.theme, None, self)
        if dlg.exec():
            self.items.append(dlg.item)
            self._set_tab_checked("info", True)  # first info item: show the Info tab
            self._items_changed()

    def _edit_item(self):
        row = self.info_list.currentRow()
        if 0 <= row < len(self.items):
            dlg = InfoItemEditor(self.theme, self.items[row], self)
            if dlg.exec():
                self.items[row] = dlg.item
                self._items_changed()

    def _delete_item(self):
        row = self.info_list.currentRow()
        if 0 <= row < len(self.items):
            self.items.pop(row)
            self._items_changed()

    # ---------------------------------------------------------- Visibility
    def _build_behavior_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("<b>When should the island be on screen?</b>"))
        self.rb_always = QRadioButton("Always visible at the top")
        self.rb_autohide = QRadioButton("Hide at the top — slide down when my cursor touches the top edge")
        group = QButtonGroup(w)
        group.addButton(self.rb_always)
        group.addButton(self.rb_autohide)
        (self.rb_autohide if self.config.get("visibility_mode") == "autohide" else self.rb_always).setChecked(True)
        lay.addWidget(self.rb_always)
        lay.addWidget(self.rb_autohide)
        self.chk_peek = QCheckBox("   …but peek down for timers, finished builds and alerts")
        self.chk_peek.setChecked(self.config.get("peek_on_activity", True))
        lay.addWidget(self.chk_peek)
        self.rb_autohide.toggled.connect(self.chk_peek.setEnabled)
        self.chk_peek.setEnabled(self.rb_autohide.isChecked())

        self.chk_fullscreen = QCheckBox("Hide while a full-screen app is open (games, videos, presentations)")
        self.chk_fullscreen.setChecked(self.config.get("hide_in_fullscreen", True))
        lay.addWidget(self.chk_fullscreen)

        arow = QHBoxLayout()
        arow.addWidget(QLabel("Also hide while these apps are in front"))
        self.hide_apps = QLineEdit(", ".join(self.config.get("hide_for_apps", [])))
        self.hide_apps.setPlaceholderText("e.g. vlc.exe, powerpnt.exe")
        arow.addWidget(self.hide_apps, 1)
        lay.addLayout(arow)

        lay.addSpacing(6)
        lay.addWidget(QLabel("<b>Don't block what's underneath</b>"))
        self.chk_through = QCheckBox("Click-through pill: clicks go to the tab / button under it (it fades while the cursor is there)")
        self.chk_through.setChecked(self.config.get("through_mode", True))
        lay.addWidget(self.chk_through)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("   Open the island by"))
        self.open_combo = QComboBox()
        self.open_combo.addItem("Pushing the cursor against the top edge above it", "edge")
        self.open_combo.addItem("Resting the cursor on the pill", "dwell")
        self.open_combo.addItem("Hotkey or tray icon only", "manual")
        self.open_combo.setCurrentIndex(max(0, self.open_combo.findData(self.config.get("through_open", "edge"))))
        orow.addWidget(self.open_combo, 1)
        lay.addLayout(orow)
        self.chk_through.toggled.connect(self.open_combo.setEnabled)
        self.open_combo.setEnabled(self.chk_through.isChecked())
        prow = QHBoxLayout()
        prow.addWidget(QLabel("Position along the top"))
        self.offset_spin = QSpinBox()
        self.offset_spin.setRange(-4000, 4000)
        self.offset_spin.setSingleStep(20)
        self.offset_spin.setSuffix(" px from center")
        self.offset_spin.setValue(int(self.config.get("island_offset_x", 0)))
        prow.addWidget(self.offset_spin, 1)
        screen_w = self.screen().geometry().width() if self.screen() else 1920
        for text, value in (("⟵ Left", -int(screen_w * 0.3)), ("Center", 0), ("Right ⟶", int(screen_w * 0.3))):
            b = QPushButton(text)
            b.clicked.connect(lambda _, v=value: self.offset_spin.setValue(v))
            prow.addWidget(b)
        lay.addLayout(prow)

        lay.addSpacing(6)
        lay.addWidget(QLabel("<b>Opening & look</b>"))
        self.chk_hover = QCheckBox("Expand when the cursor hovers over the pill (when click-through is off)")
        self.chk_hover.setChecked(self.config.get("expand_on_hover", True))
        lay.addWidget(self.chk_hover)
        self.chk_click = QCheckBox("Click the pill to open it (when click-through is off)")
        self.chk_click.setChecked(self.config.get("click_to_expand", True))
        lay.addWidget(self.chk_click)
        self.chk_lyrics = QCheckBox("Show synced song lyrics (looks up the song title and artist on lrclib.net)")
        self.chk_lyrics.setChecked(self.config.get("lyrics_enabled", True))
        lay.addWidget(self.chk_lyrics)
        self.chk_notch = QCheckBox("Notch mode: sit flush against the top edge")
        self.chk_notch.setChecked(self.config.get("notch_mode", False))
        lay.addWidget(self.chk_notch)
        trow = QHBoxLayout()
        trow.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        for key, val in THEMES.items():
            self.theme_combo.addItem(val["name"], key)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.config.get("theme", "obsidian"))))
        self.theme_combo.currentIndexChanged.connect(self._update_preview)
        trow.addWidget(self.theme_combo, 1)
        lay.addLayout(trow)
        lay.addStretch()
        return w

    # -------------------------------------------------------------- Save
    def reject(self):
        self.info.save_items(self._original_items)  # undo live edits
        super().reject()

    def _reset(self):
        self._fill_slot_combos(("ai_dot", "clock", "battery_icon"))
        self.width_spin.setValue(200)
        for i in range(self.tab_list.count()):
            key = self.tab_list.item(i).data(Qt.ItemDataRole.UserRole)
            self._set_tab_checked(key, key in DEFAULT_TABS)
        self.rb_always.setChecked(True)
        self.chk_fullscreen.setChecked(True)
        self.chk_through.setChecked(True)
        self.open_combo.setCurrentIndex(0)
        self.offset_spin.setValue(0)
        self._update_preview()

    def _save(self):
        tabs = self._visible_tabs()
        if not tabs:
            QMessageBox.warning(self, "No tabs", "Keep at least one tab visible.")
            return
        left, center, right = self._current_slots()
        c = self.config
        c.set("pill_left", left)
        c.set("pill_center", center)
        c.set("pill_right", right)
        c.set("compact_width", self.width_spin.value())
        c.set("tabs_visible", tabs)
        c.set("visibility_mode", "autohide" if self.rb_autohide.isChecked() else "always")
        c.set("peek_on_activity", self.chk_peek.isChecked())
        c.set("hide_in_fullscreen", self.chk_fullscreen.isChecked())
        c.set("hide_for_apps", [a.strip().lower() for a in self.hide_apps.text().split(",") if a.strip()])
        c.set("lyrics_enabled", self.chk_lyrics.isChecked())
        c.set("through_mode", self.chk_through.isChecked())
        c.set("through_open", self.open_combo.currentData())
        c.set("island_offset_x", self.offset_spin.value())
        c.set("expand_on_hover", self.chk_hover.isChecked())
        c.set("click_to_expand", self.chk_click.isChecked())
        c.set("notch_mode", self.chk_notch.isChecked())
        c.set("theme", self.theme_combo.currentData())
        self.info.save_items(self.items)
        self.accept()
