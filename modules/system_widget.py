from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QPen, QBrush

class CircularGauge(QWidget):
    def __init__(self, title, unit="%", parent=None):
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.value = 0.0
        self.color = QColor("#00f0ff")
        self.bg_color = QColor("#1e293b")
        self.text_color = QColor("#ffffff")
        self.subtext = ""
        self.setFixedSize(96, 96)

    def set_value(self, val, subtext=""):
        self.value = max(0.0, min(100.0, float(val)))
        self.subtext = subtext
        self.update()

    def set_colors(self, gauge_color, bg_color, text_color):
        self.color = QColor(gauge_color)
        self.bg_color = QColor(bg_color)
        self.text_color = QColor(text_color)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        cx, cy = self.width() / 2, self.height() / 2
        radius = 34
        rect = self.rect().adjusted(10, 10, -10, -10)

        # Background track arc
        pen_bg = QPen(self.bg_color, 6)
        pen_bg.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_bg)
        painter.drawArc(rect, 0, 360 * 16)

        # Value active arc
        pen_val = QPen(self.color, 6)
        pen_val.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_val)
        
        # Start at 90 deg (top), draw clockwise
        start_angle = 90 * 16
        span_angle = -int((self.value / 100.0) * 360 * 16)
        painter.drawArc(rect, start_angle, span_angle)

        # Draw Center Value
        painter.setPen(self.text_color)
        font = QFont("Segoe UI", 11, QFont.Weight.Bold)
        painter.setFont(font)
        val_str = f"{int(self.value)}{self.unit}"
        painter.drawText(self.rect().adjusted(0, -6, 0, 0), Qt.AlignmentFlag.AlignCenter, val_str)

        # Draw Title below value
        font_sub = QFont("Segoe UI", 8, QFont.Weight.DemiBold)
        painter.setFont(font_sub)
        painter.setPen(QColor(self.text_color.red(), self.text_color.green(), self.text_color.blue(), 160))
        painter.drawText(self.rect().adjusted(0, 18, 0, 0), Qt.AlignmentFlag.AlignCenter, self.title)

class AppBar(QWidget):
    """One row: app name, a thin bar for its share of the RAM, and the size."""
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme, self.name, self.size_text, self.share = theme, "", "", 0.0
        self.setFixedHeight(17)

    def set(self, name, size_text, share, tip=""):
        self.name, self.size_text, self.share = name, size_text, max(0.0, min(1.0, share))
        self.setToolTip(tip)
        self.update()

    def paintEvent(self, _e):
        if not self.name:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        track = QColor(self.theme["text_secondary"])
        track.setAlpha(40)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(0, h - 4, w, 3, 1.5, 1.5)
        fill = QColor(self.theme["warning"] if self.share > 0.2 else self.theme["accent"])
        p.setBrush(fill)
        p.drawRoundedRect(0, h - 4, max(3, int(w * self.share)), 3, 1.5, 1.5)
        p.setPen(QColor(self.theme["text_primary"]))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(0, 0, w - 60, h - 4, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.name)
        p.setPen(QColor(self.theme["text_secondary"]))
        p.drawText(w - 60, 0, 60, h - 4, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, self.size_text)


