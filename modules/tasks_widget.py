"""Tasks tab: to-do list with timed reminders and snooze."""
import datetime as dt

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem, QLineEdit
)

from services.tasks_service import due_label
from styles import badge_style, small_button_style, list_style, input_style

ID_ROLE = Qt.ItemDataRole.UserRole


class TasksWidget(QWidget):
    def __init__(self, theme, tasks_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.tasks = tasks_service
        self._filling = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 6)
        lay.setSpacing(5)
        head = QHBoxLayout()
        self.badge = QLabel("✅ TASKS & REMINDERS")
        head.addWidget(self.badge)
        head.addStretch()
        self.count = QLabel("")
        head.addWidget(self.count)
        lay.addLayout(head)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Add a task…  e.g.  Call mom at 17:30   ·   Stretch in 20m   ·   Report tomorrow 9am")
        self.input.returnPressed.connect(self._add)
        lay.addWidget(self.input)

        self.list = QListWidget()
        self.list.itemChanged.connect(self._on_item_changed)
        lay.addWidget(self.list, 1)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.btn_snooze = QPushButton("💤 Snooze 10m")
        self.btn_snooze.clicked.connect(lambda: self._with_selected(lambda i: self.tasks.snooze(i, 10)))
        self.btn_hour = QPushButton("+1h")
        self.btn_hour.setToolTip("Remind me in an hour")
        self.btn_hour.clicked.connect(lambda: self._with_selected(lambda i: self.tasks.snooze(i, 60)))
        self.btn_del = QPushButton("✕ Delete")
        self.btn_del.clicked.connect(lambda: self._with_selected(self.tasks.remove))
        self.btn_clear = QPushButton("Clear done")
        self.btn_clear.clicked.connect(self.tasks.clear_done)
        for b in (self.btn_snooze, self.btn_hour, self.btn_del):
            row.addWidget(b)
        row.addStretch()
        row.addWidget(self.btn_clear)
        lay.addLayout(row)

        self.tasks.changed.connect(self.refresh)
        self._apply_styles()
        self.refresh()

    def _apply_styles(self):
        self.badge.setStyleSheet(badge_style(self.theme))
        self.count.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 9px;")
        self.input.setStyleSheet(f"QLineEdit {{ {input_style(self.theme)} }}")
        self.list.setStyleSheet(list_style(self.theme))
        css = small_button_style(self.theme)
        for b in (self.btn_snooze, self.btn_hour, self.btn_del, self.btn_clear):
            b.setStyleSheet(css)

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()
        self.refresh()

    def focus_input(self):
        self.input.setFocus()

    def _add(self):
        if self.tasks.add(self.input.text()):
            self.input.clear()

    def _with_selected(self, fn):
        item = self.list.currentItem()
        if item and item.data(ID_ROLE):
            fn(item.data(ID_ROLE))

    def _on_item_changed(self, item):
        if not self._filling and item.data(ID_ROLE):
            self.tasks.set_done(item.data(ID_ROLE), item.checkState() == Qt.CheckState.Checked)

    def refresh(self):
        selected = self.list.currentItem().data(ID_ROLE) if self.list.currentItem() else None
        self._filling = True
        self.list.clear()
        now = dt.datetime.now()
        tasks = self.tasks.sorted_tasks()
        for t in tasks:
            due = due_label(t.get("due"), now)
            ringing = t.get("notified") and not t.get("done")
            text = ("⏰ " if ringing else "") + (f"{due}  ·  " if due else "") + t["title"]
            item = QListWidgetItem(text)
            item.setData(ID_ROLE, t["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if t.get("done") else Qt.CheckState.Unchecked)
            if t.get("done"):
                font = item.font()
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QColor(self.theme["text_secondary"]))
            elif ringing:
                item.setForeground(QColor(self.theme["warning"]))
            self.list.addItem(item)
            if t["id"] == selected:
                self.list.setCurrentItem(item)
        if not tasks:
            hint = QListWidgetItem("Nothing to do. Type a task above and press Enter.")
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(hint)
        self._filling = False
        open_count = sum(not t.get("done") for t in tasks)
        self.count.setText(f"{open_count} open" if tasks else "")
