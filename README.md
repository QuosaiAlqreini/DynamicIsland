# 🏝️ Dynamic Island for Windows (Antigravity & Claude Code Edition)

<p align="center">
  <b>A fluid, glassmorphic Dynamic Island overlay for Windows 10 & 11, featuring native media controls, real-time hardware telemetry, AI Screen Vision pair-programming, multi-provider AI accounts (Gemini, Claude, OpenAI, Ollama), and a MacBook-style Taskbar customizer inspired by Windhawk Taskbar Styler.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d4?style=for-the-badge&logo=windows" />
  <img src="https://img.shields.io/badge/Language-Python%203.12-3776ab?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/UI-PyQt6-41cd52?style=for-the-badge&logo=qt" />
  <img src="https://img.shields.io/badge/Vision%20AI-Multimodal-ec4899?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Taskbar-MacBook%20Vibe-10b981?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-purple?style=for-the-badge" />
</p>

---

## ✨ Features

### 1. 🏝️ Fluid Adaptive Island
* **Apple Dynamic Island Aesthetics:** Anti-aliased rounded pill geometry, glowing borders, and hardware-accelerated spring animations (`QEasingCurve.OutCubic`).
* **Idle Pill Mode:** Compact (210×36px) glanceable pill showing the live time, battery indicator, audio wave animation, and a pulsating glowing dot reflecting the AI agent's active state.
* **Smart Hover Expansion:** Hover over the island to smoothly morph into an expanded multi-tab dashboard. Move away, and it tucks back into a pill.
* **Drag & Snap Placement:** Left-click and drag the island anywhere along the top edge of your screen. Release it near the middle to smoothly snap to center.
* **Notch Mode:** Toggle top-edge flush docking (like a MacBook notch or Notch Nook) or a floating pill.

### 2. 🎨 Make It Yours: Customize Island & Smart Hiding (NEW!)
Right-click the island (or the tray icon) ➔ **`🎨 Customize Island…`**. A live preview of the pill updates as you change things.
* **💊 Pill:** choose what the left, middle and right of the small pill show: the AI status dot, a clock (with or without seconds), the date, a battery icon or %, CPU, RAM, the song that's playing, or any of your own info items. You can also change the pill's width. The default stays the classic AI dot · clock · battery.
* **🗂️ Tabs:** tick the tabs you want and drag them into your order. `Ctrl+1..9` follows your order.
* **ℹ️ Info (add your own info to the island):**
  * **World clock:** `Asia/Riyadh`, `Europe/London`, or an offset like `+3`.
  * **Countdown:** to a date like `2026-12-25 18:00`.
  * **Custom text:** a reminder or a status line.
  * **Command output:** the first line a command prints, refreshed every N seconds. For example, weather with `curl -s "wttr.in/?format=%t+%C"`.
  * Every item gets a card in the **ℹ️ Info** tab, and you can put any of them in the pill.
* **👻 It never blocks what's under it (click-through pill, on by default):**
  * Clicks on the folded pill go straight to the browser tab, title bar or button underneath, and the pill fades while your cursor is over it so you can see what you're clicking.
  * To open the island, push the cursor against the top edge of the screen above the pill for a moment, or press `Ctrl+Alt+Space`. You can switch this to "rest the cursor on the pill" or "hotkey only".
  * A click never makes it pop open under your cursor.
  * Dragging a file onto the pill still works: hold it over the pill for a moment.
  * Toggle with `Ctrl+Alt+G`, the tray menu, or the right-click menu.
  * **Position:** shift the island left or right along the top edge (Customize → Visibility), or drag it when click-through is off. It opens where it sits.
* **👁️ Visibility:**
  * **Hide in full screen:** the island disappears while a game, video, presentation or full-screen (F11) browser is in front, and comes back when you leave. `Ctrl+Alt+Space` still opens it if you need it.
  * **Hide at the top:** the island tucks away above the screen and slides down when your cursor touches the top edge near it. Optionally it peeks down for finished timers, builds and alerts. Quick toggle: right-click ➔ `🫥 Hide at Top`.
  * Hover/click-to-open, notch mode and theme are all in one place.

