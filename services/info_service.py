"""Info items the user can add to the island (pill slots and the Info tab).

Item types:
  text        - fixed text you type (a reminder, a status...)
  world_clock - time in another place: IANA zone ("Asia/Riyadh") or UTC offset ("+3", "-5:30")
  countdown   - time left until a date: "2026-12-25" or "2026-12-25 18:00"
  command     - first line printed by a command, refreshed every N seconds
"""
import datetime as dt
import re
import subprocess
import sys
import threading
import time
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

INFO_TYPES = [
    ("text", "Custom text", "The text to show"),
    ("world_clock", "World clock", "Time zone, e.g. Asia/Riyadh, Europe/London, America/New_York, or +3"),
    ("countdown", "Countdown to a date", "Date, e.g. 2026-12-25 or 2026-12-25 18:00"),
    ("command", "Command output", "Command whose first output line is shown, e.g. curl -s wttr.in/?format=3"),
]
INFO_TYPE_LABELS = {k: label for k, label, _ in INFO_TYPES}

# Built-in things the compact pill can show (key, label)
PILL_BUILTINS = [
    ("none", "Nothing"),
    ("ai_dot", "AI status dot"),
    ("clock", "Clock (14:05)"),
    ("clock_seconds", "Clock with seconds"),
    ("date", "Date (Sat 8 Nov)"),
    ("battery_icon", "Battery icon"),
    ("battery_pct", "Battery %"),
    ("cpu", "CPU usage"),
    ("ram", "RAM usage"),
    ("media_title", "Now playing"),
    ("lyrics", "Song lyrics (current line)"),
    ("next_task", "Next task / reminder"),
    ("next_prayer", "Next prayer"),
    ("water", "Water today (text)"),
    ("water_ring", "Water ring"),
    ("battery_ring", "Battery ring"),
]
CREATE_NO_WINDOW = 0x08000000


def new_info_id():
    return uuid.uuid4().hex[:8]


def _tz(value):
    value = (value or "").strip()
    m = re.fullmatch(r"(?:UTC|GMT)?\s*([+-])(\d{1,2})(?::?(\d{2}))?", value, re.I)
    if m:
        sign = 1 if m.group(1) == "+" else -1
        delta = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3) or 0))
        return dt.timezone(sign * delta)
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(value)
    except Exception:
        return None


def world_clock_text(value, now=None):
    tz = _tz(value)
    if tz is None:
        return "bad zone"
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.astimezone(tz).strftime("%H:%M")


def _parse_date(value):
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def countdown_text(value, now=None):
    target = _parse_date(value or "")
    if target is None:
        return "bad date"
    secs = int((target - (now or dt.datetime.now())).total_seconds())
    if secs <= 0:
        return "now 🎉"
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


class InfoService(QObject):
    values_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.values = {}           # item id -> display value
        self._last_run = {}        # item id -> monotonic time of last command start
        self._running = set()
        self.sys = {}
        self.media = {}
        self.lyrics = self.tasks = self.day = None   # set by the island
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    # ------------------------------------------------------------ items
    @property
    def items(self):
        return [i for i in self.config.get("info_items", []) if isinstance(i, dict) and i.get("id")]

    def save_items(self, items):
        self.config.set("info_items", [dict(i) for i in items])
        self._last_run.clear()
        self.refresh()

    def item(self, item_id):
        return next((i for i in self.items if i["id"] == item_id), None)

    # ------------------------------------------------------- live inputs
    def update_system(self, stats):
        self.sys = stats

    def update_media(self, media):
        self.media = media

    def builtin_text(self, key):
        s = self.sys
        if key == "lyrics":
            return self.lyrics.line if self.lyrics else ""
        if key == "next_task" and self.tasks:
            task = self.tasks.next_due()
            if not task:
                return ""
            from services.tasks_service import due_label
            return f"{due_label(task['due'])} {task['title']}"
        if key == "next_prayer":
            return self.day.next_prayer_text() if self.day else ""
        if key == "water" and self.day:
            return f"💧{self.day.water_ml / 1000:.2g}/{self.day.water_goal / 1000:.2g}L"
        if key == "clock":
            return time.strftime("%H:%M")
        if key == "clock_seconds":
            return time.strftime("%H:%M:%S")
        if key == "date":
            now = dt.datetime.now()
            return f"{now:%a} {now.day} {now:%b}"
        if key == "battery_pct":
            return f"{'⚡' if s.get('battery_plugged', True) else '🔋'}{int(s.get('battery_percent', 100))}%"
        if key == "cpu":
            return f"CPU {int(s.get('cpu_percent', 0))}%"
        if key == "ram":
            return f"RAM {int(s.get('mem_percent', 0))}%"
        if key == "media_title":
            if self.media.get("has_media") or self.media.get("is_playing"):
                return f"♪ {self.media.get('title', '')}"
            return ""
        return ""

    def slot_text(self, slot):
        """Text for a pill slot key ('clock', 'info:<id>', ...)."""
        if slot.startswith("info:"):
            item = self.item(slot[5:])
            if not item:
                return ""
            value = self.values.get(item["id"], "…")
            label = (item.get("label") or "").strip()
            if item.get("type") == "text":
                return value
            return f"{label} {value}".strip() if label else value
        return self.builtin_text(slot)

    # ----------------------------------------------------------- refresh
    def refresh(self):
        now_utc = dt.datetime.now(dt.timezone.utc)
        for item in self.items:
            kind, value, iid = item.get("type"), str(item.get("value", "")), item["id"]
            if kind == "text":
                self.values[iid] = value
            elif kind == "world_clock":
                self.values[iid] = world_clock_text(value, now_utc)
            elif kind == "countdown":
                self.values[iid] = countdown_text(value)
            elif kind == "command":
                self._maybe_run_command(item)
        self.values_changed.emit()

    def _maybe_run_command(self, item):
        iid = item["id"]
        interval = max(5, int(item.get("interval", 60) or 60))
        last = self._last_run.get(iid)
        if iid in self._running or (last is not None and time.monotonic() - last < interval):
            return
        cmd = str(item.get("value", "")).strip()
        if not cmd:
            self.values[iid] = ""
            return
        self._last_run[iid] = time.monotonic()
        self._running.add(iid)
        self.values.setdefault(iid, "…")
        threading.Thread(target=self._run_command, args=(iid, cmd), daemon=True).start()

    def _run_command(self, iid, cmd):
        try:
            kwargs = {"creationflags": CREATE_NO_WINDOW} if sys.platform == "win32" else {}
            out = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                 timeout=15, encoding="utf-8", errors="replace", **kwargs)
            text = (out.stdout or out.stderr or "").strip().splitlines()
            value = text[0].strip()[:80] if text else ""
        except subprocess.TimeoutExpired:
            value = "timeout"
        except Exception as e:
            value = f"error: {e}"[:60]
        self.values[iid] = value
        self._running.discard(iid)
