"""What is using the RAM: the biggest apps (all their processes added up), the island's own
share, and tips that fit what was found. Scans run on a background thread, and only while
someone is looking (the System tab is open)."""
import os
import threading

import psutil
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

FRIENDLY = {
    "msedge": "Microsoft Edge", "chrome": "Google Chrome", "firefox": "Firefox", "brave": "Brave",
    "opera": "Opera", "code": "VS Code", "teams": "Teams", "ms-teams": "Teams", "discord": "Discord",
    "spotify": "Spotify", "slack": "Slack", "explorer": "File Explorer", "ollama": "Ollama (local AI)",
    "ollama_llama_server": "Ollama (local AI)", "llama-server": "Ollama (local AI)",
    "msmpeng": "Windows Defender", "searchhost": "Windows Search", "dwm": "Desktop Window Manager",
    "whatsapp": "WhatsApp", "steam": "Steam", "steamwebhelper": "Steam", "onedrive": "OneDrive",
    "python": "Python", "pythonw": "Python", "dynamicisland": "Dynamic Island",
    "memory compression": "Memory compression (Windows)", "vmmem": "WSL / virtual machine",
    "vmmemwsl": "WSL / virtual machine", "msedgewebview2": "Edge WebView (used by apps)",
    "node": "Node.js", "claude": "Claude", "winword": "Word", "excel": "Excel",
    "powerpnt": "PowerPoint", "outlook": "Outlook", "olk": "Outlook",
}
BROWSERS = {"Microsoft Edge", "Google Chrome", "Firefox", "Brave", "Opera"}


def friendly_name(proc_name):
    base = proc_name.lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return FRIENDLY.get(base, proc_name[:-4] if proc_name.lower().endswith(".exe") else proc_name)


def group_processes(rows):
    """rows: [(process name, bytes)] -> [(app name, bytes, process count)] biggest first."""
    apps = {}
    for name, size in rows:
        if not name or not size:
            continue
        app = friendly_name(name)
        total, count = apps.get(app, (0, 0))
        apps[app] = (total + size, count + 1)
    return sorted(((a, s, n) for a, (s, n) in apps.items()), key=lambda x: -x[1])


def own_usage():
    """Bytes this app uses (the process plus any helper it started)."""
    try:
        me = psutil.Process(os.getpid())
        total = me.memory_info().rss
        for child in me.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                pass
        return total
    except psutil.Error:
        return 0


def scan(limit=6):
    rows = []
    for p in psutil.process_iter(["name", "memory_info"]):
        info = p.info.get("memory_info")
        if info is not None:
            rows.append((p.info.get("name") or "", info.rss))
    mem = psutil.virtual_memory()
    return {"apps": group_processes(rows)[:limit], "own": own_usage(),
            "used": mem.total - mem.available, "total": mem.total, "percent": mem.percent}


def tips(result, eco_on=False):
    """Short, concrete advice for what was actually found (most useful first)."""
    out = []
    apps = result.get("apps", [])
    total = result.get("total") or 1
    names = [a for a, _s, _n in apps]
    for app, size, count in apps[:4]:
        share = size / total
        if app in BROWSERS and share > 0.08:
            out.append(f"{app} uses {fmt(size)} across {count} processes: close tabs you don't need, "
                       f"or turn on sleeping tabs / Memory Saver in its settings.")
        elif app.startswith("Ollama") and size > 1.5 * 2**30:
            out.append(f"The local AI keeps {fmt(size)} loaded. In AI settings tick “Free the RAM right "
                       f"after each answer”, or pick qwen3.5:2b.")
        elif app == "WSL / virtual machine":
            out.append("WSL / a virtual machine holds RAM until it stops: run “wsl --shutdown” when done.")
        elif app in ("Teams", "Discord", "Slack", "Spotify", "Steam", "WhatsApp") and share > 0.04:
            out.append(f"{app} keeps running in the tray: quit it there when you don't need it.")
    if result.get("percent", 0) > 80:
        out.append("RAM is almost full: Windows will slow down. Restarting the laptop also frees memory "
                   "that leaky apps never gave back.")
    out.append("Stop apps from starting with Windows: Settings › Apps › Startup.")
    if not eco_on:
        out.append("Eco mode makes this island lighter (no blur, lyrics, weather or build watching).")
    seen, unique = set(), []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


def fmt(size):
    gb = size / 2**30
    return f"{gb:.1f} GB" if gb >= 1 else f"{size / 2**20:.0f} MB"


class MemoryService(QObject):
    updated = pyqtSignal(dict)

    def __init__(self, interval_ms=8000, parent=None):
        super().__init__(parent)
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.refresh)
        self._busy = False
        self.last = None

    def watch(self, on):
        """Scan only while the list is on screen."""
        if on:
            self.refresh()
            self.timer.start()
        else:
            self.timer.stop()

    def refresh(self):
        if self._busy:
            return
        self._busy = True

        def work():
            try:
                result = scan()
                self.last = result
            except Exception as e:
                result = {"apps": [], "own": 0, "used": 0, "total": 0, "percent": 0, "error": str(e)}
            self._busy = False
            self.updated.emit(result)
        threading.Thread(target=work, name="memory-scan", daemon=True).start()


def trim_own_memory():
    """Give unused pages back to Windows (they come back on demand). Windows only."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        psapi = ctypes.WinDLL("psapi")
        psapi.EmptyWorkingSet.argtypes = (wintypes.HANDLE,)
        psapi.EmptyWorkingSet.restype = wintypes.BOOL
        return bool(psapi.EmptyWorkingSet(wintypes.HANDLE(-1)))   # -1 = this process
    except Exception:
        return False
