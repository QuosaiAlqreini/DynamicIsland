import time
import math
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class IdlePillWidget(QWidget):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.agent_status = "Idle"
        self.agent_color = QColor("#10b981")
        self.is_playing = False
        self.battery_pct = 100
        self.battery_plugged = True
        self.time_str = time.strftime("%H:%M")

        self.pulse_phase = 0.0
        self.wave_phase = 0.0

        # Animation timer for pulse and waveform
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._animate_tick)
        self.anim_timer.start(50)

        # Clock timer
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start(1000)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _animate_tick(self):
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        if self.is_playing:
            self.wave_phase = (self.wave_phase + 0.25) % (2 * math.pi)
        self.update()

    def _update_clock(self):
        new_time = time.strftime("%H:%M")
        if new_time != self.time_str:
            self.time_str = new_time
            self.update()

    def update_agent_status(self, status, color_hex):
        self.agent_status = status
        self.agent_color = QColor(color_hex)
        self.update()

    def update_media(self, media_data):
        self.is_playing = media_data.get("is_playing", False)
        self.update()

    def update_system(self, sys_data):
        self.battery_pct = sys_data.get("battery_percent", 100)
        self.battery_plugged = sys_data.get("battery_plugged", True)
        self.update()

    def update_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # 1. AI Glowing Dot / Ring on Left
        pulse_alpha = int(120 + 80 * math.sin(self.pulse_phase))
        dot_color = QColor(self.agent_color)
        dot_color.setAlpha(pulse_alpha)

        # Glow halo
        painter.setPen(Qt.PenStyle.NoPen)
        halo_color = QColor(self.agent_color)
        halo_color.setAlpha(int(40 + 30 * math.sin(self.pulse_phase)))
        painter.setBrush(QBrush(halo_color))
        painter.drawEllipse(10, int(h / 2 - 8), 16, 16)

        # Inner vibrant core
        painter.setBrush(QBrush(self.agent_color))
        painter.drawEllipse(13, int(h / 2 - 5), 10, 10)

        # 2. Center Content: Clock + optional audio wave
        painter.setPen(QColor(self.theme["text_primary"]))
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(font)

        # Draw time text
        time_x = int(w / 2 - 20)
        painter.drawText(time_x, int(h / 2 + 5), self.time_str)

        # Draw wave bars if playing
        if self.is_playing:
            wave_color = QColor(self.theme["accent"])
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(wave_color))
            bar_x = time_x + 44
            for i in range(3):
                bar_h = int(4 + 6 * abs(math.sin(self.wave_phase + i * 0.8)))
                bar_y = int(h / 2 - bar_h / 2)
                painter.drawRoundedRect(bar_x + i * 4, bar_y, 2, bar_h, 1, 1)

        # 3. Right: Battery Pill
        bat_w, bat_h = 20, 10
        bat_x = w - bat_w - 14
        bat_y = int(h / 2 - bat_h / 2)

        # Battery outline
        painter.setPen(QPen(QColor(self.theme["text_secondary"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(bat_x, bat_y, bat_w, bat_h, 2, 2)
        # Battery terminal
        painter.drawRect(bat_x + bat_w, bat_y + 3, 2, 4)

        # Battery fill level
        fill_w = max(2, int((bat_w - 4) * (self.battery_pct / 100.0)))
        fill_color = QColor(self.theme["success"] if self.battery_pct > 20 else self.theme["danger"])
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(bat_x + 2, bat_y + 2, fill_w, bat_h - 4)
