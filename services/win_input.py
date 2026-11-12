"""Win32 keyboard / window / system helpers for the automation engine.

Everything degrades to a printed no-op on non-Windows platforms so the app
(and its tests) still run elsewhere.
"""
import os
import subprocess
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    ULONG_PTR = ctypes.c_size_t

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowLongW.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, ctypes.c_int, wintypes.UINT)
    user32.MonitorFromWindow.restype = wintypes.HANDLE
    user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFO))
    user32.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
    user32.MoveWindow.argtypes = (wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.BOOL)
    user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
    user32.IsZoomed.argtypes = (wintypes.HWND,)
    user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetAsyncKeyState.restype = ctypes.c_short
    user32.VkKeyScanW.restype = ctypes.c_short

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x1
KEYEVENTF_KEYUP = 0x2
KEYEVENTF_UNICODE = 0x4

VK_BACK, VK_TAB, VK_RETURN = 0x08, 0x09, 0x0D
VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C

# Virtual-key names shared by hotkey parsing and key sending
VK_NAMES = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
    "home": 0x24, "end": 0x23, "pgup": 0x21, "pageup": 0x21, "pgdown": 0x22, "pagedown": 0x22,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "capslock": 0x14, "scrolllock": 0x91, "numlock": 0x90, "pause": 0x13,
    "print": 0x2C, "printscreen": 0x2C, "apps": 0x5D, "menu": 0x5D,
    "volume_up": 0xAF, "volumeup": 0xAF, "volume_down": 0xAE, "volumedown": 0xAE,
    "volume_mute": 0xAD, "volumemute": 0xAD, "media_next": 0xB0, "medianext": 0xB0,
    "media_prev": 0xB1, "mediaprev": 0xB1, "media_play_pause": 0xB3, "mediaplay": 0xB3,
    "`": 0xC0, "backquote": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD,
    "\\": 0xDC, ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}
MOD_NAMES = {"ctrl": VK_CONTROL, "control": VK_CONTROL, "alt": VK_MENU,
             "shift": VK_SHIFT, "win": VK_LWIN, "meta": VK_LWIN}
_EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B, 0x5C, 0x5D,
             0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB3}


def key_to_vk(name):
    """'a' / 'F5' / 'Left' / '/' -> virtual-key code, or None."""
    part = name.strip().lower()
    if part in VK_NAMES:
        return VK_NAMES[part]
    if len(part) == 1 and (part.isalpha() or part.isdigit()):
        return ord(part.upper())
    if part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
        return 0x70 + int(part[1:]) - 1
    if part.startswith("numpad") and part[6:].isdigit():
        return 0x60 + int(part[6:]) % 10
    if IS_WINDOWS and len(name.strip()) == 1:
        res = user32.VkKeyScanW(ord(name.strip()))
        if res != -1:
            return res & 0xFF
    return None


def _noop(what):
    print(f"[automation] {what} is only available on Windows")
    return False


def _key_input(vk=0, scan=0, flags=0):
    inp = INPUT(type=INPUT_KEYBOARD)
    if vk in _EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    inp.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return inp


def _send(inputs):
    if not inputs:
        return True
    arr = (INPUT * len(inputs))(*inputs)
    return user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT)) == len(inputs)


def tap_vk(vk, times=1):
    if not IS_WINDOWS:
        return _noop("Key sending")
    seq = []
    for _ in range(max(1, times)):
        seq += [_key_input(vk), _key_input(vk, flags=KEYEVENTF_KEYUP)]
    return _send(seq)


def send_combo(combo):
    """Press a combination such as 'Ctrl+Shift+Esc', 'Win+Left' or 'F5'."""
    if not IS_WINDOWS:
        return _noop("Key sending")
    mods, key = [], None
    for raw in combo.split("+"):
        part = raw.strip().lower()
        if not part:
            continue
        if part in MOD_NAMES:
            mods.append(MOD_NAMES[part])
        else:
            key = key_to_vk(raw)
            if key is None:
                print(f"[automation] Unknown key in {combo!r}: {raw!r}")
                return False
    seq = [_key_input(m) for m in mods]
    if key is not None:
        seq += [_key_input(key), _key_input(key, flags=KEYEVENTF_KEYUP)]
    seq += [_key_input(m, flags=KEYEVENTF_KEYUP) for m in reversed(mods)]
    return _send(seq)


