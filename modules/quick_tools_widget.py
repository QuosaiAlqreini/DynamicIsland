import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton, QMenu,
    QFileDialog, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal

from config import ConfigManager
from services.launcher import open_target
from styles import small_button_style

MAX_LAUNCHERS = 6

class QuickToolsWidget(QWidget):
    volume_changed = pyqtSignal(int)
    open_tab_requested = pyqtSignal(int)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.config = ConfigManager()
        self.launcher_buttons = []
        self.current_volume = 65
        self.is_muted = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Header
        header_row = QHBoxLayout()
        badge = QLabel("🛠️ QUICK UTILITIES")
        badge.setStyleSheet(f"""
            color: {self.theme['accent']};
            font-size: 10px;
            font-weight: 700;
            background: rgba(0, 240, 255, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
        """)
        header_row.addWidget(badge)
        header_row.addStretch()

        dnd_btn = QPushButton("🌙 Focus Mode")
        dnd_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                font-size: 9px;
                padding: 2px 6px;
            }}
            QPushButton:hover {{
                color: {self.theme['text_primary']};
                border-color: {self.theme['accent']};
            }}
        """)
        header_row.addWidget(dnd_btn)
        layout.addLayout(header_row)

        # Volume Slider Row
        vol_row = QHBoxLayout()
        vol_row.setSpacing(10)
        self.vol_icon = QLabel("🔊")
        self.vol_icon.setStyleSheet("font-size: 14px;")
        vol_row.addWidget(self.vol_icon)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(self.current_volume)
        self.slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 6px;
                background: {self.theme['bg_secondary']};
                border-radius: 3px;
            }}
            QSlider::sub-page:horizontal {{
                background: {self.theme['accent']};
                border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {self.theme['text_primary']};
                width: 14px;
                margin-top: -4px;
                margin-bottom: -4px;
                border-radius: 7px;
            }}
        """)
        self.slider.valueChanged.connect(self._on_vol_changed)
        vol_row.addWidget(self.slider)

        self.vol_text = QLabel(f"{self.current_volume}%")
        self.vol_text.setStyleSheet(f"color: {self.theme['text_primary']}; font-size: 11px; font-weight: bold;")
        vol_row.addWidget(self.vol_text)
        layout.addLayout(vol_row)

        # Shortcut Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_style = f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_primary']};
                font-size: 11px;
                font-weight: 600;
                border: 1px solid {self.theme['border_color']};
                border-radius: 8px;
                padding: 8px 10px;
            }}
            QPushButton:hover {{
                border-color: {self.theme['accent']};
                color: {self.theme['accent']};
                background: rgba(0, 240, 255, 0.1);
            }}
        """

        snip_btn = QPushButton("✂️ Snipping")
        snip_btn.setStyleSheet(btn_style)
        snip_btn.clicked.connect(self._launch_snipping)
        btn_row.addWidget(snip_btn)

        term_btn = QPushButton("💻 Terminal")
        term_btn.setStyleSheet(btn_style)
        term_btn.clicked.connect(self._launch_terminal)
        btn_row.addWidget(term_btn)

        task_btn = QPushButton("📊 TaskMgr")
        task_btn.setStyleSheet(btn_style)
        task_btn.clicked.connect(self._launch_task_manager)
        btn_row.addWidget(task_btn)

        calc_btn = QPushButton("🧮 Calc")
        calc_btn.setStyleSheet(btn_style)
        calc_btn.clicked.connect(self._launch_calc)
        btn_row.addWidget(calc_btn)

        layout.addLayout(btn_row)

        # Pinned launchers: one click to any app, folder, file or URL
        self.launcher_row = QHBoxLayout()
        self.launcher_row.setSpacing(6)
        layout.addLayout(self.launcher_row)
        self._rebuild_launchers()

    # ------------------------------------------------------------ Launchers
    def _launchers(self):
        items = self.config.get("pinned_launchers", []) or []
        return [l for l in items if isinstance(l, dict) and l.get("target")]

    def _rebuild_launchers(self):
        while self.launcher_row.count():
            item = self.launcher_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.launcher_buttons = []
        css = small_button_style(self.theme)
        pin_label = QLabel("📌")
        pin_label.setToolTip("Pinned launchers — right-click one to remove it")
        self.launcher_row.addWidget(pin_label)
        for idx, launcher in enumerate(self._launchers()[:MAX_LAUNCHERS]):
            btn = QPushButton(launcher.get("name") or os.path.basename(launcher["target"]))
            btn.setToolTip(launcher["target"])
            btn.setStyleSheet(css)
            btn.clicked.connect(lambda _, t=launcher["target"]: open_target(t))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda _, i=idx, b=btn: self._launcher_menu(i, b))
            self.launcher_row.addWidget(btn)
            self.launcher_buttons.append(btn)
        if len(self._launchers()) < MAX_LAUNCHERS:
            add_btn = QPushButton("＋")
            add_btn.setToolTip("Pin an app, file, folder or URL")
            add_btn.setStyleSheet(css)
            add_btn.clicked.connect(self._add_launcher_menu)
            self.launcher_row.addWidget(add_btn)
            self.launcher_buttons.append(add_btn)
        self.launcher_row.addStretch()

    def _save_launchers(self, launchers):
        self.config.set("pinned_launchers", launchers)
        self._rebuild_launchers()

    def add_launcher(self, target, name=None):
        target = (target or "").strip()
        if not target:
            return
        launchers = self._launchers()
        if any(l["target"] == target for l in launchers):
            return
        if not name:
            base = os.path.basename(target.rstrip("\\/")) or target
            name = os.path.splitext(base)[0][:14]
        launchers.append({"name": name, "target": target})
        self._save_launchers(launchers[:MAX_LAUNCHERS])

    def _add_launcher_menu(self):
        menu = QMenu(self)
        menu.addAction("📄 App or file…").triggered.connect(self._pick_file)
        menu.addAction("📁 Folder…").triggered.connect(self._pick_folder)
        menu.addAction("🔗 URL or command…").triggered.connect(self._pick_url)
        menu.exec(self.cursor().pos())

    def _pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self.window(), "Pin an app or file")
        if path:
            self.add_launcher(path)

    def _pick_folder(self):
        path = QFileDialog.getExistingDirectory(self.window(), "Pin a folder")
        if path:
            self.add_launcher(path)

    def _pick_url(self):
        url, ok = QInputDialog.getText(self.window(), "Pin a URL", "URL or URI (https://…, ms-settings:, spotify:):")
        if ok and url.strip():
            name, ok2 = QInputDialog.getText(self.window(), "Pin a URL", "Button label:")
            self.add_launcher(url.strip(), name.strip() if ok2 and name.strip() else None)

    def _launcher_menu(self, index, button):
        menu = QMenu(self)
        menu.addAction("✕ Unpin").triggered.connect(lambda: self._remove_launcher(index))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _remove_launcher(self, index):
        launchers = self._launchers()
        if 0 <= index < len(launchers):
            launchers.pop(index)
            self._save_launchers(launchers)

    def _on_vol_changed(self, val):
        self.current_volume = val
        self.vol_text.setText(f"{val}%")
        self.vol_icon.setText("🔇" if val == 0 else ("🔉" if val < 50 else "🔊"))
        self.volume_changed.emit(val)

    def _launch_snipping(self):
        try:
            os.system("start ms-screenclip:")
        except Exception:
            pass

    def _launch_terminal(self):
        try:
            os.system("start powershell")
        except Exception:
            pass

    def _launch_task_manager(self):
        try:
            os.system("start taskmgr")
        except Exception:
            pass

    def _launch_calc(self):
        try:
            os.system("start calc")
        except Exception:
            pass

    def update_theme(self, theme):
        self.theme = theme
        self._rebuild_launchers()
