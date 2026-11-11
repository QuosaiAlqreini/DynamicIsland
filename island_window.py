import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, QPoint, QEvent, pyqtSignal,
    QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QCursor, QKeySequence, QShortcut
)
from PyQt6.QtWidgets import QApplication, QLineEdit, QPlainTextEdit, QTextEdit

from config import ConfigManager
from styles import get_theme, THEMES
from modules.pill_idle import IdlePillWidget
from modules.media_widget import MediaWidget
from modules.system_widget import SystemWidget
from modules.ai_agent_widget import AIAgentWidget
from modules.quick_tools_widget import QuickToolsWidget
from modules.settings_dialog import SettingsDialog
from modules.shelf_widget import ShelfWidget
from modules.notes_widget import NotesWidget
from modules.focus_widget import FocusWidget
from services.clipboard_service import ClipboardService
from services.focus_timer_service import FocusTimerService, format_seconds
from services.build_watch_service import BuildWatchService
from services.automation_service import AutomationService
from modules.keys_widget import KeysWidget
from modules.automation_dialog import AutomationDialog
from modules.info_widget import InfoWidget
from modules.customize_dialog import CustomizeDialog
from modules.tab_registry import TAB_REGISTRY, DEFAULT_TABS
from services.info_service import InfoService
from services.tasks_service import TasksService
from services.day_service import DayService
from services.lyrics_service import LyricsService
from services.volume_service import VolumeService
from modules.tasks_widget import TasksWidget
from modules.day_widget import DayWidget
from modules.command_bar import CommandBar
from PyQt6.QtWidgets import QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QComboBox
from services import win_input
import time

# Tab indices (kept stable so existing shortcuts keep working)
TAB_MEDIA, TAB_SYSTEM, TAB_AI, TAB_TOOLS, TAB_SHELF, TAB_NOTES, TAB_FOCUS, TAB_KEYS, TAB_INFO, TAB_TASKS, TAB_DAY = range(11)
TAB_KEY_TO_INDEX = {"media": TAB_MEDIA, "system": TAB_SYSTEM, "ai": TAB_AI, "tools": TAB_TOOLS,
                    "shelf": TAB_SHELF, "notes": TAB_NOTES, "focus": TAB_FOCUS, "keys": TAB_KEYS,
                    "info": TAB_INFO, "tasks": TAB_TASKS, "day": TAB_DAY}
TAB_NAMES = dict(TAB_KEY_TO_INDEX, sys=TAB_SYSTEM, clipboard=TAB_SHELF,
                 timer=TAB_FOCUS, automations=TAB_KEYS, todo=TAB_TASKS, water=TAB_DAY,
                 prayer=TAB_DAY)
NOTCH_SHOULDER = 14       # width of the curved "ears" joining the notch to the screen edge


def notch_path(w, h, expanded=False):
    """Smooth notch silhouette: flat top on the screen edge, soft S-curved
    shoulders flowing into the bezel, and round bottom corners."""
    from PyQt6.QtCore import QRectF
    from PyQt6.QtGui import QPainterPath
    e = NOTCH_SHOULDER
    r = min(24 if expanded else 16, (h - e) / 2, (w - 2 * e) / 2)
    k = 0.55                                           # bezier "roundness"
    p = QPainterPath()
    p.moveTo(0, 0)
    p.lineTo(w, 0)
    p.cubicTo(w - e * k, 0, w - e, e * (1 - k), w - e, e)            # right shoulder
    p.lineTo(w - e, h - r)
    p.arcTo(QRectF(w - e - 2 * r, h - 2 * r, 2 * r, 2 * r), 0, -90)   # bottom-right
    p.lineTo(e + r, h)
    p.arcTo(QRectF(e, h - 2 * r, 2 * r, 2 * r), 270, -90)             # bottom-left
    p.lineTo(e, e)
    p.cubicTo(e, e * (1 - k), e * k, 0, 0, 0)                         # left shoulder
    p.closeSubpath()
    return p


# Extra room per size choice: (pill width, pill height, panel width, panel height)
SIZE_PROFILES = {"compact": (0, 0, 0, 0), "comfortable": (30, 4, 24, 14), "roomy": (70, 8, 60, 30)}
NOTCH_EXTRA = (50, 0, 2 * 14 + 8, 10)   # the notch needs width for its curved shoulders
# The folded notch is slim, like a real one: total height per size choice
NOTCH_HEIGHTS = {"compact": 24, "comfortable": 28, "roomy": 32}

MAX_LABELED_TABS = 8          # more visible tabs than this -> icon-only nav buttons
AUTOHIDE_DELAY_S = 0.7        # cursor away this long -> tuck the island back up
CLICK_MOVE_THRESHOLD = 4

