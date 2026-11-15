"""Linux desktop integration (X11 and XWayland): the Linux side of what win_input,
media, volume and brightness do on Windows.

Uses the standard tools every distro ships or can install with one command:
  playerctl     media (MPRIS: Spotify, Firefox, Chrome, VLC, ...)
  wpctl/pactl   volume (PipeWire / PulseAudio)
  brightnessctl laptop screen brightness
  xprop         which window is in front / fullscreen
  xdotool       automations that press keys or type text
Every function fails soft (returns None / False) when its tool is missing."""
import ctypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

IS_LINUX = sys.platform.startswith("linux")


def has(tool):
    return shutil.which(tool) is not None


def run(args, timeout=2.0):
    """stdout of a quick command, or None if it is missing / failed."""
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def missing_tools():
    """Helper programs that would make more features work, with what they are for."""
    wanted = {"playerctl": "music in the island", "xprop": "hiding during fullscreen",
              "xdotool": "automations that press keys / type text",
              "brightnessctl": "brightness keys and popup"}
    if not (has("wpctl") or has("pactl")):
        wanted["wpctl"] = "volume"
    return {t: why for t, why in wanted.items() if not has(t)}


# ------------------------------------------------------------------ windows (X11)
def active_window_id():
    out = run(["xprop", "-root", "-notype", "_NET_ACTIVE_WINDOW"])
    m = re.search(r"window id # (0x[0-9a-f]+)", out or "")
    return m.group(1) if m and int(m.group(1), 16) else None


def window_info(wid):
    """{'fullscreen': bool, 'pid': int|None, 'class': str} of an X11 window."""
    out = run(["xprop", "-id", wid, "-notype", "_NET_WM_STATE", "_NET_WM_PID", "WM_CLASS"]) or ""
    pid = re.search(r"_NET_WM_PID = (\d+)", out)
    cls = re.search(r'WM_CLASS = "([^"]*)", "([^"]*)"', out)
    return {"fullscreen": "_NET_WM_STATE_FULLSCREEN" in out,
            "pid": int(pid.group(1)) if pid else None,
            "class": (cls.group(2) if cls else "").lower()}


def fullscreen_app_active():
    wid = active_window_id()
    if not wid:
        return False
    info = window_info(wid)
    return info["fullscreen"] and info["pid"] != os.getpid() and info["class"] not in ("desktop_window",)


def foreground_process_name():
    wid = active_window_id()
    pid = window_info(wid)["pid"] if wid else None
    if not pid:
        return ""
    try:
        import psutil
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


class _X11Pointer:
    """Mouse buttons anywhere on screen, straight from Xlib (fast enough to poll)."""
    def __init__(self):
        self.ok = False
        try:
            self.x = ctypes.CDLL("libX11.so.6")
            self.x.XOpenDisplay.restype = ctypes.c_void_p
            self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.x.XDefaultRootWindow.restype = ctypes.c_ulong
            self.x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
            u, i = ctypes.c_ulong, ctypes.c_int
            self.x.XQueryPointer.argtypes = [ctypes.c_void_p, u, ctypes.POINTER(u), ctypes.POINTER(u),
                                             ctypes.POINTER(i), ctypes.POINTER(i), ctypes.POINTER(i),
                                             ctypes.POINTER(i), ctypes.POINTER(ctypes.c_uint)]
            self.x.XQueryPointer.restype = ctypes.c_int
            self.display = self.x.XOpenDisplay(None)
            self.root = self.x.XDefaultRootWindow(self.display) if self.display else 0
            self.ok = bool(self.display)
        except OSError:
            pass

    def buttons_down(self):
        if not self.ok:
            return False
        u, i = ctypes.c_ulong(), ctypes.c_int()
        mask = ctypes.c_uint()
        self.x.XQueryPointer(self.display, self.root, ctypes.byref(u), ctypes.byref(ctypes.c_ulong()),
                             ctypes.byref(i), ctypes.byref(ctypes.c_int()), ctypes.byref(ctypes.c_int()),
                             ctypes.byref(ctypes.c_int()), ctypes.byref(mask))
        return bool(mask.value & ((1 << 8) | (1 << 10)))     # Button1Mask | Button3Mask


_pointer = None


def mouse_button_down():
    global _pointer
    if _pointer is None:
        _pointer = _X11Pointer() if os.environ.get("DISPLAY") else False
    return bool(_pointer and _pointer.buttons_down())


# ------------------------------------------------------------------ system
_inhibitor = None


def set_keep_awake(on):
    """Stop the screen from sleeping (systemd-inhibit) while on."""
    global _inhibitor
    if _inhibitor is not None:
        _inhibitor.terminate()
        _inhibitor = None
    if on and has("systemd-inhibit"):
        _inhibitor = subprocess.Popen(["systemd-inhibit", "--what=idle:sleep", "--who=Dynamic Island",
                                       "--why=Keep awake", "sleep", "infinity"])
        return True
    return not on


def lock_pc():
    for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"]):
        if has(cmd[0]) and run(cmd) is not None:
            return True
    return False


def sleep_pc():
    return run(["systemctl", "suspend"]) is not None


def toggle_dark_mode():
    """GNOME / most GTK desktops. Returns True if now dark, None if not possible."""
    if not has("gsettings"):
        return None
    cur = run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"]) or ""
    dark = "dark" not in cur
    run(["gsettings", "set", "org.gnome.desktop.interface", "color-scheme",
         "prefer-dark" if dark else "default"])
    return dark


