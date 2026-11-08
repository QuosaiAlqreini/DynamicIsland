import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".dynamic_island"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "theme": "obsidian",
    "expand_on_hover": True,
    "hover_delay_ms": 120,
    "collapse_delay_ms": 300,
    "anchor_top_offset": 8,
    "compact_width": 200,
    "compact_height": 36,
    "expanded_width": 480,
    "expanded_height": 185,
    "active_module": "media",
    "notch_mode": False,
    "always_on_top": True,
    "sound_effects": True,
    "agent_status": "Idle",
    "agent_mode": "Antigravity",
    "ai_provider": "gemini",
    "gemini_api_key": "",
    "claude_api_key": "",
    "openai_api_key": "",
    "ollama_url": "http://localhost:11434",
    "ollama_model": "llama3",
    "ai_vision_enabled": True,
    "ai_auto_capture_screen": False,
    "active_ai_model": "gemini-1.5-flash",
    "taskbar_autohide_macbook": False,
    "taskbar_translucent": True,
    "taskbar_hide_clock_tray": False,
    # --- Notch productivity features (Shelf, Clipboard, Notes, Focus, Builds) ---
    "global_hotkey": "Ctrl+Alt+Space",
    "click_to_expand": True,
    "remember_last_tab": True,
    "last_tab": 0,
    "shelf_items": [],
    "shelf_max_items": 30,
    "clipboard_history_enabled": True,
    "clipboard_history_size": 25,
    "clipboard_pinned": [],
    "quick_notes": "",
    "focus_presets_min": [5, 25, 50],
    "build_watch_enabled": True,
    "build_watch_min_seconds": 5,
    "build_watch_patterns": [
        "npm run build", "npm install", "npm ci", "yarn build", "pnpm build",
        "vite build", "next build", "tsc", "webpack",
        "cargo build", "cargo test", "go build", "go test",
        "dotnet build", "dotnet test", "msbuild", "gradle", "mvn",
        "pytest", "pip install", "docker build", "docker compose build",
        "make", "cmake --build", "ninja", "flutter build"
    ],
    # --- Visibility & customization ---
    "visibility_mode": "always",       # "always" | "autohide" (tucked at the top, cursor reveals)
    "hide_in_fullscreen": True,
    "peek_on_activity": True,          # auto-hide mode: slide down for timers/builds/alerts
    "reveal_zone_px": 220,             # half-width of the top-edge hot zone around the island
    "pill_left": "ai_dot",
    "pill_center": "clock",
    "pill_right": "battery_icon",
    "tabs_visible": ["media", "shelf", "notes", "focus", "keys", "ai", "system", "tools"],
    "info_items": [],
    # --- AutoHotkey-style automation ---
    "launch_at_login": False,
    "hotstrings_enabled": True,
    "automations": [
        {"name": "Terminal", "hotkey": "Ctrl+Alt+T", "action": "run", "arg": "wt", "enabled": True},
        {"name": "Quick note", "hotkey": "Ctrl+Alt+N", "action": "quick_note", "arg": "", "enabled": True},
        {"name": "Shelf & clipboard", "hotkey": "Ctrl+Alt+V", "action": "island_tab", "arg": "shelf", "enabled": True},
        {"name": "Pin window on top", "hotkey": "Ctrl+Alt+P", "action": "win_top", "arg": "", "enabled": True},
        {"name": "Center window", "hotkey": "Ctrl+Alt+C", "action": "win_center", "arg": "", "enabled": True},
        {"name": "Keep awake", "hotkey": "Ctrl+Alt+K", "action": "keep_awake", "arg": "", "enabled": True},
        {"name": "Focus 25 min", "hotkey": "Ctrl+Alt+F", "action": "focus", "arg": "25", "enabled": True},
        {"name": "Brightness up", "hotkey": "Ctrl+Alt+PgUp", "action": "bright_up", "arg": "10", "enabled": True},
        {"name": "Brightness down", "hotkey": "Ctrl+Alt+PgDown", "action": "bright_down", "arg": "10", "enabled": True},
        {"name": "Dark mode", "hotkey": "Ctrl+Alt+D", "action": "dark_mode", "arg": "", "enabled": True},
        {"name": "Screenshot", "hotkey": "", "action": "screenshot", "arg": "", "enabled": True},
        {"name": "Lock", "hotkey": "", "action": "lock", "arg": "", "enabled": True}
    ],
    "hotstrings": [
        {"trigger": ";date", "replacement": "{date}", "instant": False, "enabled": True},
        {"trigger": ";time", "replacement": "{time}", "instant": False, "enabled": True},
        {"trigger": ";now", "replacement": "{datetime}", "instant": False, "enabled": True},
        {"trigger": ";shrug", "replacement": "¯\\_(ツ)_/¯", "instant": False, "enabled": True},
        {"trigger": ";ty", "replacement": "Thank you!", "instant": False, "enabled": True}
    ],
    "pinned_launchers": [
        {"name": "Explorer", "target": "explorer.exe"},
        {"name": "Downloads", "target": "~/Downloads"},
        {"name": "Settings", "target": "ms-settings:"}
    ],
    "ai_quick_actions": [
        "See Screen & Analyze",
        "Explain Clipboard",
        "Fix Code in Clipboard",
        "Run Ralph Loop",
        "CodeRabbit Review",
        "Generate Phase Plan"
    ]
}

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.data = {**DEFAULT_CONFIG, **json.load(f)}
            except Exception:
                self.data = DEFAULT_CONFIG.copy()
        else:
            self.data = DEFAULT_CONFIG.copy()
            self.save()

    def get(self, key, default=None):
        return self.data.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.data[key] = value
        self.save()

    def save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            print(f"Error saving config: {e}")
