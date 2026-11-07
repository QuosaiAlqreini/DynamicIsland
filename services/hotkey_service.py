"""System-wide hotkey (default Ctrl+Alt+Space) to summon the island from anywhere.

Uses the Win32 RegisterHotKey API through ctypes and a Qt native event filter.
On non-Windows platforms it is a silent no-op so the app still runs.
"""
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, pyqtSignal

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
         "shift": MOD_SHIFT, "win": MOD_WIN, "meta": MOD_WIN}
_KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "`": 0xC0,
         "backquote": 0xC0, "home": 0x24, "end": 0x23, "insert": 0x2D}


def parse_hotkey(text):
    """'Ctrl+Alt+Space' -> (modifiers, virtual_key) or None if invalid."""
    mods, vk = 0, None
    for raw in (text or "").split("+"):
        part = raw.strip().lower()
        if not part:
            continue
        if part in _MODS:
            mods |= _MODS[part]
        elif part in _KEYS:
            vk = _KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x70 + int(part[1:]) - 1
        else:
            return None
    if vk is None or mods == 0:
        return None
    return mods, vk


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                from ctypes import wintypes
                import ctypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    self.callback(msg.wParam)
                    return True, 0
            except Exception:
                pass
        return False, 0


class HotkeyService(QObject):
    activated = pyqtSignal(int)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._registered = []
        self._filter = None
        self.available = sys.platform == "win32"

    def register(self, hotkey_id, text):
        """Register a global hotkey. Returns True on success."""
        if not self.available:
            return False
        parsed = parse_hotkey(text)
        if not parsed:
            print(f"[hotkey] Invalid hotkey: {text!r}")
            return False
        try:
            import ctypes
            if self._filter is None:
                self._filter = _HotkeyFilter(self.activated.emit)
                self.app.installNativeEventFilter(self._filter)
            mods, vk = parsed
            ok = ctypes.windll.user32.RegisterHotKey(None, hotkey_id, mods | MOD_NOREPEAT, vk)
            if ok:
                self._registered.append(hotkey_id)
            else:
                print(f"[hotkey] {text} is already used by another app")
            return bool(ok)
        except Exception as e:
            print(f"[hotkey] Registration failed: {e}")
            return False

    def unregister_all(self):
        if not self.available:
            return
        try:
            import ctypes
            for hotkey_id in self._registered:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        except Exception:
            pass
        self._registered.clear()
