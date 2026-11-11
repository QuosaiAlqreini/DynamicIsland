"""Daily wellbeing: water intake tracking + (optional) prayer times and reminders."""
import datetime as dt

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager
from services import prayer


class DayService(QObject):
    changed = pyqtSignal()
    water_reminder = pyqtSignal()
    prayer_time = pyqtSignal(str)     # prayer name, at its time

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self._times_date = None
        self._times = {}
        self._announced = set()
        self._last_water_nudge = dt.datetime.now()
        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    # -------------------------------------------------------------- water
    @staticmethod
    def _today():
        return dt.date.today().isoformat()

    @property
    def water_goal(self):
        return max(250, int(self.config.get("water_goal_ml", 2000)))

    @property
    def glass_ml(self):
        return max(50, int(self.config.get("water_glass_ml", 250)))

    @property
    def water_ml(self):
        log = self.config.get("water_log", {}) or {}
        return int(log.get(self._today(), 0))

    @property
    def water_fraction(self):
        return min(1.0, self.water_ml / self.water_goal)

    def add_water(self, ml=None):
        ml = self.glass_ml if ml is None else ml
        today = self._today()
        log = dict(self.config.get("water_log", {}) or {})
        log[today] = max(0, int(log.get(today, 0)) + int(ml))
        # keep two weeks of history
        for key in sorted(log)[:-14]:
            del log[key]
        self.config.set("water_log", log)
        self._last_water_nudge = dt.datetime.now()
        self.changed.emit()

    # ------------------------------------------------------------- prayer
    @property
    def prayer_enabled(self):
        return bool(self.config.get("prayer_enabled", False))

    def prayer_times(self, now=None):
        now = now or dt.datetime.now()
        key = (now.date(), self.config.get("prayer_lat"), self.config.get("prayer_lng"),
               self.config.get("prayer_method"), self.config.get("prayer_asr_hanafi"),
               self.config.get("prayer_high_lat"), str(self.config.get("prayer_offsets")))
        if key != self._times_date:
            self._times_date = key
            self._times = prayer.prayer_times(
                now.date(), float(self.config.get("prayer_lat", 24.7136)),
                float(self.config.get("prayer_lng", 46.6753)), prayer.local_utc_offset_hours(),
                self.config.get("prayer_method", "umm_al_qura"),
                bool(self.config.get("prayer_asr_hanafi", False)),
                self.config.get("prayer_high_lat", "angle"), self.config.get("prayer_offsets", {}))
            self._announced = {n for n, t in self._times.items() if t <= now}
        return self._times

    def next_prayer(self, now=None):
        now = now or dt.datetime.now()
        if not self.prayer_enabled:
            return None
        nxt = prayer.next_prayer(self.prayer_times(now), now)
        if nxt:
            return nxt
        # After Isha: tomorrow's Fajr
        tomorrow = prayer.prayer_times(
            now.date() + dt.timedelta(days=1), float(self.config.get("prayer_lat", 24.7136)),
            float(self.config.get("prayer_lng", 46.6753)), prayer.local_utc_offset_hours(),
            self.config.get("prayer_method", "umm_al_qura"),
            bool(self.config.get("prayer_asr_hanafi", False)),
            self.config.get("prayer_high_lat", "angle"), self.config.get("prayer_offsets", {}))
        return "Fajr", tomorrow["Fajr"]

    def next_prayer_text(self, now=None):
        now = now or dt.datetime.now()
        nxt = self.next_prayer(now)
        if not nxt:
            return ""
        name, when = nxt
        mins = int((when - now).total_seconds() // 60)
        if mins < 60:
            return f"{name} in {max(mins, 0)}m"
        return f"{name} {when:%H:%M}"

    # --------------------------------------------------------------- tick
    def tick(self, now=None):
        now = now or dt.datetime.now()
        if self.prayer_enabled:
            for name, when in self.prayer_times(now).items():
                if name != "Sunrise" and when <= now and name not in self._announced:
                    self._announced.add(name)
                    if (now - when).total_seconds() < 120:
                        self.prayer_time.emit(name)
        every = int(self.config.get("water_remind_min", 0) or 0)
        if (every and 8 <= now.hour < 22 and self.water_ml < self.water_goal
                and (now - self._last_water_nudge).total_seconds() >= every * 60):
            self._last_water_nudge = now
            self.water_reminder.emit()
        self.changed.emit()
