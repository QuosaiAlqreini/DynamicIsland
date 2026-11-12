"""Home: a dashboard of tiles (your AI, music, focus, time, settings)."""
import datetime as dt

from PyQt6.QtCore import Qt, QTimer, QPointF, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QGridLayout, QLabel, QPushButton, QFrame

from modules.robo import RoboWidget, mood_for
from services.focus_timer_service import format_seconds


class HomeWidget(QWidget):
    open_tab = pyqtSignal(str)
    open_settings = pyqtSignal()
    robo_dropped = pyqtSignal(QPointF)

    def __init__(self, theme, island, parent=None):
        super().__init__(parent)
        self.theme, self.island = theme, island
        root = QHBoxLayout(self)
        root.setContentsMargins(12, 4, 12, 6)
        root.setSpacing(8)

        # Big card: your AI
        self.agent_card = QFrame()
        self.agent_card.setCursor(Qt.CursorShape.PointingHandCursor)
        self.agent_card.mousePressEvent = lambda e: self.open_tab.emit("agents")
        al = QHBoxLayout(self.agent_card)
        al.setContentsMargins(10, 8, 10, 8)
        al.setSpacing(10)
        self.robo = RoboWidget(theme, 60)
        self.robo.dropped_on_screen.connect(self.robo_dropped)
        al.addWidget(self.robo, alignment=Qt.AlignmentFlag.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.agent_title = QLabel("Your AI")
        self.agent_status = QLabel("")
        self.agent_detail = QLabel("")
        self.agent_detail.setWordWrap(True)
        self.agent_detail.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.agent_title)
        col.addWidget(self.agent_status)
        col.addWidget(self.agent_detail, 1)
        al.addLayout(col, 1)
        root.addWidget(self.agent_card, 5)

        # Tiles
        grid = QGridLayout()
        grid.setSpacing(8)
        self.tiles = {}
        for i, (key, icon) in enumerate((("media", "🎵"), ("focus", "⏱️"), ("day", "🕒"), ("settings", "⚙️"))):
            b = QPushButton()
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(52)
            b.clicked.connect(lambda _, k=key: self.open_settings.emit() if k == "settings" else self.open_tab.emit(k))
            b.setProperty("icon_text", icon)
            grid.addWidget(b, i // 2, i % 2)
            self.tiles[key] = b
        root.addLayout(grid, 6)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        island.agent_service.changed.connect(self.refresh)
        self._apply_styles()
        self.refresh()

    def _apply_styles(self):
        t = self.theme
        self.agent_card.setStyleSheet(f"QFrame {{ background: {t['card_bg']}; border: 1px solid {t['border_color']};"
                                      f" border-radius: 14px; }} QLabel {{ border: none; background: transparent; }}")
        self.agent_title.setStyleSheet(f"color: {t['text_primary']}; font-size: 12px; font-weight: 700;")
        self.agent_status.setStyleSheet(f"color: {t['accent']}; font-size: 11px; font-weight: 600;")
        self.agent_detail.setStyleSheet(f"color: {t['text_secondary']}; font-size: 10px;")
        for b in self.tiles.values():
            b.setStyleSheet(f"""QPushButton {{ background: {t['card_bg']}; color: {t['text_primary']};
                border: 1px solid {t['border_color']}; border-radius: 12px; text-align: left;
                padding: 6px 10px; font-size: 11px; font-weight: 600; }}
                QPushButton:hover {{ border-color: {t['accent']}; }}""")

    def update_theme(self, theme):
        self.theme = self.robo.theme = theme
        self._apply_styles()

    def refresh(self):
        if not self.isVisible():
            return
        isl = self.island
        agents = isl.agent_service
        status, activity = agents.summary()
        self.robo.set_mood(mood_for(status))
        sessions = sorted(agents.sessions.values(), key=lambda s: -s["updated"])
        if sessions:
            s = sessions[0]
            self.agent_title.setText(f"{s['project'] or 'Session'}  ·  {s['agent']}")
            self.agent_status.setText({"working": "● Working", "waiting": "● Needs you",
                                       "done": "✓ Done", "idle": "Idle"}[s["status"]])
            self.agent_detail.setText((s["answer"] if s["status"] == "done" and s["answer"] else s["activity"])[:150])
        else:
            connected = agents.claude_connected() or agents.codex_connected()
            self.agent_title.setText("Your AI")
            self.agent_status.setText("Waiting for Claude Code…" if connected else "Not connected")
            self.agent_detail.setText("Start Claude Code and its work shows up here." if connected
                                      else "Click here to connect Claude Code or Codex.")
        media = isl.media_service.current_media
        playing = media.get("has_media")
        self.tiles["media"].setText(f"🎵  {media.get('title', '')[:18]}\n      {media.get('artist', '')[:20]}"
                                    if playing else "🎵  Music\n      Not playing")
        t = isl.timer_service
        self.tiles["focus"].setText(f"⏱️  {format_seconds(t.remaining_sec)}\n      {t.label}" if t.active
                                    else "⏱️  Focus\n      Start a timer")
        now = dt.datetime.now()
        nxt = isl.day_service.next_prayer_text() if isl.day_service.prayer_enabled else f"{now:%a} {now.day} {now:%b}"
        self.tiles["day"].setText(f"🕒  {now:%H:%M}\n      {nxt}")
        self.tiles["settings"].setText("⚙️  Settings\n      Look & keys")
