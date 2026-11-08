"""Tab keys -> (icon, label, tooltip). Order here is the default display order."""
TAB_REGISTRY = {
    "media": ("🎵", "Media", "Media controls"),
    "shelf": ("📥", "Shelf", "Dropped files + clipboard history"),
    "notes": ("📝", "Notes", "Quick scratchpad"),
    "focus": ("⏱️", "Focus", "Focus timer + build tracker"),
    "keys": ("⌨️", "Keys", "Automations: hotkeys, hotstrings, laptop toggles"),
    "info": ("ℹ️", "Info", "Your own info: world clocks, countdowns, command output"),
    "ai": ("🤖", "AI", "AI Companion"),
    "system": ("⚡", "Sys", "System telemetry"),
    "tools": ("🛠️", "Tools", "Launchers & utilities"),
}
DEFAULT_TABS = ["media", "shelf", "notes", "focus", "keys", "ai", "system", "tools"]
