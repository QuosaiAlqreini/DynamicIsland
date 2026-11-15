"""Small things worth a glance in the notch (as in CrestIsland):
Caps Lock, charger plugged/unplugged, internet lost/back, and green privacy
dots while the microphone or camera is in use."""
import socket
import sys
import threading
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

IS_WINDOWS = sys.platform == "win32"
CONSENT_ROOT = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore"


def apps_using(kind):
    """Names of apps using the 'microphone' or 'webcam' right now (Windows privacy registry).

    Windows records LastUsedTimeStop = 0 for an app while it is using the device."""
    if not IS_WINDOWS:
        return []
    import winreg
    users = []

    def scan(path):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, i)
                    except OSError:
                        break
                    i += 1
                    if sub == "NonPackaged":
                        scan(path + "\\" + sub)
                        continue
                    try:
                        with winreg.OpenKey(key, sub) as app:
                            stop, _t = winreg.QueryValueEx(app, "LastUsedTimeStop")
                            start, _t = winreg.QueryValueEx(app, "LastUsedTimeStart")
                            if stop == 0 and start:
                                users.append(sub.split("#")[-1].split("_")[0])
                    except OSError:
                        continue
        except OSError:
            pass
    scan(CONSENT_ROOT + "\\" + kind)
    return users


def caps_lock_on():
    if not IS_WINDOWS:
        return False
    import ctypes
    return bool(ctypes.windll.user32.GetKeyState(0x14) & 1)


def internet_ok():
    for host in (("1.1.1.1", 53), ("8.8.8.8", 53)):
        try:
            socket.create_connection(host, timeout=2).close()
            return True
        except OSError:
            continue
    return False


class NoticesService(QObject):
    notice = pyqtSignal(str, str)            # text, colour role (accent / success / warning / danger)
    privacy_changed = pyqtSignal(bool, bool)  # microphone in use, camera in use
    _net = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.caps = None
        self.plugged = None
        self.online = None
        self.mic = self.cam = False
        self._net.connect(self._on_net)
        self.timer = QTimer(self)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self._tick)
        self._ticks = 0
        if IS_WINDOWS:
            self.timer.start()
            threading.Thread(target=self._net_loop, name="net-watch", daemon=True).start()

    def _tick(self):
        self._ticks += 1
        caps = caps_lock_on()
        if self.caps is not None and caps != self.caps:
            self.notice.emit("⇪ Caps Lock on" if caps else "⇪ Caps Lock off", "warning" if caps else "accent")
        self.caps = caps
        if self._ticks % 3 == 0:              # privacy every ~2 s
            mic, cam = bool(apps_using("microphone")), bool(apps_using("webcam"))
            if (mic, cam) != (self.mic, self.cam):
                self.mic, self.cam = mic, cam
                self.privacy_changed.emit(mic, cam)

    def update_power(self, stats):
        plugged = bool(stats.get("battery_plugged", True))
        if self.plugged is not None and plugged != self.plugged:
            pct = int(stats.get("battery_percent", 0))
            self.notice.emit(f"⚡ Charging · {pct}%" if plugged else f"🔋 On battery · {pct}%",
                             "success" if plugged else "accent")
        self.plugged = plugged

    def _net_loop(self):
        while True:
            self._net.emit(internet_ok())
            time.sleep(12)

    def _on_net(self, ok):
        if self.online is not None and ok != self.online:
            self.notice.emit("🌐 Back online" if ok else "📡 Internet connection lost", "success" if ok else "danger")
        self.online = ok
