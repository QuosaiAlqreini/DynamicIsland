"""Agents tab: Robo, live activity of Claude Code / Codex, Allow / Deny, and the AI chat
(ask anything, see the screen, explain / fix the clipboard, ask about a window)."""
import time

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QFrame, QLineEdit, QMenu
)

from modules.robo import RoboWidget, mood_for
from styles import badge_style, small_button_style, list_style, input_style, _rgba


class AgentsWidget(QWidget):
    CHAT_HINT = "Ask Robo anything… (Enter)"
    ask_about_window = pyqtSignal(QPointF)       # global position where Robo was dropped
    question_submitted = pyqtSignal(str)         # question about the captured window
    chat_submitted = pyqtSignal(str)             # a normal question for the AI
    see_screen = pyqtSignal()
    clipboard_action = pyqtSignal(str)           # "explain" | "fix"
    open_ai_settings = pyqtSignal()
    message = pyqtSignal(str)

    def __init__(self, theme, agent_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.agents = agent_service
        self._showing_request = None

        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 6)
        root.setSpacing(12)

        # Left: Robo + status
        left = QVBoxLayout()
        left.setSpacing(4)
        self.robo = RoboWidget(theme, 84)
        self.robo.dropped_on_screen.connect(self.ask_about_window)
        left.addWidget(self.robo, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.status = QLabel("Not connected yet")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setFixedWidth(120)
        left.addWidget(self.status)
        self.model = QLabel("")
        self.model.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.model.setFixedWidth(120)
        self.model.setToolTip("The AI Robo uses · click ⚙ to change")
        left.addWidget(self.model)
        self.btn_connect = QPushButton("🔗 Connect AI")
        self.btn_connect.clicked.connect(self._connect_menu)
        left.addWidget(self.btn_connect)
        left.addStretch()
        root.addLayout(left)

        # Right: permission card / ask box / feed
        right = QVBoxLayout()
        right.setSpacing(5)
        head = QHBoxLayout()
        self.badge = QLabel("👾 AI AGENTS")
        head.addWidget(self.badge)
        head.addStretch()
        self.project = QLabel("")
        head.addWidget(self.project)
        right.addLayout(head)

        self.card = QFrame()
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(4)
        self.card_title = QLabel("")
        self.card_detail = QLabel("")
        self.card_detail.setWordWrap(True)
        self.card_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(self.card_title)
        cl.addWidget(self.card_detail)
        btns = QHBoxLayout()
        self.btn_allow = QPushButton("✓ Allow")
        self.btn_deny = QPushButton("✕ Deny")
        self.btn_later = QPushButton("Decide in terminal")
        self.btn_later.setToolTip("Hide this card; Claude Code keeps waiting and asks in its own window")
        self.btn_allow.clicked.connect(lambda: self._decide(True))
        self.btn_deny.clicked.connect(lambda: self._decide(False))
        self.btn_later.clicked.connect(self._dismiss)
        btns.addWidget(self.btn_allow)
        btns.addWidget(self.btn_deny)
        btns.addStretch()
        btns.addWidget(self.btn_later)
        cl.addLayout(btns)
        right.addWidget(self.card)

        ask_row = QHBoxLayout()
        ask_row.setSpacing(4)
        self.ask = QLineEdit()
        self.ask.setPlaceholderText(self.CHAT_HINT)
        self.ask.returnPressed.connect(self._submit_question)
        ask_row.addWidget(self.ask, 1)
        self.tool_buttons = []
        for icon, tip, slot in (("👁", "Look at my screen and explain it", self.see_screen.emit),
                                ("📋", "Explain what I copied", lambda: self.clipboard_action.emit("explain")),
                                ("🛠", "Fix the code I copied", lambda: self.clipboard_action.emit("fix")),
                                ("⚙", "AI settings: Qwen 3.5 (free), cloud, keys", self.open_ai_settings.emit)):
            b = QPushButton(icon)
            b.setToolTip(tip)
            b.setFixedSize(26, 24)
            b.clicked.connect(slot)
            ask_row.addWidget(b)
            self.tool_buttons.append(b)
        right.addLayout(ask_row)
        self._window_question = False

        self.feed = QListWidget()
        self.feed.setWordWrap(True)
        self.feed.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.feed.setToolTip("Double-click a line to copy it")
        self.feed.itemDoubleClicked.connect(self._copy_item)
        self._answers = []                       # AI answers stay on top of the activity feed
        right.addWidget(self.feed, 1)
        root.addLayout(right, 1)

        self._dismissed = set()
        self.agents.changed.connect(self.refresh)
        self._apply_styles()
        self.refresh()

    # ------------------------------------------------------------ styling
    def _apply_styles(self):
        t = self.theme
        self.badge.setStyleSheet(badge_style(t))
        self.status.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px;")
        self.project.setStyleSheet(f"color: {t['text_secondary']}; font-size: 9px;")
        self.feed.setStyleSheet(list_style(t))
        self.model.setStyleSheet(f"color: {t['accent']}; font-size: 9px;")
        self.ask.setStyleSheet(f"QLineEdit {{ {input_style(t)} border-color: {t['accent']}; }}")
        css = small_button_style(t)
        for b in (self.btn_connect, self.btn_later, *self.tool_buttons):
            b.setStyleSheet(css)
        self.card.setStyleSheet(f"QFrame {{ background: {_rgba(t['warning'], 0.12)}; border: 1px solid {t['warning']};"
                                f" border-radius: 10px; }} QLabel {{ border: none; background: transparent; }}")
        self.card_title.setStyleSheet(f"color: {t['text_primary']}; font-size: 12px; font-weight: 700;")
        self.card_detail.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px; font-family: Consolas, monospace;")
        self.btn_allow.setStyleSheet(f"QPushButton {{ background: {t['success']}; color: {t['bg_color']}; border: none;"
                                     f" border-radius: 6px; padding: 5px 16px; font-weight: 700; font-size: 11px; }}")
        self.btn_deny.setStyleSheet(f"QPushButton {{ background: {t['danger']}; color: #ffffff; border: none;"
                                    f" border-radius: 6px; padding: 5px 16px; font-weight: 700; font-size: 11px; }}")

    def update_theme(self, theme):
        self.theme = self.robo.theme = theme
        self._apply_styles()
        self.refresh()

    # ------------------------------------------------------------ actions
    def _connect_menu(self):
        menu = QMenu(self)
        a = self.agents
        if a.claude_connected():
            menu.addAction("Disconnect Claude Code").triggered.connect(lambda: self._report(a.disconnect_claude()))
        else:
            menu.addAction("Connect Claude Code").triggered.connect(lambda: self._report(a.connect_claude()))
        if a.codex_connected():
            menu.addAction("Disconnect Codex").triggered.connect(lambda: self._report(a.disconnect_codex()))
        else:
            menu.addAction("Connect Codex (finish alerts)").triggered.connect(lambda: self._report(a.connect_codex()))
        menu.exec(self.btn_connect.mapToGlobal(self.btn_connect.rect().bottomLeft()))

    def _report(self, result):
        ok, text = result
        self.message.emit(("✅ " if ok else "⚠️ ") + text)
        self.feed.insertItem(0, ("✅ " if ok else "⚠️ ") + text)
        self.refresh_status()

    def _decide(self, allow):
        if self._showing_request:
            self.agents.decide(self._showing_request, allow)
            self.robo.flash_mood("happy" if allow else "wink", 1.5)

    def _dismiss(self):
        if self._showing_request:
            self._dismissed.add(self._showing_request)
            self.refresh()

    def start_question(self, title):
        """Called after Robo was dropped on a window and it was captured."""
        self._window_question = True
        self.ask.setPlaceholderText(f"Ask Robo about “{title[:40]}”… then press Enter")
        self.ask.setFocus()
        self.robo.flash_mood("curious", 4)

    def _submit_question(self):
        text = self.ask.text().strip()
        if self._window_question:
            text = text or "What is on this window? Explain it briefly and point out anything important."
        elif not text:
            return
        self.ask.clear()
        self._add_answer(f"🙋 {text}")
        if self._window_question:
            self._window_question = False
            self.ask.setPlaceholderText(self.CHAT_HINT)
            self.question_submitted.emit(text)
        else:
            self.chat_submitted.emit(text)
        self.status.setText("Thinking…")
        self.robo.flash_mood("curious", 3)

    def _add_answer(self, text):
        self._answers.insert(0, text)
        del self._answers[12:]
        self.refresh()

    def show_answer(self, title, content):
        head = "" if title in ("Robo", "") else f"{title}: "
        self._add_answer(f"👾 {head}{content.strip()[:4000]}")
        self.robo.flash_mood("wink" if title == "AI not ready" else "happy", 2.5)
        self.refresh_status()

    def set_ai_status(self, status, _color=""):
        if status in ("Thinking", "Coding", "Seeing Screen"):
            self.status.setText({"Thinking": "Thinking…", "Coding": "Fixing…",
                                 "Seeing Screen": "Looking…"}[status])
        else:
            self.refresh_status()

    def set_model(self, text):
        self.model.setText(text)

    def _copy_item(self, item):
        from PyQt6.QtWidgets import QApplication
        text = item.text()
        for prefix in ("👾 ", "🙋 "):
            if text.startswith(prefix):
                text = text[len(prefix):]
        QApplication.clipboard().setText(text)
        self.message.emit("📋 Copied")

    # ------------------------------------------------------------ refresh
    def refresh_status(self):
        a = self.agents
        status, activity = a.summary()
        self.robo.set_mood(mood_for(status))
        connected = [n for n, on in (("Claude Code", a.claude_connected()), ("Codex", a.codex_connected())) if on]
        if a.error:
            self.status.setText("⚠️ " + a.error)
        elif status == "idle":
            self.status.setText(("Watching " + " & ".join(connected)) if connected
                                else "Connect Claude Code or Codex to follow them here")
        else:
            self.status.setText({"working": "Working…", "waiting": "Needs you", "done": "Done"}[status])
        self.btn_connect.setText("🔗 Connections" if connected else "🔗 Connect AI")

    def refresh(self):
        self.refresh_status()
        a = self.agents
        pending = [p for p in a.pending if p["id"] not in self._dismissed]
        if pending:
            req = pending[0]
            self._showing_request = req["id"]
            more = f"  (+{len(pending) - 1} more)" if len(pending) > 1 else ""
            self.card_title.setText(f"{req['agent']} wants to: {req['icon']} {req['summary']}{more}")
            self.card_detail.setText(req["detail"])
            self.card.show()
        else:
            self._showing_request = None
            self.card.hide()
        sessions = sorted(a.sessions.values(), key=lambda s: -s["updated"])
        self.project.setText(" · ".join(f"{s['agent']}: {s['project']}" for s in sessions[:2] if s["project"]))

        self.feed.clear()
        for text in self._answers:
            self.feed.addItem(text)
        for s in sessions[:2]:
            if s["status"] == "done" and s["answer"]:
                self.feed.addItem(f"💬 {s['agent']} said: {s['answer'][:600]}")
        for entry in list(a.feed)[:40]:
            stamp = time.strftime("%H:%M", time.localtime(entry["t"]))
            self.feed.addItem(f"{stamp}  {entry['icon']} {entry['text']}")
        if self.feed.count() == 0:
            hint = QListWidgetItem("Ask Robo anything above (👁 looks at your screen, 📋/🛠 explain or fix "
                                   "what you copied). Click “Connect AI” to follow Claude Code here: every "
                                   "file it reads, every command, and Allow / Deny for its requests.")
            hint.setFlags(Qt.ItemFlag.NoItemFlags)
            self.feed.addItem(hint)
