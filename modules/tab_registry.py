"""Tab keys -> (icon, label, tooltip). Order here is the default display order."""
TAB_REGISTRY = {
    "media": ("🎵", "Media", "Media controls"),
    "shelf": ("📥", "Shelf", "Dropped files + clipboard history"),
    "tasks": ("✅", "Tasks", "To-do list with timed reminders"),
    "notes": ("📝", "Notes", "Quick scratchpad"),
    "focus": ("⏱️", "Focus", "Focus timer + build tracker"),
    "day": ("💧", "Day", "Water tracker and prayer times"),
    "keys": ("⌨️", "Keys", "Automations: hotkeys, hotstrings, laptop toggles"),
    "info": ("ℹ️", "Info", "Your own info: world clocks, countdowns, command output"),
    "ai": ("🤖", "AI", "AI Companion"),
    "system": ("⚡", "Sys", "System telemetry"),
    "tools": ("🛠️", "Tools", "Launchers & utilities"),
}
DEFAULT_TABS = ["media", "shelf", "tasks", "notes", "focus", "day", "keys", "ai", "system", "tools"]