def send_text(text):
    """Type arbitrary Unicode text into the focused app."""
    if not IS_WINDOWS:
        return _noop("Typing text")
    seq = []
    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            seq += [_key_input(VK_RETURN), _key_input(VK_RETURN, flags=KEYEVENTF_KEYUP)]
        elif ch == "\t":
            seq += [_key_input(VK_TAB), _key_input(VK_TAB, flags=KEYEVENTF_KEYUP)]
        else:
            data = ch.encode("utf-16-le")
            for i in range(0, len(data), 2):  # surrogate pairs -> two units
                unit = int.from_bytes(data[i:i + 2], "little")
                seq += [_key_input(scan=unit, flags=KEYEVENTF_UNICODE),
                        _key_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
    return _send(seq)


def modifiers_down():
    if not IS_WINDOWS:
        return False
    return any(user32.GetAsyncKeyState(vk) & 0x8000
               for vk in (VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN))


# ----------------------------------------------------------------- Windows
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
GWL_EXSTYLE, WS_EX_TOPMOST = -20, 0x8
HWND_TOPMOST, HWND_NOTOPMOST = -1, -2
SW_MINIMIZE, SW_MAXIMIZE, SW_RESTORE = 6, 3, 9
WM_CLOSE = 0x0010


def foreground_window():
    return user32.GetForegroundWindow() if IS_WINDOWS else None


def window_title(hwnd):
    if not IS_WINDOWS or not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(hwnd, buf, 256)
    return buf.value


def toggle_always_on_top(hwnd=None):
    """Returns True if the window is now pinned on top, False if unpinned, None on failure."""
    if not IS_WINDOWS:
        return _noop("Always-on-top") or None
    hwnd = hwnd or foreground_window()
    if not hwnd:
        return None
    topmost = bool(user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOPMOST)
    after = HWND_NOTOPMOST if topmost else HWND_TOPMOST
    user32.SetWindowPos(hwnd, after, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
    return not topmost


def _work_area(hwnd):
    mon = user32.MonitorFromWindow(hwnd, 2)  # MONITOR_DEFAULTTONEAREST
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    user32.GetMonitorInfoW(mon, ctypes.byref(info))
    return info.rcWork


def move_window(position, hwnd=None):
    """position: center | left | right | top | bottom (halves of the work area)."""
    if not IS_WINDOWS:
        return _noop("Window moving")
    hwnd = hwnd or foreground_window()
    if not hwnd:
        return False
    if user32.IsZoomed(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    wa = _work_area(hwnd)
    W, H = wa.right - wa.left, wa.bottom - wa.top
    if position == "center":
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        w, h = min(r.right - r.left, W), min(r.bottom - r.top, H)
        x, y = wa.left + (W - w) // 2, wa.top + (H - h) // 2
    elif position == "left":
        x, y, w, h = wa.left, wa.top, W // 2, H
    elif position == "right":
        x, y, w, h = wa.left + W // 2, wa.top, W - W // 2, H
    elif position == "top":
        x, y, w, h = wa.left, wa.top, W, H // 2
    elif position == "bottom":
        x, y, w, h = wa.left, wa.top + H // 2, W, H - H // 2
    else:
        return False
    return bool(user32.MoveWindow(hwnd, x, y, w, h, True))


def window_command(cmd, hwnd=None):
    """cmd: minimize | maximize (toggle) | close."""
    if not IS_WINDOWS:
        return _noop("Window commands")
    hwnd = hwnd or foreground_window()
    if not hwnd:
        return False
    if cmd == "minimize":
        user32.ShowWindow(hwnd, SW_MINIMIZE)
    elif cmd == "maximize":
        user32.ShowWindow(hwnd, SW_RESTORE if user32.IsZoomed(hwnd) else SW_MAXIMIZE)
    elif cmd == "close":
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
    else:
        return False
    return True


# ------------------------------------------------------------------ System
ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x1, 0x2
CREATE_NO_WINDOW = 0x08000000


def set_keep_awake(on):
    if not IS_WINDOWS:
        return _noop("Keep awake")
    flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED if on else 0)
    return bool(kernel32.SetThreadExecutionState(flags))


def lock_pc():
    return bool(user32.LockWorkStation()) if IS_WINDOWS else _noop("Lock")


def run_hidden(args):
    """Start a process without a console window; never blocks."""
    try:
        kwargs = {"creationflags": CREATE_NO_WINDOW} if IS_WINDOWS else {}
        subprocess.Popen(args, **kwargs)
        return True
    except OSError as e:
        print(f"[automation] Could not run {args!r}: {e}")
        return False


def change_brightness(delta):
    """Laptop screen brightness +/- delta percent via WMI (internal displays only)."""
    if not IS_WINDOWS:
        return _noop("Brightness")
    delta = int(delta)
    script = (
        "$b=(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness;"
        f"$n=[Math]::Max(0,[Math]::Min(100,$b+({delta})));"
        "Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods | "
        "Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{Timeout=1;Brightness=[byte]$n} | Out-Null"
    )
    return run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])


def sleep_pc():
    if not IS_WINDOWS:
        return _noop("Sleep")
    return run_hidden(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])


def toggle_dark_mode():
    """Flip Windows apps + system theme. Returns True if dark mode is now on."""
    if not IS_WINDOWS:
        return _noop("Dark mode") or None
    import winreg
    path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0,
                        winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            light = winreg.QueryValueEx(key, "AppsUseLightTheme")[0]
        except OSError:
            light = 1
        new = 0 if light else 1
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, new)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, new)
    return new == 0


