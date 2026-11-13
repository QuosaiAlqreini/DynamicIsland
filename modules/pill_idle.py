import time
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

DEFAULT_SLOTS = ("none", "robo", "none")
TEXT_MAX_SIDE = 110  # max width of a text item in the left/right slot


class IdlePillWidget(QWidget):
    """Compact pill. Its left / center / right areas show whatever the user picked
    in Customize Island (defaults: AI dot, clock, battery icon)."""

    # Emitted when a live activity appears/disappears so the island can resize
    activity_changed = pyqtSignal(bool)

    def __init__(self, theme, parent=None, info_service=None):
        super().__init__(parent)
        self.theme = theme
        self.info = info_service
        self.slots = list(DEFAULT_SLOTS)
        self.agent_status = "Idle"
        self.agent_color = QColor("#10b981")
        self.is_playing = False
        self.battery_pct = 100
        self.battery_plugged = True
        self.time_str = time.strftime("%H:%M")

        self.pulse_phase = 0.0
        self.wave_phase = 0.0
        self.robo_mood = "idle"
        self.album_art = None
        self.music_enabled = True
        self._t0 = time.monotonic()

        # Live activities (timer, builds, ...) shown instead of the center item.
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

        # Clock timer (every second so "clock with seconds" works)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._clock_tick)
        self.clock_timer.start(1000)

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _clock_tick(self):
        # Bound method (not a lambda): Qt drops the connection when this widget is destroyed
        if self.isVisible():
            self.update()

    # ------------------------------------------------------------- config
    def set_slots(self, left, center, right):
        self.slots = [left or "none", center or "none", right or "none"]
        self.update()

    def _animate_tick(self):
        if not self.isVisible() or not self.window().isVisible():
            return  # hidden (expanded, tucked, full screen): don't repaint
        self.pulse_phase = (self.pulse_phase + 0.08) % (2 * math.pi)
        if self.is_playing:
            self.wave_phase = (self.wave_phase + 0.25) % (2 * math.pi)
        if "ai_dot" in self.slots or "robo" in self.slots or self.is_playing:
            self.update()

    def set_album_art(self, pixmap):
        self.album_art = pixmap
        self.update()

    def music_mode(self):
        """Music playing and nothing more important to show: art + waveform beside the notch."""
        return self.music_enabled and self.is_playing and not self.current_activity()

    def set_robo_mood(self, mood):
        self.robo_mood = mood
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

    # ------------------------------------------------------------ painting
    def _text_for(self, slot):
        if slot == "clock" and self.info is None:
            return time.strftime("%H:%M")
        if self.info is not None:
            return self.info.slot_text(slot)
        return ""

    def _side_width(self, painter, slot):
        if slot in ("none", ""):
            return 0
        if slot == "ai_dot":
            return 20
        if slot == "robo":
            return 22
        if slot == "battery_icon":
            return 24
        if slot in ("water_ring", "battery_ring"):
            return 18
        text = self._text_for(slot)
        return min(TEXT_MAX_SIDE, painter.fontMetrics().horizontalAdvance(text) + 3) if text else 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        left_slot, center_slot, right_slot = self.slots
        if self.music_mode():
            self._paint_music(painter, w, h, center_slot)
            return
        if self.current_activity() and center_slot == "robo" and right_slot in ("none", ""):
            right_slot = "robo"          # make room for the text, keep Robo in view

        # Left slot (starts at x=10, like the original AI dot)
        lw = self._side_width(painter, left_slot)
        self._paint_slot(painter, left_slot, 10, lw, h, Qt.AlignmentFlag.AlignLeft)
        left_end = 10 + lw + (6 if lw else 0)

        # Right slot (ends 12px from the edge, like the original battery)
        rw = self._side_width(painter, right_slot)
        right_start = w - 12 - rw
        self._paint_slot(painter, right_slot, right_start, rw, h, Qt.AlignmentFlag.AlignRight)
        right_end = right_start - (6 if rw else 0)

        # Shelf badge (number of parked files) sits just left of the right slot
        if self.shelf_count:
            bx, by = right_end - 14, int(h / 2 - 7)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(self.theme["accent"])))
            painter.drawEllipse(bx, by, 14, 14)
            painter.setPen(QColor(self.theme["bg_color"]))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(bx, by, 14, 14, Qt.AlignmentFlag.AlignCenter,
                             str(self.shelf_count) if self.shelf_count < 10 else "9+")
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            right_end = bx - 6

        # Center: live activity, or the chosen center item (+ audio wave)
        activity = self.current_activity()
        if activity:
            self._paint_activity(painter, activity, left_end, right_end, h)
        else:
            self._paint_center(painter, center_slot, left_end, right_end, w, h)

    def _paint_slot(self, painter, slot, x, width, h, align):
        if not width:
            return
        if slot == "robo":
            from modules.robo import paint_robo
            from PyQt6.QtCore import QRectF
            size = min(22, h - 4)
            paint_robo(painter, QRectF(x, (h - size) / 2, size, size), self.robo_mood,
                       time.monotonic() - self._t0, self.theme)
        elif slot == "ai_dot":
            self._paint_ai_dot(painter, x, h)
        elif slot == "battery_icon":
            self._paint_battery(painter, x, h)
        elif slot in ("water_ring", "battery_ring"):
            self._paint_ring(painter, slot, x, h)
        else:
            text = self._text_for(slot)
            painter.setPen(QColor(self.theme["text_secondary"]))
            text = painter.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, width)
            painter.drawText(x, 0, width, h, align | Qt.AlignmentFlag.AlignVCenter, text)

    def _paint_center(self, painter, slot, left, right, w, h):
        if slot in ("none", ""):
            return
        if slot in ("ai_dot", "robo", "battery_icon", "water_ring", "battery_ring"):
            cx = int(w / 2 - (10 if slot == "ai_dot" else 12))
            self._paint_slot(painter, slot, cx, 24, h, Qt.AlignmentFlag.AlignCenter)
            return
        text = self._text_for(slot)
        metrics = painter.fontMetrics()
        wave_w = 14 if self.is_playing else 0
        avail = max(10, right - left - wave_w)
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, avail)
        tw = metrics.horizontalAdvance(text)
        # Center on the whole pill when there is room, otherwise within the free area
        x = int(w / 2 - (tw + wave_w) / 2)
        x = max(left, min(x, right - tw - wave_w))
        painter.setPen(QColor(self.theme["text_primary"]))
        painter.drawText(x, 0, tw + 2, h, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        if self.is_playing:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(self.theme["accent"])))
            bar_x = x + tw + 4
            for i in range(3):
                bar_h = int(4 + 6 * abs(math.sin(self.wave_phase + i * 0.8)))
                painter.drawRoundedRect(bar_x + i * 4, int(h / 2 - bar_h / 2), 2, bar_h, 1, 1)

    def _paint_ring(self, painter, slot, x, h):
        """Small status ring: battery level or today's water intake."""
        if slot == "water_ring":
            day = getattr(self.info, "day", None)
            frac = day.water_fraction if day else 0.0
            color = QColor(self.theme["accent"])
        else:
            frac = self.battery_pct / 100.0
            color = QColor(self.theme["success"] if self.battery_pct > 20 else self.theme["danger"])
        track = QColor(self.theme["text_secondary"])
        track.setAlpha(70)
        pen = QPen(track, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(pen)
        y = int(h / 2 - 8)
        painter.drawEllipse(x + 1, y, 16, 16)
        pen.setColor(color)
        painter.setPen(pen)
        painter.drawArc(x + 1, y, 16, 16, 90 * 16, -int(max(0.0, min(1.0, frac)) * 360 * 16))

    def _paint_music(self, painter, w, h, center_slot):
        """NotchNook-style: album cover on the left, live waveform on the right."""
        from PyQt6.QtCore import QRectF
        from PyQt6.QtGui import QPainterPath
        size = max(12, min(h - 6, 22))
        y = (h - size) / 2
        art_rect = QRectF(4, y, size, size)
        clip = QPainterPath()
        clip.addRoundedRect(art_rect, size * 0.28, size * 0.28)
        painter.save()
        painter.setClipPath(clip)
        if self.album_art is not None and not self.album_art.isNull():
            painter.drawPixmap(art_rect.toRect(), self.album_art)
        else:
            painter.fillPath(clip, QBrush(QColor(self.theme["accent"])))
            painter.setPen(QColor(self.theme["bg_color"]))
            painter.drawText(art_rect, Qt.AlignmentFlag.AlignCenter, "♪")
        painter.restore()
        # Waveform: soft rounded bars with a gentle, uneven rhythm
        bars, bw, gap = 5, 3, 2.5
        total = bars * bw + (bars - 1) * gap
        x0 = w - 6 - total
        color = QColor(self.theme["accent"])
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(bars):
            amp = 0.35 + 0.65 * abs(math.sin(self.wave_phase * (0.9 + i * 0.17) + i * 1.3))
            bh = max(3.0, (h - 12) * amp)
            c = QColor(color)
            c.setAlphaF(0.55 + 0.45 * amp)
            painter.setBrush(QBrush(c))
            painter.drawRoundedRect(QRectF(x0 + i * (bw + gap), (h - bh) / 2, bw, bh), bw / 2, bw / 2)
        # Robo stays in the middle if he is the centre item
        if center_slot == "robo":
            self._paint_slot(painter, "robo", int(w / 2 - 11), 22, h, Qt.AlignmentFlag.AlignCenter)

    def _paint_ai_dot(self, painter, x, h):
        painter.setPen(Qt.PenStyle.NoPen)
        halo = QColor(self.agent_color)
        halo.setAlpha(int(40 + 30 * math.sin(self.pulse_phase)))
        painter.setBrush(QBrush(halo))
        painter.drawEllipse(x, int(h / 2 - 8), 16, 16)
        painter.setBrush(QBrush(self.agent_color))
        painter.drawEllipse(x + 3, int(h / 2 - 5), 10, 10)

    def _paint_battery(self, painter, x, h):
        bat_w, bat_h = 20, 10
        bat_y = int(h / 2 - bat_h / 2)
        painter.setPen(QPen(QColor(self.theme["text_secondary"]), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x, bat_y, bat_w, bat_h, 2, 2)
        painter.drawRect(x + bat_w, bat_y + 3, 2, 4)
        fill_w = max(2, int((bat_w - 4) * (self.battery_pct / 100.0)))
        fill_color = QColor(self.theme["success"] if self.battery_pct > 20 else self.theme["danger"])
        painter.setBrush(QBrush(fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(x + 2, bat_y + 2, fill_w, bat_h - 4)

    def _paint_activity(self, painter, activity, left, right, h):
        color = QColor(activity.get("color") or self.theme["accent"])
        painter.setPen(QColor(self.theme["text_primary"]))
        metrics = painter.fontMetrics()
        text = metrics.elidedText(activity["text"], Qt.TextElideMode.ElideRight, max(10, right - left))
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
