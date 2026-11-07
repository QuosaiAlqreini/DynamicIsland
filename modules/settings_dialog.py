import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QTabWidget, QWidget, QTextEdit, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from config import ConfigManager
from services.taskbar_service import TaskbarService, WINDHAWK_PRESETS

class SettingsDialog(QDialog):
    def __init__(self, theme, ai_service, taskbar_service, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.ai_service = ai_service
        self.taskbar_service = taskbar_service
        self.config = ConfigManager()

        self.setWindowTitle("Dynamic Island Settings - AI Accounts & Taskbar")
        self.setFixedSize(620, 520)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {self.theme['bg_color']};
                color: {self.theme['text_primary']};
                font-family: 'Segoe UI', sans-serif;
            }}
            QTabWidget::pane {{
                border: 1px solid {self.theme['border_color']};
                background: {self.theme['bg_secondary']};
                border-radius: 8px;
            }}
            QTabBar::tab {{
                background: {self.theme['bg_color']};
                color: {self.theme['text_secondary']};
                padding: 8px 16px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                font-weight: 600;
                font-size: 11px;
            }}
            QTabBar::tab:selected {{
                background: {self.theme['bg_secondary']};
                color: {self.theme['accent']};
                border: 1px solid {self.theme['border_color']};
                border-bottom: none;
            }}
            QLabel {{
                color: {self.theme['text_primary']};
                font-size: 11px;
            }}
            QLineEdit, QComboBox {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_primary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 11px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {self.theme['accent']};
            }}
            QPushButton {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_primary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                border-color: {self.theme['accent']};
                color: {self.theme['accent']};
            }}
            QCheckBox {{
                color: {self.theme['text_primary']};
                font-size: 11px;
            }}
        """)

        self._build_ui()
        self._load_values()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # Header Title
        title_box = QHBoxLayout()
        icon_lbl = QLabel("⚙️")
        icon_lbl.setStyleSheet("font-size: 20px;")
        title_box.addWidget(icon_lbl)

        title_text = QLabel("Dynamic Island Preferences")
        title_text.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {self.theme['text_primary']};")
        title_box.addWidget(title_text)
        title_box.addStretch()
        main_layout.addLayout(title_box)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tab_ai = QWidget()
        self.tab_taskbar = QWidget()
        self.tab_appearance = QWidget()

        self._build_ai_tab()
        self._build_taskbar_tab()
        self._build_appearance_tab()

        self.tabs.addTab(self.tab_ai, "🤖 AI Accounts & Vision")
        self.tabs.addTab(self.tab_taskbar, "💻 Taskbar & MacBook Vibe")
        self.tabs.addTab(self.tab_appearance, "🎨 Appearance & Quick Reach")
        main_layout.addWidget(self.tabs)

        # Bottom Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setStyleSheet(f"""
            QPushButton {{
                background: {self.theme['accent']};
                color: {self.theme['bg_color']};
                font-weight: bold;
                border: none;
            }}
            QPushButton:hover {{
                background: {self.theme['text_primary']};
            }}
        """)
        self.btn_save.clicked.connect(self._save_and_close)
        btn_box.addWidget(self.btn_save)

        main_layout.addLayout(btn_box)

    def _build_ai_tab(self):
        layout = QVBoxLayout(self.tab_ai)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Provider Selection
        p_row = QHBoxLayout()
        p_row.addWidget(QLabel("AI Provider:"))
        self.combo_provider = QComboBox()
        self.combo_provider.addItem("Google Gemini (Free Tier Available)", "gemini")
        self.combo_provider.addItem("Anthropic Claude (Claude 3.5 Sonnet)", "claude")
        self.combo_provider.addItem("OpenAI (GPT-4o & GPT-4o-mini)", "openai")
        self.combo_provider.addItem("Ollama (100% Free, Local & Offline)", "ollama")
        self.combo_provider.addItem("Claude Code / Antigravity CLI Local Bridge", "local")
        self.combo_provider.currentIndexChanged.connect(self._on_provider_changed)
        p_row.addWidget(self.combo_provider, 1)
        layout.addLayout(p_row)

        # Free tier helper banner
        self.banner_free = QLabel("💡 Google Gemini includes a generous 100% free API tier with 15 RPM / 1M TPM!")
        self.banner_free.setStyleSheet(f"""
            color: {self.theme['accent']};
            background: rgba(0, 240, 255, 0.08);
            border: 1px dashed {self.theme['border_color']};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 10px;
        """)
        layout.addWidget(self.banner_free)

        # API Key input row
        self.key_container = QWidget()
        self.key_row = QHBoxLayout(self.key_container)
        self.key_row.setContentsMargins(0, 0, 0, 0)
        self.key_label = QLabel("API Key:")
        self.key_row.addWidget(self.key_label)
        self.edit_key = QLineEdit()
        self.edit_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_key.setPlaceholderText("Paste your AI API key here...")
        self.key_row.addWidget(self.edit_key, 1)

        self.btn_toggle_key = QPushButton("👁️")
        self.btn_toggle_key.setFixedWidth(30)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        self.key_row.addWidget(self.btn_toggle_key)
        layout.addWidget(self.key_container)

        # Links & Connect buttons row
        link_row = QHBoxLayout()
        self.btn_get_free_key = QPushButton("🔗 Get Free Account / API Key")
        self.btn_get_free_key.clicked.connect(self._open_free_account_url)
        link_row.addWidget(self.btn_get_free_key)

        self.btn_test_conn = QPushButton("⚡ Test Connection")
        self.btn_test_conn.clicked.connect(self._test_connection)
        link_row.addWidget(self.btn_test_conn)
        layout.addLayout(link_row)

        # Connection feedback label
        self.lbl_conn_status = QLabel("")
        self.lbl_conn_status.setStyleSheet("font-size: 10px; font-weight: bold;")
        layout.addWidget(self.lbl_conn_status)

        layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))

        # Screen Vision Settings
        v_title = QLabel("👀 AI Screen Vision & Pair Programming")
        v_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {self.theme['accent']};")
        layout.addWidget(v_title)

        self.chk_vision = QCheckBox("Enable Screen Capture for AI pair programming")
        self.chk_vision.setChecked(True)
        layout.addWidget(self.chk_vision)

        self.chk_auto_capture = QCheckBox("Automatically capture and attach screen to prompt messages")
        layout.addWidget(self.chk_auto_capture)

        layout.addStretch()

    def _build_taskbar_tab(self):
        layout = QVBoxLayout(self.tab_taskbar)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        # Intro text about avoiding duplicate options
        desc = QLabel(
            "Dynamic Island already puts your clock, battery, media controls, and system monitor at the top.\n"
            "Enable MacBook Mode to eliminate redundant taskbar widgets and enjoy a clean desktop look!"
        )
        desc.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # 1. Native Windows Taskbar Auto-Hide (MacBook Mode)
        mb_box = QHBoxLayout()
        self.chk_autohide = QCheckBox("🍏 MacBook Mode: Auto-Hide Windows Taskbar")
        self.chk_autohide.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.chk_autohide.toggled.connect(self._toggle_autohide)
        mb_box.addWidget(self.chk_autohide)
        mb_box.addStretch()
        layout.addWidget(self.chk_autohide)

        hint = QLabel("• Keeps your desktop pristine with only Dynamic Island visible at the top.\n• The taskbar smoothly glides in only when your cursor touches the bottom edge.")
        hint.setStyleSheet(f"color: {self.theme['text_secondary']}; font-size: 10px; margin-left: 18px;")
        layout.addWidget(hint)

        layout.addWidget(QFrame(frameShape=QFrame.Shape.HLine))

        # 2. Windhawk Windows 11 Taskbar Styler Presets
        wh_title = QLabel("🎨 Windhawk 'Windows 11 Taskbar Styler' Presets")
        wh_title.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {self.theme['accent']};")
        layout.addWidget(wh_title)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.combo_windhawk = QComboBox()
        self.combo_windhawk.addItem("MacBook DockLike (Floating Centered Dock)", "dock_like")
        self.combo_windhawk.addItem("Translucent Acrylic Glass", "translucent")
        self.combo_windhawk.addItem("Clean Desk (Hide Redundant Clock & Tray)", "hide_redundant_tray")
        self.combo_windhawk.currentIndexChanged.connect(self._on_windhawk_preset_changed)
        preset_row.addWidget(self.combo_windhawk, 1)
        layout.addLayout(preset_row)

        self.txt_xaml_preview = QTextEdit()
        self.txt_xaml_preview.setReadOnly(True)
        self.txt_xaml_preview.setFixedHeight(100)
        self.txt_xaml_preview.setStyleSheet(f"""
            QTextEdit {{
                background: {self.theme['card_bg']};
                color: {self.theme['text_secondary']};
                border: 1px solid {self.theme['border_color']};
                border-radius: 6px;
                font-family: Consolas, monospace;
                font-size: 9px;
            }}
        """)
        layout.addWidget(self.txt_xaml_preview)

        wh_btn_row = QHBoxLayout()
        self.btn_copy_xaml = QPushButton("📋 Copy Preset XAML for Windhawk")
        self.btn_copy_xaml.clicked.connect(self._copy_windhawk_xaml)
        wh_btn_row.addWidget(self.btn_copy_xaml)

        self.btn_open_windhawk = QPushButton("🌐 Open Windhawk Taskbar Styler Page")
        self.btn_open_windhawk.clicked.connect(lambda: webbrowser.open("https://windhawk.net/mods/windows-11-taskbar-styler"))
        wh_btn_row.addWidget(self.btn_open_windhawk)
        layout.addLayout(wh_btn_row)

        layout.addStretch()

    def _build_appearance_tab(self):
        layout = QVBoxLayout(self.tab_appearance)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Theme selector
        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("Theme Palette:"))
        self.combo_theme = QComboBox()
        self.combo_theme.addItem("Obsidian Dark (OLED Black)", "obsidian")
        self.combo_theme.addItem("Cyberpunk Neon (Hot Pink & Cyan)", "cyberpunk")
        self.combo_theme.addItem("Nord Arctic (Slate Blue)", "nord")
        self.combo_theme.addItem("Glassmorphic (Frosted Acrylic)", "glassmorphic")
        self.combo_theme.addItem("Porcelain Light (Modern Clean)", "porcelain")
        t_row.addWidget(self.combo_theme, 1)
        layout.addLayout(t_row)

        # Notch Mode
        self.chk_notch = QCheckBox("📌 Notch Mode: Dock flush with top screen bezel")
        layout.addWidget(self.chk_notch)

        # Hover sensitivity
        self.chk_hover = QCheckBox("Expand automatically when cursor hovers over the island")
        layout.addWidget(self.chk_hover)

        # --- Quick reach & productivity ---
        self.chk_click = QCheckBox("Click the pill to open it (no hover wait)")
        layout.addWidget(self.chk_click)
        self.chk_last_tab = QCheckBox("Reopen on the last tab I used")
        layout.addWidget(self.chk_last_tab)
        self.chk_clip = QCheckBox("📋 Keep clipboard history (memory only — only pinned items are saved)")
        layout.addWidget(self.chk_clip)
        self.chk_builds = QCheckBox("🔨 Track builds, installs & test runs as live activities")
        layout.addWidget(self.chk_builds)

        hk_row = QHBoxLayout()
        hk_row.addWidget(QLabel("Global hotkey (restart to apply):"))
        self.edit_hotkey = QLineEdit()
        self.edit_hotkey.setPlaceholderText("Ctrl+Alt+Space")
        hk_row.addWidget(self.edit_hotkey, 1)
        layout.addLayout(hk_row)

        layout.addStretch()

    def _load_values(self):
        # AI Tab values
        provider = self.config.get("ai_provider", "gemini")
        idx = self.combo_provider.findData(provider)
        if idx >= 0:
            self.combo_provider.setCurrentIndex(idx)
        self._on_provider_changed(idx)

        self.chk_vision.setChecked(self.config.get("ai_vision_enabled", True))
        self.chk_auto_capture.setChecked(self.config.get("ai_auto_capture_screen", False))

        # Taskbar Tab values
        is_autohide = self.taskbar_service.is_autohide_enabled()
        self.chk_autohide.setChecked(is_autohide)
        self._on_windhawk_preset_changed(0)

        # Appearance Tab values
        th = self.config.get("theme", "obsidian")
        t_idx = self.combo_theme.findData(th)
        if t_idx >= 0:
            self.combo_theme.setCurrentIndex(t_idx)
        self.chk_notch.setChecked(self.config.get("notch_mode", False))
        self.chk_hover.setChecked(self.config.get("expand_on_hover", True))
        self.chk_click.setChecked(self.config.get("click_to_expand", True))
        self.chk_last_tab.setChecked(self.config.get("remember_last_tab", True))
        self.chk_clip.setChecked(self.config.get("clipboard_history_enabled", True))
        self.chk_builds.setChecked(self.config.get("build_watch_enabled", True))
        self.edit_hotkey.setText(self.config.get("global_hotkey", "Ctrl+Alt+Space"))

        # Connect AI service signal
        self.ai_service.connection_tested.connect(self._on_connection_tested)

    def _on_provider_changed(self, index):
        provider = self.combo_provider.currentData()
        if provider == "gemini":
            self.key_label.setText("Gemini Key:")
            self.edit_key.setText(self.config.get("gemini_api_key", ""))
            self.banner_free.setText("💡 Google Gemini Free Tier: 15 RPM / 1M TPM at aistudio.google.com without billing.")
            self.key_container.show()
        elif provider == "claude":
            self.key_label.setText("Claude Key:")
            self.edit_key.setText(self.config.get("claude_api_key", ""))
            self.banner_free.setText("💡 Anthropic Claude: Uses Claude 3.5 Sonnet Vision for state-of-the-art coding.")
            self.key_container.show()
        elif provider == "openai":
            self.key_label.setText("OpenAI Key:")
            self.edit_key.setText(self.config.get("openai_api_key", ""))
            self.banner_free.setText("💡 OpenAI: Uses GPT-4o / GPT-4o-mini Vision.")
            self.key_container.show()
        elif provider == "ollama":
            self.key_label.setText("Ollama URL:")
            self.edit_key.setText(self.config.get("ollama_url", "http://localhost:11434"))
            self.banner_free.setText("💡 Ollama is 100% Free, Private & runs fully offline on your PC!")
            self.key_container.show()
        else: # local CLI
            self.key_container.hide()
            self.banner_free.setText("💡 Connected to your local Claude Code & Antigravity developer CLI session.")

    def _toggle_key_visibility(self):
        if self.edit_key.echoMode() == QLineEdit.EchoMode.Password:
            self.edit_key.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.edit_key.setEchoMode(QLineEdit.EchoMode.Password)

    def _open_free_account_url(self):
        provider = self.combo_provider.currentData()
        if provider == "gemini":
            webbrowser.open("https://aistudio.google.com/app/apikey")
        elif provider == "ollama":
            webbrowser.open("https://ollama.com/")
        elif provider == "claude":
            webbrowser.open("https://console.anthropic.com/")
        elif provider == "openai":
            webbrowser.open("https://platform.openai.com/api-keys")

    def _test_connection(self):
        provider = self.combo_provider.currentData()
        key = self.edit_key.text()
        self.lbl_conn_status.setText("Pinging API server...")
        self.lbl_conn_status.setStyleSheet("color: #f59e0b;")
        self.ai_service.test_connection(provider, api_key=key, ollama_url=key)

    def _on_connection_tested(self, success, message):
        color = "#10b981" if success else "#ef4444"
        self.lbl_conn_status.setStyleSheet(f"color: {color};")
        self.lbl_conn_status.setText(f"{'✓' if success else '✗'} {message}")

    def _toggle_autohide(self, checked):
        self.taskbar_service.set_autohide(checked)

    def _on_windhawk_preset_changed(self, index):
        preset_key = self.combo_windhawk.currentData()
        xaml = self.taskbar_service.get_windhawk_preset_xaml(preset_key)
        self.txt_xaml_preview.setText(xaml)

    def _copy_windhawk_xaml(self):
        from PyQt6.QtWidgets import QApplication
        xaml = self.txt_xaml_preview.toPlainText()
        QApplication.clipboard().setText(xaml)
        QMessageBox.information(
            self,
            "Copied to Clipboard",
            "Windhawk Styler XAML has been copied!\n\nOpen Windhawk ➔ Windows 11 Taskbar Styler ➔ Settings, and paste it into the custom styles area."
        )

    def _save_and_close(self):
        provider = self.combo_provider.currentData()
        self.config.set("ai_provider", provider)
        val = self.edit_key.text().strip()
        if provider == "gemini":
            self.config.set("gemini_api_key", val)
        elif provider == "claude":
            self.config.set("claude_api_key", val)
        elif provider == "openai":
            self.config.set("openai_api_key", val)
        elif provider == "ollama":
            self.config.set("ollama_url", val)

        self.config.set("ai_vision_enabled", self.chk_vision.isChecked())
        self.config.set("ai_auto_capture_screen", self.chk_auto_capture.isChecked())
        self.config.set("theme", self.combo_theme.currentData())
        self.config.set("notch_mode", self.chk_notch.isChecked())
        self.config.set("expand_on_hover", self.chk_hover.isChecked())
        self.config.set("click_to_expand", self.chk_click.isChecked())
        self.config.set("remember_last_tab", self.chk_last_tab.isChecked())
        self.config.set("clipboard_history_enabled", self.chk_clip.isChecked())
        self.config.set("build_watch_enabled", self.chk_builds.isChecked())
        self.config.set("global_hotkey", self.edit_hotkey.text().strip() or "Ctrl+Alt+Space")

        self.accept()
