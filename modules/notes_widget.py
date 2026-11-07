"""Notes tab: an always-there scratchpad that autosaves as you type."""
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit
)

from config import ConfigManager
from styles import badge_style, small_button_style, input_style


class NotesWidget(QWidget):
    def __init__(self, theme, clipboard_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.config = ConfigManager()
        self.clipboard_service = clipboard_service

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(600)
        self.save_timer.timeout.connect(self._save)

        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 6)
        layout.setSpacing(4)

        head = QHBoxLayout()
        self.badge = QLabel("📝 QUICK NOTES")
        head.addWidget(self.badge)
        head.addStretch()
        self.status = QLabel("autosaved")
        head.addWidget(self.status)
        self.btn_stamp = QPushButton("🕒")
        self.btn_stamp.setToolTip("Insert timestamp")
        self.btn_stamp.clicked.connect(self._insert_timestamp)
        head.addWidget(self.btn_stamp)
        self.btn_paste = QPushButton("Paste")
        self.btn_paste.setToolTip("Append clipboard text")
        self.btn_paste.clicked.connect(self._append_clipboard)
        head.addWidget(self.btn_paste)
        self.btn_copy = QPushButton("Copy all")
        self.btn_copy.clicked.connect(lambda: self.clipboard_service.copy(self.editor.toPlainText()))
        head.addWidget(self.btn_copy)
        self.btn_clear = QPushButton("Clear")
        self.btn_clear.clicked.connect(self._clear)
        head.addWidget(self.btn_clear)
        layout.addLayout(head)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Jot anything — todos, snippets, phone numbers…  (Ctrl+Alt+Space opens the island from anywhere)")
        self.editor.setPlainText(self.config.get("quick_notes", "") or "")
        self.editor.textChanged.connect(self._on_changed)
        layout.addWidget(self.editor)

    def _apply_styles(self):
        self.badge.setStyleSheet(badge_style(self.theme))
        self.status.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 9px;")
        self.editor.setStyleSheet(f"QPlainTextEdit {{ {input_style(self.theme)} }}")
        css = small_button_style(self.theme)
        for b in (self.btn_stamp, self.btn_paste, self.btn_copy, self.btn_clear):
            b.setStyleSheet(css)

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()

    def focus_editor(self):
        self.editor.setFocus()
        cursor = self.editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.editor.setTextCursor(cursor)

    def append_text(self, text):
        current = self.editor.toPlainText()
        sep = "" if not current or current.endswith("\n") else "\n"
        self.editor.setPlainText(current + sep + text)
        self.focus_editor()

    def _insert_timestamp(self):
        import time
        self.editor.insertPlainText(time.strftime("[%Y-%m-%d %H:%M] "))
        self.editor.setFocus()

    def _append_clipboard(self):
        text = self.clipboard_service.clipboard.text()
        if text:
            self.append_text(text)

    def _clear(self):
        self.editor.clear()
        self._save()

    def _on_changed(self):
        self.status.setText("editing…")
        self.save_timer.start()

    def _save(self):
        self.config.set("quick_notes", self.editor.toPlainText())
        self.status.setText("autosaved")
