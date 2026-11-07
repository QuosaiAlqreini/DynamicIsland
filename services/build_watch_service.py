"""Build / long-task tracker (Notchification-style live activity).

Polls running processes in a background thread and reports build-like
commands (npm run build, cargo build, pytest, docker build, ...) so the
island can show "building..." and announce when they finish.
"""
import os
import threading
import time

import psutil
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import ConfigManager

_STRIP_EXT = (".exe", ".cmd", ".bat", ".ps1", ".js", ".cjs", ".mjs", ".py")
_SKIP_TOKENS = {"--watch", "watch", "-w", "serve", "dev", "start"}


def _normalize(token):
    token = token.strip().strip('"').strip("'")
    base = os.path.basename(token.replace("\\", "/")).lower()
    for ext in _STRIP_EXT:
        if base.endswith(ext):
            base = base[: -len(ext)]
            break
    if base.endswith("-cli"):
        base = base[:-4]
    return base


def tokenize(cmdline):
    tokens = []
    for part in cmdline:
        for sub in str(part).split():
            norm = _normalize(sub)
            if norm:
                tokens.append(norm)
    return tokens


def match_pattern(tokens, patterns):
    """Return the first pattern whose tokens appear consecutively in `tokens`."""
    if not tokens or _SKIP_TOKENS.intersection(tokens):
        return None
    for pattern in patterns:
        ptoks = [_normalize(t) if i == 0 else t.lower() for i, t in enumerate(pattern.split())]
        n = len(ptoks)
        if n == 0:
            continue
        for i in range(len(tokens) - n + 1):
            if tokens[i:i + n] == ptoks:
                return pattern
    return None


class BuildWatchService(QObject):
    jobs_changed = pyqtSignal(list)       # list of {pid, name, project, started}
    job_finished = pyqtSignal(str, int)   # display name, duration seconds
    _scan_done = pyqtSignal(dict)

    def __init__(self, interval_ms=2000, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.jobs = {}
        self._scanning = False
        self._scan_done.connect(self._apply_scan)
        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self._kick_scan)

    def start(self):
        self.timer.start()
        self._kick_scan()

    def stop(self):
        self.timer.stop()

    def _kick_scan(self):
        if self._scanning or not self.config.get("build_watch_enabled", True):
            return
        self._scanning = True
        patterns = list(self.config.get("build_watch_patterns", []))
        threading.Thread(target=self._scan, args=(patterns,), daemon=True).start()

    def _scan(self, patterns):
        found = {}
        try:
            own_pid = os.getpid()
            for proc in psutil.process_iter(["pid", "ppid", "cmdline", "create_time"]):
                info = proc.info
                if info["pid"] == own_pid or not info.get("cmdline"):
                    continue
                pattern = match_pattern(tokenize(info["cmdline"]), patterns)
                if not pattern:
                    continue
                project = ""
                try:
                    project = os.path.basename(proc.cwd().rstrip("\\/"))
                except (psutil.Error, OSError):
                    pass
                found[info["pid"]] = {
                    "pid": info["pid"],
                    "ppid": info.get("ppid"),
                    "name": pattern,
                    "project": project,
                    "started": info.get("create_time") or time.time(),
                }
        except Exception:
            pass
        # Keep only the outermost process of a chain (cmd -> npm -> node ...)
        roots = {pid: job for pid, job in found.items() if job["ppid"] not in found}
        self._scan_done.emit(roots)

    def _apply_scan(self, roots):
        self._scanning = False
        min_sec = int(self.config.get("build_watch_min_seconds", 5))
        now = time.time()
        for pid, job in list(self.jobs.items()):
            if pid not in roots:
                del self.jobs[pid]
                duration = int(now - job["started"])
                if duration >= min_sec:
                    self.job_finished.emit(self.display_name(job), duration)
        for pid, job in roots.items():
            self.jobs.setdefault(pid, job)
        self.jobs_changed.emit(self.visible_jobs())

    def visible_jobs(self):
        """Jobs that have been running long enough to be worth showing."""
        min_sec = int(self.config.get("build_watch_min_seconds", 5))
        now = time.time()
        jobs = [j for j in self.jobs.values() if now - j["started"] >= min_sec]
        return sorted(jobs, key=lambda j: j["started"])

    @staticmethod
    def display_name(job):
        return f"{job['name']} · {job['project']}" if job.get("project") else job["name"]
