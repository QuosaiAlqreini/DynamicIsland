"""Day tab: water intake ring and (optional) prayer times with a sun arc."""
import datetime as dt
import math

import threading

import requests
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QDialog, QFormLayout,
    QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit
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
    _geo_done = pyqtSignal(list, str)

    def __init__(self, theme, parent=None):
        super().__init__(parent)
        # The island is always-on-top; settings windows must sit above it
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.config = ConfigManager()
        self.setWindowTitle("Day settings")
        self.setStyleSheet(dialog_style(theme))
        self.setMinimumWidth(500)
        self._geo_done.connect(self._on_geo_results)
        self._geo_results = []
        c = self.config
        from PyQt6.QtWidgets import QScrollArea, QFrame
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("daybody")
        body.setStyleSheet("QWidget#daybody { background: transparent; }")
        scroll.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        scroll.setWidget(body)
        outer.addWidget(scroll)
        self.resize(560, 640)
        form = QFormLayout(body)
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

        form.addRow(QLabel("<b>🕌 Prayer times</b> (calculated on this PC)"))
        self.enabled = QCheckBox("Show prayer times and remind me")
        # First time here: on by default (you opened this to set it up)
        self.enabled.setChecked(bool(c.get("prayer_enabled", False))
                                or not c.get("prayer_location_set", False))
        form.addRow(self.enabled)

        # Country + city: what was saved, or (first time) a guess from Windows' region
        if c.get("prayer_location_set", False):
            saved_city = c.get("prayer_city", "") or ""
            saved_country = c.get("prayer_country") or prayer.country_of(saved_city)
            start_lat, start_lng = float(c.get("prayer_lat", 0)), float(c.get("prayer_lng", 0))
        else:
            saved_country, saved_city, start_lat, start_lng = prayer.detect_default_location()
        self.country = QComboBox()
        self.country.addItem("Custom location", None)
        for name in prayer.COUNTRIES:
            self.country.addItem(name, name)
        self.city = QComboBox()
        self.country.setCurrentIndex(max(0, self.country.findData(saved_country)))
        self._fill_cities(saved_city)
        self.country.currentIndexChanged.connect(self._on_country)
        self.city.currentIndexChanged.connect(self._on_city)
        # Choosing a place means you want the times: tick the box for you
        for combo in (self.country, self.city):
            combo.activated.connect(lambda *_: self.enabled.setChecked(True))
        form.addRow("Country", self.country)
        form.addRow("City", self.city)

        # Search any town
        srow = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Find any town, e.g. Gießen, Paderborn, Wolfsburg…")
        self.search.returnPressed.connect(self._search)
        srow.addWidget(self.search, 1)
        self.search_btn = QPushButton("🔎 Find")
        self.search_btn.clicked.connect(self._search)
        srow.addWidget(self.search_btn)
        form.addRow("Search", srow)
        self.results = QComboBox()
        self.results.setVisible(False)
        self.results.activated.connect(self._use_result)
        form.addRow("", self.results)
        self.search_note = QLabel("Searching sends only the town name to open-meteo.com.")
        self.search_note.setWordWrap(True)
        form.addRow("", self.search_note)

        self.lat = QDoubleSpinBox()
        self.lat.setRange(-66, 66)
        self.lat.setDecimals(4)
        self.lat.setValue(start_lat)
        self.lng = QDoubleSpinBox()
        self.lng.setRange(-180, 180)
        self.lng.setDecimals(4)
        self.lng.setValue(start_lng)
        coords = QHBoxLayout()
        coords.addWidget(QLabel("Lat"))
        coords.addWidget(self.lat)
        coords.addWidget(QLabel("Lng"))
        coords.addWidget(self.lng)
        form.addRow("Location", coords)

        self.method = QComboBox()
        start_method = (c.get("prayer_method", "mwl") if c.get("prayer_location_set", False)
                        else prayer.suggested_method(saved_country))
        self._fill_methods(start_method)
        form.addRow("Method", self.method)
        self.high_lat = QComboBox()
        for key, label in prayer.HIGH_LAT_RULES.items():
            self.high_lat.addItem(label, key)
        self.high_lat.setCurrentIndex(max(0, self.high_lat.findData(c.get("prayer_high_lat", "angle"))))
        self.high_lat.setToolTip("In Germany and further north the sky never gets fully dark in summer,\n"
                                 "so Fajr and Isha need a rule. Most German timetables use angle-based.")
        form.addRow("Summer nights", self.high_lat)
        self.hanafi = QCheckBox("Hanafi Asr (later Asr time)")
        self.hanafi.setChecked(bool(c.get("prayer_asr_hanafi", False)))
        form.addRow(self.hanafi)

        # Per-prayer adjustments to match the local mosque
        offsets = c.get("prayer_offsets", {}) or {}
        orow = QHBoxLayout()
        self.offset_spins = {}
        for name in ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"):
            box = QVBoxLayout()
            lab = QLabel(name)
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin = QSpinBox()
            spin.setRange(-60, 60)
            spin.setSuffix("m")
            spin.setValue(int(offsets.get(name, 0)))
            box.addWidget(lab)
            box.addWidget(spin)
            orow.addLayout(box)
            self.offset_spins[name] = spin
        form.addRow("Adjust (min)", orow)
        tip = QLabel("Your mosque's timetable differs by a few minutes? Enter the difference here, "
                     "e.g. +2 for Maghrib.")
        tip.setWordWrap(True)
        form.addRow("", tip)

        self.preview = QLabel("")
        self.preview.setWordWrap(True)
        form.addRow("Today", self.preview)
        for widget in (self.lat, self.lng):
            widget.valueChanged.connect(self._update_preview)
        for widget in (self.method, self.high_lat):
            widget.currentIndexChanged.connect(self._update_preview)
        self.hanafi.toggled.connect(self._update_preview)
        for spin in self.offset_spins.values():
            spin.valueChanged.connect(self._update_preview)

        form.addRow(QLabel("<b>☀️ Weather</b> (Open-Meteo, uses the location above; only coordinates are sent)"))
        self.weather_on = QCheckBox("Show the weather")
        self.weather_on.setChecked(bool(c.get("weather_enabled", True)))
        form.addRow(self.weather_on)
        self.weather_unit = QComboBox()
        self.weather_unit.addItem("°C", "c")
        self.weather_unit.addItem("°F", "f")
        self.weather_unit.setCurrentIndex(max(0, self.weather_unit.findData(c.get("weather_unit", "c"))))
        form.addRow("Unit", self.weather_unit)
        form.addRow(QLabel("<b>🧘 Breaks & notices</b> (counted from the time you're actually using the PC)"))
        self.break_eye = QCheckBox("Every 20 minutes: look away for 20 seconds (rests your eyes)")
        self.break_eye.setChecked(bool(c.get("break_eye_enabled", True)))
        form.addRow(self.break_eye)
        self.break_hour = QCheckBox("Every hour: stand up and take a short break")
        self.break_hour.setChecked(bool(c.get("break_hourly_enabled", True)))
        form.addRow(self.break_hour)
        self.notices_on = QCheckBox("Little notices in the notch: Caps Lock, charger, internet lost / back")
        self.notices_on.setChecked(bool(c.get("notices_enabled", True)))
        form.addRow(self.notices_on)
        self.pause = QCheckBox("Pause music at prayer time")
        self.pause.setChecked(bool(c.get("prayer_pause_media", False)))
        form.addRow(self.pause)
        # Buttons stay visible below the scrolling page
        row = QHBoxLayout()
        row.setContentsMargins(12, 6, 12, 10)
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Save")
        ok.setDefault(True)
        ok.clicked.connect(self._save)
        row.addWidget(cancel)
        row.addWidget(ok)
        outer.addLayout(row)
        self._update_preview()

    # ------------------------------------------------------------ presets
    def _fill_methods(self, select=None):
        """Plain method names; the one that fits the chosen country first, marked ★."""
        country = self.country.currentData()
        best = prayer.suggested_method(country) if country else None
        select = select or self.method.currentData() or best or "mwl"
        self.method.blockSignals(True)
        self.method.clear()
        order = ([best] if best else []) + [k for k in prayer.METHODS if k != best]
        for key in order:
            label = prayer.METHODS[key][0]
            if key == best:
                label = f"★ {label} — recommended for {country}"
            self.method.addItem(label, key)
            if key == best and len(order) > 1:
                self.method.insertSeparator(self.method.count())
        self.method.setCurrentIndex(max(0, self.method.findData(select)))
        self.method.blockSignals(False)

    def _fill_cities(self, select=None):
        self.city.blockSignals(True)
        self.city.clear()
        country = self.country.currentData()
        if country:
            for name in prayer.COUNTRIES[country]:
                self.city.addItem(name, name)
            idx = self.city.findData(select) if select else -1
            self.city.setCurrentIndex(idx if idx >= 0 else -1)
            if select and self.city.findData(select) < 0 and select not in prayer.CITIES:
                self.city.addItem(select, select)          # a searched town in this country
                self.city.setCurrentIndex(self.city.count() - 1)
        else:
            self.city.addItem(select or "Custom coordinates", None)
        self.city.blockSignals(False)

    def _on_country(self):
        self._fill_cities()
        country = self.country.currentData()
        if country:
            self._fill_methods(prayer.suggested_method(country))
            self.city.setCurrentIndex(0)
            self._on_city()

    def _on_city(self):
        name = self.city.currentData()
        if name and name in prayer.CITIES:
            self.lat.setValue(prayer.CITIES[name][0])
            self.lng.setValue(prayer.CITIES[name][1])

    # ------------------------------------------------------------- search
    def _search(self):
        name = self.search.text().strip()
        if len(name) < 2:
            return
        self.search_btn.setEnabled(False)
        self.search_note.setText("Searching…")
        threading.Thread(target=self._geo_lookup, args=(name,), daemon=True).start()

    def _geo_lookup(self, name):
        try:
            r = requests.get("https://geocoding-api.open-meteo.com/v1/search", timeout=8,
                             params={"name": name, "count": 8, "language": "en", "format": "json"})
            r.raise_for_status()
            found = [(f"{x['name']}, {x.get('admin1', '')}, {x.get('country', '')}".replace(", ,", ","),
                      float(x["latitude"]), float(x["longitude"])) for x in r.json().get("results", [])]
            self._geo_done.emit(found, "" if found else f"No town called “{name}” found.")
        except Exception as e:
            self._geo_done.emit([], f"Search failed ({e.__class__.__name__}). Check the connection or "
                                    "enter the coordinates yourself.")

    def _on_geo_results(self, found, message):
        self.search_btn.setEnabled(True)
        self._geo_results = found
        self.results.clear()
        for label, _lat, _lng in found:
            self.results.addItem(label)
        self.results.setVisible(bool(found))
        self.search_note.setText(message or "Pick your town from the list:")
        if len(found) == 1:
            self._use_result(0)

    def _use_result(self, index):
        if 0 <= index < len(self._geo_results):
            label, lat, lng = self._geo_results[index]
            self.enabled.setChecked(True)
            group = prayer.country_for_place(label)          # keep the town under its country
            self.country.blockSignals(True)
            self.country.setCurrentIndex(max(0, self.country.findData(group)) if group else 0)
            self.country.blockSignals(False)
            self._fill_cities(label.split(",")[0])
            self.lat.setValue(lat)
            self.lng.setValue(lng)
            self._fill_methods(prayer.suggested_method(group) if group else None)
            self.search_note.setText(f"Using {label}.")

    # ------------------------------------------------------------ preview
    def _offsets(self):
        return {name: spin.value() for name, spin in self.offset_spins.items() if spin.value()}

    def _update_preview(self):
        times = prayer.prayer_times(dt.date.today(), self.lat.value(), self.lng.value(),
                                    prayer.local_utc_offset_hours(), self.method.currentData(),
                                    self.hanafi.isChecked(), self.high_lat.currentData(), self._offsets())
        self.preview.setText("  ·  ".join(f"{n} {t:%H:%M}" for n, t in times.items() if n != "Sunrise"))

    def _save(self):
        c = self.config
        c.set("water_goal_ml", self.goal.value())
        c.set("water_glass_ml", self.glass.value())
        c.set("water_remind_min", self.remind.value())
        c.set("prayer_enabled", self.enabled.isChecked())
        c.set("prayer_city", self.city.currentData() or self.city.currentText() or "")
        c.set("prayer_country", self.country.currentData())
        c.set("prayer_location_set", True)
        c.set("prayer_lat", self.lat.value())
        c.set("prayer_lng", self.lng.value())
        c.set("prayer_method", self.method.currentData())
        c.set("prayer_high_lat", self.high_lat.currentData())
        c.set("prayer_offsets", self._offsets())
        c.set("prayer_asr_hanafi", self.hanafi.isChecked())
        c.set("prayer_pause_media", self.pause.isChecked())
        c.set("weather_enabled", self.weather_on.isChecked())
        c.set("weather_unit", self.weather_unit.currentData())
        c.set("break_eye_enabled", self.break_eye.isChecked())
        c.set("break_hourly_enabled", self.break_hour.isChecked())
        c.set("notices_enabled", self.notices_on.isChecked())
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
        dlg = DaySettings(self.theme, self.window())
        runner = getattr(self.window(), "run_dialog", None)
        if (runner(dlg) if runner else dlg.exec()):
            self.day.tick()
            self.refresh()
            pill = getattr(self.window(), "idle_pill", None)
            text = self.day.next_prayer_text()
            if pill is not None and text:
                pill.flash(f"🕌 {text}", self.theme["accent"], 3500)
            weather = getattr(self.window(), "weather_service", None)
            if weather is not None:
                weather.refresh()

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
