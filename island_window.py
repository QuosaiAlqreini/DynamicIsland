import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QStackedWidget, QMenu
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QRect, QEasingCurve, pyqtProperty, QPoint
)
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QAction, QCursor
)

from config import ConfigManager
from styles import get_theme, THEMES
from modules.pill_idle import IdlePillWidget
from modules.media_widget import MediaWidget
from modules.system_widget import SystemWidget
from modules.ai_agent_widget import AIAgentWidget
from modules.quick_tools_widget import QuickToolsWidget
from modules.settings_dialog import SettingsDialog

class DynamicIslandWindow(QWidget):
    def __init__(self, media_service, sys_service, ai_service, taskbar_service):
        super().__init__()
        self.config = ConfigManager()
        self.theme_name = self.config.get("theme", "obsidian")
        self.theme = get_theme(self.theme_name)

        self.media_service = media_service
        self.sys_service = sys_service
        self.ai_service = ai_service
        self.taskbar_service = taskbar_service

        # State tracking
        self.is_expanded = False
        self.is_dragging = False
        self.drag_start_pos = QPoint()

        # Dimensions
        self.compact_w = self.config.get("compact_width", 210)
        self.compact_h = self.config.get("compact_height", 36)
        self.expanded_w = self.config.get("expanded_width", 490)
        self.expanded_h = self.config.get("expanded_height", 200)
        self.top_offset = self.config.get("anchor_top_offset", 8)
        self.notch_mode = self.config.get("notch_mode", False)

        # Window Flags
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Timers for hover smoothing
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.expand)

        self.leave_timer = QTimer(self)
        self.leave_timer.setSingleShot(True)
        self.leave_timer.timeout.connect(self.collapse)

        # Build UI and position
        self._build_ui()
        self._setup_connections()
        self._reposition_compact()

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

        self.stack.addWidget(self.media_widget) # Index 0
        self.stack.addWidget(self.sys_widget)   # Index 1
        self.stack.addWidget(self.ai_widget)    # Index 2
        self.stack.addWidget(self.tools_widget) # Index 3

        self.exp_layout.addWidget(self.stack)

        # Navigation Bar for switching modules in expanded mode
        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(16, 0, 16, 6)
        nav_row.setSpacing(8)
        nav_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        nav_btn_style = f"""
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 12px;
                padding: 4px 12px;
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

        self.nav_media = QPushButton("🎵 Media")
        self.nav_media.setStyleSheet(nav_btn_style)
        self.nav_media.setCheckable(True)
        self.nav_media.setChecked(True)
        self.nav_media.clicked.connect(lambda: self._switch_tab(0))
        nav_row.addWidget(self.nav_media)

        self.nav_sys = QPushButton("⚡ System")
        self.nav_sys.setStyleSheet(nav_btn_style)
        self.nav_sys.setCheckable(True)
        self.nav_sys.clicked.connect(lambda: self._switch_tab(1))
        nav_row.addWidget(self.nav_sys)

        self.nav_ai = QPushButton("🤖 AI Companion")
        self.nav_ai.setStyleSheet(nav_btn_style)
        self.nav_ai.setCheckable(True)
        self.nav_ai.clicked.connect(lambda: self._switch_tab(2))
        nav_row.addWidget(self.nav_ai)

        self.nav_tools = QPushButton("🛠️ Tools")
        self.nav_tools.setStyleSheet(nav_btn_style)
        self.nav_tools.setCheckable(True)
        self.nav_tools.clicked.connect(lambda: self._switch_tab(3))
        nav_row.addWidget(self.nav_tools)

        self.nav_buttons = [self.nav_media, self.nav_sys, self.nav_ai, self.nav_tools]
        self.exp_layout.addLayout(nav_row)

        self.main_layout.addWidget(self.expanded_container)
        self.expanded_container.hide()

    def _switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav_buttons):
            btn.setChecked(i == index)

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

    def enterEvent(self, event):
        self.leave_timer.stop()
        if not self.is_expanded and self.config.get("expand_on_hover", True):
            delay = self.config.get("hover_delay_ms", 120)
            self.hover_timer.start(delay)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hover_timer.stop()
        if self.is_expanded:
            delay = self.config.get("collapse_delay_ms", 300)
            self.leave_timer.start(delay)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging = True
            self.drag_start_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
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

        # AI Companion Quick Trigger
        ai_action = menu.addAction("🤖 Open AI Companion")
        ai_action.triggered.connect(lambda: (self.expand(), self._switch_tab(2)))

        # Screen vision quick trigger
        vision_action = menu.addAction("👁️ Capture Screen & Ask AI")
        vision_action.triggered.connect(lambda: (self.expand(), self._switch_tab(2), self.ai_service.analyze_screen()))

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
