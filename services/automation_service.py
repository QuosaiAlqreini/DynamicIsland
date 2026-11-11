"""AutoHotkey-style automation: user hotkeys -> actions, hotstrings, AHK import.

Macros live in the config as
    {"name", "hotkey", "action", "arg", "enabled"}
and hotstrings as
    {"trigger", "replacement", "instant", "enabled"}.
"""
import re
import subprocess
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from config import ConfigManager
from services import win_input
from services.hotstring_engine import HotstringEngine
from services.launcher import open_target

HOTKEY_ID_BASE = 1000

# (key, label, group, argument hint or None)
ACTIONS = [
    ("run", "Open app / file / folder / URL", "Apps & files", "Path, app name or URL (e.g. wt, notepad, https://…)"),
    ("command", "Run command (cmd)", "Apps & files", "Command line, e.g. code C:\\projects\\app"),
    ("powershell", "Run PowerShell (hidden)", "Apps & files", "PowerShell script"),
    ("ahk", "Run AutoHotkey script (.ahk)", "Apps & files", "Path to .ahk file (AutoHotkey must be installed)"),
    ("type", "Type text", "Typing", "Text to type. Tokens: {date} {time} {datetime} {clipboard}"),
    ("paste", "Paste text (fast, for long text)", "Typing", "Text to paste. Same tokens as Type text"),
    ("send", "Send keys", "Typing", "Key combos separated by commas, e.g. Ctrl+Shift+T, Enter"),
    ("win_top", "Window: toggle always-on-top", "Windows", None),
    ("win_center", "Window: center", "Windows", None),
    ("win_left", "Window: snap left half", "Windows", None),
    ("win_right", "Window: snap right half", "Windows", None),
    ("win_max", "Window: maximize / restore", "Windows", None),
    ("win_min", "Window: minimize", "Windows", None),
    ("win_close", "Window: close", "Windows", None),
    ("vol_up", "Volume up", "Laptop", None),
    ("vol_down", "Volume down", "Laptop", None),
    ("mute", "Mute / unmute", "Laptop", None),
    ("media_play", "Media: play / pause", "Laptop", None),
    ("media_next", "Media: next track", "Laptop", None),
    ("media_prev", "Media: previous track", "Laptop", None),
    ("bright_up", "Brightness up", "Laptop", "Step in % (default 10)"),
    ("bright_down", "Brightness down", "Laptop", "Step in % (default 10)"),
    ("keep_awake", "Keep awake (toggle)", "Laptop", None),
    ("dark_mode", "Toggle Windows dark mode", "Laptop", None),
    ("screenshot", "Screenshot (Snipping Tool)", "Laptop", None),
    ("show_desktop", "Show desktop", "Laptop", None),
    ("lock", "Lock PC", "Laptop", None),
    ("sleep", "Sleep", "Laptop", None),
    ("island_toggle", "Island: open / close", "Island", None),
    ("island_tab", "Island: open tab", "Island", "media, shelf, notes, focus, ai, system, tools or keys"),
    ("quick_note", "Island: quick note", "Island", None),
    ("focus", "Island: start focus timer", "Island", "Minutes (default 25)"),
    ("see_screen", "Island: AI look at my screen", "Island", None),
    ("through_toggle", "Island: click-through pill on / off", "Island", None),
    ("island_visibility", "Island: show / hide", "Island", None),
    ("style_toggle", "Island: switch island / notch look", "Island", None),
    ("command_bar", "Island: command bar", "Island", None),
    ("add_task", "Island: add task / reminder", "Island", "Task phrase, e.g. Stretch in 30m (empty = open Tasks)"),
    ("water", "Island: log a glass of water", "Island", None),
    ("pomodoro", "Island: start Pomodoro", "Island", None),
]
ACTION_INFO = {key: (label, group, hint) for key, label, group, hint in ACTIONS}
WINDOW_ACTIONS = {"win_top", "win_center", "win_left", "win_right", "win_max", "win_min", "win_close"}
TYPING_ACTIONS = {"type", "paste", "send"}
_SIMPLE_VK = {"vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD,
              "media_play": 0xB3, "media_next": 0xB0, "media_prev": 0xB1}


def action_label(key):
    return ACTION_INFO.get(key, (key, "", None))[0]


def expand_tokens(text):
    if "{" not in text:
        return text
    now = time.localtime()
    repl = {
        "{date}": time.strftime("%Y-%m-%d", now),
        "{time}": time.strftime("%H:%M", now),
        "{datetime}": time.strftime("%Y-%m-%d %H:%M", now),
    }
    for k, v in repl.items():
        text = text.replace(k, v)
    if "{clipboard}" in text:
        app = QApplication.instance()
        text = text.replace("{clipboard}", app.clipboard().text() if app else "")
    return text


