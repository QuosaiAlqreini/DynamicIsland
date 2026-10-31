import os
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

class QuickToolsWidget(QWidget):
    volume_changed = pyqtSignal(int)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
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
