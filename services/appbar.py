"""Reserve a strip at the top of the screen (like the taskbar does at the bottom),
so maximized windows start below the notch/island instead of behind it.

Uses the Windows AppBar API. The reservation is released on exit; Windows also
drops it when the owning window is destroyed.
"""
import sys

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    class APPBARDATA(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("hWnd", wintypes.HWND),
                    ("uCallbackMessage", wintypes.UINT), ("uEdge", wintypes.UINT),
                    ("rc", wintypes.RECT), ("lParam", wintypes.LPARAM)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

    _shell32 = ctypes.WinDLL("shell32")
    _user32 = ctypes.WinDLL("user32")
    _shell32.SHAppBarMessage.argtypes = (wintypes.DWORD, ctypes.POINTER(APPBARDATA))
    _shell32.SHAppBarMessage.restype = ctypes.c_size_t
    _user32.MonitorFromWindow.restype = wintypes.HANDLE
    _user32.MonitorFromWindow.argtypes = (wintypes.HWND, wintypes.DWORD)
    _user32.GetMonitorInfoW.argtypes = (wintypes.HANDLE, ctypes.POINTER(MONITORINFO))

ABM_NEW, ABM_REMOVE, ABM_QUERYPOS, ABM_SETPOS = 0, 1, 2, 3
ABE_TOP = 1


class TopReservation:
    """Owns at most one reserved strip at the top of one monitor."""

    def __init__(self):
        self.hwnd = None          # window the reservation is registered with
        self.reserved = None      # (monitor handle, height in physical px) currently applied
        self.registered = False

    def _data(self):
        abd = APPBARDATA()
        abd.cbSize = ctypes.sizeof(APPBARDATA)
        abd.hWnd = self.hwnd
        return abd

    def reserve(self, owner_hwnd, near_hwnd, height_px):
        """Reserve `height_px` physical pixels at the top of the monitor showing `near_hwnd`.

        Returns True when Windows accepted it (False without a taskbar/shell)."""
        if not IS_WINDOWS or not owner_hwnd:
            return False
        height_px = max(0, int(height_px))
        mon = _user32.MonitorFromWindow(near_hwnd or owner_hwnd, 2)
        if self.reserved == (mon, height_px) and self.registered:
            return True
        if self.registered and owner_hwnd != self.hwnd:
            self.release()
        self.hwnd = owner_hwnd
        if not self.registered:
            abd = self._data()
            abd.uCallbackMessage = _user32.RegisterWindowMessageW("DynamicIslandAppBar")
            if not _shell32.SHAppBarMessage(ABM_NEW, ctypes.byref(abd)):
                return False
            self.registered = True
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        _user32.GetMonitorInfoW(mon, ctypes.byref(info))
        m = info.rcMonitor
        abd = self._data()
        abd.uEdge = ABE_TOP
        abd.rc = wintypes.RECT(m.left, m.top, m.right, m.top + height_px)
        _shell32.SHAppBarMessage(ABM_QUERYPOS, ctypes.byref(abd))   # Windows may shift it (top taskbar)
        abd.rc.bottom = abd.rc.top + height_px
        _shell32.SHAppBarMessage(ABM_SETPOS, ctypes.byref(abd))
        self.reserved = (mon, height_px)
        return True

    def release(self):
        if IS_WINDOWS and self.registered and self.hwnd:
            try:
                _shell32.SHAppBarMessage(ABM_REMOVE, ctypes.byref(self._data()))
            except Exception:
                pass
        self.registered = False
        self.reserved = None


def work_area_top():
    """Top of the primary monitor's work area (physical px), for tests."""
    if not IS_WINDOWS:
        return None
    rect = wintypes.RECT()
    _user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)   # SPI_GETWORKAREA
    return rect.top