### 🪄 Smooth & easy (NEW in 1.6)
* **Roomier, smoother notch:** the notch has more space, soft curved shoulders and no outline, and its content stays clear of the curves. Choose **Compact / Comfortable / Roomy** size.
* **Gentle motion:** the island opens with a soft spring and closes smoothly. Hiding, auto-hide and full screen all glide up into the top edge and fade, and it slides back down when it returns.
* **Easier to find your way:** the open tab shows its name next to its icon.
* **One settings window with a sidebar:** Look & pill · Tabs · My info · Visibility · Shortcuts · Day, AI & more. Every change shows on the island immediately; **Cancel** undoes everything, **Done** keeps it.
* **Change the main shortcuts without restarting:** Customize ➔ ⌨️ Shortcuts. You're warned right there if another app already uses one.

### 🌙 Daily Life: Tasks, Water, Prayer Times, Pomodoro, Lyrics & Command Bar (NEW in 1.5)
* **✅ Tasks & reminders:** type a task the way you'd say it: `Call mom at 17:30`, `Stretch in 20m`, `Report tomorrow 9am`. When it's due, the pill shows it, Windows shows a notification, and you can snooze it (10 min or 1 hour) or tick it off. Tasks sort by time.
* **💧 Water tracker:** a ring fills as you log glasses toward your daily goal, with optional reminders. Put the ring in the pill from Customize.
* **🕌 Prayer times (optional, off by default):** calculated on your PC, shown with a sun arc, a reminder at each prayer and an option to pause music.
  * **Location:** pick a country and city (50+ German cities, plus Austria, Switzerland, the Netherlands, Belgium, France, the UK, Scandinavia, the Middle East and more), or **search any town** (only the town name is sent to open-meteo.com), or type coordinates.
  * **Methods:** MWL, Diyanet/DITIB, Umm al-Qura, Egyptian, ISNA, UOIF (France), Karachi, Gulf, Kuwait, JAKIM, Kemenag; Hanafi Asr option.
  * **Northern summers:** in Germany and further north the sky never gets fully dark in summer, so Fajr and Isha use a rule you choose (angle-based, one-seventh of the night, or middle of the night).
  * **Match your mosque:** adjust each prayer by a few minutes so the times match your local mosque's timetable exactly. A live preview shows today's times as you change settings.
* **🍅 Pomodoro:** the 🍅 button in Focus runs 4 rounds of 25 min focus with 5 min breaks and a long break at the end, moving on automatically. Click it again to skip a phase.
* **🎵 Synced lyrics and real volume:** the Media tab shows the line being sung (from the open LRCLIB database; only the song title and artist are sent, and you can turn it off in Customize). The volume slider and mute button now control the real Windows volume.
* **🔎 Command bar (`Alt+Space`):** one box for everything:
  * type an app name to launch it
  * `2*(3+4)` or `sqrt(16)` to calculate (Enter copies the answer)
  * `timer 10m`, `pomodoro`, `water`
  * `remind Call mom at 17:30`, `note buy milk`
  * `upper`, `lower`, `base64`, `json`, `urlencode`… to transform whatever is on your clipboard
  * `> ipconfig` to run a command, a tab or automation name to open it, or anything else to search the web
* **Mouse wheel and ← → keys** switch pages while the island is open.
* **Hide for chosen apps:** list programs (e.g. `vlc.exe`) in Customize → Visibility and the island hides while one is in front.

### 3. 🧲 Notch Productivity: Shelf, Clipboard, Notes, Focus & Builds (NEW!)
Make the island the one place you reach for, instead of hunting through windows.
* **📥 Shelf (drop tray):** Drag files onto the island from anywhere; it pops open on the Shelf tab. Drag them back out into mail, chat, a browser upload or another folder later. Open, show in Explorer, copy path, or remove. The pill shows a badge with how many files are parked.
* **📋 Clipboard history:** Your recent copies sit next to the shelf. Click one to copy it again; 📌 pin the ones you reuse. Unpinned history stays in memory only and is never written to disk.
* **📝 Quick Notes:** An autosaving scratchpad. Drop text on the island to append it; insert timestamps or paste the clipboard in one click.
* **⏱️ Focus timer:** 5/25/50-minute presets or custom minutes, with pause, +5m and stop. The countdown runs as a live activity in the pill with a progress bar.
* **🔨 Build & task tracker:** Long-running builds, installs and test runs (`npm run build`, `cargo build`, `pytest`, `docker build`, `dotnet build`, `gradle`, ...) are detected automatically and shown as a live activity. When one finishes you get a pill flash and a Windows toast with its duration. Edit `build_watch_patterns` in the config to add your own.
* **📌 Pinned launchers:** One-click buttons in the Tools tab for apps, folders, files or URLs (`＋` to add, right-click to unpin).

