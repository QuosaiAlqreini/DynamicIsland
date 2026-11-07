import ctypes
from ctypes import wintypes
import os
from PyQt6.QtCore import QObject, pyqtSignal
from config import ConfigManager

# Win32 APPBARDATA structures for Taskbar Auto-Hide
class APPBARDATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uCallbackMessage", wintypes.UINT),
        ("uEdge", wintypes.UINT),
        ("rc", wintypes.RECT),
        ("lParam", wintypes.LPARAM),
    ]

ABM_GETSTATE = 4
ABM_SETSTATE = 10
ABS_MANUAL = 0
ABS_AUTOHIDE = 1

# Windhawk Styler XAML Theme Presets
WINDHAWK_PRESETS = {
    "dock_like": {
        "name": "MacBook DockLike (Floating Pill Dock)",
        "description": "Transforms Windows 11 taskbar into a centered floating dock with rounded corners and margins.",
        "xaml": """// Windhawk Windows 11 Taskbar Styler - DockLike Theme
// Source: https://github.com/ramensoftware/windows-11-taskbar-styling-guide
Taskbar.TaskbarFrame#TaskbarFrame {
    Margin: 0,0,0,10;
    CornerRadius: 18;
    Height: 48;
    HorizontalAlignment: Center;
    Background: #CC12131A;
    BorderBrush: #33FFFFFF;
    BorderThickness: 1;
}
Taskbar.TaskbarFrame#TaskbarFrame > Border#BackgroundBorder {
    CornerRadius: 18;
}
"""
    },
    "translucent": {
        "name": "Translucent Acrylic Glass",
        "description": "Makes the Windows 11 taskbar completely translucent with frosted glass backdrop.",
        "xaml": """// Windhawk Windows 11 Taskbar Styler - Translucent Glass
Taskbar.TaskbarFrame#TaskbarFrame {
    Background: #22000000;
    BorderThickness: 0;
}
Taskbar.TaskbarFrame#TaskbarFrame > Border#BackgroundBorder {
    Background: Transparent;
}
"""
    },
    "hide_redundant_tray": {
        "name": "Clean Desk (Hide Redundant Clock & Tray)",
        "description": "Hides the duplicated clock, date, and battery in the taskbar since Dynamic Island handles them.",
        "xaml": """// Windhawk Windows 11 Taskbar Styler - Hide Redundant Tray Elements
SystemTray.ClockButtonControl#ClockButton {
    Visibility: Collapsed;
}
SystemTray.NotifyIconOverflowWindow#OverflowWindow {
    CornerRadius: 12;
}
"""
    }
}

class TaskbarService(QObject):
    taskbar_state_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        # windll only exists on Windows; methods below already fail soft
        windll = getattr(ctypes, "windll", None)
        self._user32 = windll.user32 if windll else None
        self._shell32 = windll.shell32 if windll else None

    def is_autohide_enabled(self) -> bool:
        try:
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            state = self._shell32.SHAppBarMessage(ABM_GETSTATE, ctypes.byref(abd))
            return bool(state & ABS_AUTOHIDE)
        except Exception:
            return False

    def set_autohide(self, enable: bool) -> bool:
        try:
            abd = APPBARDATA()
            abd.cbSize = ctypes.sizeof(APPBARDATA)
            hwnd = self._user32.FindWindowW("Shell_TrayWnd", None)
            abd.hWnd = hwnd if hwnd else 0
            abd.lParam = ABS_AUTOHIDE if enable else ABS_MANUAL
            self._shell32.SHAppBarMessage(ABM_SETSTATE, ctypes.byref(abd))
            self.config.set("taskbar_autohide_macbook", enable)
            self.taskbar_state_changed.emit(enable)
            return True
        except Exception as e:
            print(f"Error setting taskbar autohide: {e}")
            return False

    def get_windhawk_preset_xaml(self, preset_key: str) -> str:
        preset = WINDHAWK_PRESETS.get(preset_key)
        return preset["xaml"] if preset else ""