class SystemWidget(QWidget):
    """CPU / RAM / battery, which apps use the RAM, the island's own share, tips and Eco mode."""
    eco_toggled = pyqtSignal(bool)
    ROWS = 5

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.sys_data = {"cpu_percent": 0.0, "mem_percent": 0.0, "mem_used_gb": 0.0, "mem_total_gb": 0.0,
                         "battery_percent": 100, "battery_plugged": True, "uptime": "0h 0m"}
        self._tips, self._tip_i = [], 0
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 6, 14, 6)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(0)
        self.ram_gauge = CircularGauge("RAM", "%")
        self.ram_gauge.setFixedSize(84, 84)
        left.addWidget(self.ram_gauge, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.cpu_label = QLabel("CPU 0%")
        self.gb_label = QLabel("")
        self.bat_label = QLabel("🔋 100%")
        self.uptime_label = QLabel("Up 0h 0m")
        for lbl in (self.gb_label, self.cpu_label, self.bat_label, self.uptime_label):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            left.addWidget(lbl)
        left.addStretch()
        root.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(2)
        head = QHBoxLayout()
        self.title = QLabel("WHAT USES MY RAM")
        head.addWidget(self.title)
        head.addStretch()
        self.own = QLabel("")
        self.own.setToolTip("How much memory this island itself uses")
        head.addWidget(self.own)
        self.eco = QPushButton("🌿 Eco")
        self.eco.setCheckable(True)
        self.eco.setToolTip("Eco mode: no blur, lyrics, weather or build watching; slower polling. "
                            "Lighter on RAM, CPU and battery.")
        self.eco.toggled.connect(self.eco_toggled)
        head.addWidget(self.eco)
        right.addLayout(head)
        self.rows = [AppBar(self.theme) for _ in range(self.ROWS)]
        for r in self.rows:
            right.addWidget(r)
        self.empty = QLabel("Looking…")
        right.addWidget(self.empty)
        right.addStretch()
        self.tip = QLabel("")
        self.tip.setWordWrap(True)
        self.tip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tip.setToolTip("Click for the next tip")
        self.tip.mousePressEvent = lambda _e: self._next_tip()
        right.addWidget(self.tip)
        root.addLayout(right, 1)
        self.footer_label = self.uptime_label        # kept for older callers
        self._apply_styles()

    def _apply_styles(self):
        t = self.theme
        self.ram_gauge.set_colors(t["accent_secondary"], t["bg_secondary"], t["text_primary"])
        for lbl in (self.gb_label, self.cpu_label, self.bat_label, self.uptime_label):
            lbl.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px;")
        self.title.setStyleSheet(f"color: {t['accent']}; font-size: 9px; font-weight: 700; letter-spacing: 1px;")
        self.own.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px;")
        self.empty.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px;")
        self.tip.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px; font-style: italic;")
        from styles import small_button_style
        self.eco.setStyleSheet(small_button_style(t) +
                               f" QPushButton:checked {{ background: {t['success']}; color: {t['bg_color']}; }}")
        for r in self.rows:
            r.theme = t
            r.update()

    def set_eco(self, on):
        self.eco.blockSignals(True)
        self.eco.setChecked(bool(on))
        self.eco.blockSignals(False)

    def update_system(self, stats):
        self.sys_data = stats
        self.ram_gauge.set_value(stats["mem_percent"])
        self.gb_label.setText(f"{stats['mem_used_gb']} / {stats['mem_total_gb']} GB")
        self.cpu_label.setText(f"CPU {stats['cpu_percent']:.0f}%")
        self.bat_label.setText(("🔌 " if stats["battery_plugged"] else "🔋 ") + f"{stats['battery_percent']}%")
        self.uptime_label.setText(f"Up {stats['uptime']}")

    def update_memory(self, result, tips=()):
        from services.memory_service import fmt
        apps, total = result.get("apps", []), result.get("total") or 1
        for row, item in zip(self.rows, list(apps) + [None] * self.ROWS):
            if item:
                name, size, count = item
                row.set(name + (f"  ×{count}" if count > 1 else ""), fmt(size), size / total,
                        f"{name}: {fmt(size)} in {count} process(es), {size / total:.0%} of your RAM")
                row.show()
            else:
                row.hide()
        self.empty.setVisible(not apps)
        self.empty.setText(result.get("error", "Looking…") if not apps else "")
        self.own.setText(f"Island {fmt(result.get('own', 0))}" if result.get("own") else "")
        self._tips = list(tips)
        self._tip_i %= max(1, len(self._tips))
        self._show_tip()

    def _show_tip(self):
        self.tip.setText(("💡 " + self._tips[self._tip_i]) if self._tips else "")

    def _next_tip(self):
        if self._tips:
            self._tip_i = (self._tip_i + 1) % len(self._tips)
            self._show_tip()

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()
