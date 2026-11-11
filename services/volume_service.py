"""Real Windows master volume (via pycaw) on a worker thread.

Falls back to the keyboard volume keys when pycaw is not available.
"""
import queue
import sys
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from services import win_input


class VolumeService(QObject):
    volume_changed = pyqtSignal(int, bool)   # percent, muted

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = False
        self.percent, self.muted = 50, False
        self._q = queue.Queue()
        if sys.platform == "win32":
            threading.Thread(target=self._worker, name="volume", daemon=True).start()

    def _worker(self):
        try:
            import comtypes
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
            comtypes.CoInitialize()

            def endpoint():
                device = AudioUtilities.GetSpeakers()
                iface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
                return iface.QueryInterface(IAudioEndpointVolume)
            vol = endpoint()
            self.available = True
        except Exception as e:
            print(f"[volume] pycaw unavailable, using volume keys: {e}")
            return
        while True:
            cmd, arg = self._q.get()
            try:
                # Collapse a burst of slider moves into the latest one
                while cmd == "set" and not self._q.empty():
                    nxt = self._q.get_nowait()
                    if nxt[0] != "set":
                        self._q.put(nxt)
                        break
                    cmd, arg = nxt
                if cmd == "set":
                    vol.SetMasterVolumeLevelScalar(max(0.0, min(1.0, arg / 100)), None)
                elif cmd == "mute":
                    vol.SetMute(0 if vol.GetMute() else 1, None)
                self.percent = int(round(vol.GetMasterVolumeLevelScalar() * 100))
                self.muted = bool(vol.GetMute())
                self.volume_changed.emit(self.percent, self.muted)
            except Exception:
                try:
                    vol = endpoint()   # output device changed
                except Exception:
                    pass

    def refresh(self):
        self._q.put(("get", None))

    def set_percent(self, percent):
        if self.available or sys.platform != "win32":
            self._q.put(("set", int(percent)))
        else:
            # No pycaw: nudge with the volume keys (2% per press)
            steps = (int(percent) - self.percent) // 2
            if steps:
                win_input.tap_vk(0xAF if steps > 0 else 0xAE, abs(steps))
                self.percent += steps * 2

    def toggle_mute(self):
        if self.available:
            self._q.put(("mute", None))
        else:
            win_input.tap_vk(0xAD)