# ---------------------------------------------------------------- AHK import
_AHK_MODS = {"^": "Ctrl", "!": "Alt", "+": "Shift", "#": "Win"}
_AHK_KEY_ACTIONS = {"volume_up": "vol_up", "volume_down": "vol_down", "volume_mute": "mute",
                    "media_play_pause": "media_play", "media_next": "media_next",
                    "media_prev": "media_prev"}


def _ahk_text(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] == '"':
        s = s[1:-1]
    for a, b in (("`n", "\n"), ("`t", "\t"), ("{Enter}", "\n"), ("{Tab}", "\t"),
                 ("{Space}", " "), ("{!}", "!"), ("{#}", "#"), ("{+}", "+"), ("{^}", "^"),
                 ("{{}", "{"), ("{}}", "}"), ("`;", ";"), ("``", "`")):
        s = s.replace(a, b)
    return s


def _ahk_hotkey(prefix, key):
    mods = [_AHK_MODS[c] for c in prefix if c in _AHK_MODS]
    key = {"lbutton": None, "rbutton": None, "mbutton": None}.get(key.lower(), key)
    if key is None:
        return None
    return "+".join(mods + [key])


def parse_ahk(text):
    """Convert the simple parts of an AutoHotkey (v1/v2) script.

    Returns (macros, hotstrings, skipped) where skipped is a list of lines
    that were not understood (multi-line blocks, mouse hotkeys, logic...).
    """
    macros, hotstrings, skipped = [], [], []
    in_comment = False
    depth = 0  # inside a { ... } block we can't convert
    for raw in text.splitlines():
        line = raw.strip()
        if depth:
            depth += line.count("{") - line.count("}")
            depth = max(depth, 0)
            continue
        if line.startswith("/*"):
            in_comment = True
        if in_comment:
            if line.endswith("*/") or line.startswith("*/"):
                in_comment = False
            continue
        line = re.sub(r"\s+;.*$", "", line)
        if not line or line.startswith(";") or line.startswith("#") and "::" not in line:
            continue

        if line.startswith("{"):
            depth = max(1, line.count("{") - line.count("}"))
            if line.count("{") == line.count("}"):
                depth = 0
            continue
        if line.startswith("}") or line.lower() == "return":
            continue

        m = re.match(r"^:([^:]*):(.+?)::(.*)$", line)
        if m:
            opts, trigger, repl = m.groups()
            if not repl.strip():
                skipped.append(raw)
                continue
            hotstrings.append({"trigger": trigger, "replacement": _ahk_text(repl),
                               "instant": "*" in opts, "enabled": True})
            continue

        m = re.match(r"^([#!^+<>*~$]*)([^\s:]+)::(.*)$", line)
        if not m:
            skipped.append(raw)
            continue
        prefix, key, body = m.groups()
        hotkey = _ahk_hotkey(prefix, key)
        body = body.strip()
        if not hotkey or not body or body.endswith("{"):
            skipped.append(raw)
            if body.endswith("{"):
                depth = 1
            continue
        name = f"{hotkey}"
        cmd = re.match(r"^(\w+)\s*(?:,|\(|\s)\s*(.*?)\)?\s*$", body)
        verb, arg = (cmd.group(1).lower(), cmd.group(2)) if cmd else (body.lower(), "")
        macro = None
        if verb == "run":
            macro = {"action": "run", "arg": _ahk_text(arg.split(",")[0])}
        elif verb in ("send", "sendinput", "sendtext", "sendraw", "sendplay", "sendevent"):
            payload = arg.strip()
            km = re.fullmatch(r"\"?\{(\w+)\}\"?", payload)
            if km and km.group(1).lower() in _AHK_KEY_ACTIONS:
                macro = {"action": _AHK_KEY_ACTIONS[km.group(1).lower()], "arg": ""}
            else:
                macro = {"action": "type", "arg": _ahk_text(payload)}
        elif verb in ("winset", "winsetalwaysontop") and ("alwaysontop" in body.lower() or verb == "winsetalwaysontop"):
            macro = {"action": "win_top", "arg": ""}
        elif verb in ("winminimize",):
            macro = {"action": "win_min", "arg": ""}
        elif verb in ("winmaximize",):
            macro = {"action": "win_max", "arg": ""}
        elif verb in ("winclose",):
            macro = {"action": "win_close", "arg": ""}
        elif re.fullmatch(r"[\w]+", body) and win_input.key_to_vk(body) is not None:
            # Remap: a::b
            macro = {"action": "send", "arg": body}
        if macro is None:
            skipped.append(raw)
            continue
        macro.update({"name": f"{name} → {action_label(macro['action'])}", "hotkey": hotkey, "enabled": True})
        macros.append(macro)
    return macros, hotstrings, skipped


