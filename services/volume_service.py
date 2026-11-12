"""Real Windows master volume on a worker thread.

Talks to the Core Audio API directly through ctypes (no extra packages).
The COM objects live for the whole process and are never released, which
avoids shutdown-order crashes. Falls back to the keyboard volume keys.
"""
import queue
import sys
import threading

from PyQt6.QtCore import QObject, pyqtSignal

from services import win_input


class _EndpointVolume:
    """IAudioEndpointVolume of the default speakers, via raw COM vtable calls."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ct = ctypes
        ole32 = ctypes.WinDLL("ole32")

        class GUID(ctypes.Structure):
            _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD),
                        ("d4", ctypes.c_ubyte * 8)]

        def guid(text):
            g = GUID()
            if ole32.CLSIDFromString(ctypes.c_wchar_p(text), ctypes.byref(g)) != 0:
                raise OSError("bad GUID")
            return g

        hr = ole32.CoInitializeEx(None, 0x0)  # multithreaded apartment for this worker thread
        if hr not in (0, 1) and hr & 0xFFFFFFFF != 0x80010106:
            raise OSError(f"CoInitializeEx failed: {hr & 0xFFFFFFFF:#x}")
        clsid = guid("{BCDE0395-E52F-467C-8E3D-C4579291692E}")       # MMDeviceEnumerator
        iid_enum = guid("{A95664D2-9614-4F35-A746-DE8DB63617E6}")    # IMMDeviceEnumerator
        iid_vol = guid("{5CDF2C82-841E-4546-9722-0CF74078229A}")     # IAudioEndpointVolume

        ole32.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
                                           ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        ole32.CoCreateInstance.restype = ctypes.c_long
        enumerator = ctypes.c_void_p()
        self._check(ole32.CoCreateInstance(ctypes.byref(clsid), None, 23, ctypes.byref(iid_enum),
                                           ctypes.byref(enumerator)), "create enumerator")
        device = ctypes.c_void_p()
        # IMMDeviceEnumerator::GetDefaultAudioEndpoint(eRender=0, eMultimedia=1, **device)
        self._check(self._call(enumerator, 4, [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                               0, 1, ctypes.byref(device)), "no default speakers")
        self.volume = ctypes.c_void_p()
        # IMMDevice::Activate(iid, CLSCTX_ALL, NULL, **interface)
        self._check(self._call(device, 3, [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p,
                                           ctypes.POINTER(ctypes.c_void_p)],
                               ctypes.byref(iid_vol), 23, None, ctypes.byref(self.volume)), "activate volume")
        self._keep = (enumerator, device)  # deliberately never released

    @staticmethod
    def _check(hr, what):
        if hr != 0:
            raise OSError(f"{what} (HRESULT {hr & 0xFFFFFFFF:#x})")

    def _call(self, obj, index, argtypes, *args):
        ct = self.ct
        vtable = ct.cast(ct.cast(obj, ct.POINTER(ct.c_void_p))[0], ct.POINTER(ct.c_void_p))
        fn = ct.WINFUNCTYPE(ct.c_long, ct.c_void_p, *argtypes)(vtable[index])
        return fn(obj, *args)

    def get(self):
        ct = self.ct
        level, mute = ct.c_float(), ct.c_int()
        self._check(self._call(self.volume, 9, [ct.POINTER(ct.c_float)], ct.byref(level)), "get volume")
        self._check(self._call(self.volume, 15, [ct.POINTER(ct.c_int)], ct.byref(mute)), "get mute")
        return int(round(level.value * 100)), bool(mute.value)

    def set_percent(self, percent):
        ct = self.ct
        self._check(self._call(self.volume, 7, [ct.c_float, ct.c_void_p],
                               ct.c_float(max(0.0, min(1.0, percent / 100))), None), "set volume")

    def set_mute(self, muted):
        ct = self.ct
        hr = self._call(self.volume, 14, [ct.c_int, ct.c_void_p], 1 if muted else 0, None)
        if hr not in (0, 1):
            self._check(hr, "set mute")


class VolumeService(QObject):
    volume_changed = pyqtSignal(int, bool)   # percent, muted

    def __init__(self, parent=None):
        super().__init__(parent)
        self.available = False
        self.percent, self.muted = 50, False
        self.error = ""
        self._q = queue.Queue()
        if sys.platform == "win32":
            threading.Thread(target=self._worker, name="volume", daemon=True).start()

    def _worker(self):
        try:
            vol = _EndpointVolume()
            self.percent, self.muted = vol.get()
            self.available = True
            self.volume_changed.emit(self.percent, self.muted)
        except Exception as e:
            self.error = str(e)
            print(f"[volume] direct volume control unavailable, using volume keys: {e}")
            return
        while True:
            try:
                cmd, arg = self._q.get(timeout=0.3)
            except queue.Empty:
                # Nothing asked: watch for changes made with the keyboard volume keys
                try:
                    now = vol.get()
                    if now != (self.percent, self.muted):
                        self.percent, self.muted = now
                        self.volume_changed.emit(self.percent, self.muted)
                except Exception:
                    try:
                        vol = _EndpointVolume()
                    except Exception:
                        pass
                continue
            try:
                # Collapse a burst of slider moves into the latest one
                while cmd == "set" and not self._q.empty():
                    nxt = self._q.get_nowait()
                    if nxt[0] != "set":
                        self._q.put(nxt)
                        break
                    cmd, arg = nxt
                if cmd == "set":
                    vol.set_percent(arg)
                elif cmd == "mute":
                    vol.set_mute(not vol.get()[1])
                self.percent, self.muted = vol.get()
                self.volume_changed.emit(self.percent, self.muted)
            except Exception:
                try:
                    vol = _EndpointVolume()   # output device changed
                except Exception:
                    pass

    def refresh(self):
        self._q.put(("get", None))

    def set_percent(self, percent):
        if self.available or sys.platform != "win32":
            self._q.put(("set", int(percent)))
        else:
            # No direct control: nudge with the volume keys (2% per press)
            steps = int(round((int(percent) - self.percent) / 2))
            if steps:
                win_input.tap_vk(0xAF if steps > 0 else 0xAE, abs(steps))
                self.percent = max(0, min(100, self.percent + steps * 2))
                self.volume_changed.emit(self.percent, self.muted)

    def toggle_mute(self):
        if self.available:
            self._q.put(("mute", None))
        else:
            win_input.tap_vk(0xAD)
            self.muted = not self.muted
            self.volume_changed.emit(self.percent, self.muted)
