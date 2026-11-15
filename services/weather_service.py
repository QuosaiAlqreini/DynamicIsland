"""Weather from Open-Meteo (free, no account). Uses the location set for prayer
times / Day settings. Only the coordinates are sent."""
import threading

import requests
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

# WMO weather codes -> (day icon, night icon, words)
CODES = {0: ("☀️", "🌙", "Clear"), 1: ("🌤️", "🌙", "Mostly clear"), 2: ("⛅", "☁️", "Partly cloudy"),
         3: ("☁️", "☁️", "Cloudy"), 45: ("🌫️", "🌫️", "Fog"), 48: ("🌫️", "🌫️", "Fog"),
         51: ("🌦️", "🌧️", "Drizzle"), 53: ("🌦️", "🌧️", "Drizzle"), 55: ("🌧️", "🌧️", "Drizzle"),
         61: ("🌦️", "🌧️", "Light rain"), 63: ("🌧️", "🌧️", "Rain"), 65: ("🌧️", "🌧️", "Heavy rain"),
         66: ("🌧️", "🌧️", "Freezing rain"), 67: ("🌧️", "🌧️", "Freezing rain"),
         71: ("🌨️", "🌨️", "Light snow"), 73: ("🌨️", "🌨️", "Snow"), 75: ("❄️", "❄️", "Heavy snow"),
         77: ("🌨️", "🌨️", "Snow grains"), 80: ("🌦️", "🌧️", "Showers"), 81: ("🌧️", "🌧️", "Showers"),
         82: ("⛈️", "⛈️", "Heavy showers"), 85: ("🌨️", "🌨️", "Snow showers"), 86: ("🌨️", "🌨️", "Snow showers"),
         95: ("⛈️", "⛈️", "Thunderstorm"), 96: ("⛈️", "⛈️", "Thunderstorm"), 99: ("⛈️", "⛈️", "Thunderstorm")}


def describe(code, is_day=True):
    day, night, words = CODES.get(int(code), ("🌡️", "🌡️", "Weather"))
    return (day if is_day else night), words


def parse(data):
    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    icon, words = describe(cur.get("weather_code", -1), bool(cur.get("is_day", 1)))
    return {"temp": round(float(cur.get("temperature_2m", 0))), "icon": icon, "words": words,
            "is_day": bool(cur.get("is_day", 1)),
            "high": round(float((daily.get("temperature_2m_max") or [0])[0])),
            "low": round(float((daily.get("temperature_2m_min") or [0])[0])),
            "sunrise": (daily.get("sunrise") or [""])[0], "sunset": (daily.get("sunset") or [""])[0]}


class WeatherService(QObject):
    updated = pyqtSignal(dict)
    _done = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.current = None
        self._busy = False
        self._done.connect(self._on_done)
        self.timer = QTimer(self)
        self.timer.setInterval(20 * 60 * 1000)
        self.timer.timeout.connect(self.refresh)

    @property
    def enabled(self):
        return bool(self.config.get("weather_enabled", True)) and not self.config.get("eco_mode", False)

    def start(self):
        self.timer.start()
        QTimer.singleShot(2000, self.refresh)

    def text(self):
        w = self.current
        return f"{w['icon']} {w['temp']}°" if w else ""

    def refresh(self):
        if self._busy or not self.enabled:
            return
        self._busy = True
        lat = float(self.config.get("prayer_lat", 24.7136))
        lng = float(self.config.get("prayer_lng", 46.6753))
        unit = "fahrenheit" if self.config.get("weather_unit", "c") == "f" else "celsius"

        def work():
            try:
                r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
                    "latitude": lat, "longitude": lng, "timezone": "auto", "forecast_days": 1,
                    "current": "temperature_2m,weather_code,is_day", "temperature_unit": unit,
                    "daily": "temperature_2m_max,temperature_2m_min,sunrise,sunset"})
                r.raise_for_status()
                result = parse(r.json())
            except Exception:
                result = None
            try:
                self._done.emit(result)
            except RuntimeError:
                pass                      # the app closed while we were waiting
        threading.Thread(target=work, daemon=True).start()

    def _on_done(self, result):
        self._busy = False
        if result:
            self.current = result
            self.updated.emit(result)