### 4. ⚡ Quick Reach (less fuss)
* **Global hotkey `Ctrl+Alt+Space`:** Opens or closes the island from any app (configurable in Preferences).
* **Click to open:** Click the pill instead of hovering and waiting. **Middle-click** plays or pauses media. **Left-click the tray icon** to open the island.
* **Keyboard:** `Ctrl+1..8` jumps to a tab, `Ctrl+Tab` cycles tabs, `Esc` closes. Clicking anywhere else also closes it.
* **Stays open while you work:** It doesn't collapse while you're typing a note or dragging a file out.
* **Remembers your last tab.**

### 5. ⌨️ Automations — built-in AutoHotkey (NEW!)
A system-wide hotkey and text-expansion engine, so Dynamic Island can replace a pile of separate utilities. Open it from the **⌨️ Keys** tab → `✏️ Edit`, right-click ➔ `⌨️ Automations & Hotkeys…`, or the tray.
* **Custom global hotkeys → actions.** Record any shortcut (F-keys, Pause, `CapsLock` etc. can be used alone) and bind it to:
  * **Apps & files:** open an app/file/folder/URL, run a command, run hidden PowerShell, or run a real `.ahk` script.
  * **Typing:** type text, paste long text, or send key combos (`Ctrl+Shift+T, Enter`). Tokens: `{date}` `{time}` `{datetime}` `{clipboard}`.
  * **Windows:** toggle always-on-top, center, snap left/right, maximize/restore, minimize, close.
  * **Laptop:** volume, mute, media keys, screen brightness up/down, ☕ keep awake, dark/light mode, screenshot, show desktop, lock, sleep.
  * **Island:** open/close, jump to a tab, quick note, start a focus timer, AI look at my screen.
* **Hotstrings (text expansion, off until you turn it on in the ⌨️ Keys tab):** type `;date` + Space and it becomes today's date in any app. Supports instant triggers (AHK's `*` option). Only the current word is ever held in memory.
* **Import AutoHotkey scripts:** paste or open a `.ahk` file (v1 or v2). Simple hotkeys (`Run`, `Send`, remaps like `CapsLock::Esc`, `AlwaysOnTop`, `WinMinimize`...) and one-line hotstrings are converted; anything more complex is listed so you can run it with the "Run AutoHotkey script" action.
* **One-click panel:** the **⌨️ Keys** tab shows every automation as a button, plus toggles for hotstrings and keep-awake.
* **Start with Windows:** Preferences ➔ `🚀 Start Dynamic Island when I sign in`.

**Starter hotkeys** (change or delete them any time):

| Hotkey | Action |
|---|---|
| `Ctrl+Alt+Space` | Open / close the island |
| `Ctrl+Alt+T` | Windows Terminal |
| `Ctrl+Alt+N` | Quick note |
| `Ctrl+Alt+V` | Shelf & clipboard history |
| `Ctrl+Alt+P` | Pin current window on top |
| `Ctrl+Alt+C` | Center current window |
| `Ctrl+Alt+K` | Keep awake on/off |
| `Ctrl+Alt+F` | 25-minute focus timer |
| `Ctrl+Alt+PgUp / PgDown` | Screen brightness |
| `Ctrl+Alt+D` | Dark / light mode |

Starter hotstrings: `;date`, `;time`, `;now`, `;shrug`, `;ty`.

### 6. 👀 AI Screen Vision & Multimodal Pair Programming (NEW!)
* **Live Screen Inspection:** Click **`👁️ See Screen`** in the AI Companion tab to capture your screen in real time.
* **Multimodal Analysis:** The AI can see your IDE code, terminal compiler errors, browser layouts, or design mockups and provide immediate assistance.
* **Auto-Attach Screen Context:** Option in Settings to automatically attach a desktop screenshot to your prompt questions.

