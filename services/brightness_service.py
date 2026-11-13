"""Laptop screen brightness, watched in the background so the island can show a
popup when it changes (keyboard keys, Windows settings or our own hotkeys).

Uses WMI (internal laptop displays only). On desktops with external monitors
it quietly does nothing.
"""
import sys
import threading
import time

from PyQt6.QtCore import QObject, pyqtSignal


class BrightnessService(QObject):
    brightness_changed = pyqtSignal(int)

    def __init__(self, parent=None, interval=1.2):
        super().__init__(parent)
        self.level = None
        self.available = False
        self._interval = interval
        self._stop = threading.Event()
        self._poke = threading.Event()
        if sys.platform == "win32":
            threading.Thread(target=self._worker, name="brightness", daemon=True).start()

    def check_soon(self):
        self._poke.set()

    def stop(self):
        self._stop.set()
        self._poke.set()

    def _worker(self):
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            wmi = win32com.client.GetObject(r"winmgmts:\\.\root\WMI")
        except Exception:
            return
        while not self._stop.is_set():
            try:
                rows = list(wmi.ExecQuery("SELECT CurrentBrightness FROM WmiMonitorBrightness"))
                if rows:
                    self.available = True
                    level = int(rows[0].CurrentBrightness)
                    if level != self.level:
                        self.level = level
                        self.brightness_changed.emit(level)
            except Exception:
                if not self.available:
                    return          # no internal display: stop quietly
            self._poke.wait(self._interval)
            if self._poke.is_set():
                self._poke.clear()
                time.sleep(0.35)    # let a just-requested change land
