"""Robo: the island's little character. Drawn with QPainter so it scales from
the 16px pill icon to the big one in the Agents tab.

Moods: idle, focused (agent working), curious (agent needs you), happy (done),
wink, dizzy (poked too often).
"""
import math
import time

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QPixmap, QCursor
from PyQt6.QtWidgets import QWidget

MOOD_COLORS = {"idle": "success", "focused": "accent", "curious": "warning",
               "happy": "success", "wink": "accent_secondary", "dizzy": "danger"}


def paint_robo(p, rect, mood, phase, theme):
    """Draw Robo inside `rect` (QRectF). `phase` is a running time in seconds."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = min(rect.width(), rect.height())
    cx, cy = rect.center().x(), rect.center().y()
    bob = math.sin(phase * (5 if mood == "focused" else 2)) * s * (0.03 if mood != "dizzy" else 0.0)
    tilt = math.sin(phase * 9) * 7 if mood == "dizzy" else (6 if mood == "curious" else 0)
    p.translate(cx, cy + bob)
    p.rotate(tilt)
    color = QColor(theme.get(MOOD_COLORS.get(mood, "accent"), "#00f0ff"))

    # antenna
    if s >= 28:
        p.setPen(QPen(color, max(1.2, s * 0.045)))
        p.drawLine(QPointF(0, -s * 0.36), QPointF(0, -s * 0.47))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(color))
        p.drawEllipse(QPointF(0, -s * 0.49), s * 0.045, s * 0.045)

    # head
    head = QRectF(-s * 0.44, -s * 0.36, s * 0.88, s * 0.72)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    p.drawRoundedRect(head, s * 0.24, s * 0.24)

    # face plate
    face = head.adjusted(s * 0.09, s * 0.10, -s * 0.09, -s * 0.10)
    p.setBrush(QBrush(QColor(theme.get("bg_color", "#0b0c10"))))
    p.drawRoundedRect(face, s * 0.14, s * 0.14)

    # eyes
    ex, ey, ew, eh = s * 0.17, 0.0, s * 0.11, s * 0.20
    blink = (phase % 4.2) > 4.05 and mood in ("idle", "focused", "curious")
    look = math.sin(phase * 3) * s * 0.035 if mood == "focused" else 0
    pen = QPen(color, max(1.4, s * 0.06))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    for side in (-1, 1):
        x = side * ex + look
        if mood == "happy" or (mood == "wink" and side == 1):
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            path = QPainterPath()
            path.moveTo(x - ew * 0.8, ey + eh * 0.2)
            path.quadTo(x, ey - eh * 0.6, x + ew * 0.8, ey + eh * 0.2)
            p.drawPath(path)
        elif mood == "dizzy":
            p.setPen(pen)
            d = ew * 0.7
            p.drawLine(QPointF(x - d, ey - d), QPointF(x + d, ey + d))
            p.drawLine(QPointF(x - d, ey + d), QPointF(x + d, ey - d))
        elif blink:
            p.setPen(pen)
            p.drawLine(QPointF(x - ew * 0.6, ey), QPointF(x + ew * 0.6, ey))
        else:
            h = eh * (1.25 if mood == "curious" and side == 1 else 0.7 if mood == "focused" else 1.0)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(color))
            p.drawRoundedRect(QRectF(x - ew / 2, ey - h / 2, ew, h), ew / 2, ew / 2)
    p.restore()


def mood_for(status):
    return {"working": "focused", "waiting": "curious", "done": "happy"}.get(status, "idle")


class RoboWidget(QWidget):
    """Big Robo: poke him (click) or drag him onto a window to ask about it."""
    dropped_on_screen = pyqtSignal(QPointF)   # global position where Robo was dropped

    def __init__(self, theme, size=84, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.mood = "idle"
        self._override = None        # (mood, until)
        self._pokes = []
        self._press = None
        self._dragging = False
        self._t0 = time.monotonic()
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("This is Robo.\nDrag him onto a window to ask the AI about it.\nPoke him if you like.")
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    def _tick(self):
        if self.isVisible():
            self.update()

    def set_mood(self, mood):
        self.mood = mood
        self.update()

    def flash_mood(self, mood, seconds=2.5):
        self._override = (mood, time.monotonic() + seconds)
        self.update()

    def current_mood(self):
        if self._override:
            mood, until = self._override
            if time.monotonic() < until:
                return mood
            self._override = None
        return self.mood

    def paintEvent(self, event):
        if self._dragging:
            return           # Robo is "in your hand" (he is the cursor)
        p = QPainter(self)
        paint_robo(p, QRectF(self.rect()), self.current_mood(), time.monotonic() - self._t0, self.theme)

    def _cursor_pixmap(self):
        pm = QPixmap(56, 56)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        paint_robo(p, QRectF(4, 4, 48, 48), "curious", 0.0, self.theme)
        p.end()
        return pm

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition()

    def mouseMoveEvent(self, event):
        if self._press is not None and not self._dragging:
            if (event.globalPosition() - self._press).manhattanLength() > 8:
                self._dragging = True
                self.setCursor(QCursor(self._cursor_pixmap(), 28, 28))
                self.grabMouse()
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._dragging:
            self._dragging = False
            self.releaseMouse()
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.update()
            if not self.window().geometry().contains(event.globalPosition().toPoint()):
                self.dropped_on_screen.emit(event.globalPosition())
        elif self._press is not None:
            now = time.monotonic()
            self._pokes = [t for t in self._pokes if now - t < 2.5] + [now]
            self.flash_mood("dizzy" if len(self._pokes) >= 4 else "wink", 3.0 if len(self._pokes) >= 4 else 1.2)
        self._press = None
