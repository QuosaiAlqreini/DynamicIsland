"""AutoHotkey-style hotstrings (text expansion) via a low-level keyboard hook.

Type a trigger such as ``;sig`` followed by Space/Enter/Tab (or instantly for
"instant" hotstrings) and it is replaced by its expansion in any app.

Privacy: only the current word (max 64 chars) is held in memory; nothing is
logged or written anywhere. The buffer resets on Ctrl/Alt/Win shortcuts and
navigation keys.
"""
import sys
import threading

from PyQt6.QtCore import QObject, pyqtSignal

IS_WINDOWS = sys.platform == "win32"
MAX_BUFFER = 64
END_KEYS = {0x20: " ", 0x0D: "\n", 0x09: "\t"}
RESET_KEYS = {0x1B, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2E}  # Esc, nav, Del


class HotstringMatcher:
    """Pure matching logic (platform independent, unit-testable)."""

    def __init__(self):
        self.buffer = ""
        self.hotstrings = {}  # trigger -> {"replacement", "instant"}

    def set_hotstrings(self, items):
        self.hotstrings = {
            h["trigger"]: {"replacement": h.get("replacement", ""), "instant": bool(h.get("instant"))}
            for h in items if h.get("trigger") and h.get("enabled", True)
        }
        self.buffer = ""

    def reset(self):
        self.buffer = ""

    def backspace(self):
        self.buffer = self.buffer[:-1]

    def feed_char(self, ch):
        """Returns (trigger, replacement) for an instant match, else None."""
        self.buffer = (self.buffer + ch)[-MAX_BUFFER:]
        hs = self.hotstrings.get(self.buffer)
        if hs and hs["instant"]:
            trigger = self.buffer
            self.buffer = ""
            return trigger, hs["replacement"]
        return None

    def feed_end(self):
        """End char typed. Returns (trigger, replacement) on a match, else None."""
        word, self.buffer = self.buffer, ""
        hs = self.hotstrings.get(word)
        if hs and not hs["instant"]:
            return word, hs["replacement"]
        return None


class HotstringEngine(QObject):
    # trigger, replacement, chars to delete, end char to retype ('' for instant)
    expand = pyqtSignal(str, str, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.matcher = HotstringMatcher()
        self._thread = None
        self._thread_id = None
        self._hook = None
        self._proc = None
        self.running = False

    def set_hotstrings(self, items):
        self.matcher.set_hotstrings(items)

    # ------------------------------------------------------------ lifecycle
    def start(self):
        if not IS_WINDOWS or self.running:
            return self.running
        self.running = True
        self._thread = threading.Thread(target=self._run, name="hotstrings", daemon=True)
        self._thread.start()
        return True

    def stop(self):
        if not self.running:
            return
        self.running = False
        if IS_WINDOWS and self._thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)  # WM_QUIT
        self._thread_id = None

    def _run(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
                        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
                        ("dwExtraInfo", ctypes.c_size_t)]

        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
        user32.CallNextHookEx.restype = LRESULT
        user32.CallNextHookEx.argtypes = (wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        user32.GetAsyncKeyState.restype = ctypes.c_short
        user32.GetKeyState.restype = ctypes.c_short
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.c_void_p)
        user32.GetKeyboardLayout.restype = ctypes.c_void_p
        user32.ToUnicodeEx.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_char_p,
                                       wintypes.LPWSTR, ctypes.c_int, wintypes.UINT, ctypes.c_void_p)
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        WM_KEYDOWN, WM_SYSKEYDOWN, LLKHF_INJECTED = 0x0100, 0x0104, 0x10
        matcher = self.matcher

        def down(vk):
            return user32.GetAsyncKeyState(vk) & 0x8000

        def to_char(vk, scan):
            state = (ctypes.c_ubyte * 256)()
            if down(0x10):
                state[0x10] = 0x80
            if user32.GetKeyState(0x14) & 1:
                state[0x14] = 0x01
            if down(0xA5):  # AltGr = Ctrl + right Alt
                state[0x11] = state[0x12] = 0x80
            buf = ctypes.create_unicode_buffer(8)
            tid = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
            layout = user32.GetKeyboardLayout(tid)
            n = user32.ToUnicodeEx(vk, scan, ctypes.cast(state, ctypes.c_char_p), buf, 8, 0x4, layout)
            return buf.value[:n] if n > 0 else ""

        def callback(n_code, w_param, l_param):
            try:
                if n_code == 0 and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
                    kb = KBDLLHOOKSTRUCT.from_address(l_param)
                    vk = kb.vkCode
                    if not (kb.flags & LLKHF_INJECTED) and vk not in (0x10, 0xA0, 0xA1, 0x14):
                        ctrl_alt_win = (down(0x11) or down(0x12) or down(0x5B) or down(0x5C)) and not down(0xA5)
                        if ctrl_alt_win or vk in RESET_KEYS:
                            matcher.reset()
                        elif vk == 0x08:
                            matcher.backspace()
                        elif vk in END_KEYS:
                            hit = matcher.feed_end()
                            if hit:
                                self.expand.emit(hit[0], hit[1], len(hit[0]), END_KEYS[vk])
                                return 1  # swallow end key; it is retyped after the expansion
                        else:
                            ch = to_char(vk, kb.scanCode)
                            if ch:
                                hit = matcher.feed_char(ch)
                                if hit:
                                    # last char is swallowed, so delete one less
                                    self.expand.emit(hit[0], hit[1], len(hit[0]) - 1, "")
                                    return 1
                            else:
                                matcher.reset()
            except Exception:
                pass
            return user32.CallNextHookEx(None, n_code, w_param, l_param)

        self._proc = HOOKPROC(callback)  # keep a reference so it is not GC'd
        self._thread_id = kernel32.GetCurrentThreadId()
        self._hook = user32.SetWindowsHookExW(13, self._proc, kernel32.GetModuleHandleW(None), 0)
        if not self._hook:
            print("[hotstrings] Could not install keyboard hook")
            self.running = False
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
