"""To-do list with optional due times, reminders and snooze.

Tasks can be typed as a phrase: "Call mom at 17:30", "Stretch in 20m",
"Submit report tomorrow 9am", "Buy milk".
"""
import datetime as dt
import re
import uuid

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

_UNITS = {"s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
          "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
          "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
          "d": 86400, "day": 86400, "days": 86400}
_IN_RE = re.compile(r"\s+in\s+(\d+(?:\.\d+)?)\s*([a-z]+)\s*$", re.I)
_AT_RE = re.compile(r"\s+(tomorrow\s+)?(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*$", re.I)
_TOMORROW_RE = re.compile(r"\s+tomorrow\s*$", re.I)


def parse_task_phrase(text, now=None):
    """'Call mom at 17:30' -> ('Call mom', datetime). Due is None when no time is given."""
    now = now or dt.datetime.now()
    text = " " + text.strip()
    m = _IN_RE.search(text)
    if m and m.group(2).lower() in _UNITS:
        seconds = float(m.group(1)) * _UNITS[m.group(2).lower()]
        return text[:m.start()].strip(), now + dt.timedelta(seconds=seconds)
    m = _AT_RE.search(text)
    if m and (m.group(3) or m.group(4) or " at " in text[m.start():].lower() + " " or m.group(1)):
        hour, minute = int(m.group(2)), int(m.group(3) or 0)
        ampm = (m.group(4) or "").lower()
        if ampm == "pm" and hour < 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
        if hour < 24 and minute < 60:
            due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if m.group(1) or due <= now:
                due += dt.timedelta(days=1)
            return text[:m.start()].strip(), due
    m = _TOMORROW_RE.search(text)
    if m:
        due = (now + dt.timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return text[:m.start()].strip(), due
    return text.strip(), None


def due_label(due_ts, now=None):
    if not due_ts:
        return ""
    now = now or dt.datetime.now()
    due = dt.datetime.fromtimestamp(due_ts)
    if due.date() == now.date():
        return due.strftime("%H:%M")
    if due.date() == (now + dt.timedelta(days=1)).date():
        return "tmrw " + due.strftime("%H:%M")
    return due.strftime("%d %b %H:%M")


class TasksService(QObject):
    changed = pyqtSignal()
    reminder = pyqtSignal(dict)   # a task just became due

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.timer = QTimer(self)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self.check_due)
        self.timer.start()

    @property
    def tasks(self):
        return [t for t in self.config.get("tasks", []) if isinstance(t, dict) and t.get("id")]

    def _save(self, tasks):
        self.config.set("tasks", tasks)
        self.changed.emit()

    def sorted_tasks(self):
        """Open tasks first (timed ones by time, then untimed), done tasks last."""
        return sorted(self.tasks, key=lambda t: (bool(t.get("done")), t.get("due") is None,
                                                 t.get("due") or 0, t.get("created", 0)))

    def add(self, phrase, now=None):
        title, due = parse_task_phrase(phrase, now)
        if not title:
            return None
        task = {"id": uuid.uuid4().hex[:8], "title": title, "done": False, "notified": False,
                "due": due.timestamp() if due else None,
                "created": (now or dt.datetime.now()).timestamp()}
        self._save(self.tasks + [task])
        return task

    def _update(self, task_id, **fields):
        tasks = self.tasks
        for t in tasks:
            if t["id"] == task_id:
                t.update(fields)
        self._save(tasks)

    def set_done(self, task_id, done=True):
        self._update(task_id, done=done)

    def snooze(self, task_id, minutes=10):
        due = dt.datetime.now() + dt.timedelta(minutes=minutes)
        self._update(task_id, due=due.timestamp(), notified=False, done=False)

    def remove(self, task_id):
        self._save([t for t in self.tasks if t["id"] != task_id])

    def clear_done(self):
        self._save([t for t in self.tasks if not t.get("done")])

    def next_due(self):
        timed = [t for t in self.tasks if not t.get("done") and t.get("due")]
        return min(timed, key=lambda t: t["due"]) if timed else None

    def ringing(self):
        """Tasks whose reminder fired and that are not done or snoozed yet."""
        return [t for t in self.tasks if t.get("notified") and not t.get("done")]

    def check_due(self, now=None):
        now_ts = (now or dt.datetime.now()).timestamp()
        fired = []
        tasks = self.tasks
        for t in tasks:
            if t.get("due") and not t.get("done") and not t.get("notified") and t["due"] <= now_ts:
                t["notified"] = True
                fired.append(dict(t))
        if fired:
            self._save(tasks)
            for t in fired:
                self.reminder.emit(t)
