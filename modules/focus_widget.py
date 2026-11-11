"""Focus tab: Pomodoro-style timer + live build/task tracker."""
import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QSpinBox
)

from config import ConfigManager
from services.focus_timer_service import format_seconds
from services.build_watch_service import BuildWatchService
from styles import badge_style, small_button_style, list_style, input_style


class FocusWidget(QWidget):
    def __init__(self, theme, timer_service, build_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.config = ConfigManager()
        self.timer_service = timer_service
        self.build_service = build_service
        self.recent_done = []  # (name, duration, finished_ts)
        self._build_ui()
        self._apply_styles()

        self.timer_service.tick.connect(self._on_tick)
        self.build_service.jobs_changed.connect(self._on_jobs)
        self.build_service.job_finished.connect(self._on_job_finished)
        self._on_tick(0, 0, False)
        self._on_jobs([])

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 6)
        root.setSpacing(12)

        # Timer column
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        thead = QHBoxLayout()
        self.timer_badge = QLabel("⏱️ FOCUS TIMER")
        thead.addWidget(self.timer_badge)
        thead.addStretch()
        tcol.addLayout(thead)

        self.time_label = QLabel("00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tcol.addWidget(self.time_label, 1)

        presets = QHBoxLayout()
        presets.setSpacing(4)
        self.preset_buttons = []
        for minutes in self.config.get("focus_presets_min", [5, 25, 50]):
            b = QPushButton(f"{minutes}m")
            b.clicked.connect(lambda _, m=minutes: self.timer_service.start(m, "Focus"))
            presets.addWidget(b)
            self.preset_buttons.append(b)
        self.custom_spin = QSpinBox()
        self.custom_spin.setRange(1, 600)
        self.custom_spin.setValue(15)
        self.custom_spin.setSuffix("m")
        self.custom_spin.setToolTip("Custom minutes — press ▶")
        presets.addWidget(self.custom_spin)
        self.btn_custom = QPushButton("▶")
        self.btn_custom.clicked.connect(lambda: self.timer_service.start(self.custom_spin.value(), "Timer"))
        presets.addWidget(self.btn_custom)
        tcol.addLayout(presets)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        self.btn_toggle = QPushButton("Pause")
        self.btn_toggle.clicked.connect(self.timer_service.toggle)
        self.btn_plus = QPushButton("+5m")
        self.btn_plus.clicked.connect(lambda: self.timer_service.add_minutes(5))
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.timer_service.stop)
        self.btn_pomo = QPushButton("🍅")
        self.btn_pomo.setToolTip("Pomodoro: 4 rounds of 25 min focus with 5 min breaks, then a 15 min break.\n"
                                 "Click again while it runs to skip to the next phase.")
        self.btn_pomo.clicked.connect(self._pomodoro)
        for b in (self.btn_pomo, self.btn_toggle, self.btn_plus, self.btn_stop):
            ctrl.addWidget(b)
        tcol.addLayout(ctrl)
        root.addLayout(tcol, 1)

        # Build tracker column
        bcol = QVBoxLayout()
        bcol.setSpacing(4)
        bhead = QHBoxLayout()
        self.build_badge = QLabel("🔨 BUILDS & TASKS")
        bhead.addWidget(self.build_badge)
        bhead.addStretch()
        bcol.addLayout(bhead)
        self.build_list = QListWidget()
        self.build_list.setWordWrap(True)
        self.build_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.build_list.setToolTip("Long-running builds, installs and test runs are detected automatically.\n"
                                   "Edit the patterns in ~/.dynamic_island/config.json (build_watch_patterns).")
        bcol.addWidget(self.build_list)
        root.addLayout(bcol, 1)

    def _apply_styles(self):
        self.timer_badge.setStyleSheet(badge_style(self.theme))
        self.build_badge.setStyleSheet(badge_style(self.theme))
        self.time_label.setStyleSheet(
            f"color: {self.theme['text_primary']}; font-size: 30px; font-weight: 700;")
        self.build_list.setStyleSheet(list_style(self.theme))
        self.custom_spin.setStyleSheet(f"QSpinBox {{ {input_style(self.theme)} padding: 2px 4px; font-size: 10px; }}")
        css = small_button_style(self.theme)
        for b in self.findChildren(QPushButton):
            b.setStyleSheet(css)

    def update_theme(self, theme):
        self.theme = theme
        self._apply_styles()

    def _pomodoro(self):
        if self.timer_service.plan:
            self.timer_service.skip()
        else:
            c = self.config
            self.timer_service.start_pomodoro(c.get("pomodoro_work_min", 25), c.get("pomodoro_break_min", 5),
                                              c.get("pomodoro_long_break_min", 15), c.get("pomodoro_rounds", 4))

    def _on_tick(self, remaining, total, running):
        self.time_label.setText(format_seconds(remaining))
        self.timer_badge.setText(f"⏱️ {self.timer_service.label.upper()}" if remaining > 0 else "⏱️ FOCUS TIMER")
        active = remaining > 0
        self.btn_toggle.setEnabled(active)
        self.btn_stop.setEnabled(active)
        self.btn_toggle.setText("Pause" if running else "Resume")

    def _on_job_finished(self, name, duration):
        self.recent_done.insert(0, (name, duration, time.time()))
        del self.recent_done[5:]
        self._on_jobs(self.build_service.visible_jobs())

    def _on_jobs(self, jobs):
        self.build_list.clear()
        now = time.time()
        for job in jobs:
            elapsed = format_seconds(now - job["started"])
            self.build_list.addItem(f"⏳ {BuildWatchService.display_name(job)}  ·  {elapsed}")
        for name, duration, _ in self.recent_done:
            self.build_list.addItem(f"✅ {name}  ·  {format_seconds(duration)}")
        if self.build_list.count() == 0:
            item = QListWidgetItem("No builds running. Start one (npm, cargo, pytest, docker…) and it appears here.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.build_list.addItem(item)