# ------------------------------------------------------------------ Service
class AutomationService(QObject):
    feedback = pyqtSignal(str)            # short message for the pill
    keep_awake_changed = pyqtSignal(bool)
    changed = pyqtSignal()                # macros / hotstrings / status changed

    def __init__(self, hotkey_service, island_actions=None, clipboard_service=None, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.hotkeys = hotkey_service
        self.island_actions = island_actions or {}
        self.clipboard_service = clipboard_service
        self.keep_awake = False
        self.status = {}        # hotkey text -> error message
        self._id_to_macro = {}
        self._add_new_default_macros()
        self.engine = HotstringEngine(self)
        self.engine.expand.connect(self._on_hotstring)
        if self.hotkeys is not None:
            self.hotkeys.activated.connect(self._on_hotkey)

    # Default hotkeys added in later versions: give them to existing users once
    NEW_DEFAULTS = [
        {"name": "Show / hide island", "hotkey": "Ctrl+Alt+H", "action": "island_visibility", "arg": "", "enabled": True},
        {"name": "Click-through", "hotkey": "Ctrl+Alt+G", "action": "through_toggle", "arg": "", "enabled": True},
        {"name": "Island / notch look", "hotkey": "Ctrl+Alt+J", "action": "style_toggle", "arg": "", "enabled": True},
    ]

    def _add_new_default_macros(self):
        done = list(self.config.get("migrated_default_macros", []) or [])
        macros = self.macros
        added = False
        for default in self.NEW_DEFAULTS:
            if default["action"] in done:
                continue
            done.append(default["action"])
            if any(m.get("action") == default["action"] for m in macros):
                continue
            macro = dict(default)
            if any((m.get("hotkey") or "").lower() == macro["hotkey"].lower() for m in macros):
                macro["hotkey"] = ""   # don't steal a hotkey the user already uses
            macros.append(macro)
            added = True
        if added:
            self.config.set("automations", macros)
        self.config.set("migrated_default_macros", done)

    # ------------------------------------------------------------- data
    @property
    def macros(self):
        return [m for m in self.config.get("automations", []) if isinstance(m, dict)]

    @property
    def hotstrings(self):
        return [h for h in self.config.get("hotstrings", []) if isinstance(h, dict)]

    @property
    def hotstrings_enabled(self):
        return bool(self.config.get("hotstrings_enabled", False))

    def save_macros(self, macros):
        self.config.set("automations", [dict(m) for m in macros])
        self.apply()

    def save_hotstrings(self, items):
        self.config.set("hotstrings", [dict(h) for h in items])
        self.apply()

    def set_hotstrings_enabled(self, on):
        self.config.set("hotstrings_enabled", bool(on))
        self.apply()

    def import_ahk(self, text):
        macros, hotstrings, skipped = parse_ahk(text)
        existing_keys = {m.get("hotkey", "").lower() for m in self.macros}
        new_macros = [m for m in macros if m["hotkey"].lower() not in existing_keys]
        existing_triggers = {h.get("trigger") for h in self.hotstrings}
        new_hs = [h for h in hotstrings if h["trigger"] not in existing_triggers]
        self.config.set("automations", self.macros + new_macros)
        self.config.set("hotstrings", self.hotstrings + new_hs)
        self.apply()
        return len(new_macros), len(new_hs), skipped

    # ----------------------------------------------------------- engine
    def apply(self):
        """(Re)register all hotkeys and reload hotstrings."""
        if self.hotkeys is not None:
            for hid in list(self._id_to_macro):
                self.hotkeys.unregister(hid)
        self._id_to_macro.clear()
        self.status.clear()
        for i, macro in enumerate(self.macros):
            hotkey = (macro.get("hotkey") or "").strip()
            if not hotkey or not macro.get("enabled", True):
                continue
            hid = HOTKEY_ID_BASE + i
            if self.hotkeys is not None and self.hotkeys.available:
                if self.hotkeys.register(hid, hotkey):
                    self._id_to_macro[hid] = macro
                else:
                    self.status[hotkey] = self.hotkeys.last_error or "could not register"
        self.engine.set_hotstrings(self.hotstrings)
        if self.hotstrings_enabled and self.hotstrings:
            self.engine.start()
        else:
            self.engine.stop()
        self.changed.emit()

    def shutdown(self):
        self.engine.stop()
        if self.keep_awake:
            win_input.set_keep_awake(False)

    def _on_hotkey(self, hotkey_id):
        macro = self._id_to_macro.get(hotkey_id)
        if macro:
            self.run_macro(macro, from_hotkey=True)

    def _after_modifiers_released(self, fn, timeout_ms=1500):
        """Run fn once Ctrl/Alt/Shift/Win are up so they don't mangle typed keys."""
        deadline = time.monotonic() + timeout_ms / 1000

        def check():
            if win_input.modifiers_down() and time.monotonic() < deadline:
                QTimer.singleShot(25, check)
            else:
                fn()
        check()

    def _on_hotstring(self, trigger, replacement, delete_count, end_char):
        text = expand_tokens(replacement)

        def do():
            win_input.tap_vk(win_input.VK_BACK, delete_count) if delete_count > 0 else None
            if len(text) > 150:
                self._paste(text)
                if end_char:
                    QTimer.singleShot(120, lambda: win_input.send_text(end_char))
            else:
                win_input.send_text(text + end_char)
        self._after_modifiers_released(do, 600)

    def _paste(self, text):
        clip = QApplication.clipboard()
        previous = clip.text()
        if self.clipboard_service is not None:
            self.clipboard_service.pause(1500)
        clip.setText(text)
        QTimer.singleShot(40, lambda: win_input.send_combo("Ctrl+V"))
        QTimer.singleShot(500, lambda: clip.setText(previous))

    # ---------------------------------------------------------- actions
    def run_macro(self, macro, from_hotkey=False):
        action, arg = macro.get("action", ""), str(macro.get("arg", "") or "")
        if action in TYPING_ACTIONS:
            self._after_modifiers_released(lambda: self.run_action(action, arg))
        elif action in WINDOW_ACTIONS and not from_hotkey:
            # Triggered from the island UI: give focus back to the previous window first
            self.island_actions.get("collapse", lambda: None)()
            QTimer.singleShot(250, lambda: self.run_action(action, arg))
        else:
            self.run_action(action, arg)

    def run_action(self, action, arg=""):
        try:
            return self._run_action(action, arg)
        except Exception as e:
            print(f"[automation] {action} failed: {e}")
            self.feedback.emit(f"⚠️ {action_label(action)} failed")
            return False

    def _run_action(self, action, arg):
        arg = arg.strip() if action not in ("type", "paste") else arg
        if action == "run":
            return open_target(arg)
        if action == "command":
            subprocess.Popen(arg, shell=True)
            return True
        if action == "powershell":
            return win_input.run_hidden(["powershell", "-NoProfile", "-Command", arg])
        if action == "ahk":
            return open_target(arg)
        if action == "type":
            return win_input.send_text(expand_tokens(arg))
        if action == "paste":
            self._paste(expand_tokens(arg))
            return True
        if action == "send":
            ok = True
            for combo in [c for c in arg.split(",") if c.strip()]:
                ok = win_input.send_combo(combo.strip()) and ok
            return ok
        if action == "win_top":
            state = win_input.toggle_always_on_top()
            if state is not None:
                self.feedback.emit("📌 Pinned on top" if state else "📌 Unpinned")
            return state is not None
        if action in ("win_center", "win_left", "win_right"):
            return win_input.move_window(action[4:])
        if action in ("win_max", "win_min", "win_close"):
            return win_input.window_command({"win_max": "maximize", "win_min": "minimize",
                                             "win_close": "close"}[action])
        if action in _SIMPLE_VK:
            return win_input.tap_vk(_SIMPLE_VK[action])
        if action in ("bright_up", "bright_down"):
            step = int(arg) if arg.isdigit() else 10
            self.feedback.emit("☀️ Brighter" if action == "bright_up" else "🌙 Dimmer")
            return win_input.change_brightness(step if action == "bright_up" else -step)
        if action == "keep_awake":
            self.set_keep_awake(not self.keep_awake)
            return True
        if action == "dark_mode":
            dark = win_input.toggle_dark_mode()
            if dark is not None:
                self.feedback.emit("🌙 Dark mode" if dark else "☀️ Light mode")
            return dark is not None
        if action == "screenshot":
            return open_target("ms-screenclip:")
        if action == "show_desktop":
            return win_input.send_combo("Win+D")
        if action == "lock":
            return win_input.lock_pc()
        if action == "sleep":
            return win_input.sleep_pc()
        if action == "focus":
            minutes = float(arg) if arg.replace(".", "", 1).isdigit() else 25
            self.island_actions.get("focus", lambda m: None)(minutes)
            return True
        if action == "island_tab":
            self.island_actions.get("open_tab", lambda n: None)(arg.lower() or "media")
            return True
        if action in ("add_task", "water", "pomodoro"):
            self.island_actions.get(action, lambda *_: None)(arg) if action == "add_task" else \
                self.island_actions.get(action, lambda: None)()
            return True
        if action in ("island_toggle", "quick_note", "see_screen", "through_toggle", "command_bar",
                      "island_visibility", "style_toggle"):
            self.island_actions.get(action, lambda: None)()
            return True
        print(f"[automation] Unknown action: {action}")
        return False

    def set_keep_awake(self, on):
        self.keep_awake = bool(on)
        win_input.set_keep_awake(self.keep_awake)
        self.keep_awake_changed.emit(self.keep_awake)
        self.feedback.emit("☕ Staying awake" if self.keep_awake else "😴 Normal sleep")
