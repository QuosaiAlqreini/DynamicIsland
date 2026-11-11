"""Command bar: one box to launch apps, calculate, set timers and reminders,
transform clipboard text, run commands and search the web."""
import re
import subprocess
import urllib.parse

from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QApplication
)

from modules.tab_registry import TAB_REGISTRY
from services.commands import AppIndex, calculate, TEXT_TOOLS, run_text_tool
from services.launcher import open_target
from styles import _rgba

ACTION_ROLE = Qt.ItemDataRole.UserRole
_TIMER_RE = re.compile(r"^(?:timer\s+)?(\d+(?:\.\d+)?)\s*(m|min|mins|minutes|h|hr|hours|s|sec)?$", re.I)


class CommandBar(QWidget):
    def __init__(self, theme, island, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.island = island
        self.index = AppIndex()
        self.index.start()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        self.input = QLineEdit()
        self.input.setPlaceholderText("App, 2+2, timer 10m, remind Call mom at 17:30, upper, > command, or search the web")
        self.input.textChanged.connect(self._refresh)
        self.input.installEventFilter(self)
        lay.addWidget(self.input)
        self.results = QListWidget()
        self.results.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.results.itemClicked.connect(self._run_item)
        lay.addWidget(self.results)
        self.update_theme(theme)

    def update_theme(self, theme):
        self.theme = t = theme
        self.input.setStyleSheet(f"""QLineEdit {{ background: transparent; color: {t['text_primary']};
            border: none; font-size: 16px; padding: 6px 4px; }}""")
        self.results.setStyleSheet(f"""
            QListWidget {{ background: transparent; border: none; color: {t['text_primary']};
                           font-size: 12px; outline: none; }}
            QListWidget::item {{ padding: 6px 8px; border-radius: 6px; }}
            QListWidget::item:selected {{ background: {_rgba(t['accent'], 0.20)}; color: {t['text_primary']}; }}
        """)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor(self.theme["bg_color"])))
        p.setPen(QPen(QColor(self.theme["border_color"]), 1.2))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 16, 16)

    # ------------------------------------------------------------ show/hide
    def toggle(self):
        if self.isVisible():
            self.hide()
        else:
            self.open()

    def open(self):
        self.input.clear()
        self._refresh()
        screen = self.island.screen() or QApplication.primaryScreen()
        geom = screen.geometry()
        self.move(int(geom.x() + (geom.width() - self.width()) / 2), geom.y() + int(geom.height() * 0.22))
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            self.hide()
        super().changeEvent(event)

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self.hide()
                return True
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                step = 1 if key == Qt.Key.Key_Down else -1
                count = self.results.count()
                if count:
                    self.results.setCurrentRow((self.results.currentRow() + step) % count)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                item = self.results.currentItem()
                if item:
                    self._run_item(item)
                return True
        return super().eventFilter(obj, event)

    # -------------------------------------------------------------- results
    def suggestions(self, text):
        """[(label, action)] for the typed text; action is a no-argument callable."""
        q = text.strip()
        out = []
        if not q:
            return [("Type to search apps, calculate, set a timer, add a reminder…", None)]
        low = q.lower()
        isl = self.island

        if q.startswith(">"):
            cmd = q[1:].strip()
            if cmd:
                out.append((f"▶ Run in terminal: {cmd}", lambda: subprocess.Popen(f'start cmd /k "{cmd}"', shell=True)))
            return out or [("Type a command after >", None)]

        result = calculate(q)
        if result is not None:
            out.append((f"🧮 {result}   (Enter copies)", lambda: QApplication.clipboard().setText(result.replace(",", ""))))

        m = _TIMER_RE.match(low)
        if m and (low.startswith("timer") or m.group(2)):
            n = float(m.group(1))
            unit = (m.group(2) or "m")[0]
            minutes = n * 60 if unit == "h" else n / 60 if unit == "s" else n
            out.append((f"⏱️ Start a {q.replace('timer', '').strip()} timer",
                        lambda: isl.timer_service.start(minutes, "Timer")))
        if low in ("pomodoro", "pomo"):
            out.append(("🍅 Start Pomodoro (4 × 25 min with breaks)", isl.timer_service.start_pomodoro))

        for prefix in ("remind me to ", "remind me ", "remind ", "todo ", "task "):
            if low.startswith(prefix) and len(q) > len(prefix):
                phrase = q[len(prefix):]
                out.append((f"✅ Add task: {phrase}", lambda: isl.tasks_service.add(phrase)))
                break
        if low.startswith("note ") and len(q) > 5:
            out.append((f"📝 Add to notes: {q[5:]}", lambda: isl.notes_widget.append_text(q[5:])))
        if low in ("water", "drink"):
            out.append(("💧 Log a glass of water", isl.day_service.add_water))

        for name, (desc, _fn) in TEXT_TOOLS.items():
            if name.startswith(low) and len(low) >= 2:
                def tool(n=name):
                    clip = QApplication.clipboard()
                    clip.setText(run_text_tool(n, clip.text()))
                out.append((f"🔤 {name}: {desc}", tool))

        for key, (icon, label, tip) in TAB_REGISTRY.items():
            if label.lower().startswith(low) or key.startswith(low):
                out.append((f"{icon} Open {label} tab", lambda k=key: isl.open_tab_by_key(k)))
        for macro in isl.automation_service.macros:
            name = macro.get("name", "")
            if macro.get("enabled", True) and low in name.lower():
                out.append((f"⌨️ {name}", lambda mc=macro: isl.automation_service.run_macro(mc)))

        for name, path in self.index.search(q):
            out.append((f"🚀 {name}", lambda p=path: open_target(p)))

        if re.match(r"^[\w-]+(\.[\w-]+)+(/\S*)?$", q):
            out.append((f"🌐 Open {q}", lambda: open_target("https://" + q)))
        out.append((f"🔎 Search the web for “{q}”",
                    lambda: open_target("https://www.google.com/search?q=" + urllib.parse.quote(q))))
        return out[:9]

    def _refresh(self):
        self.results.clear()
        for label, action in self.suggestions(self.input.text()):
            item = QListWidgetItem(label)
            item.setData(ACTION_ROLE, action)
            if action is None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.results.addItem(item)
        if self.results.count() and self.results.item(0).data(ACTION_ROLE):
            self.results.setCurrentRow(0)
        rows = max(1, self.results.count())
        self.results.setFixedHeight(min(9, rows) * 32 + 4)
        self.adjustSize()

    def _run_item(self, item):
        action = item.data(ACTION_ROLE)
        if action is None:
            return
        self.hide()
        try:
            action()
        except Exception as e:
            print(f"[command bar] {e}")
