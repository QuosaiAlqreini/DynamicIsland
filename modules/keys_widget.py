"""Keys tab: one-click launcher for your automations + quick laptop toggles."""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton, QScrollArea, QFrame
)

from services.automation_service import action_label
from styles import badge_style, small_button_style, _rgba

COLUMNS = 4


class KeysWidget(QWidget):
    edit_requested = pyqtSignal()

    def __init__(self, theme, automation_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.service = automation_service
        self._build_ui()
        self.service.changed.connect(self.refresh)
        self.service.keep_awake_changed.connect(self._sync_toggles)
        self.refresh()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 6)
        lay.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(4)
        self.badge = QLabel("⌨️ AUTOMATIONS")
        head.addWidget(self.badge)
        head.addStretch()
        self.btn_hs = QPushButton("✍️ Hotstrings")
        self.btn_hs.setCheckable(True)
        self.btn_hs.setToolTip("Text expansion in every app (e.g. ;date → today's date)")
        self.btn_hs.clicked.connect(lambda on: self.service.set_hotstrings_enabled(on))
        head.addWidget(self.btn_hs)
        self.btn_awake = QPushButton("☕ Awake")
        self.btn_awake.setCheckable(True)
        self.btn_awake.setToolTip("Keep the laptop and screen from sleeping")
        self.btn_awake.clicked.connect(lambda on: self.service.set_keep_awake(on))
        head.addWidget(self.btn_awake)
        self.btn_edit = QPushButton("✏️ Edit")
        self.btn_edit.setToolTip("Add hotkeys, hotstrings or import an AutoHotkey script")
        self.btn_edit.clicked.connect(self.edit_requested)
        head.addWidget(self.btn_edit)
        lay.addLayout(head)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(5)
        self.scroll.setWidget(self.grid_host)
        lay.addWidget(self.scroll, 1)
        self._apply_styles()

    def _apply_styles(self):
        self.badge.setStyleSheet(badge_style(self.theme))
        css = small_button_style(self.theme)
        for b in (self.btn_hs, self.btn_awake, self.btn_edit):
            b.setStyleSheet(css)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; }")
        self.grid_host.setStyleSheet("background: transparent;")

    def _macro_button_css(self):
        t = self.theme
        return f"""
            QPushButton {{
                background: {t['card_bg']};
                color: {t['text_primary']};
                border: 1px solid {t['border_color']};
                border-radius: 8px;
                padding: 4px 4px;
                font-size: 10px;
                font-weight: 600;
                text-align: center;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                background: {_rgba(t['accent'], 0.10)};
            }}
        """

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()
        self.refresh()

    def _sync_toggles(self, *_):
        self.btn_hs.setChecked(self.service.hotstrings_enabled)
        self.btn_awake.setChecked(self.service.keep_awake)

    def refresh(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        css = self._macro_button_css()
        macros = [m for m in self.service.macros if m.get("enabled", True)]
        for i, macro in enumerate(macros):
            hotkey = macro.get("hotkey") or ""
            err = self.service.status.get(hotkey)
            label = macro.get("name") or action_label(macro.get("action", ""))
            sub = ("⚠️ " if err else "") + (hotkey or "click to run")
            btn = QPushButton(f"{label}\n{sub}".replace("&", "&&"))
            btn.setStyleSheet(css)
            btn.setMinimumHeight(38)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{action_label(macro.get('action', ''))}"
                           + (f"\n{macro.get('arg')}" if macro.get("arg") else "")
                           + (f"\n⚠️ {err}" if err else ""))
            btn.clicked.connect(lambda _, m=macro: self.service.run_macro(m))
            self.grid.addWidget(btn, i // COLUMNS, i % COLUMNS)
        if not macros:
            empty = QLabel("No automations yet — click ✏️ Edit to add one or import an .ahk script.")
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 10px;")
            self.grid.addWidget(empty, 0, 0, 1, COLUMNS)
        self._sync_toggles()
