import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar, QSlider
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QBrush, QPen

class MediaWidget(QWidget):
    play_pause_clicked = pyqtSignal()
    next_clicked = pyqtSignal()
    prev_clicked = pyqtSignal()
    volume_requested = pyqtSignal(int)
    mute_clicked = pyqtSignal()

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.media_info = {
            "title": "No Media Playing",
            "artist": "Windows Media System",
            "is_playing": False,
            "has_media": False,
            "source": "Windows",
            "position_sec": 0,
            "duration_sec": 180
        }
        self.visualizer_phase = 0.0

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._tick_visualizer)
        self.anim_timer.start(50)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 6)
        layout.setSpacing(6)

        # Top Bar: Source badge & animated wave
        top_row = QHBoxLayout()
        self.source_label = QLabel(f"🎵 {self.media_info['source'].upper()}")
        self.source_label.setStyleSheet(f"""
            color: {self.theme['accent']};
            font-size: 10px;
            font-weight: 700;
            letter-spacing: 1px;
            background: rgba(0, 240, 255, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
        """)
        self.source_label.setFixedHeight(20)
        top_row.addWidget(self.source_label)
        top_row.addStretch()

        self.status_badge = QLabel("PAUSED" if not self.media_info["is_playing"] else "PLAYING")
        self.status_badge.setStyleSheet(f"""
            color: {self.theme['text_secondary']};
            font-size: 9px;
            font-weight: bold;
        """)
        top_row.addWidget(self.status_badge)
        layout.addLayout(top_row)

        # Center Row: Album Art + Track Info + Spectrum
        center_row = QHBoxLayout()
        center_row.setSpacing(14)

        # Album Art Placeholder Box
        self.art_box = QLabel()
        self.art_box.setFixedSize(54, 54)
        self.art_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.art_box.setText("💿")
        self.art_box.setStyleSheet(f"""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {self.theme['accent']}, stop:1 {self.theme['accent_secondary']});
            border-radius: 12px;
            font-size: 24px;
        """)
        center_row.addWidget(self.art_box)

        # Track & Artist Labels
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        self.title_label = QLabel(self.media_info["title"])
        self.title_label.setStyleSheet(f"""
            color: {self.theme['text_primary']};
            font-size: 14px;
            font-weight: 700;
        """)
        self.artist_label = QLabel(self.media_info["artist"])
        self.artist_label.setStyleSheet(f"""
            color: {self.theme['text_secondary']};
            font-size: 11px;
        """)
        info_col.addWidget(self.title_label)
        info_col.addWidget(self.artist_label)
        self.lyric_label = QLabel("")
        self.lyric_label.setStyleSheet(f"color: {self.theme['accent']}; font-size: 11px; font-weight: 600;")
        info_col.addWidget(self.lyric_label)
        center_row.addLayout(info_col)
        center_row.addStretch()

        layout.addLayout(center_row, 1)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {self.theme['bg_secondary']};
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {self.theme['accent']};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(self.progress_bar)

        # Controls Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_row.setSpacing(16)

        btn_style = f"""
            QPushButton {{
                background: transparent;
                color: {self.theme['text_primary']};
                font-size: 14px;
                border: none;
                padding: 4px;
                border-radius: 12px;
            }}
            QPushButton:hover {{
                background: rgba(255, 255, 255, 0.1);
                color: {self.theme['accent']};
            }}
        """

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(30, 30)
        self.prev_btn.setStyleSheet(btn_style)
        self.prev_btn.clicked.connect(self.prev_clicked.emit)
        ctrl_row.addWidget(self.prev_btn)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(38, 38)
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['accent']};
                color: {self.theme['bg_color']};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 19px;
            }}
            QPushButton:hover {{
                background: {self.theme['text_primary']};
            }}
        """)
        self.play_btn.clicked.connect(self.play_pause_clicked.emit)
        ctrl_row.addWidget(self.play_btn)

        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(30, 30)
        self.next_btn.setStyleSheet(btn_style)
        self.next_btn.clicked.connect(self.next_clicked.emit)
        ctrl_row.addWidget(self.next_btn)

        # Volume (real Windows master volume)
        ctrl_row.addSpacing(18)
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(28, 28)
        self.mute_btn.setStyleSheet(btn_style)
        self.mute_btn.clicked.connect(self.mute_clicked.emit)
        ctrl_row.addWidget(self.mute_btn)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setFixedWidth(110)
        self.vol_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{ height: 4px; background: {self.theme['bg_secondary']}; border-radius: 2px; }}
            QSlider::sub-page:horizontal {{ background: {self.theme['accent']}; border-radius: 2px; }}
            QSlider::handle:horizontal {{ background: {self.theme['text_primary']}; width: 12px;
                                          margin: -4px 0; border-radius: 6px; }}
        """)
        self.vol_slider.valueChanged.connect(self._on_volume_slider)
        ctrl_row.addWidget(self.vol_slider)

        layout.addLayout(ctrl_row)

    def _tick_visualizer(self):
        if self.media_info.get("is_playing", False) and self.isVisible():
            self.visualizer_phase = (self.visualizer_phase + 0.3) % (2 * math.pi)
            self.update()

    def set_album_art(self, pixmap):
        from PyQt6.QtGui import QPainter, QPainterPath, QPixmap
        from PyQt6.QtCore import QRectF
        if pixmap is None or pixmap.isNull():
            self.art_box.setPixmap(QPixmap())
            self.art_box.setText("💿")
            return
        size = self.art_box.width()
        rounded = QPixmap(size, size)
        rounded.fill(Qt.GlobalColor.transparent)
        p = QPainter(rounded)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, size, size), 12, 12)
        p.setClipPath(path)
        p.drawPixmap(0, 0, pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation))
        p.end()
        self.art_box.setText("")
        self.art_box.setPixmap(rounded)

    def set_lyric(self, line):
        self.lyric_label.setText(("♪ " + line[:58]) if line else "")

    def set_volume(self, percent, muted):
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(percent)
        self.vol_slider.blockSignals(False)
        self.mute_btn.setText("🔇" if muted or percent == 0 else "🔊")

    def _on_volume_slider(self, value):
        self.volume_requested.emit(value)

    def update_media(self, media_data):
        self.media_info = media_data
        self.title_label.setText(media_data.get("title", "No Media Playing")[:35])
        self.artist_label.setText(media_data.get("artist", "")[:40])
        self.source_label.setText(f"🎵 {media_data.get('source', 'WINDOWS').upper()}")
        
        is_playing = media_data.get("is_playing", False)
        self.status_badge.setText("PLAYING" if is_playing else "PAUSED")
        self.play_btn.setText("⏸" if is_playing else "▶")

        dur = media_data.get("duration_sec", 180)
        pos = media_data.get("position_sec", 0)
        pct = int((pos / dur) * 100) if dur > 0 else 0
        self.progress_bar.setValue(pct)

    def update_theme(self, theme):
        self.theme = theme
        # Re-apply styles
        self.source_label.setStyleSheet(f"""
            color: {self.theme['accent']};
            font-size: 10px;
            font-weight: 700;
            background: rgba(0, 240, 255, 0.12);
            padding: 2px 8px;
            border-radius: 6px;
        """)
        self.title_label.setStyleSheet(f"color: {self.theme['text_primary']}; font-size: 14px; font-weight: 700;")
        self.artist_label.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 11px;")
        self.play_btn.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['accent']};
                color: {self.theme['bg_color']};
                font-size: 16px;
                font-weight: bold;
                border: none;
                border-radius: 19px;
            }}
            QPushButton:hover {{
                background: {self.theme['text_primary']};
            }}
        """)
