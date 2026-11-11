"""Time-synced lyrics from the open LRCLIB database (lrclib.net).

Only the song title, artist and length are sent, and only while
"lyrics_enabled" is on. Fetching happens on a background thread.
"""
import re
import threading

import requests
from PyQt6.QtCore import QObject, pyqtSignal

from config import ConfigManager

_LINE_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)")


def parse_lrc(text):
    """'[01:02.50] words' lines -> sorted [(seconds, text)]."""
    lines = []
    for raw in (text or "").splitlines():
        m = _LINE_RE.match(raw.strip())
        if m:
            lines.append((int(m.group(1)) * 60 + float(m.group(2)), m.group(3).strip()))
    return sorted(lines)


def line_at(lines, position):
    """The lyric line being sung at `position` seconds ('' before the first line)."""
    current = ""
    for start, text in lines:
        if start > position:
            break
        current = text
    return current


class LyricsService(QObject):
    line_changed = pyqtSignal(str)
    _fetched = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.track_key = ""
        self.lines = []
        self.line = ""
        self._cache = {}
        self._fetched.connect(self._on_fetched)

    @property
    def enabled(self):
        return bool(self.config.get("lyrics_enabled", True))

    def update_media(self, media):
        if not self.enabled or not media.get("has_media"):
            self._set_line("")
            return
        title, artist = media.get("title", ""), media.get("artist", "")
        key = f"{artist}|{title}"
        if key != self.track_key:
            self.track_key = key
            self.lines = self._cache.get(key, [])
            self._set_line("")
            if key not in self._cache and title and title != "Unknown Track":
                self._cache[key] = []
                threading.Thread(target=self._fetch, daemon=True,
                                 args=(key, title, artist, media.get("duration_sec", 0))).start()
        if self.lines and media.get("is_playing"):
            self._set_line(line_at(self.lines, media.get("position", media.get("position_sec", 0)) + 0.3))

    def _fetch(self, key, title, artist, duration):
        lines = []
        try:
            r = requests.get("https://lrclib.net/api/search", timeout=8,
                             params={"track_name": title, "artist_name": artist},
                             headers={"User-Agent": "DynamicIsland-for-Windows"})
            if r.ok:
                results = [x for x in r.json() if x.get("syncedLyrics")]
                if results:
                    best = min(results, key=lambda x: abs((x.get("duration") or 0) - (duration or 0)))
                    lines = parse_lrc(best["syncedLyrics"])
        except Exception:
            pass
        self._fetched.emit(key, lines)

    def _on_fetched(self, key, lines):
        self._cache[key] = lines
        if key == self.track_key:
            self.lines = lines

    def _set_line(self, line):
        if line != self.line:
            self.line = line
            self.line_changed.emit(line)
