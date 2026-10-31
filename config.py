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
