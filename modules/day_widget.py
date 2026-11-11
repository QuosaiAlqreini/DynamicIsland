"""Day tab: water intake ring and (optional) prayer times with a sun arc."""
import datetime as dt
import math

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, QFormLayout,
    QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox
)

from config import ConfigManager
from services import prayer
from styles import badge_style, small_button_style, dialog_style


class WaterRing(QWidget):
    def __init__(self, theme, day, parent=None):
        super().__init__(parent)
        self.theme, self.day = theme, day
        self.setFixedSize(96, 96)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(8, 8, 80, 80)
        pen = QPen(QColor(self.theme["bg_secondary"]), 8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        pen.setColor(QColor(self.theme["accent"]))
        p.setPen(pen)
        p.drawArc(rect, 90 * 16, -int(self.day.water_fraction * 360 * 16))
        p.setPen(QColor(self.theme["text_primary"]))
        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        p.drawText(self.rect().adjusted(0, -6, 0, 0), Qt.AlignmentFlag.AlignCenter,
                   f"{self.day.water_ml / 1000:.2g} L")
        p.setFont(QFont("Segoe UI", 7))
        p.setPen(QColor(self.theme["text_secondary"]))
        p.drawText(self.rect().adjusted(0, 22, 0, 0), Qt.AlignmentFlag.AlignCenter,
                   f"of {self.day.water_goal / 1000:.2g} L")


class SunArc(QWidget):
    """Sun's path from sunrise to sunset with the prayer times marked."""

    def __init__(self, theme, day, parent=None):
        super().__init__(parent)
        self.theme, self.day = theme, day
        self.setMinimumHeight(64)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        times = self.day.prayer_times()
        now = dt.datetime.now()
        rise, sunset = times["Sunrise"], times["Maghrib"]
        span = max(1.0, (sunset - rise).total_seconds())
        cx, base, rx, ry = w / 2, h - 10, w / 2 - 14, h - 22

        def point(when):
            f = (when - rise).total_seconds() / span
            ang = math.pi * (1 - max(0.0, min(1.0, f)))
            return QPointF(cx + rx * math.cos(ang), base - ry * math.sin(ang))

        p.setPen(QPen(QColor(self.theme["border_color"]), 1))
        p.drawLine(QPointF(6, base), QPointF(w - 6, base))
        pen = QPen(QColor(self.theme["text_secondary"]), 1.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawArc(QRectF(cx - rx, base - ry, 2 * rx, 2 * ry), 0, 180 * 16)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(self.theme["text_secondary"])))
        for name in ("Dhuhr", "Asr"):
            p.drawEllipse(point(times[name]), 2.5, 2.5)
        if rise <= now <= sunset:
            sun = point(now)
            glow = QColor(self.theme["warning"])
            glow.setAlpha(70)
            p.setBrush(QBrush(glow))
            p.drawEllipse(sun, 9, 9)
            p.setBrush(QBrush(QColor(self.theme["warning"])))
            p.drawEllipse(sun, 5, 5)
        else:
            p.setPen(QColor(self.theme["text_secondary"]))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect().adjusted(0, 0, 0, -14), Qt.AlignmentFlag.AlignCenter, "🌙")


class DaySettings(QDialog):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowTitle("Day settings")
        self.setStyleSheet(dialog_style(theme))
        self.setMinimumWidth(420)
        c = self.config
        form = QFormLayout(self)
        form.addRow(QLabel("<b>💧 Water</b>"))
        self.goal = QSpinBox()
        self.goal.setRange(500, 6000)
        self.goal.setSingleStep(250)
        self.goal.setSuffix(" ml")
        self.goal.setValue(int(c.get("water_goal_ml", 2000)))
        form.addRow("Daily goal", self.goal)
        self.glass = QSpinBox()
        self.glass.setRange(50, 1000)
        self.glass.setSingleStep(50)
        self.glass.setSuffix(" ml")
        self.glass.setValue(int(c.get("water_glass_ml", 250)))
        form.addRow("One glass", self.glass)
        self.remind = QSpinBox()
        self.remind.setRange(0, 240)
        self.remind.setSingleStep(15)
        self.remind.setSuffix(" min")
        self.remind.setSpecialValueText("Off")
        self.remind.setValue(int(c.get("water_remind_min", 0)))
        form.addRow("Remind me every", self.remind)

        form.addRow(QLabel("<b>🕌 Prayer times</b> (calculated on this PC, nothing is sent anywhere)"))
        self.enabled = QCheckBox("Show prayer times and remind me")
        self.enabled.setChecked(bool(c.get("prayer_enabled", False)))
        form.addRow(self.enabled)
        self.city = QComboBox()
        self.city.addItem("Custom location", None)
        for name in sorted(prayer.CITIES):
            self.city.addItem(name, name)
        self.city.setCurrentIndex(max(0, self.city.findData(c.get("prayer_city", "Riyadh"))))
        self.city.currentIndexChanged.connect(self._on_city)
        form.addRow("City", self.city)
        self.lat = QDoubleSpinBox()
        self.lat.setRange(-66, 66)
        self.lat.setDecimals(4)
        self.lat.setValue(float(c.get("prayer_lat", 24.7136)))
        self.lng = QDoubleSpinBox()
        self.lng.setRange(-180, 180)
        self.lng.setDecimals(4)
        self.lng.setValue(float(c.get("prayer_lng", 46.6753)))
        form.addRow("Latitude", self.lat)
        form.addRow("Longitude", self.lng)
        self.method = QComboBox()
        for key, spec in prayer.METHODS.items():
            self.method.addItem(spec[0], key)
        self.method.setCurrentIndex(max(0, self.method.findData(c.get("prayer_method", "umm_al_qura"))))
        form.addRow("Method", self.method)
        self.hanafi = QCheckBox("Hanafi Asr (later Asr time)")
        self.hanafi.setChecked(bool(c.get("prayer_asr_hanafi", False)))
        form.addRow(self.hanafi)
        self.pause = QCheckBox("Pause music at prayer time")
        self.pause.setChecked(bool(c.get("prayer_pause_media", False)))
        form.addRow(self.pause)
        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Save")
        ok.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(ok)
        form.addRow(row)

    def _on_city(self):
        name = self.city.currentData()
        if name:
            self.lat.setValue(prayer.CITIES[name][0])
            self.lng.setValue(prayer.CITIES[name][1])

    def _save(self):
        c = self.config
        c.set("water_goal_ml", self.goal.value())
        c.set("water_glass_ml", self.glass.value())
        c.set("water_remind_min", self.remind.value())
        c.set("prayer_enabled", self.enabled.isChecked())
        c.set("prayer_city", self.city.currentData() or "")
        c.set("prayer_lat", self.lat.value())
        c.set("prayer_lng", self.lng.value())
        c.set("prayer_method", self.method.currentData())
        c.set("prayer_asr_hanafi", self.hanafi.isChecked())
        c.set("prayer_pause_media", self.pause.isChecked())
        self.accept()