### 7. 🤖 Multi-Provider AI Accounts & Free Tier Connections (NEW!)
Open the Preferences dialog (Right-click ➔ `⚙️ Preferences & AI Accounts` or click `⚙️` in the AI tab) to connect your preferred provider:
* **Google Gemini (Recommended Free Tier):** Generous 100% free API tier (15 RPM / 1M TPM) available via Google AI Studio without credit card.
* **Anthropic Claude:** Industry-leading Claude 3.5 Sonnet Vision for state-of-the-art coding assistance.
* **OpenAI:** GPT-4o & GPT-4o-mini multimodal vision.
* **Ollama (100% Free, Local & Private):** Connects to `http://localhost:11434` for completely offline vision & text models (e.g. `llama3.2-vision`, `llava`, `deepseek-r1`).
* **Claude Code / Antigravity CLI Local Bridge:** Connects to your active local developer CLI sessions.
* **Connection Tester:** Real-time ping button verifying API keys, models, and network latency.

### 8. 🍏 Taskbar Customizer & MacBook Vibe (Windhawk Styler Integration) (NEW!)
Because Dynamic Island already provides the clock, battery percentage, volume, and media player at the top of your screen, these options become redundant on the Windows taskbar!
* **MacBook Clean Desktop Vibe (Auto-Hide Taskbar):** One-click toggle that automatically tucks away the Windows taskbar, leaving only the Dynamic Island at the top. The taskbar only slides in when your cursor touches the bottom edge.
* **Windhawk Windows 11 Taskbar Styler Presets:** Direct XAML profiles ready to copy with one click:
  * **MacBook DockLike Theme:** Floats the taskbar as a centered rounded pill dock.
  * **Translucent Acrylic Glass:** Transforms the taskbar into transparent frosted glass.
  * **Clean Desk (Hide Redundant Clock & Tray):** Hides the duplicate taskbar clock, date, and tray icons.

### 9. 🎵 Native Windows Media Transport Controls
* Integrates directly with Windows System Media Transport Controls (`winsdk`) to detect music playing from **Spotify**, **Chrome**, **Edge**, **Apple Music**, or **Windows Media Player**.
* **Controls:** One-tap Play/Pause, Next Track, Previous Track.
* **Audio Visualizer:** Dynamic multi-bar animated waveform reacting during playback.
* **Progress Bar:** Real-time track timeline tracking.

### 10. ⚡ Real-Time Hardware Performance Telemetry
* Circular animated SVG/Canvas gauges for:
  * **CPU Load %**
  * **RAM Usage %** (with live used / total GB)
  * **Battery %** (with charging status & power source indicator)
* System uptime monitor.

### 11. 🛠️ Quick Utilities & Shortcuts
* Master **Volume Slider** with live percentage and instant mute toggle.
* One-click **Windows Snipping Tool** (`ms-screenclip:`).
* One-click **PowerShell Terminal** launcher.
* One-click **Task Manager** launcher.
* **Focus / Do Not Disturb Mode** toggle.

### 12. 🎨 5 Curated Themes
Right-click the island or tray icon to instantly switch themes:
1. **Obsidian Dark (Default):** Deep OLED black with neon cyan and violet accents.
2. **Cyberpunk Neon:** Midnight purple with electric hot pink and cyan glow.
3. **Nord Arctic:** Crisp Scandinavian slate with ice blue accents.
4. **Glassmorphism:** Frosted translucent glass with bright rim lighting.
5. **Porcelain Light:** Clean modern light theme with deep charcoal typography.

---

## ⬇️ Download & Install (no Python needed)