def set_launch_at_login(enabled, command):
    """Add/remove the app from HKCU\\...\\Run so it starts with Windows."""
    if not IS_WINDOWS:
        return _noop("Launch at login")
    import winreg
    path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "DynamicIsland", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "DynamicIsland")
            except FileNotFoundError:
                pass
    return True


def app_launch_command():
    """Command line that starts this app without a console window."""
    if getattr(sys, "frozen", False):  # packaged .exe
        return f'"{sys.executable}"'
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        pyw = exe[:-10] + "pythonw.exe"
        if os.path.exists(pyw):
            exe = pyw
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app.py"))
    return f'"{exe}" "{script}"'


# -------------------------------------------------------------- Fullscreen
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                  "XamlExplorerHostIslandWindow", "MultitaskingViewFrame", "ForegroundStaging",
                  "Windows.UI.Core.CoreWindow", "TaskListThumbnailWnd"}
QUNS_BUSY, QUNS_D3D_FULLSCREEN, QUNS_PRESENTATION = 2, 3, 4


def _class_name(hwnd):
    buf = ctypes.create_unicode_buffer(128)
    user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def looks_fullscreen(win, mon, zoomed, has_caption, tolerance=2):
    """Pure decision used by fullscreen_app_active (rects are (l, t, r, b)).

    A window that covers its monitor is full screen, except an ordinary
    maximized window with a title bar (that can cover the monitor when the
    taskbar auto-hides).
    """
    covers = (win[0] <= mon[0] + tolerance and win[1] <= mon[1] + tolerance
              and win[2] >= mon[2] - tolerance and win[3] >= mon[3] - tolerance)
    return covers and not (zoomed and has_caption)


def fullscreen_app_active(island_hwnd=None):
    """True when a full-screen app (game, video, F11 browser, slideshow) is in
    front on the same monitor as the island."""
    if not IS_WINDOWS:
        return False
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd or (island_hwnd and int(hwnd) == int(island_hwnd)):
            return False
        if _class_name(hwnd) in _SHELL_CLASSES:
            return False
        mon = user32.MonitorFromWindow(hwnd, 2)
        if island_hwnd and mon != user32.MonitorFromWindow(island_hwnd, 2):
            return False
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(mon, ctypes.byref(info))
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        m = info.rcMonitor
        has_caption = (user32.GetWindowLongW(hwnd, -16) & 0x00C00000) == 0x00C00000  # WS_CAPTION
        if looks_fullscreen((r.left, r.top, r.right, r.bottom), (m.left, m.top, m.right, m.bottom),
                            bool(user32.IsZoomed(hwnd)), has_caption):
            return True
        # Ask Windows too: exclusive-mode games, slideshows and other full-screen apps
        state = ctypes.c_int(0)
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) == 0:
            return state.value in (QUNS_BUSY, QUNS_D3D_FULLSCREEN, QUNS_PRESENTATION)
    except Exception:
        pass
    return False


# ------------------------------------------------------------ Click-through
WS_EX_TRANSPARENT, WS_EX_LAYERED = 0x20, 0x80000
VK_LBUTTON, VK_RBUTTON = 0x01, 0x02


def set_click_through(hwnd, on):
    """Make a window ignore the mouse so clicks land on whatever is underneath."""
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new = (style | WS_EX_TRANSPARENT | WS_EX_LAYERED) if on else (style & ~WS_EX_TRANSPARENT)
        if new != style:
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
        return True
    except Exception:
        return False


def mouse_button_down():
    """True while the left or right mouse button is held."""
    if not IS_WINDOWS:
        return False
    return bool((user32.GetAsyncKeyState(VK_LBUTTON) | user32.GetAsyncKeyState(VK_RBUTTON)) & 0x8000)


def foreground_process_name():
    """Lower-case exe name of the app in front (e.g. 'chrome.exe'), or ''."""
    if not IS_WINDOWS:
        return ""
    try:
        import psutil
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), ctypes.byref(pid))
        return psutil.Process(pid.value).name().lower() if pid.value else ""
    except Exception:
        return ""


def window_at(x, y):
    """Top-level window under a screen point (physical px): (title, (l, t, r, b)) or None."""
    if not IS_WINDOWS:
        return None
    try:
        user32.WindowFromPoint.restype = wintypes.HWND
        user32.WindowFromPoint.argtypes = (wintypes.POINT,)
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        hwnd = user32.GetAncestor(user32.WindowFromPoint(wintypes.POINT(int(x), int(y))), 2)  # GA_ROOT
        if not hwnd or _class_name(hwnd) in ("Progman", "WorkerW"):
            return None
        r = wintypes.RECT()
        # Visible bounds without the invisible resize border
        if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
            user32.GetWindowRect(hwnd, ctypes.byref(r))
        return window_title(hwnd), (r.left, r.top, r.right, r.bottom)
    except Exception:
        return None
