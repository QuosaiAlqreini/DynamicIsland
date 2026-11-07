import time
import math
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class IdlePillWidget(QWidget):
    # Emitted when a live activity appears/disappears so the island can resize
    activity_changed = pyqtSignal(bool)

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

        # Live activities (timer, builds, ...) shown instead of the clock.
        # key -> {"text", "progress" (0-1 or None), "color", "priority"}
        self.activities = {}
        self.flash_activity = None
        self.shelf_count = 0
        self.flash_timer = QTimer(self)
        self.flash_timer.setSingleShot(True)
        self.flash_timer.timeout.connect(self._end_flash)

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

    # ------------------------------------------------------ Live activities
    def set_activity(self, key, text, progress=None, color=None, priority=0):
        had = self.current_activity() is not None
        self.activities[key] = {"text": text, "progress": progress,
                                "color": color, "priority": priority}
        if not had:
            self.activity_changed.emit(True)
        self.update()

    def clear_activity(self, key):
        if self.activities.pop(key, None) is not None:
            if self.current_activity() is None:
                self.activity_changed.emit(False)
            self.update()

    def flash(self, text, color=None, duration_ms=6000):
        """Temporarily show a short message (e.g. 'Build finished')."""
        had = self.current_activity() is not None
        self.flash_activity = {"text": text, "progress": None, "color": color, "priority": 100}
        self.flash_timer.start(duration_ms)
        if not had:
            self.activity_changed.emit(True)
        self.update()

    def _end_flash(self):
        self.flash_activity = None
        if self.current_activity() is None:
            self.activity_changed.emit(False)
        self.update()

    def set_shelf_count(self, count):
        self.shelf_count = int(count)
        self.update()

    def current_activity(self):
        if self.flash_activity:
            return self.flash_activity
        if not self.activities:
            return None
        return max(self.activities.values(), key=lambda a: a["priority"])

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

        # 2. Center Content: live activity, or clock + optional audio wave
        font = QFont("Segoe UI", 10, QFont.Weight.DemiBold)
        painter.setFont(font)
        activity = self.current_activity()
        if activity:
            self._paint_activity(painter, activity, w, h)
            self._paint_battery(painter, w, h)
            return
        painter.setPen(QColor(self.theme["text_primary"]))

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

        self._paint_battery(painter, w, h)

    def _paint_activity(self, painter, activity, w, h):
        color = QColor(activity.get("color") or self.theme["accent"])
        left, right = 32, w - 44 - (18 if self.shelf_count else 0)
        painter.setPen(QColor(self.theme["text_primary"]))
        metrics = painter.fontMetrics()
        text = metrics.elidedText(activity["text"], Qt.TextElideMode.ElideRight, right - left)
        painter.drawText(left, 0, right - left, h, Qt.AlignmentFlag.AlignCenter, text)

        progress = activity.get("progress")
        if progress is not None:
            track_w = right - left
            painter.setPen(Qt.PenStyle.NoPen)
            track = QColor(self.theme["text_secondary"])
            track.setAlpha(60)
            painter.setBrush(QBrush(track))
            painter.drawRoundedRect(left, h - 6, track_w, 3, 1.5, 1.5)
            painter.setBrush(QBrush(color))
            painter.drawRoundedRect(left, h - 6, max(3, int(track_w * min(1.0, progress))), 3, 1.5, 1.5)

    def _paint_battery(self, painter, w, h):
        # Shelf badge (number of parked files)
        if self.shelf_count:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(self.theme["accent"])))
            bx, by = w - 56, int(h / 2 - 7)
            painter.drawEllipse(bx, by, 14, 14)
            painter.setPen(QColor(self.theme["bg_color"]))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(bx, by, 14, 14, Qt.AlignmentFlag.AlignCenter,
                             str(self.shelf_count) if self.shelf_count < 10 else "9+")

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