class DayWidget(QWidget):
    def __init__(self, theme, day_service, parent=None):
        super().__init__(parent)
        self.theme, self.day = theme, day_service
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 6)
        root.setSpacing(12)

        # Water column
        wcol = QVBoxLayout()
        wcol.setSpacing(4)
        self.water_badge = QLabel("💧 WATER")
        self.water_badge.setFixedHeight(20)
        wcol.addWidget(self.water_badge, alignment=Qt.AlignmentFlag.AlignLeft)
        wcol.addStretch()
        self.ring = WaterRing(theme, day_service)
        wcol.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignCenter)
        wcol.addStretch()
        wbtns = QHBoxLayout()
        wbtns.setSpacing(4)
        self.btn_drink = QPushButton("+ Glass")
        self.btn_drink.clicked.connect(lambda: self.day.add_water())
        self.btn_undo = QPushButton("↶")
        self.btn_undo.setToolTip("Undo one glass")
        self.btn_undo.clicked.connect(lambda: self.day.add_water(-self.day.glass_ml))
        wbtns.addWidget(self.btn_drink)
        wbtns.addWidget(self.btn_undo)
        wcol.addLayout(wbtns)
        root.addLayout(wcol)

        # Prayer column
        pcol = QVBoxLayout()
        pcol.setSpacing(2)
        head = QHBoxLayout()
        self.prayer_badge = QLabel("🕌 PRAYER TIMES")
        head.addWidget(self.prayer_badge)
        head.addStretch()
        self.next_label = QLabel("")
        head.addWidget(self.next_label)
        self.btn_settings = QPushButton("⚙")
        self.btn_settings.setToolTip("Water goal, city, calculation method, reminders")
        self.btn_settings.clicked.connect(self.open_settings)
        head.addWidget(self.btn_settings)
        pcol.addLayout(head)
        self.arc = SunArc(theme, day_service)
        pcol.addWidget(self.arc, 1)
        self.times_label = QLabel("")
        self.times_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.times_label.setTextFormat(Qt.TextFormat.RichText)
        pcol.addWidget(self.times_label)
        self.setup_hint = QLabel("Prayer times are off.\nClick ⚙ to pick your city and turn them on.")
        self.setup_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pcol.addWidget(self.setup_hint, 1)
        root.addLayout(pcol, 1)

        self.day.changed.connect(self.refresh)
        self._apply_styles()
        self.refresh()

    def _apply_styles(self):
        t = self.theme
        self.water_badge.setStyleSheet(badge_style(t))
        self.prayer_badge.setStyleSheet(badge_style(t))
        self.next_label.setStyleSheet(f"color: {t['accent']}; font-size: 10px; font-weight: 700;")
        self.times_label.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px;")
        self.setup_hint.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px;")
        css = small_button_style(t)
        for b in (self.btn_drink, self.btn_undo, self.btn_settings):
            b.setStyleSheet(css)

    def update_theme(self, theme):
        self.theme = self.ring.theme = self.arc.theme = theme
        self._apply_styles()
        self.refresh()

    def open_settings(self):
        if DaySettings(self.theme, self.window()).exec():
            self.day.tick()

    def refresh(self):
        self.ring.update()
        on = self.day.prayer_enabled
        self.arc.setVisible(on)
        self.times_label.setVisible(on)
        self.setup_hint.setVisible(not on)
        self.next_label.setText(self.day.next_prayer_text() if on else "")
        if not on:
            return
        now = dt.datetime.now()
        nxt = self.day.next_prayer(now)
        parts = []
        for name, when in self.day.prayer_times(now).items():
            if name == "Sunrise":
                continue
            cell = f"{name} {when:%H:%M}"
            if nxt and nxt[0] == name and nxt[1].date() == now.date():
                cell = f"<b style='color:{self.theme['text_primary']}'>{cell}</b>"
            parts.append(cell)
        self.times_label.setText(" &nbsp;·&nbsp; ".join(parts))
        self.arc.update()
