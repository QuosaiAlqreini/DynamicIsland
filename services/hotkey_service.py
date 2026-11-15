"""System-wide hotkey (default Ctrl+Alt+Space) to summon the island from anywhere.

Windows: the Win32 RegisterHotKey API through ctypes and a Qt native event filter.
Linux (X11 / XWayland): pynput's global hotkeys. Under pure Wayland, desktops don't let apps
grab keys: bind a desktop shortcut to `dynamic-island --toggle` instead.
"""
import os
import sys

from PyQt6.QtCore import QAbstractNativeEventFilter, QObject, pyqtSignal

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

_MODS = {"ctrl": MOD_CONTROL, "control": MOD_CONTROL, "alt": MOD_ALT,
         "shift": MOD_SHIFT, "win": MOD_WIN, "meta": MOD_WIN}


def parse_hotkey(text):
    """'Ctrl+Alt+Space' -> (modifiers, virtual_key) or None if invalid.

    Letters/digits/space need at least one modifier; F-keys, Pause,
    Insert, media keys etc. may be used on their own (AutoHotkey-style).
    """
    from services.win_input import key_to_vk
    mods, vk, key_name = 0, None, ""
    parts = [p for p in (text or "").split("+")]
    # Allow '+' itself as a key ("Ctrl++")
    if text and text.endswith("++"):
        parts = parts[:-2] + ["="]
    for raw in parts:
        part = raw.strip().lower()
        if not part:
            continue
        if part in _MODS:
            mods |= _MODS[part]
        elif vk is None:
            vk = key_to_vk(raw)
            key_name = part
            if vk is None:
                return None
        else:
            return None
    if vk is None:
        return None
    typing_key = len(key_name) == 1 or key_name in ("space", "enter", "return", "tab",
                                                     "backspace", "esc", "escape")
    if mods == 0 and typing_key:
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


_PYNPUT_KEYS = {"space": "<space>", "enter": "<enter>", "return": "<enter>", "tab": "<tab>",
                "esc": "<esc>", "escape": "<esc>", "backspace": "<backspace>", "delete": "<delete>",
                "del": "<delete>", "insert": "<insert>", "ins": "<insert>", "home": "<home>",
                "end": "<end>", "pgup": "<page_up>", "pageup": "<page_up>", "pgdown": "<page_down>",
                "pagedown": "<page_down>", "up": "<up>", "down": "<down>", "left": "<left>",
                "right": "<right>", "pause": "<pause>", "printscreen": "<print_screen>"}
_PYNPUT_MODS = {"ctrl": "<ctrl>", "control": "<ctrl>", "alt": "<alt>", "shift": "<shift>",
                "win": "<cmd>", "meta": "<cmd>"}


def pynput_hotkey(text):
    """'Ctrl+Alt+Space' -> '<ctrl>+<alt>+<space>' (None if not valid)."""
    if not parse_hotkey(text):
        return None
    out = []
    for raw in text.split("+"):
        part = raw.strip().lower()
        if not part:
            continue
        if part in _PYNPUT_MODS:
            out.append(_PYNPUT_MODS[part])
        elif part in _PYNPUT_KEYS:
            out.append(_PYNPUT_KEYS[part])
        elif len(part) > 1 and part[0] == "f" and part[1:].isdigit():
            out.append(f"<{part}>")
        elif len(part) == 1:
            out.append(part)
        else:
            return None
    return "+".join(out)


def _linux_hotkeys_possible():
    return sys.platform.startswith("linux") and bool(os.environ.get("DISPLAY"))


class HotkeyService(QObject):
    activated = pyqtSignal(int)

    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self._registered = []
        self._filter = None
        self.linux = _linux_hotkeys_possible()
        self.available = sys.platform == "win32" or self.linux
        self.last_error = ""
        self._linux_keys = {}          # hotkey_id -> pynput combo
        self._listener = None

    # ------------------------------------------------------------ Linux
    def _restart_listener(self):
        """Registering many shortcuts in a row restarts the listener once (batched): stopping an
        X11 listener that is still starting crashes inside Xlib."""
        if not getattr(self, "_restart_pending", False):
            self._restart_pending = True
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, self._apply_listener)

    def _apply_listener(self):
        self._restart_pending = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as e:
                print(f"[hotkey] stopping the old listener: {e}")
            self._listener = None
        if not self._linux_keys:
            return
        try:
            from pynput import keyboard
        except Exception as e:
            self.last_error = f"global hotkeys need the 'pynput' package ({e})"
            print(f"[hotkey] {self.last_error}")
            return
        mapping = {combo: (lambda i=i: self.activated.emit(i)) for i, combo in self._linux_keys.items()}
        self._listener = keyboard.GlobalHotKeys(mapping)
        self._listener.daemon = True
        self._listener.start()
        self._listener.wait()          # ready before anyone may stop it

    def _register_linux(self, hotkey_id, text):
        combo = pynput_hotkey(text)
        if not combo:
            self.last_error = f"'{text}' is not a valid hotkey"
            return False
        if combo in self._linux_keys.values() and self._linux_keys.get(hotkey_id) != combo:
            self.last_error = f"{text} is already used by another island shortcut"
            return False
        self._linux_keys[hotkey_id] = combo
        self._registered.append(hotkey_id)
        self._restart_listener()
        return True

    def register(self, hotkey_id, text):
        """Register a global hotkey. Returns True on success."""
        if not self.available:
            return False
        if self.linux:
            return self._register_linux(hotkey_id, text)
        parsed = parse_hotkey(text)
        if not parsed:
            print(f"[hotkey] Invalid hotkey: {text!r}")
            self.last_error = f"'{text}' is not a valid hotkey"
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
                self.last_error = f"{text} is already used by Windows or another app"
            return bool(ok)
        except Exception as e:
            print(f"[hotkey] Registration failed: {e}")
            return False

    def unregister(self, hotkey_id):
        if not self.available or hotkey_id not in self._registered:
            return
        if self.linux:
            self._registered.remove(hotkey_id)
            self._linux_keys.pop(hotkey_id, None)
            self._restart_listener()
            return
        try:
            import ctypes
            ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        except Exception:
            pass
        self._registered.remove(hotkey_id)

    def unregister_all(self):
        if not self.available:
            return
        if self.linux:
            self._registered.clear()
            self._linux_keys.clear()
            self._restart_listener()
            return
        try:
            import ctypes
            for hotkey_id in self._registered:
                ctypes.windll.user32.UnregisterHotKey(None, hotkey_id)
        except Exception:
            pass
        self._registered.clear()
