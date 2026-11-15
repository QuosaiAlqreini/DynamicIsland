"""Pick any colour on screen (as in CrestIsland): a magnifier follows the cursor,
click to copy HEX, RGB and HSL. Esc or right-click cancels."""
from PyQt6.QtCore import Qt, QRect, QRectF, QPoint, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor, QGuiApplication
from PyQt6.QtWidgets import QWidget, QApplication


def color_formats(c):
    h, s, l, _a = c.getHslF()
    return {"hex": c.name().upper(), "rgb": f"rgb({c.red()}, {c.green()}, {c.blue()})",
            "hsl": f"hsl({round(max(h, 0) * 360)}, {round(s * 100)}%, {round(l * 100)}%)"}


def contrast_ratio(a, b):
    def lum(c):
        def ch(v):
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


class ColorPicker(QWidget):
    picked = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self.screen_ref = screen
        self.shot = screen.grabWindow(0)
        self.image = self.shot.toImage()
        self.ratio = self.shot.devicePixelRatio() or 1.0
        self.setGeometry(screen.geometry())
        self.pos_local = self.mapFromGlobal(QCursor.pos())

    def color_at(self, p):
        x = int(min(max(p.x() * self.ratio, 0), self.image.width() - 1))
        y = int(min(max(p.y() * self.ratio, 0), self.image.height() - 1))
        return self.image.pixelColor(x, y)

    def start(self):
        self.show()
        self.raise_()
        self.activateWindow()
        self.grabKeyboard()

    def paintEvent(self, event):
        p = QPainter(self)
        p.drawPixmap(self.rect(), self.shot)
        pos = self.pos_local
        c = self.color_at(pos)
        # Magnifier: 11x11 pixels around the cursor, drawn big
        zoom, cells = 10, 11
        size = zoom * cells
        box = QRect(pos.x() + 24, pos.y() + 24, size, size)
        if box.right() > self.width():
            box.moveRight(pos.x() - 24)
        if box.bottom() + 40 > self.height():
            box.moveBottom(pos.y() - 64)
        src = QRect(int(pos.x() * self.ratio) - cells // 2, int(pos.y() * self.ratio) - cells // 2, cells, cells)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        p.drawImage(box, self.image, src)
        p.setPen(QPen(QColor(255, 255, 255, 230), 2))
        p.drawRect(box)
        mid = QRect(box.x() + (cells // 2) * zoom, box.y() + (cells // 2) * zoom, zoom, zoom)
        p.setPen(QPen(QColor(0, 0, 0, 220), 1))
        p.drawRect(mid)
        # Label
        label = QRect(box.x(), box.bottom() + 6, size, 30)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor(20, 22, 28, 230))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(label), 8, 8)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(label.x() + 6, label.y() + 6, 18, 18), 4, 4)
        p.setPen(QColor(240, 240, 245))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.drawText(label.adjusted(30, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, c.name().upper())

    def mouseMoveEvent(self, event):
        self.pos_local = event.position().toPoint()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.picked.emit(self.color_at(event.position().toPoint()))
        self._finish()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._finish()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.picked.emit(self.color_at(self.pos_local))
            self._finish()

    def _finish(self):
        self.releaseKeyboard()
        self.close()
