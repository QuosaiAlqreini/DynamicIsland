"""Clipboard history (Notch-style "paste anything again" tray).

History is kept in memory only; only items the user explicitly pins are
persisted to the config file, so copied secrets never land on disk.
"""
import time

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from config import ConfigManager

MAX_ITEM_CHARS = 5000


class ClipboardService(QObject):
    history_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.history = []  # newest first, unpinned items only
        self._paused_until = 0.0
        self.pinned = [str(p) for p in self.config.get("clipboard_pinned", []) if p]
        self.clipboard = QApplication.clipboard()
        self.clipboard.dataChanged.connect(self._on_clipboard_changed)

    @property
    def enabled(self):
        return bool(self.config.get("clipboard_history_enabled", True))

    def pause(self, ms):
        """Ignore clipboard changes for a while (automation pastes)."""
        self._paused_until = time.monotonic() + ms / 1000

    def _on_clipboard_changed(self):
        if not self.enabled or time.monotonic() < self._paused_until:
            return
        mime = self.clipboard.mimeData()
        if mime is None or not mime.hasText():
            return
        text = mime.text()
        if not text or not text.strip():
            return
        self.add_text(text[:MAX_ITEM_CHARS])

    def add_text(self, text):
        if text in self.pinned:
            return
        if text in self.history:
            self.history.remove(text)
        self.history.insert(0, text)
        limit = max(1, int(self.config.get("clipboard_history_size", 25)))
        del self.history[limit:]
        self.history_changed.emit()

    def items(self):
        """Pinned entries first, then recent history: list of (text, pinned)."""
        return [(t, True) for t in self.pinned] + [(t, False) for t in self.history]

    def copy(self, text):
        # dataChanged fires afterwards and simply moves the entry to the top.
        self.clipboard.setText(text)

    def toggle_pin(self, text):
        if text in self.pinned:
            self.pinned.remove(text)
            self.history.insert(0, text)
        else:
            if text in self.history:
                self.history.remove(text)
            self.pinned.insert(0, text)
        self.config.set("clipboard_pinned", list(self.pinned))
        self.history_changed.emit()

    def remove(self, text):
        changed = False
        if text in self.history:
            self.history.remove(text)
            changed = True
        if text in self.pinned:
            self.pinned.remove(text)
            self.config.set("clipboard_pinned", list(self.pinned))
            changed = True
        if changed:
            self.history_changed.emit()

    def clear_history(self):
        self.history.clear()
        self.history_changed.emit()