1. Go to the **[latest release](https://github.com/QuosaiAlqreini/DynamicIsland/releases/latest)**.
2. Download **`DynamicIsland-x.y.z-Setup.exe`** and run it.
   * Installs for your user only (no admin needed), adds Start menu / desktop shortcuts, and can start the island when you sign in.
   * Windows may say *"Windows protected your PC"* because the app isn't code-signed yet: click **More info → Run anyway**.
3. Prefer no installer? Download **`DynamicIsland-x.y.z-portable.zip`**, unzip it anywhere and run `DynamicIsland.exe`.

Uninstall from **Settings → Apps → Installed apps → Dynamic Island**. Your settings live in `%USERPROFILE%\.dynamic_island\config.json`.

**Building it yourself:** run `powershell -ExecutionPolicy Bypass -File build.ps1` (needs Python 3.10+; install [Inno Setup 6](https://jrsoftware.org/isdl.php) to also get the Setup.exe). Every push is built and tested on Windows by GitHub Actions, and pushing a `v*` tag publishes a release.

---

## 🚀 Quick Start (from source)

### Prerequisites
* Windows 10 or 11
* Python 3.10+ (Python 3.12 recommended)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/QuosaiAlqreini/DynamicIsland.git
   cd DynamicIsland
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Dynamic Island:**
   ```bash
   python app.py
   ```
   *(Or simply double-click [`run.bat`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/run.bat))*

---

## ⚙️ Connecting Your AI Account (Free Tier)

1. Hover over the Island, click the **🤖 AI Companion** tab, and click the **⚙️** icon in the header (or right-click the island ➔ `⚙️ Preferences & AI Accounts`).
2. Choose **Google Gemini** from the AI Provider dropdown.
3. Click **"🔗 Get Free Account / API Key"** to open [Google AI Studio](https://aistudio.google.com/app/apikey) in your browser.
4. Copy your key, paste it into the **API Key** field, and click **⚡ Test Connection**.
5. Click **Save Settings**! Now you can click **`👁️ See Screen`** anytime for instant vision pair-programming!

---

## 🍏 Setting Up the MacBook Taskbar Look

To achieve the clean macOS look without duplicated taskbar icons:
1. Right-click the Island and click **"🍏 MacBook Mode (Auto-Hide Taskbar)"**.
   * *Your Windows taskbar will auto-hide, leaving your wallpaper and the Dynamic Island clean at the top.*
2. For an authentic floating dock, open Preferences ➔ **Taskbar & MacBook Vibe**:
   * Select **"MacBook DockLike"** or **"Clean Desk (Hide Redundant Clock & Tray)"**.
   * Click **"📋 Copy Preset XAML for Windhawk"**.
   * Open [Windhawk's Windows 11 Taskbar Styler mod](https://windhawk.net/mods/windows-11-taskbar-styler) and paste the styles!

---

## ⌨️ Controls & Interactions

| Action | How to Trigger |
|---|---|
| **Expand Dashboard** | Hover over the pill, click it, or press `Ctrl+Alt+Space` anywhere |
| **Park files on the Shelf** | Drag files onto the island, then drag them out when you need them |
| **Reuse a copied snippet** | `📥 Shelf` tab → click a clipboard entry (📌 to pin) |
| **Quick note** | `📝 Notes` tab, or right-click / tray ➔ `📝 Quick Note` |
| **Focus timer** | `⏱️ Focus` tab, or right-click ➔ `⏱️ Start Focus Timer` |
| **Customize pill, tabs & info** | Right-click ➔ `🎨 Customize Island…` |
| **Open the island (click-through on)** | Push the cursor against the top edge above the pill, or `Ctrl+Alt+Space` |
| **Click-through on / off** | `Ctrl+Alt+G`, or tray ➔ `👻 Click-Through Pill` |
| **Hide at the top** | Right-click ➔ `🫥 Hide at Top`, then touch the top edge to show it |
| **Jump to a tab** | `Ctrl+1..9`, `Ctrl+Tab` to cycle, `Esc` to close |
| **Show / hide the island** | `Ctrl+Alt+H`, tray ➔ `🙈 Hide Island` / `👁️ Show Island`, or right-click ➔ `🙈 Hide Island` |
| **Island or notch look** | Tray icon ➔ `📱 Look: Island or Notch`, `Ctrl+Alt+J`, or Customize ➔ 💊 Pill ➔ Look |
| **Command bar** | `Alt+Space` |
| **Add a task / reminder** | `✅ Tasks` tab, or command bar: `remind Call mom at 17:30` |
| **Switch pages** | Mouse wheel or `←` `→` while the island is open |
| **Edit automations** | `⌨️ Keys` tab ➔ `✏️ Edit`, or right-click ➔ `⌨️ Automations & Hotkeys…` |
| **Play / Pause** | Middle-click the island |
| **Collapse Dashboard** | Move your cursor away, click elsewhere, or press `Esc` |
| **Move / Reposition** | Left-click and drag the pill across the top edge |
| **Snap to Center** | Release the pill near the center of your screen |
| **AI Screen Vision** | Open `🤖 AI Companion` tab and click `👁️ See Screen` |
| **Open Preferences** | Click `⚙️` in AI tab or right-click pill ➔ `⚙️ Preferences & AI Accounts` |
| **Toggle MacBook Mode** | Right-click pill ➔ `🍏 MacBook Mode (Auto-Hide Taskbar)` |
| **Switch Tabs** | Click `🎵 Media`, `📥 Shelf`, `📝 Notes`, `⏱️ Focus`, `⌨️ Keys`, `🤖 AI`, `⚡ Sys`, or `🛠️ Tools` |
| **Change Theme** | Right-click ➔ `Select Theme` (Obsidian, Cyberpunk, Nord, Glassmorphic, Porcelain) |
| **Toggle Notch Mode** | Right-click ➔ `Toggle Notch Mode (Top Flush)` |
| **Exit** | Right-click ➔ `Exit Dynamic Island` |

---

## 🏗️ Project Architecture

```
DynamicIsland/
├── app.py                     # Main application entry point & Windows System Tray
├── island_window.py           # Core frameless floating window & spring animation physics
├── config.py                  # User settings manager (~/.dynamic_island/config.json)
├── styles.py                  # 5 distinct theme color palettes & QSS styling
├── modules/
│   ├── pill_idle.py           # Compact idle pill (clock, battery, mini wave, agent glow)
│   ├── media_widget.py        # Windows media card (title, artist, controls, animated visualizer)
│   ├── system_widget.py       # Hardware monitor (circular gauges for CPU, RAM, Battery)
│   ├── ai_agent_widget.py     # AI Companion Hub (screen vision, prompt bar, clipboard fixer, Ralph & CodeRabbit)
│   ├── quick_tools_widget.py  # Quick Utilities HUD (volume, screenshot, terminal, pinned launchers)
│   ├── shelf_widget.py        # File drop shelf (drag in / drag out) + clipboard history
│   ├── notes_widget.py        # Autosaving quick notes scratchpad
│   ├── focus_widget.py        # Focus timer + build/task tracker
│   ├── customize_dialog.py    # Customize Island: pill slots, tabs, info items, visibility
│   ├── info_widget.py         # Info tab cards for your own info items
│   ├── tab_registry.py        # Tab names/icons and default order
│   ├── keys_widget.py         # One-click automations panel + hotstring / keep-awake toggles
│   ├── automation_dialog.py   # Hotkey recorder, action editor, hotstrings table, .ahk importer
│   └── settings_dialog.py     # Preferences Dialog (AI accounts, free tiers, screen vision, taskbar styler)
├── services/
│   ├── media_service.py       # Winsdk Windows Media Session integration + demo fallback
│   ├── system_service.py      # Psutil hardware metrics collector
│   ├── ai_service.py          # AI agent status, screen capture & multimodal API dispatch
│   ├── taskbar_service.py     # Windows taskbar auto-hide controller & Windhawk XAML presets
│   ├── clipboard_service.py   # Clipboard history (memory only, pinned items persisted)
│   ├── focus_timer_service.py # Focus / Pomodoro countdown
│   ├── build_watch_service.py # Detects long builds/tests via psutil (background thread)
│   ├── hotkey_service.py      # Global hotkeys via Win32 RegisterHotKey
│   ├── info_service.py        # World clocks, countdowns, custom text, command output
│   ├── automation_service.py  # Action engine, macro registration, AutoHotkey script converter
│   ├── hotstring_engine.py    # Text expansion via low-level keyboard hook
│   ├── win_input.py           # SendInput typing, window control, brightness, keep-awake, dark mode
│   └── launcher.py            # Open apps/files/folders/URLs, reveal in Explorer
├── version.py                 # App version (used by the build & installer)
├── build.ps1                  # Builds DynamicIsland.exe, portable zip and Setup.exe
├── packaging/                 # Inno Setup installer script + icon generator
├── assets/                    # App icon
├── tests/                     # pytest suite (runs on Windows in CI)
├── .github/workflows/         # Windows build, test & release pipeline
├── requirements.txt           # Python dependencies
├── run.bat                    # Double-click Windows launcher
└── prd.json                   # Ralph Loop specification & quality checks
```

---

## 🤖 Built-in AI Tooling

This repository also includes standard configurations for pair-programming with AI:
* [`.coderabbit.yaml`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/.coderabbit.yaml) – CodeRabbit pre-merge review rules
* [`.roomodes`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/.roomodes) – Roo Code custom modes (Architect, Coder, Ralph Runner, Reviewer, Debugger)
* [`prd.json`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/prd.json) – Product Requirement Document for Ralph Loop
* [`ralph.ps1`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/ralph.ps1) – PowerShell autonomous test-driven iteration loop
* [`AGENTS.md`](file:///C:/Users/quoss/.gemini/antigravity-ide/scratch/DynamicIsland/AGENTS.md) – Universal pair programming rules

---

## 📜 License
MIT License. Created by [Quosai Alqreini](https://github.com/QuosaiAlqreini).
