"""Tab keys -> (icon, label, tooltip). Order here is the default display order."""
TAB_REGISTRY = {
    "home": ("🏠", "Home", "Dashboard: your AI, music, focus, time, settings"),
    "media": ("🎵", "Media", "Media controls"),
    "agents": ("👾", "Robo", "Robo the AI: ask anything, see the screen, fix clipboard code; follow Claude Code / Codex"),
    "shelf": ("📥", "Shelf", "Dropped files + clipboard history"),
    "tasks": ("✅", "Tasks", "To-do list with timed reminders"),
    "notes": ("📝", "Notes", "Quick scratchpad"),
    "focus": ("⏱️", "Focus", "Focus timer + build tracker"),
    "day": ("💧", "Day", "Water tracker and prayer times"),
    "keys": ("⌨️", "Keys", "Automations: hotkeys, hotstrings, laptop toggles"),
    "info": ("ℹ️", "Info", "Your own info: world clocks, countdowns, command output"),
    "system": ("⚡", "Sys", "System telemetry"),
    "tools": ("🛠️", "Tools", "Launchers & utilities"),
}
DEFAULT_TABS = ["home", "agents", "media", "shelf", "tasks", "notes", "focus", "day", "keys", "system", "tools"]
