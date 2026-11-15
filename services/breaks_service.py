"""Break reminders counted from active computer time (as in CrestIsland):
every 20 minutes look away for 20 seconds (eye rest), every hour a real break.
Paused while you're away, in full screen, or in a focus session."""
import sys
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

AWAY_RESET_S = 5 * 60      # this long without input counts as a break already taken


def idle_seconds():
    if sys.platform != "win32":
        return 0.0
    import ctypes
    from ctypes import wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return max(0.0, (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0)


class BreaksService(QObject):
    eye_break = pyqtSignal()
    long_break = pyqtSignal()

    def __init__(self, parent=None, idle_fn=idle_seconds, step=15):
        super().__init__(parent)
        self.config = ConfigManager()
        self.idle_fn = idle_fn
        self.step = step
        self.active_eye = 0.0          # active seconds since the last eye break
        self.active_long = 0.0
        self.paused = lambda: False    # set by the island (full screen, focus timer...)
        self.timer = QTimer(self)
        self.timer.setInterval(step * 1000)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def tick(self, seconds=None):
        seconds = self.step if seconds is None else seconds
        idle = self.idle_fn()
        if idle >= AWAY_RESET_S:
            self.active_eye = self.active_long = 0.0      # you were away: that was a break
            return
        if idle > seconds or self.paused():
            return
        self.active_eye += seconds
        self.active_long += seconds
        if self.config.get("break_eye_enabled", True) and self.active_eye >= 20 * 60:
            self.active_eye = 0.0
            self.eye_break.emit()
        if self.config.get("break_hourly_enabled", True) and self.active_long >= 60 * 60:
            self.active_long = 0.0
            self.active_eye = 0.0
            self.long_break.emit()