def autostart_file():
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "autostart" / "dynamic-island.desktop"


def desktop_entry(command, autostart=False):
    lines = ["[Desktop Entry]", "Type=Application", "Name=Dynamic Island",
             "Comment=A notch / Dynamic Island for your desktop", f"Exec={command}",
             "Icon=dynamic-island", "Terminal=false", "Categories=Utility;"]
    if autostart:
        lines.append("X-GNOME-Autostart-enabled=true")
    return "\n".join(lines) + "\n"


def set_launch_at_login(enabled, command):
    f = autostart_file()
    if enabled:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(desktop_entry(command, autostart=True), encoding="utf-8")
    elif f.exists():
        f.unlink()
    return True


# ------------------------------------------------------------------ brightness
def brightness_get():
    out = run(["brightnessctl", "-m"])            # intel_backlight,backlight,800,80%,1000
    m = re.search(r",(\d+)%,", out or "")
    return int(m.group(1)) if m else None


def brightness_change(delta):
    step = f"{abs(int(delta))}%{'+' if delta > 0 else '-'}"
    return run(["brightnessctl", "set", step]) is not None


# ------------------------------------------------------------------ volume
def parse_wpctl(out):
    m = re.search(r"Volume:\s*([\d.]+)", out or "")
    return (int(round(float(m.group(1)) * 100)), "[MUTED]" in out) if m else None


def volume_get():
    if has("wpctl"):
        got = parse_wpctl(run(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"]))
        if got:
            return got
    if has("pactl"):
        vol = re.search(r"(\d+)%", run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"]) or "")
        mute = "yes" in (run(["pactl", "get-sink-mute", "@DEFAULT_SINK@"]) or "")
        if vol:
            return int(vol.group(1)), mute
    return None


def volume_set(percent):
    percent = max(0, min(100, int(percent)))
    if has("wpctl"):
        return run(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%"]) is not None
    return run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%"]) is not None


def volume_toggle_mute():
    if has("wpctl"):
        return run(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"]) is not None
    return run(["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"]) is not None


# ------------------------------------------------------------------ media (MPRIS)
PLAYERCTL_FORMAT = ("{{status}}\t{{title}}\t{{artist}}\t{{album}}\t{{position}}\t"
                    "{{mpris:length}}\t{{mpris:artUrl}}\t{{playerName}}")


def parse_playerctl(line):
    """One playerctl metadata line -> media dict (same keys as on Windows) or None."""
    parts = (line or "").rstrip("\n").split("\t")
    if len(parts) < 8 or not (parts[1] or parts[2]):
        return None
    status, title, artist, album, pos, length, art, player = parts[:8]
    to_s = lambda us: (int(us) / 1_000_000) if us.strip().isdigit() else 0
    dur = to_s(length)
    name = player.split(".")[0].capitalize() or "Player"
    return {"title": title or "Unknown Track", "artist": artist or "Unknown Artist", "album": album,
            "is_playing": status.strip() == "Playing", "has_media": True, "source": name,
            "position_sec": int(to_s(pos)), "position": to_s(pos),
            "duration_sec": int(dur) if dur > 0 else 180, "art_url": art}


def media_read():
    return parse_playerctl(run(["playerctl", "metadata", "--format", PLAYERCTL_FORMAT]))


def media_art(url):
    """Album cover bytes from a file:// or https:// URL (b'' if none)."""
    try:
        if url.startswith("file://"):
            from urllib.parse import unquote, urlparse
            return Path(unquote(urlparse(url).path)).read_bytes()
        if url.startswith(("http://", "https://")):
            import requests
            r = requests.get(url, timeout=5)
            return r.content if r.ok else b""
    except Exception:
        pass
    return b""


def media_command(action):
    """play-pause | next | previous"""
    return run(["playerctl", action]) is not None


# ------------------------------------------------------------------ keys (xdotool)
_XDO_KEYS = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift", "win": "super",
             "meta": "super", "enter": "Return", "esc": "Escape", "escape": "Escape", "tab": "Tab",
             "space": "space", "backspace": "BackSpace", "delete": "Delete", "del": "Delete",
             "pgup": "Prior", "pgdown": "Next", "up": "Up", "down": "Down", "left": "Left",
             "right": "Right", "home": "Home", "end": "End", "printscreen": "Print"}


def xdotool_combo(combo):
    """'Ctrl+Shift+T' -> 'ctrl+shift+t' (xdotool key syntax)."""
    out = []
    for part in combo.split("+"):
        p = part.strip()
        if not p:
            continue
        low = p.lower()
        out.append(_XDO_KEYS.get(low, p.upper() if re.fullmatch(r"f\d{1,2}", low) else low))
    return "+".join(out)


def send_combo(combo):
    return run(["xdotool", "key", "--clearmodifiers", xdotool_combo(combo)]) is not None


def send_text(text):
    return run(["xdotool", "type", "--delay", "4", "--", text], timeout=10) is not None


def prefer_x11():
    """On Wayland, run through XWayland so the island may sit at the top, stay on top and be
    click-through (plain Wayland apps are not allowed to place themselves)."""
    if IS_LINUX and os.environ.get("WAYLAND_DISPLAY") and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "xcb"
