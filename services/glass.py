"""Glass for the island: frosted blur of what is behind it, plus the soft
material painting (tint, light rim, specular highlight, shadow).

The frosted blur works by excluding the island from screen capture
(Windows 10 2004+), grabbing the small area behind it a few times a second
and blurring that picture. If Windows refuses, the island still looks like
glass, just without the blur.
"""
import sys

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QBrush, QLinearGradient, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QApplication

WDA_EXCLUDEFROMCAPTURE = 0x11

# name -> (label, tint colour, tint alpha top, tint alpha bottom, rim alpha, highlight alpha, dark text?)
MATERIALS = {
    "frosted": ("Frosted glass", "#1b1e25", 0.50, 0.64, 0.16, 0.10, False),
    "smoke": ("Smoked glass (darker)", "#0e1015", 0.68, 0.80, 0.12, 0.07, False),
    "clear": ("Clear glass (most see-through)", "#20232b", 0.30, 0.44, 0.20, 0.12, False),
    "milk": ("Milk glass (light)", "#f2f4f8", 0.62, 0.74, 0.55, 0.30, True),
    "tinted": ("Tinted glass (accent colour)", None, 0.42, 0.58, 0.18, 0.10, False),
    "solid": ("Solid (no glass)", None, 1.0, 1.0, 0.0, 0.0, False),
}


def exclude_from_capture(hwnd):
    """Keep the island out of screenshots/captures so it can see what's behind it."""
    if sys.platform != "win32" or not hwnd:
        return False
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
        user32.GetWindowDisplayAffinity.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
        if not user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            return False
        got = wintypes.DWORD()
        return bool(user32.GetWindowDisplayAffinity(hwnd, ctypes.byref(got))) and got.value == WDA_EXCLUDEFROMCAPTURE
    except Exception:
        return False


def frosted(pixmap, strength=14):
    """Cheap, smooth blur: shrink a lot, then grow back with smoothing (twice)."""
    if pixmap is None or pixmap.isNull():
        return None
    w, h = pixmap.width(), pixmap.height()
    small = pixmap.scaled(max(1, w // strength), max(1, h // strength),
                          Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    mid = small.scaled(max(1, w // 3), max(1, h // 3),
                       Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
    return mid.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)


def grab_behind(global_rect):
    """Picture of the screen under `global_rect` (logical px), or None."""
    screen = QApplication.screenAt(global_rect.center()) or QApplication.primaryScreen()
    if screen is None:
        return None
    sg = screen.geometry()
    r = global_rect.intersected(sg)
    if r.isEmpty():
        return None
    pm = screen.grabWindow(0, r.x() - sg.x(), r.y() - sg.y(), r.width(), r.height())
    return None if pm.isNull() else pm


def material(theme, name):
    spec = MATERIALS.get(name, MATERIALS["frosted"])
    tint = spec[1] or (theme["accent"] if name == "tinted" else theme["pill_gradient_end"])
    return {"name": name, "tint": QColor(tint), "a_top": spec[2], "a_bottom": spec[3],
            "rim": spec[4], "highlight": spec[5], "dark_text": spec[6]}


def paint_glass(p, path, rect, mat, blur=None, glow=None, shadow=True, notch=False):
    """Paint the island body: shadow, frosted backdrop, tint, highlight, rim, status glow."""
    w, h = rect.width(), rect.height()
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if shadow and h > 12:
        # Soft shadow: a few widening, fading strokes under the body
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i, alpha in enumerate((34, 22, 13, 7)):
            p.setPen(QPen(QColor(0, 0, 0, alpha), 2 + i * 3))
            p.save()
            p.translate(0, 2 + i)
            p.drawPath(path)
            p.restore()
    p.setClipPath(path)
    if blur is not None and mat["name"] != "solid":
        p.drawPixmap(rect.toRect(), blur)
    tint = QColor(mat["tint"])
    g = QLinearGradient(0, 0, 0, h)
    top, bottom = QColor(tint), QColor(tint)
    top.setAlphaF(mat["a_top"] if blur is not None or mat["name"] == "solid" else min(1.0, mat["a_top"] + 0.30))
    bottom.setAlphaF(mat["a_bottom"] if blur is not None or mat["name"] == "solid" else min(1.0, mat["a_bottom"] + 0.24))
    g.setColorAt(0.0, top)
    g.setColorAt(1.0, bottom)
    p.fillPath(path, QBrush(g))
    if glow is not None:
        # Status colour glowing softly from the bottom edge (working / needs you / done / album)
        rg = QRadialGradient(w / 2, h + h * 0.2, max(w, h) * 0.75)
        c = QColor(glow)
        c.setAlpha(70)
        rg.setColorAt(0.0, c)
        c2 = QColor(glow)
        c2.setAlpha(0)
        rg.setColorAt(1.0, c2)
        p.fillPath(path, QBrush(rg))
    if mat["highlight"] > 0:
        # Specular sheen across the top
        hl = QLinearGradient(0, 0, 0, min(h, 60) * 0.9)
        hl.setColorAt(0.0, QColor(255, 255, 255, int(255 * mat["highlight"])))
        hl.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(path, QBrush(hl))
    p.setClipping(False)
    if mat["rim"] > 0:
        # Thin light rim, brighter at the top: the edge of the glass
        rim = QLinearGradient(0, 0, 0, h)
        rim.setColorAt(0.0, QColor(255, 255, 255, 0 if notch else int(255 * mat["rim"])))
        rim.setColorAt(1.0, QColor(255, 255, 255, int(255 * mat["rim"] * 0.45)))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    if glow is not None:
        c = QColor(glow)
        c.setAlpha(150)
        p.setPen(QPen(c, 1.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.restore()


def average_color(pixmap):
    """Soft average colour of an image (for the album glow)."""
    if pixmap is None or pixmap.isNull():
        return None
    img = pixmap.scaled(1, 1, Qt.AspectRatioMode.IgnoreAspectRatio,
                        Qt.TransformationMode.SmoothTransformation).toImage()
    c = img.pixelColor(0, 0)
    h, s, v, _a = c.getHsvF()
    c.setHsvF(max(0.0, h), min(1.0, s * 1.3 + 0.1), max(0.55, v))   # lift so it glows on dark glass
    return c
