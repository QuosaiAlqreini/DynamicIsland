"""Best guess at which program already owns a global hotkey.

Windows has no way to ask who registered a hotkey, so this matches the
combination against well-known defaults and checks which of those apps are
running right now. It is a hint, not a certainty.
"""
import psutil

# combo (lowercase, modifiers sorted) -> [(process name starts with, app label)]
KNOWN = {
    "alt+ctrl+space": [("claude", "Claude desktop app (quick entry)")],
    "ctrl+shift+space": [("1password", "1Password (Quick Access)"), ("claude", "Claude desktop app")],
    "alt+space": [("chatgpt", "ChatGPT desktop app"), ("powertoys", "PowerToys Run"),
                  ("flow.launcher", "Flow Launcher"), ("claude", "Claude desktop app"),
                  ("raycast", "Raycast")],
    "alt+win+space": [("powertoys", "PowerToys Command Palette")],
    "alt+shift+space": [("powertoys", "PowerToys"), ("wox", "Wox")],
    "alt+z": [("nvidia", "NVIDIA overlay"), ("nvcontainer", "NVIDIA overlay")],
    "alt+r": [("nvidia", "NVIDIA overlay"), ("amd", "AMD Software")],
    "alt+f9": [("nvidia", "NVIDIA overlay (recording)")],
    "ctrl+shift+m": [("discord", "Discord (mute)")],
    "ctrl+shift+d": [("discord", "Discord (deafen)")],
    "ctrl+shift+c": [("powertoys", "PowerToys Color Picker")],
    "shift+win+c": [("powertoys", "PowerToys Color Picker")],
    "shift+win+t": [("powertoys", "PowerToys Text Extractor")],
    "ctrl+win+v": [("powertoys", "PowerToys Advanced Paste")],
    "alt+ctrl+v": [("powertoys", "PowerToys / clipboard tool")],
    "ctrl+shift+s": [("sharex", "ShareX"), ("lightshot", "Lightshot")],
    "alt+ctrl+t": [("windowsterminal", "Windows Terminal (if set)")],
}
# Apps that commonly register global hotkeys (used when the combo itself is unknown)
HOTKEY_APPS = {"powertoys": "PowerToys", "discord": "Discord", "claude": "Claude", "chatgpt": "ChatGPT",
               "sharex": "ShareX", "autohotkey": "AutoHotkey", "nvidia": "NVIDIA overlay",
               "nvcontainer": "NVIDIA overlay", "steam": "Steam", "obs": "OBS", "1password": "1Password",
               "flow.launcher": "Flow Launcher", "everything": "Everything", "ditto": "Ditto",
               "greenshot": "Greenshot", "lightshot": "Lightshot", "teams": "Teams", "slack": "Slack",
               "spotify": "Spotify", "raycast": "Raycast", "logioptions": "Logi Options", "razer": "Razer Synapse"}
_MOD_ALIASES = {"control": "ctrl", "meta": "win"}


def normalize(combo):
    parts = [_MOD_ALIASES.get(p.strip().lower(), p.strip().lower()) for p in (combo or "").split("+") if p.strip()]
    mods = sorted(p for p in parts if p in ("ctrl", "alt", "shift", "win"))
    keys = [p for p in parts if p not in ("ctrl", "alt", "shift", "win")]
    return "+".join(mods + keys)


def running_process_names():
    names = set()
    try:
        for proc in psutil.process_iter(["name"]):
            if proc.info.get("name"):
                names.add(proc.info["name"].lower())
    except Exception:
        pass
    return names


def guess_owner(combo, running=None):
    """Short human hint: who probably uses this shortcut."""
    key = normalize(combo)
    running = running_process_names() if running is None else {n.lower() for n in running}

    def is_running(prefix):
        return any(n.startswith(prefix) for n in running)

    candidates = KNOWN.get(key, [])
    live = [label for prefix, label in candidates if is_running(prefix)]
    if live:
        return "Probably used by " + " or ".join(dict.fromkeys(live)) + " (it's running)"
    if key.startswith("win+") or "+win+" in "+" + key + "+" or key.split("+")[0] == "win":
        return "Probably reserved by Windows itself (Win-key shortcuts)"
    if candidates:
        return "Often used by " + " or ".join(dict.fromkeys(label for _p, label in candidates))
    others = list(dict.fromkeys(label for prefix, label in HOTKEY_APPS.items() if is_running(prefix)))
    if others:
        return "Taken by another running app. Likely candidates: " + ", ".join(others[:4])
    return "Taken by another app or by Windows (Windows doesn't say which)"