class DynamicIslandWindow(QWidget):
    # title, message -> shown as a Windows toast by the tray icon
    notify = pyqtSignal(str, str)

    def __init__(self, media_service, sys_service, ai_service, taskbar_service,
                 clipboard_service=None, timer_service=None, build_service=None,
                 automation_service=None, info_service=None):
        super().__init__()
        self.config = ConfigManager()
        self.theme_name = self.config.get("theme", "obsidian")
        self.theme = get_theme(self.theme_name)

        self.media_service = media_service
        self.sys_service = sys_service
        self.ai_service = ai_service
        self.taskbar_service = taskbar_service
        self.clipboard_service = clipboard_service or ClipboardService(self)
        self.timer_service = timer_service or FocusTimerService(self)
        self.build_service = build_service or BuildWatchService(parent=self)
        self.automation_service = automation_service or AutomationService(
            None, clipboard_service=self.clipboard_service, parent=self)
        self.automation_service.island_actions.update(self.island_actions())
        self.info_service = info_service or InfoService(self)
        self.tasks_service = TasksService(self)
        self.day_service = DayService(self)
        self.lyrics_service = LyricsService(self)
        self.volume_service = VolumeService(self)
        self.info_service.tasks = self.tasks_service
        self.info_service.day = self.day_service
        self.info_service.lyrics = self.lyrics_service
        self.command_bar = None

        # State tracking
        self.is_expanded = False
        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self.press_global_pos = QPoint()
        self.drag_out_active = False   # a file is being dragged out of the shelf
        self.drop_hovering = False     # something is being dragged over the island
        # Visibility state
        self.tucked = False            # auto-hide mode: slid up out of view
        self.fullscreen_hidden = False # hidden because a full-screen app is in front
        self.user_hidden = False       # hidden from the tray menu
        self.summoned = False          # opened via hotkey/tray: ignore fullscreen until closed
        self._away_since = None
        # Click-through ("through mode") state
        self._passthrough = False      # window currently ignores the mouse
        self._zone_inside = False
        self._dwell_since = None
        self._dwell_blocked = False    # a click happened under the pill: don't pop open
        self._drag_in_since = None     # something is being dragged onto the pill
        self._drop_override = False

        # Dimensions
        self.top_offset = self.config.get("anchor_top_offset", 8)
        self.notch_mode = self.config.get("notch_mode", False)
        self._apply_size_profile()
        self.compact_w = self.base_compact_w

        # Window Flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

        # Timers for hover smoothing
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.expand)

        self.leave_timer = QTimer(self)
        self.leave_timer.setSingleShot(True)
        self.leave_timer.timeout.connect(self._auto_collapse)

        # Build UI and position
        self._build_ui()
        self._setup_connections()
        self._setup_shortcuts()
        self._reposition_compact()
        self._setup_visibility()
        if self.config.get("remember_last_tab", True):
            last = self.config.get("last_tab", 0)
            if isinstance(last, int) and 0 <= last < self.stack.count():
                self._switch_tab(last, save=False)

        # Apply saved taskbar setting if configured
        if self.config.get("taskbar_autohide_macbook", False):
            self.taskbar_service.set_autohide(True)

    def _build_ui(self):
        # No top-level layout: the pill and the expanded panel are positioned
        # manually (see resizeEvent) so the grow/shrink animation never forces
        # the heavy expanded panel to re-layout on every frame.

        # 1. Idle Pill Widget (Visible when collapsed)
        self.idle_pill = IdlePillWidget(self.theme, self, info_service=self.info_service)
        self.idle_pill.set_slots(self.config.get("pill_left", "ai_dot"),
                                 self.config.get("pill_center", "clock"),
                                 self.config.get("pill_right", "battery_icon"))

        # 2. Expanded Container (Visible when expanded)
        self.expanded_container = QWidget(self)
        self.exp_layout = QVBoxLayout(self.expanded_container)
        self.exp_layout.setContentsMargins(0, 0, 0, 0)
        self.exp_layout.setSpacing(4)

        # Stack of Modules
        self.stack = QStackedWidget(self.expanded_container)
        self.media_widget = MediaWidget(self.theme, self)
        self.sys_widget = SystemWidget(self.theme, self)
        self.ai_widget = AIAgentWidget(self.theme, self)
        self.tools_widget = QuickToolsWidget(self.theme, self)
        self.shelf_widget = ShelfWidget(self.theme, self.clipboard_service, self)
        self.notes_widget = NotesWidget(self.theme, self.clipboard_service, self)
        self.focus_widget = FocusWidget(self.theme, self.timer_service, self.build_service, self)
        self.keys_widget = KeysWidget(self.theme, self.automation_service, self)
        self.info_widget = InfoWidget(self.theme, self.info_service, self)
        self.tasks_widget = TasksWidget(self.theme, self.tasks_service, self)
        self.day_widget = DayWidget(self.theme, self.day_service, self)

        self.stack.addWidget(self.media_widget) # Index 0
        self.stack.addWidget(self.sys_widget)   # Index 1
        self.stack.addWidget(self.ai_widget)    # Index 2
        self.stack.addWidget(self.tools_widget) # Index 3
        self.stack.addWidget(self.shelf_widget) # Index 4
        self.stack.addWidget(self.notes_widget) # Index 5
        self.stack.addWidget(self.focus_widget) # Index 6
        self.stack.addWidget(self.keys_widget)  # Index 7
        self.stack.addWidget(self.info_widget)  # Index 8
        self.stack.addWidget(self.tasks_widget) # Index 9
        self.stack.addWidget(self.day_widget)   # Index 10

        self.exp_layout.addWidget(self.stack)

        # Navigation Bar (which tabs, and their order, come from Customize Island)
        self.nav_row = QHBoxLayout()
        self.nav_row.setContentsMargins(10, 0, 10, 6)
        self.nav_row.setSpacing(5)
        self.nav_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.nav_buttons = {}
        self.nav_order = []
        self._rebuild_nav()
        self.exp_layout.addLayout(self.nav_row)

        self.expanded_container.setGeometry(4, 4, self.expanded_w - 8, self.expanded_h - 8)
        self.expanded_container.hide()

    def _style_nav(self):
        css = f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 11px;
                padding: {'3px 10px' if getattr(self, '_nav_icon_only', False) else '3px 6px'};
                font-size: {'14px' if getattr(self, '_nav_icon_only', False) else '10px'};
                font-weight: 600;
            }}
            QPushButton:hover {{
                color: {self.theme['text_primary']};
                border-color: {self.theme['accent']};
            }}
            QPushButton:checked {{
                background: {self.theme['accent']};
                color: {self.theme['bg_color']};
                border-color: {self.theme['accent']};
            }}
        """
        for btn in self.nav_buttons.values():
            btn.setStyleSheet(css)

    def _rebuild_nav(self):
        while self.nav_row.count():
            item = self.nav_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        keys = [k for k in self.config.get("tabs_visible", DEFAULT_TABS) if k in TAB_REGISTRY]
        keys = keys or list(DEFAULT_TABS)
        icon_only = self._nav_icon_only = len(keys) > MAX_LABELED_TABS
        self.nav_buttons = {}
        self.nav_order = []
        for pos, key in enumerate(keys, start=1):
            icon, label, tip = TAB_REGISTRY[key]
            index = TAB_KEY_TO_INDEX[key]
            btn = QPushButton(icon if icon_only else f"{icon} {label}")
            btn.setProperty("nav_icon", icon)
            btn.setProperty("nav_label", label)
            btn.setCheckable(True)
            btn.setToolTip(f"{label}: {tip}" + (f"  (Ctrl+{pos})" if pos <= 9 else ""))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=index: self._switch_tab(i))
            self.nav_row.addWidget(btn)
            self.nav_buttons[index] = btn
            self.nav_order.append(index)
        self._style_nav()
        current = self.stack.currentIndex()
        if current not in self.nav_order:
            self._switch_tab(self.nav_order[0], save=False)
        else:
            self._switch_tab(current, save=False)

    def _switch_tab(self, index, save=True):
        self.stack.setCurrentIndex(index)
        for i, btn in self.nav_buttons.items():
            btn.setChecked(i == index)
            if getattr(self, "_nav_icon_only", False):
                # Icons only (many tabs): the open tab also shows its name
                icon, label = btn.property("nav_icon"), btn.property("nav_label")
                btn.setText(f"{icon} {label}" if i == index else icon)
        if save and self.config.get("remember_last_tab", True):
            self.config.set("last_tab", index)

    def island_actions(self):
        """Callbacks the automation engine can trigger."""
        return {
            "island_toggle": self.summon,
            "quick_note": self.quick_note,
            "see_screen": lambda: (self.open_tab(TAB_AI), self.ai_service.analyze_screen()),
            "open_tab": lambda name: self.open_tab(TAB_NAMES.get(name.strip().lower(), TAB_MEDIA)),
            "focus": lambda minutes: self.timer_service.start(minutes, "Focus"),
            "collapse": self.collapse,
            "through_toggle": self.toggle_through_mode,
            "island_visibility": self.toggle_visibility,
            "style_toggle": lambda: self.set_style(not self.notch_mode),
            "command_bar": self.toggle_command_bar,
            "add_task": lambda phrase="": (self.tasks_service.add(phrase) if phrase.strip()
                                           else self.open_tab_by_key("tasks")),
            "water": lambda: self.day_service.add_water(),
            "pomodoro": lambda: self.timer_service.start_pomodoro(),
        }

    def open_customize(self):
        dlg = CustomizeDialog(self.theme, self.info_service, self)
        self.summoned = True  # keep visible while the dialog is open
        if dlg.exec():
            self.apply_customization()
        self.summoned = False

    def apply_customization(self):
        """Re-read layout / visibility settings and apply them live."""
        self.idle_pill.set_slots(self.config.get("pill_left", "ai_dot"),
                                 self.config.get("pill_center", "clock"),
                                 self.config.get("pill_right", "battery_icon"))
        self.notch_mode = self.config.get("notch_mode", False)
        self._apply_size_profile()
        self.compact_w = self.base_compact_w + self._activity_extra()
        self._rebuild_nav()
        theme = self.config.get("theme", self.theme_name)
        if theme != self.theme_name:
            self.set_theme(theme)
        self._apply_visibility_mode()
        if self.is_expanded:
            self._animate_to(QRect(self._centered_x(self.expanded_w), self._rest_y(),
                                   self.expanded_w, self.expanded_h))
        elif not self.tucked and not self.user_hidden:
            self._animate_to(QRect(self._centered_x(self.compact_w), self._rest_y(),
                                   self.compact_w, self.compact_h))
        self.resizeEvent(None)
        self.update_reserved_space()
        self.update()

    def rebind_core_hotkeys(self):
        """(Re)register the open-island and command-bar hotkeys from the config.

        Returns a list of shortcuts that another program already owns."""
        hk = getattr(self, "hotkey_service", None)
        if hk is None or not hk.available:
            return []
        bound = self.__dict__.setdefault("_bound_hotkeys", {})
        problems = []
        for hid, key, default, label in ((1, "global_hotkey", "Ctrl+Alt+Space", "Open island"),
                                         (2, "command_bar_hotkey", "Alt+Space", "Command bar")):
            text = self.config.get(key, default)
            if bound.get(hid) == text:
                continue
            hk.unregister(hid)
            if text and hk.register(hid, text):
                bound[hid] = text
            else:
                bound[hid] = None
                if text:
                    problems.append(f"{label}: {text}")
        return problems

    def open_automations(self):
        dlg = AutomationDialog(self.theme, self.automation_service, self)
        dlg.exec()

    def open_tab(self, index):
        """Show the island expanded on a given tab (used by menus, tray, hotkey)."""
        self.summoned = True
        self.user_hidden = False
        self.tucked = False
        self.show()
        self.expand()
        self._switch_tab(index)

    def summon(self):
        """Global-hotkey entry point: toggle the island open and focus it."""
        if self.is_expanded and self.isActiveWindow():
            self.collapse()
            return
        self.summoned = True
        self.user_hidden = False
        self.fullscreen_hidden = False
        self.tucked = False
        self.show()
        self.expand()
        self.raise_()
        self.activateWindow()
        if self.stack.currentIndex() == TAB_NOTES:
            self.notes_widget.focus_editor()

    def quick_note(self):
        """Open the Notes tab with the cursor ready to type."""
        self.open_tab(TAB_NOTES)
        self.raise_()
        self.activateWindow()
        self.notes_widget.focus_editor()

    def _setup_shortcuts(self):
        ctx = Qt.ShortcutContext.WindowShortcut
        for pos in range(1, 10):
            sc = QShortcut(QKeySequence(f"Ctrl+{pos}"), self, context=ctx)
            sc.activated.connect(lambda p=pos: self._shortcut_tab(p))
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self, context=ctx)
        esc.activated.connect(self.collapse)
        for keys, step in (("Ctrl+Tab", 1), ("Ctrl+Shift+Tab", -1)):
            sc = QShortcut(QKeySequence(keys), self, context=ctx)
            sc.activated.connect(lambda s=step: self._cycle_tab(s))

    def _shortcut_tab(self, pos):
        if pos <= len(self.nav_order):
            self.expand()
            self._switch_tab(self.nav_order[pos - 1])

    def _cycle_tab(self, step):
        cur = self.stack.currentIndex()
        pos = self.nav_order.index(cur) if cur in self.nav_order else 0
        self._switch_tab(self.nav_order[(pos + step) % len(self.nav_order)])

    def _setup_connections(self):
        # Media updates
        self.media_service.media_updated.connect(self.idle_pill.update_media)
        self.media_service.media_updated.connect(self.media_widget.update_media)
        self.media_widget.play_pause_clicked.connect(self.media_service.toggle_play_pause)
        self.media_widget.next_clicked.connect(self.media_service.next_track)
        self.media_widget.prev_clicked.connect(self.media_service.previous_track)

        # System updates
        self.sys_service.stats_updated.connect(self.idle_pill.update_system)
        self.sys_service.stats_updated.connect(self.sys_widget.update_system)

        # AI updates & Vision
        self.ai_service.status_changed.connect(self.idle_pill.update_agent_status)
        self.ai_service.status_changed.connect(self.ai_widget.update_agent_status)
        self.ai_service.response_ready.connect(self.ai_widget.set_output)
        self.ai_widget.ask_prompt_submitted.connect(self._on_prompt_submitted)
        self.ai_widget.see_screen_requested.connect(self.ai_service.analyze_screen)
        self.ai_widget.open_settings_requested.connect(self.open_settings_dialog)
        self.ai_widget.clipboard_action_requested.connect(self.ai_service.process_clipboard)
        self.ai_widget.coderabbit_requested.connect(self.ai_service.run_coderabbit_review)
        self.ai_widget.ralph_requested.connect(self.ai_service.run_ralph_loop)

        self.idle_pill.activity_changed.connect(self._on_pill_activity)

        # Shelf: keep the island open while dragging files out of it
        self.shelf_widget.count_changed.connect(self.idle_pill.set_shelf_count)
        self.idle_pill.set_shelf_count(len(self.shelf_widget.paths))
        self.shelf_widget.drag_out_started.connect(self._on_drag_out_started)
        self.shelf_widget.drag_out_finished.connect(self._on_drag_out_finished)

        # Live activities in the compact pill
        self.timer_service.tick.connect(self._on_timer_tick)
        self.timer_service.finished.connect(self._on_timer_finished)
        self.build_service.jobs_changed.connect(self._on_build_jobs)
        self.build_service.job_finished.connect(self._on_build_finished)
        self.tools_widget.open_tab_requested.connect(self._switch_tab)

        # Lyrics + real volume
        self.media_service.media_updated.connect(self.lyrics_service.update_media)
        self.lyrics_service.line_changed.connect(self.media_widget.set_lyric)
        self.lyrics_service.line_changed.connect(lambda _l: self.idle_pill.update())
        self.volume_service.volume_changed.connect(self.media_widget.set_volume)
        self.volume_service.volume_changed.connect(self.tools_widget.set_volume)
        self.media_widget.volume_requested.connect(self.volume_service.set_percent)
        self.media_widget.mute_clicked.connect(self.volume_service.toggle_mute)
        self.tools_widget.volume_changed.connect(self.volume_service.set_percent)
        self.volume_service.refresh()

        # Tasks, water, prayer
        self.tasks_service.reminder.connect(self._on_task_reminder)
        self.tasks_service.changed.connect(self._sync_task_alert)
        self.day_service.water_reminder.connect(self._on_water_reminder)
        self.day_service.prayer_time.connect(self._on_prayer_time)
        self.day_service.changed.connect(self.idle_pill.update)

        # Custom info
        self.sys_service.stats_updated.connect(self.info_service.update_system)
        self.media_service.media_updated.connect(self.info_service.update_media)
        self.info_widget.customize_requested.connect(self.open_customize)

        # Automations
        self.keys_widget.edit_requested.connect(self.open_automations)
        self.automation_service.feedback.connect(
            lambda msg: self.idle_pill.flash(msg, self.theme["accent"], 2000))
        self.automation_service.keep_awake_changed.connect(
            lambda on: self.idle_pill.set_activity("awake", "☕ Awake", None, self.theme["warning"], priority=1)
            if on else self.idle_pill.clear_activity("awake"))

    # ------------------------------------------------------ Live activities
    def _on_pill_activity(self, active):
        """Grow the pill while a live activity (timer, build, toast) is shown."""
        self.compact_w = self.base_compact_w + (90 if active else 0)
        if getattr(self, "glide", None) is not None and self.glide.state() == self.glide.State.Running:
            return   # a show/hide glide is in progress; it ends at the right size
        if not self.is_expanded and not self.is_dragging and not self.tucked:
            # Use the resting position, not the current one: another animation (e.g. switching
            # to the notch) may still be moving the window and must not be cancelled midway.
            self._animate_to(QRect(self._centered_x(self.compact_w), self._rest_y(),
                                   self.compact_w, self.compact_h))

    def _on_timer_tick(self, remaining, total, running):
        if remaining <= 0:
            self.idle_pill.clear_activity("timer")
            return
        icon = "⏱" if running else "⏸"
        progress = 1.0 - (remaining / total) if total else None
        self.idle_pill.set_activity("timer", f"{icon} {self.timer_service.label} {format_seconds(remaining)}",
                                    progress, self.theme["accent_secondary"], priority=20)

    def _on_timer_finished(self, label):
        self.idle_pill.flash(f"🔔 {label} done!", self.theme["success"], 10000)
        self.notify.emit("⏱️ Timer finished", f"Your {label.lower()} session is over.")
        if self.config.get("sound_effects", True):
            QApplication.beep()

    def _on_build_jobs(self, jobs):
        if not jobs:
            self.idle_pill.clear_activity("build")
            return
        import time as _time
        first = jobs[0]
        elapsed = format_seconds(_time.time() - first["started"])
        extra = f" +{len(jobs) - 1}" if len(jobs) > 1 else ""
        self.idle_pill.set_activity("build", f"🔨 {first['name']}{extra} {elapsed}",
                                    None, self.theme["warning"], priority=10)

    def _on_build_finished(self, name, duration):
        self.idle_pill.flash(f"✅ {name} · {format_seconds(duration)}", self.theme["success"], 8000)
        self.notify.emit("🔨 Task finished", f"{name} finished after {format_seconds(duration)}.")

    # ---------------------------------------------- Tasks / water / prayer
    def _on_task_reminder(self, task):
        self._sync_task_alert()
        self.idle_pill.flash(f"⏰ {task['title']}", self.theme["warning"], 12000)
        self.notify.emit("⏰ Reminder", task["title"])
        if self.config.get("sound_effects", True):
            QApplication.beep()

    def _sync_task_alert(self):
        ringing = self.tasks_service.ringing()
        if ringing:
            extra = f" +{len(ringing) - 1}" if len(ringing) > 1 else ""
            self.idle_pill.set_activity("task", f"⏰ {ringing[0]['title']}{extra}", None,
                                        self.theme["warning"], priority=30)
        else:
            self.idle_pill.clear_activity("task")
        self.idle_pill.update()

    def _on_water_reminder(self):
        self.idle_pill.flash("💧 Time for some water", self.theme["accent"], 8000)
        self.notify.emit("💧 Drink water", f"{self.day_service.water_ml} of {self.day_service.water_goal} ml today.")

    def _on_prayer_time(self, name):
        self.idle_pill.flash(f"🕌 Time for {name}", self.theme["success"], 20000)
        self.notify.emit("🕌 Prayer time", f"It is time for {name}.")
        if self.config.get("prayer_pause_media", False) and self.media_service.current_media.get("is_playing"):
            self.media_service.toggle_play_pause()

    def open_tab_by_key(self, key):
        self.open_tab(TAB_KEY_TO_INDEX.get(key, TAB_MEDIA))
        if key == "tasks":
            self.raise_()
            self.activateWindow()
            self.tasks_widget.focus_input()

    def toggle_command_bar(self):
        if self.command_bar is None:
            self.command_bar = CommandBar(self.theme, self)
        self.command_bar.update_theme(self.theme)
        self.command_bar.toggle()

    # ----------------------------------------- Wheel / arrow page switching
    def wheelEvent(self, event):
        if not self.is_expanded or event.angleDelta().y() == 0:
            return super().wheelEvent(event)
        w = QApplication.widgetAt(QCursor.pos())
        while w is not None and w is not self:
            if isinstance(w, (QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QComboBox)):
                return  # let lists, sliders and editors keep the wheel
            w = w.parentWidget()
        self._cycle_tab(-1 if event.angleDelta().y() > 0 else 1)
        event.accept()

    def keyPressEvent(self, event):
        if self.is_expanded and event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._cycle_tab(-1 if event.key() == Qt.Key.Key_Left else 1)
            event.accept()
            return
        super().keyPressEvent(event)

    # -------------------------------------------------------- Drag & drop
    def _on_drag_out_started(self):
        self.drag_out_active = True
        self.leave_timer.stop()

    def _on_drag_out_finished(self):
        self.drag_out_active = False
        if not self.geometry().contains(QCursor.pos()):
            self.leave_timer.start(self.config.get("collapse_delay_ms", 300))

    def dragEnterEvent(self, event):
        mime = event.mimeData()
        if self.drag_out_active:
            event.ignore()
            return
        if mime.hasUrls() or mime.hasText():
            self.drop_hovering = True
            self.leave_timer.stop()
            self.expand()
            self._switch_tab(TAB_SHELF if mime.hasUrls() else TAB_NOTES, save=False)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self.drop_hovering:
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_hovering = False
        self.leave_timer.start(max(600, self.config.get("collapse_delay_ms", 300)))

    def dropEvent(self, event):
        self.drop_hovering = False
        mime = event.mimeData()
        local = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime.hasUrls() else []
        if local:
            added = self.shelf_widget.add_paths(local)
            self.idle_pill.flash(f"📥 {added} added to shelf" if added else "📥 Already on shelf",
                                 self.theme["accent"], 2500)
            self._switch_tab(TAB_SHELF)
        elif mime.hasText():
            self.notes_widget.append_text(mime.text())
            self._switch_tab(TAB_NOTES)
        event.acceptProposedAction()

    def _on_prompt_submitted(self, prompt):
        auto_vision = self.config.get("ai_auto_capture_screen", False)
        self.ai_service.ask_ai(prompt, include_screen=auto_vision)

    def open_settings_dialog(self):
        dlg = SettingsDialog(self.theme, self.ai_service, self.taskbar_service, self)
        if dlg.exec():
            # Refresh theme and configuration
            new_theme = self.config.get("theme", "obsidian")
            self.set_theme(new_theme)
            self.notch_mode = self.config.get("notch_mode", False)
            provider = self.config.get("ai_provider", "gemini").upper()
            self.ai_widget.update_model_label(f"AI: {provider}")
            if not self.is_expanded:
                self._reposition_compact()

    def _get_screen_geometry(self):
        screen = self.screen() or self.windowHandle().screen() if self.windowHandle() else None
        if not screen:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
        return screen.geometry()

    def _apply_size_profile(self):
        """Window sizes from the configured size + style (the notch gets extra room)."""
        dw, dh, dew, deh = SIZE_PROFILES.get(self.config.get("island_size", "comfortable"),
                                             SIZE_PROFILES["comfortable"])
        if self.notch_mode:
            nw, nh, new, neh = NOTCH_EXTRA
            dw, dh, dew, deh = dw + nw, dh + nh, dew + new, deh + neh
        self.base_compact_w = int(self.config.get("compact_width", 200)) + dw
        self.compact_h = int(self.config.get("compact_height", 36)) + dh
        if self.notch_mode:
            self.compact_h = NOTCH_HEIGHTS.get(self.config.get("island_size", "comfortable"), 28)
        self.expanded_w = int(self.config.get("expanded_width", 490)) + dew
        # Shelf / Focus tabs need a little more room for their lists
        self.expanded_h = max(int(self.config.get("expanded_height", 200)), 240) + deh

    # --------------------------------------------- keep apps below the notch
    def _wants_reserved_space(self):
        return (bool(self.config.get("reserve_top_space", True)) and win_input.IS_WINDOWS
                and not self.user_hidden and not self.fullscreen_hidden and not self.tucked
                and not self._autohide_enabled() and self.isVisible())

    def update_reserved_space(self):
        """Reserve a strip at the top so maximized windows start below the notch/island."""
        if not hasattr(self, "reservation"):
            from services.appbar import TopReservation
            self.reservation = TopReservation()
            # A hidden helper window owns the reservation, so the island itself can move freely
            self._appbar_owner = QWidget(None, Qt.WindowType.Tool)
            self._appbar_owner.winId()
        if not self._wants_reserved_space() or not self.windowHandle():
            self.reservation.release()
            return
        logical = self.compact_h if self.notch_mode else self.top_offset + self.compact_h + 4
        ratio = self.windowHandle().devicePixelRatio() or 1.0
        self.reservation.reserve(int(self._appbar_owner.winId()), int(self.winId()), round(logical * ratio))

    def release_reserved_space(self):
        if hasattr(self, "reservation"):
            self.reservation.release()

    def _activity_extra(self):
        return 90 if self.idle_pill.current_activity() else 0

    def _rest_y(self):
        geom = self._get_screen_geometry()
        return geom.y() if self.notch_mode else geom.y() + self.top_offset

    def _hidden_y(self, height):
        return self._get_screen_geometry().y() - height - 4

    def _centered_x(self, width):
        """X for a window of `width`, honoring the user's shift along the top edge."""
        geom = self._get_screen_geometry()
        x = int(geom.x() + (geom.width() - width) / 2 + int(self.config.get("island_offset_x", 0)))
        return max(geom.x() + 4, min(x, geom.x() + geom.width() - width - 4))

    def _reposition_compact(self):
        y = self._hidden_y(self.compact_h) if self.tucked else self._rest_y()
        self.setGeometry(self._centered_x(self.compact_w), y, self.compact_w, self.compact_h)

    def expand(self):
        if self.is_expanded:
            return
        if self.tucked:
            self._reveal(animate=False)
        self.is_expanded = True
        self._update_passthrough()
        self.idle_pill.hide()
        self.expanded_container.show()
        self._animate_to(QRect(self._centered_x(self.expanded_w), self._rest_y(),
                               self.expanded_w, self.expanded_h))

    def collapse(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.summoned = False
        self._zone_inside = True    # don't treat the cursor as "just arrived"
        self._dwell_blocked = True  # ...and don't reopen until it has left
        self._update_passthrough()
        self.expanded_container.hide()
        self.idle_pill.show()
        self._animate_to(QRect(self._centered_x(self.compact_w), self._rest_y(),
                               self.compact_w, self.compact_h))

    # -------------------------------------------------------- Visibility
    def _setup_visibility(self):
        # Auto-hide: watch the cursor at the top edge
        self.reveal_timer = QTimer(self)
        self.reveal_timer.setInterval(80)
        self.reveal_timer.timeout.connect(self._autohide_tick)
        # Through mode: follow the cursor without ever receiving mouse events
        self.through_timer = QTimer(self)
        self.through_timer.setInterval(50)
        self.through_timer.timeout.connect(self._through_tick)
        # Full-screen apps: check what is in front
        self.fullscreen_timer = QTimer(self)
        self.fullscreen_timer.setInterval(700)
        self.fullscreen_timer.timeout.connect(self._fullscreen_tick)
        self.fullscreen_timer.start()
        self._apply_visibility_mode()

    def showEvent_reserve(self):
        QTimer.singleShot(0, self.update_reserved_space)

    def _autohide_enabled(self):
        return self.config.get("visibility_mode", "always") == "autohide"

    def _apply_visibility_mode(self):
        if self._autohide_enabled():
            self.reveal_timer.start()
        else:
            self.reveal_timer.stop()
            if self.tucked:
                self._reveal()
        if self._through_enabled():
            self.through_timer.start()
        else:
            self.through_timer.stop()
            self.setWindowOpacity(1.0)
        self._update_passthrough()

    # ------------------------------------------------------ Through mode
    def _through_enabled(self):
        return bool(self.config.get("through_mode", True))

    def toggle_through_mode(self, on=None):
        on = (not self._through_enabled()) if on is None else bool(on)
        self.config.set("through_mode", on)
        self._apply_visibility_mode()
        self.idle_pill.flash("👻 Clicks pass through me" if on else "🖱️ Pill is clickable again",
                             self.theme["accent"], 2200)

    def _update_passthrough(self):
        """The folded pill ignores the mouse in through mode; the open island never does."""
        want = (self._through_enabled() and not self.is_expanded
                and not self._drop_override and not self.is_dragging)
        if want != self._passthrough:
            self._passthrough = want
            if self.windowHandle():
                win_input.set_click_through(int(self.winId()), want)
            if not want:
                self.setWindowOpacity(1.0)

    def showEvent(self, event):
        super().showEvent(event)
        # The native window may be new: re-apply the click-through style
        if self.windowHandle():
            win_input.set_click_through(int(self.winId()), self._passthrough)
        self.showEvent_reserve()

    def _hot_zone(self):
        """Pill area plus the strip between it and the top edge of the screen."""
        g = self.geometry()
        top = self._get_screen_geometry().y()
        return QRect(g.x(), top, g.width(), g.bottom() - top + 1)

    def _through_tick(self):
        self._through_step(QCursor.pos(), win_input.mouse_button_down(), time.monotonic())

    def _through_step(self, pos, button_down, now):
        """One step of the through-mode state machine (separate so tests can drive it)."""
        if self.is_expanded:
            # We may never get a leaveEvent if we opened under a still cursor
            if (not self.geometry().adjusted(-6, -6, 6, 6).contains(pos) and not button_down
                    and not self._should_stay_open() and not self.leave_timer.isActive()
                    and not self.summoned):
                self.leave_timer.start(self.config.get("collapse_delay_ms", 300))
            return
        if not self.isVisible() or self.tucked:
            return
        inside = self._hot_zone().contains(pos)
        if not inside:
            self._zone_inside = False
            self._dwell_since = None
            self._drag_in_since = None
            self._dwell_blocked = False
            if self._drop_override and not button_down:
                self._drop_override = False
            self._update_passthrough()
            if self.windowOpacity() != 1.0:
                self.setWindowOpacity(1.0)
            return

        entered = not self._zone_inside
        self._zone_inside = True
        if entered:
            # Arriving with a button held = dragging something towards the island
            self._drag_in_since = now if button_down else None
        if not self._drop_override:
            self.setWindowOpacity(float(self.config.get("through_opacity", 0.35)))
            if self.windowHandle():  # re-assert in case the style was reset
                win_input.set_click_through(int(self.winId()), True)

        if button_down:
            self._dwell_since = None
            if self._drag_in_since is None:
                self._dwell_blocked = True       # a click on whatever is underneath
            elif now - self._drag_in_since >= 0.25 and not self._drop_override:
                self._drop_override = True       # become a drop target for the drag
                self._update_passthrough()
            return
        self._drag_in_since = None
        if self._drop_override:
            self._drop_override = False
            self._update_passthrough()

        how = self.config.get("through_open", "edge")
        at_edge = pos.y() <= self._get_screen_geometry().y() + 1
        triggering = (how == "dwell") or (how == "edge" and at_edge)
        if self._dwell_blocked or not triggering:
            self._dwell_since = None
            return
        if self._dwell_since is None:
            self._dwell_since = now
        elif now - self._dwell_since >= int(self.config.get("through_dwell_ms", 350)) / 1000:
            self._dwell_since = None
            self.expand()

    def toggle_visibility(self):
        """Manual show / hide (hotkey, tray, right-click menu)."""
        self.set_user_hidden(not self.user_hidden)
        if not self.user_hidden:
            self.idle_pill.flash("👋 Back", self.theme["accent"], 1200)

    def set_style(self, notch):
        """Switch between the floating island and the notch, live."""
        self.notch_mode = bool(notch)
        self.config.set("notch_mode", self.notch_mode)
        self._apply_size_profile()
        self.compact_w = self.base_compact_w + self._activity_extra()
        self.resizeEvent(None)
        if self.is_expanded:
            self.collapse()
        elif not self.tucked:
            self._animate_to(QRect(self._centered_x(self.compact_w), self._rest_y(),
                                   self.compact_w, self.compact_h))
        self.update()
        self.update_reserved_space()
        self.idle_pill.flash("📱 Notch" if self.notch_mode else "🏝️ Island", self.theme["accent"], 1500)

    def set_user_hidden(self, hidden):
        """Tray 'Toggle Island'."""
        self.user_hidden = hidden
        if hidden:
            self.collapse()
            self._glide_out()
        else:
            self.tucked = False
            self.fullscreen_hidden = False
            self._glide_in()

    def _tuck(self):
        if self.tucked or self.is_expanded:
            return
        self.tucked = True
        self._away_since = None
        self._glide_out(on_done=lambda: None if self.tucked else self._glide_in(), duration=300)

    def _reveal(self, animate=True):
        if self.user_hidden or self.fullscreen_hidden:
            return
        self.tucked = False
        self._away_since = None
        target = QRect(self._centered_x(self.compact_w), self._rest_y(), self.compact_w, self.compact_h)
        if animate:
            self._glide_in(duration=300)
        else:
            self._stop_glide()
            self.setWindowOpacity(1.0)
            self.setGeometry(target)
            self.show()

    def _peeking(self):
        return bool(self.config.get("peek_on_activity", True) and self.idle_pill.flash_activity)

    def _autohide_tick(self):
        if self.user_hidden or self.fullscreen_hidden or self.is_dragging:
            return
        pos = QCursor.pos()
        geom = self._get_screen_geometry()
        zone = int(self.config.get("reveal_zone_px", 220))
        center_x = geom.x() + geom.width() / 2
        at_top = (geom.contains(pos) and pos.y() <= geom.y() + 2
                  and abs(pos.x() - center_x) <= max(zone, self.width() / 2 + 40))
        if self.tucked:
            if at_top or self._peeking():
                self._reveal()
            return
        near = self.geometry().adjusted(-40, -10, 40, 40).contains(pos)
        if (self.is_expanded or near or at_top or self.summoned or self._peeking()
                or self._should_stay_open()):
            self._away_since = None
            return
        if self._away_since is None:
            self._away_since = time.monotonic()
        elif time.monotonic() - self._away_since >= AUTOHIDE_DELAY_S:
            self._tuck()

    def _fullscreen_tick(self):
        enabled = ((self.config.get("hide_in_fullscreen", True) or self.config.get("hide_for_apps"))
                   and win_input.IS_WINDOWS)
        if not enabled:
            if self.fullscreen_hidden:
                self._leave_fullscreen_hide()
            return
        if self.summoned or self.user_hidden:
            return
        hwnd = int(self.winId()) if self.windowHandle() else None
        apps = [a.lower() for a in self.config.get("hide_for_apps", []) if a]
        if win_input.fullscreen_app_active(hwnd) or (apps and win_input.foreground_process_name() in apps):
            self._fs_clear_ticks = 0
            if not self.fullscreen_hidden:
                self.fullscreen_hidden = True
                self.collapse()
                self._glide_out(duration=160)
        elif self.fullscreen_hidden:
            # Come back only after a moment, so switching tabs in a game doesn't flicker it
            self._fs_clear_ticks = getattr(self, "_fs_clear_ticks", 0) + 1
            if self._fs_clear_ticks >= 2:
                self._leave_fullscreen_hide()

    def _leave_fullscreen_hide(self):
        self.fullscreen_hidden = False
        if self.user_hidden or (self._autohide_enabled() and self.tucked):
            return
        self._glide_in()

    def resizeEvent(self, event):
        # Pill follows the window; the expanded panel keeps its final size and is
        # simply revealed/clipped by the window while it animates.
        side = NOTCH_SHOULDER + 2 if self.notch_mode else 4
        top = 2 if self.notch_mode else 4
        self.idle_pill.setGeometry(side, top, max(0, self.width() - 2 * side), max(0, self.height() - 2 * top))
        cw = self.expanded_w - 2 * side
        self.expanded_container.setGeometry(int((self.width() - cw) / 2), top, cw, self.expanded_h - 2 * top - 2)
        if event is not None:
            super().resizeEvent(event)

    def _animate_to(self, target_rect, on_done=None, duration=None, easing=None):
        """Move/resize smoothly. Growing gets a soft spring, everything else eases out."""
        old = getattr(self, "anim", None)
        if old is not None:
            old.stop()
        glide = getattr(self, "glide", None)
        if glide is not None and glide.state() == glide.State.Running:
            glide.stop()               # a new move wins over a show/hide glide
            self.setWindowOpacity(1.0)
        self.anim = QPropertyAnimation(self, b"geometry")
        if on_done is not None:
            self.anim.finished.connect(on_done)
        grows = target_rect.width() * target_rect.height() > self.width() * self.height() * 1.5
        if easing is None:
            if grows:
                easing = QEasingCurve(QEasingCurve.Type.OutBack)
                easing.setOvershoot(0.7)       # gentle spring, not a bounce
            else:
                easing = QEasingCurve(QEasingCurve.Type.OutQuart)
        self.anim.setDuration(duration or (380 if grows else 300))
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(target_rect)
        self.anim.setEasingCurve(easing)
        self.anim.start()

    # ------------------------------------------- gliding show / hide
    def _glide_out(self, on_done=None, duration=260):
        """Slide up into the top edge while fading out, then hide."""
        if not self.isVisible():
            if on_done:
                on_done()
            return
        self._stop_glide()
        start = self.geometry()
        end = QRect(start.x(), self._hidden_y(start.height()), start.width(), start.height())
        self.glide = self._glide_group(start, end, self.windowOpacity(), 0.0, duration,
                                       QEasingCurve.Type.InCubic)

        def finish():
            self.hide()
            self.setWindowOpacity(1.0)
            self.update_reserved_space()     # give the space back while hidden
            if on_done:
                on_done()
        self.glide.finished.connect(finish)
        self.glide.start()

    def _glide_in(self, duration=340):
        """Appear from the top edge: slide down while fading in."""
        self._stop_glide()
        end = QRect(self._centered_x(self.compact_w), self._rest_y(), self.compact_w, self.compact_h)
        start = QRect(end.x(), self._hidden_y(end.height()), end.width(), end.height())
        self.setGeometry(start)
        self.setWindowOpacity(0.0)
        self.show()
        self.glide = self._glide_group(start, end, 0.0, 1.0, duration, QEasingCurve.Type.OutCubic)
        self.glide.start()
        QTimer.singleShot(0, self.update_reserved_space)

    def _glide_group(self, start, end, op_from, op_to, duration, curve):
        group = QParallelAnimationGroup()
        move = QPropertyAnimation(self, b"geometry")
        move.setStartValue(start)
        move.setEndValue(end)
        move.setDuration(duration)
        move.setEasingCurve(curve)
        fade = QPropertyAnimation(self, b"windowOpacity")
        fade.setStartValue(op_from)
        fade.setEndValue(op_to)
        fade.setDuration(duration)
        fade.setEasingCurve(QEasingCurve.Type.OutQuad)
        group.addAnimation(move)
        group.addAnimation(fade)
        return group

    def _stop_glide(self):
        glide = getattr(self, "glide", None)
        if glide is not None:
            glide.stop()
        anim = getattr(self, "anim", None)
        if anim is not None:
            anim.stop()

    def _should_stay_open(self):
        """Don't yank the island away while the user is typing or dragging."""
        if self.drag_out_active or self.drop_hovering:
            return True
        focus = QApplication.focusWidget()
        typing = isinstance(focus, (QLineEdit, QPlainTextEdit, QTextEdit)) and self.isAncestorOf(focus)
        return typing and self.isActiveWindow()

    def _auto_collapse(self):
        if self.geometry().contains(QCursor.pos()) or self._should_stay_open():
            return
        self.collapse()

    def changeEvent(self, event):
        # Clicking anywhere else closes the island (useful after hotkey summon)
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if self.is_expanded and not self.drag_out_active:
                self.leave_timer.start(self.config.get("collapse_delay_ms", 300))
        super().changeEvent(event)

    def enterEvent(self, event):
        self.leave_timer.stop()
        if not self.is_expanded and self.config.get("expand_on_hover", True):
            delay = self.config.get("hover_delay_ms", 120)
            self.hover_timer.start(delay)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        if self.is_expanded and not self._should_stay_open():
            delay = self.config.get("collapse_delay_ms", 300)
            self.leave_timer.start(delay)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.press_global_pos = event.globalPosition().toPoint()
            self.drag_start_pos = self.press_global_pos - self.frameGeometry().topLeft()
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            # Middle-click anywhere on the island: play / pause
            self.media_service.toggle_play_pause()
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()

    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() == Qt.MouseButton.LeftButton:
            new_pos = event.globalPosition().toPoint() - self.drag_start_pos
            # Clamp Y near top edge
            new_pos.setY(max(0, min(100, new_pos.y())))
            self.move(new_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            moved = (event.globalPosition().toPoint() - self.press_global_pos).manhattanLength()
            if moved <= CLICK_MOVE_THRESHOLD:
                # Plain click on the pill opens it (no hover-and-wait needed)
                if not self.is_expanded and self.config.get("click_to_expand", True):
                    self.hover_timer.stop()
                    self.expand()
                event.accept()
                return
            # Remember where it was dropped (snaps to center when close to the middle)
            geom = self._get_screen_geometry()
            offset = int(self.x() + self.width() / 2 - (geom.x() + geom.width() / 2))
            self.config.set("island_offset_x", 0 if abs(offset) < 60 else offset)
            if self.is_expanded:
                self.move(self._centered_x(self.width()), self._rest_y())
            else:
                self._reposition_compact()
            event.accept()

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {self.theme['bg_color']};
                color: {self.theme['text_primary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 8px;
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 16px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {self.theme['card_bg']};
                color: {self.theme['accent']};
            }}
        """)

        # Settings Dialog Action
        settings_action = menu.addAction("⚙️ Preferences & AI Accounts")
        settings_action.triggered.connect(self.open_settings_dialog)

        # MacBook Taskbar Toggle
        is_autohide = self.taskbar_service.is_autohide_enabled()
        mb_action = menu.addAction("🍏 MacBook Mode (Auto-Hide Taskbar)")
        mb_action.setCheckable(True)
        mb_action.setChecked(is_autohide)
        mb_action.triggered.connect(lambda: self.taskbar_service.set_autohide(not is_autohide))

        menu.addSeparator()

        # Theme submenu
        theme_menu = menu.addMenu("🎨 Select Theme")
        for key, val in THEMES.items():
            action = theme_menu.addAction(val["name"])
            action.triggered.connect(lambda checked, k=key: self.set_theme(k))

        # Notch Mode Toggle
        style_menu = menu.addMenu("📱 Style: Island or Notch")
        island_style = style_menu.addAction("🏝️ Floating island")
        island_style.setCheckable(True)
        island_style.setChecked(not self.notch_mode)
        island_style.triggered.connect(lambda: self.set_style(False))
        notch_style = style_menu.addAction("📱 Notch (attached to the top edge)")
        notch_style.setCheckable(True)
        notch_style.setChecked(self.notch_mode)
        notch_style.triggered.connect(lambda: self.set_style(True))
        menu.addAction("🙈 Hide Island (show again from tray or hotkey)").triggered.connect(
            lambda: self.set_user_hidden(True))

        # Quick reach actions
        menu.addAction("📥 Open Shelf").triggered.connect(lambda: self.open_tab(TAB_SHELF))
        menu.addAction("📝 Quick Note").triggered.connect(self.quick_note)
        menu.addAction("✅ Add Task / Reminder").triggered.connect(lambda: self.open_tab_by_key("tasks"))
        menu.addAction("🔎 Command Bar").triggered.connect(self.toggle_command_bar)
        focus_menu = menu.addMenu("⏱️ Start Focus Timer")
        for minutes in self.config.get("focus_presets_min", [5, 25, 50]):
            focus_menu.addAction(f"{minutes} minutes").triggered.connect(
                lambda _, m=minutes: self.timer_service.start(m, "Focus"))
        if self.timer_service.active:
            focus_menu.addAction("⏹ Stop timer").triggered.connect(self.timer_service.stop)

        menu.addAction("🎨 Customize Island…").triggered.connect(self.open_customize)
        through = menu.addAction("👻 Click-Through Pill (don't block what's under it)")
        through.setCheckable(True)
        through.setChecked(self._through_enabled())
        through.triggered.connect(lambda on: self.toggle_through_mode(on))
        autohide = menu.addAction("🫥 Hide at Top (show when cursor touches top)")
        autohide.setCheckable(True)
        autohide.setChecked(self._autohide_enabled())
        autohide.triggered.connect(self._toggle_autohide)
        menu.addAction("⌨️ Automations & Hotkeys…").triggered.connect(self.open_automations)
        awake = menu.addAction("☕ Keep Awake")
        awake.setCheckable(True)
        awake.setChecked(self.automation_service.keep_awake)
        awake.triggered.connect(lambda on: self.automation_service.set_keep_awake(on))

        # AI Companion Quick Trigger
        ai_action = menu.addAction("🤖 Open AI Companion")
        ai_action.triggered.connect(lambda: self.open_tab(TAB_AI))

        # Screen vision quick trigger
        vision_action = menu.addAction("👁️ Capture Screen & Ask AI")
        vision_action.triggered.connect(lambda: (self.open_tab(TAB_AI), self.ai_service.analyze_screen()))

        menu.addSeparator()
        quit_action = menu.addAction("❌ Exit Dynamic Island")
        quit_action.triggered.connect(sys.exit)

        menu.exec(pos)

    def _toggle_autohide(self, on):
        self.config.set("visibility_mode", "autohide" if on else "always")
        self._apply_visibility_mode()
        if on:
            self.idle_pill.flash("🫥 Move cursor to the top to show me", self.theme["accent"], 2500)

    def _toggle_notch_mode(self):
        self.notch_mode = not self.notch_mode
        self.config.set("notch_mode", self.notch_mode)
        if self.is_expanded:
            self.collapse()
        else:
            self._reposition_compact()

    def set_theme(self, theme_key):
        self.theme_name = theme_key
        self.theme = get_theme(theme_key)
        self.config.set("theme", theme_key)

        # Propagate to child widgets
        self.idle_pill.update_theme(self.theme)
        self.media_widget.update_theme(self.theme)
        self.sys_widget.update_theme(self.theme)
        self.ai_widget.update_theme(self.theme)
        self.tools_widget.update_theme(self.theme)
        self.shelf_widget.update_theme(self.theme)
        self.notes_widget.update_theme(self.theme)
        self.focus_widget.update_theme(self.theme)
        self.keys_widget.update_theme(self.theme)
        self.info_widget.update_theme(self.theme)
        self.tasks_widget.update_theme(self.theme)
        self.day_widget.update_theme(self.theme)
        self._style_nav()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        radius = h / 2 if not self.is_expanded else 24

        # Background Gradient
        gradient = QLinearGradient(0, 0, 0, h)
        gradient.setColorAt(0.0, QColor(self.theme["pill_gradient_start"]))
        gradient.setColorAt(1.0, QColor(self.theme["pill_gradient_end"]))

        painter.setBrush(QBrush(gradient))

        # Subtle Glowing / Accent Border
        border_pen = QPen(QColor(self.theme["border_color"]), 1.2)
        painter.setPen(border_pen)

        if self.notch_mode:
            # No outline: the notch melts into the screen bezel
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(notch_path(w, h, self.is_expanded))
        else:
            # Draw rounded pill shape
            painter.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)
