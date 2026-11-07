import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, QPoint, QEvent, pyqtSignal
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

# Tab indices (kept stable so existing shortcuts keep working)
TAB_MEDIA, TAB_SYSTEM, TAB_AI, TAB_TOOLS, TAB_SHELF, TAB_NOTES, TAB_FOCUS, TAB_KEYS = range(8)
TAB_NAMES = {"media": TAB_MEDIA, "system": TAB_SYSTEM, "sys": TAB_SYSTEM, "ai": TAB_AI,
             "tools": TAB_TOOLS, "shelf": TAB_SHELF, "clipboard": TAB_SHELF, "notes": TAB_NOTES,
             "focus": TAB_FOCUS, "timer": TAB_FOCUS, "keys": TAB_KEYS, "automations": TAB_KEYS}
CLICK_MOVE_THRESHOLD = 4

class DynamicIslandWindow(QWidget):
    # title, message -> shown as a Windows toast by the tray icon
    notify = pyqtSignal(str, str)

    def __init__(self, media_service, sys_service, ai_service, taskbar_service,
                 clipboard_service=None, timer_service=None, build_service=None,
                 automation_service=None):
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

        # State tracking
        self.is_expanded = False
        self.is_dragging = False
        self.drag_start_pos = QPoint()
        self.press_global_pos = QPoint()
        self.drag_out_active = False   # a file is being dragged out of the shelf
        self.drop_hovering = False     # something is being dragged over the island

        # Dimensions
        self.base_compact_w = self.config.get("compact_width", 210)
        self.compact_w = self.base_compact_w
        self.compact_h = self.config.get("compact_height", 36)
        self.expanded_w = self.config.get("expanded_width", 490)
        # Shelf / Focus tabs need a little more room for their lists
        self.expanded_h = max(self.config.get("expanded_height", 200), 210)
        self.top_offset = self.config.get("anchor_top_offset", 8)
        self.notch_mode = self.config.get("notch_mode", False)

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
        if self.config.get("remember_last_tab", True):
            last = self.config.get("last_tab", 0)
            if isinstance(last, int) and 0 <= last < self.stack.count():
                self._switch_tab(last, save=False)

        # Apply saved taskbar setting if configured
        if self.config.get("taskbar_autohide_macbook", False):
            self.taskbar_service.set_autohide(True)

    def _build_ui(self):
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(4, 4, 4, 4)
        self.main_layout.setSpacing(0)

        # 1. Idle Pill Widget (Visible when collapsed)
        self.idle_pill = IdlePillWidget(self.theme, self)
        self.main_layout.addWidget(self.idle_pill)

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

        self.stack.addWidget(self.media_widget) # Index 0
        self.stack.addWidget(self.sys_widget)   # Index 1
        self.stack.addWidget(self.ai_widget)    # Index 2
        self.stack.addWidget(self.tools_widget) # Index 3
        self.stack.addWidget(self.shelf_widget) # Index 4
        self.stack.addWidget(self.notes_widget) # Index 5
        self.stack.addWidget(self.focus_widget) # Index 6
        self.stack.addWidget(self.keys_widget)  # Index 7

        self.exp_layout.addWidget(self.stack)

        # Navigation Bar for switching modules in expanded mode
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(10, 0, 10, 6)
        nav_row.setSpacing(5)
        nav_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # (label, tab index, tooltip) in display order
        nav_spec = [
            ("🎵 Media", TAB_MEDIA, "Media controls"),
            ("📥 Shelf", TAB_SHELF, "Dropped files + clipboard history"),
            ("📝 Notes", TAB_NOTES, "Quick scratchpad"),
            ("⏱️ Focus", TAB_FOCUS, "Focus timer + build tracker"),
            ("⌨️ Keys", TAB_KEYS, "Automations: hotkeys, hotstrings, laptop toggles"),
            ("🤖 AI", TAB_AI, "AI Companion"),
            ("⚡ Sys", TAB_SYSTEM, "System telemetry"),
            ("🛠️ Tools", TAB_TOOLS, "Launchers & utilities"),
        ]
        self.nav_buttons = {}
        for pos, (label, index, tip) in enumerate(nav_spec, start=1):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setToolTip(f"{tip}  (Ctrl+{pos})")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, i=index: self._switch_tab(i))
            nav_row.addWidget(btn)
            self.nav_buttons[index] = btn
        self.nav_order = [index for _, index, _ in nav_spec]
        self._style_nav()
        self.nav_buttons[TAB_MEDIA].setChecked(True)
        self.exp_layout.addLayout(nav_row)

        self.main_layout.addWidget(self.expanded_container)
        self.expanded_container.hide()

    def _style_nav(self):
        css = f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 11px;
                padding: 3px 6px;
                font-size: 10px;
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

    def _switch_tab(self, index, save=True):
        self.stack.setCurrentIndex(index)
        for i, btn in self.nav_buttons.items():
            btn.setChecked(i == index)
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
        }

    def open_automations(self):
        dlg = AutomationDialog(self.theme, self.automation_service, self)
        dlg.exec()

    def open_tab(self, index):
        """Show the island expanded on a given tab (used by menus, tray, hotkey)."""
        self.show()
        self.expand()
        self._switch_tab(index)

    def summon(self):
        """Global-hotkey entry point: toggle the island open and focus it."""
        if self.is_expanded and self.isActiveWindow():
            self.collapse()
            return
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
        for pos, index in enumerate(self.nav_order, start=1):
            sc = QShortcut(QKeySequence(f"Ctrl+{pos}"), self, context=ctx)
            sc.activated.connect(lambda i=index: (self.expand(), self._switch_tab(i)))
        esc = QShortcut(QKeySequence(Qt.Key.Key_Escape), self, context=ctx)
        esc.activated.connect(self.collapse)
        for keys, step in (("Ctrl+Tab", 1), ("Ctrl+Shift+Tab", -1)):
            sc = QShortcut(QKeySequence(keys), self, context=ctx)
            sc.activated.connect(lambda s=step: self._cycle_tab(s))

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
        if not self.is_expanded and not self.is_dragging:
            geom = self._get_screen_geometry()
            x = int(geom.x() + (geom.width() - self.compact_w) / 2)
            self._animate_to(QRect(x, self.y(), self.compact_w, self.compact_h))

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

    def _reposition_compact(self):
        geom = self._get_screen_geometry()
        x = int(geom.x() + (geom.width() - self.compact_w) / 2)
        y = geom.y() if self.notch_mode else geom.y() + self.top_offset
        self.setGeometry(x, y, self.compact_w, self.compact_h)

    def expand(self):
        if self.is_expanded:
            return
        self.is_expanded = True
        self.idle_pill.hide()
        self.expanded_container.show()

        geom = self._get_screen_geometry()
        target_x = int(geom.x() + (geom.width() - self.expanded_w) / 2)
        target_y = geom.y() if self.notch_mode else geom.y() + self.top_offset
        target_rect = QRect(target_x, target_y, self.expanded_w, self.expanded_h)

        self._animate_to(target_rect)

    def collapse(self):
        if not self.is_expanded:
            return
        self.is_expanded = False
        self.expanded_container.hide()
        self.idle_pill.show()

        geom = self._get_screen_geometry()
        target_x = int(geom.x() + (geom.width() - self.compact_w) / 2)
        target_y = geom.y() if self.notch_mode else geom.y() + self.top_offset
        target_rect = QRect(target_x, target_y, self.compact_w, self.compact_h)

        self._animate_to(target_rect)

    def _animate_to(self, target_rect):
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(220)
        self.anim.setStartValue(self.geometry())
        self.anim.setEndValue(target_rect)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.start()

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
            # Snap to center if close to middle
            geom = self._get_screen_geometry()
            cur_x = self.x() + self.width() / 2
            screen_center = geom.x() + geom.width() / 2
            if abs(cur_x - screen_center) < 140:
                snap_x = int(geom.x() + (geom.width() - self.width()) / 2)
                self.move(snap_x, self.y())
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
        notch_action = menu.addAction("📌 Toggle Notch Mode (Top Flush)")
        notch_action.setCheckable(True)
        notch_action.setChecked(self.notch_mode)
        notch_action.triggered.connect(self._toggle_notch_mode)

        # Quick reach actions
        menu.addAction("📥 Open Shelf").triggered.connect(lambda: self.open_tab(TAB_SHELF))
        menu.addAction("📝 Quick Note").triggered.connect(self.quick_note)
        focus_menu = menu.addMenu("⏱️ Start Focus Timer")
        for minutes in self.config.get("focus_presets_min", [5, 25, 50]):
            focus_menu.addAction(f"{minutes} minutes").triggered.connect(
                lambda _, m=minutes: self.timer_service.start(m, "Focus"))
        if self.timer_service.active:
            focus_menu.addAction("⏹ Stop timer").triggered.connect(self.timer_service.stop)

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

        # Draw rounded pill shape
        painter.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)
