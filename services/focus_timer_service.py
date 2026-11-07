"""Focus / Pomodoro countdown that drives a live activity in the idle pill."""
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal


class FocusTimerService(QObject):
    # remaining_sec, total_sec, running
    tick = pyqtSignal(int, int, bool)
    finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.total_sec = 0
        self.remaining_sec = 0
        self.label = "Focus"
        self._end_ts = None
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._on_tick)

    @property
    def running(self):
        return self._end_ts is not None

    @property
    def active(self):
        return self.remaining_sec > 0

    def start(self, minutes, label="Focus"):
        minutes = max(0.1, float(minutes))
        self.total_sec = int(minutes * 60)
        self.remaining_sec = self.total_sec
        self.label = label
        self._end_ts = time.monotonic() + self.total_sec
        self.timer.start()
        self._emit()

    def pause(self):
        if not self.running:
            return
        self.remaining_sec = max(0, int(round(self._end_ts - time.monotonic())))
        self._end_ts = None
        self.timer.stop()
        self._emit()

    def resume(self):
        if self.running or self.remaining_sec <= 0:
            return
        self._end_ts = time.monotonic() + self.remaining_sec
        self.timer.start()
        self._emit()

    def toggle(self):
        if self.running:
            self.pause()
        else:
            self.resume()

    def add_minutes(self, minutes):
        delta = int(minutes * 60)
        if self.running:
            self._end_ts += delta
            self.remaining_sec += delta
        elif self.remaining_sec > 0:
            self.remaining_sec += delta
        else:
            self.start(minutes, self.label)
            return
        self.total_sec += delta
        self._emit()

    def stop(self):
        self._end_ts = None
        self.timer.stop()
        self.remaining_sec = 0
        self.total_sec = 0
        self._emit()

    def _on_tick(self):
        if not self.running:
            return
        self.remaining_sec = max(0, int(round(self._end_ts - time.monotonic())))
        if self.remaining_sec <= 0:
            label = self.label
            self.stop()
            self.finished.emit(label)
            return
        self._emit()

    def _emit(self):
        self.tick.emit(self.remaining_sec, self.total_sec, self.running)


def format_seconds(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"
