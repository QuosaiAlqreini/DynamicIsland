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

### 2. 👀 AI Screen Vision & Multimodal Pair Programming (NEW!)
* **Live Screen Inspection:** Click **`👁️ See Screen`** in the AI Companion tab to capture your screen in real time.
* **Multimodal Analysis:** The AI can see your IDE code, terminal compiler errors, browser layouts, or design mockups and provide immediate assistance.
* **Auto-Attach Screen Context:** Option in Settings to automatically attach a desktop screenshot to your prompt questions.

### 3. 🤖 Multi-Provider AI Accounts & Free Tier Connections (NEW!)
Open the Preferences dialog (Right-click ➔ `⚙️ Preferences & AI Accounts` or click `⚙️` in the AI tab) to connect your preferred provider:
* **Google Gemini (Recommended Free Tier):** Generous 100% free API tier (15 RPM / 1M TPM) available via Google AI Studio without credit card.
* **Anthropic Claude:** Industry-leading Claude 3.5 Sonnet Vision for state-of-the-art coding assistance.
* **OpenAI:** GPT-4o & GPT-4o-mini multimodal vision.
* **Ollama (100% Free, Local & Private):** Connects to `http://localhost:11434` for completely offline vision & text models (e.g. `llama3.2-vision`, `llava`, `deepseek-r1`).
* **Claude Code / Antigravity CLI Local Bridge:** Connects to your active local developer CLI sessions.
* **Connection Tester:** Real-time ping button verifying API keys, models, and network latency.

### 4. 🍏 Taskbar Customizer & MacBook Vibe (Windhawk Styler Integration) (NEW!)
Because Dynamic Island already provides the clock, battery percentage, volume, and media player at the top of your screen, these options become redundant on the Windows taskbar!
* **MacBook Clean Desktop Vibe (Auto-Hide Taskbar):** One-click toggle that automatically tucks away the Windows taskbar, leaving only the Dynamic Island at the top. The taskbar only slides in when your cursor touches the bottom edge.
* **Windhawk Windows 11 Taskbar Styler Presets:** Direct XAML profiles ready to copy with one click:
  * **MacBook DockLike Theme:** Floats the taskbar as a centered rounded pill dock.
  * **Translucent Acrylic Glass:** Transforms the taskbar into transparent frosted glass.
  * **Clean Desk (Hide Redundant Clock & Tray):** Hides the duplicate taskbar clock, date, and tray icons.

### 5. 🎵 Native Windows Media Transport Controls
* Integrates directly with Windows System Media Transport Controls (`winsdk`) to detect music playing from **Spotify**, **Chrome**, **Edge**, **Apple Music**, or **Windows Media Player**.
* **Controls:** One-tap Play/Pause, Next Track, Previous Track.
* **Audio Visualizer:** Dynamic multi-bar animated waveform reacting during playback.
* **Progress Bar:** Real-time track timeline tracking.

### 6. ⚡ Real-Time Hardware Performance Telemetry
* Circular animated SVG/Canvas gauges for:
  * **CPU Load %**
  * **RAM Usage %** (with live used / total GB)
  * **Battery %** (with charging status & power source indicator)
* System uptime monitor.

### 7. 🛠️ Quick Utilities & Shortcuts
* Master **Volume Slider** with live percentage and instant mute toggle.
* One-click **Windows Snipping Tool** (`ms-screenclip:`).
* One-click **PowerShell Terminal** launcher.
* One-click **Task Manager** launcher.
* **Focus / Do Not Disturb Mode** toggle.

### 8. 🎨 5 Curated Themes
Right-click the island or tray icon to instantly switch themes:
1. **Obsidian Dark (Default):** Deep OLED black with neon cyan and violet accents.
2. **Cyberpunk Neon:** Midnight purple with electric hot pink and cyan glow.
3. **Nord Arctic:** Crisp Scandinavian slate with ice blue accents.
4. **Glassmorphism:** Frosted translucent glass with bright rim lighting.
5. **Porcelain Light:** Clean modern light theme with deep charcoal typography.

---

## 🚀 Quick Start

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
| **Expand Dashboard** | Hover your cursor over the compact pill |
| **Collapse Dashboard** | Move your cursor away from the expanded card |
| **Move / Reposition** | Left-click and drag the pill across the top edge |
| **Snap to Center** | Release the pill near the center of your screen |
| **AI Screen Vision** | Open `🤖 AI Companion` tab and click `👁️ See Screen` |
| **Open Preferences** | Click `⚙️` in AI tab or right-click pill ➔ `⚙️ Preferences & AI Accounts` |
| **Toggle MacBook Mode** | Right-click pill ➔ `🍏 MacBook Mode (Auto-Hide Taskbar)` |
| **Switch Tabs** | Click `🎵 Media`, `⚡ System`, `🤖 AI Companion`, or `🛠️ Tools` |
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
│   ├── quick_tools_widget.py  # Quick Utilities HUD (volume slider, screenshot, terminal)
│   └── settings_dialog.py     # Preferences Dialog (AI accounts, free tiers, screen vision, taskbar styler)
├── services/
│   ├── media_service.py       # Winsdk Windows Media Session integration + demo fallback
│   ├── system_service.py      # Psutil hardware metrics collector
│   ├── ai_service.py          # AI agent status, screen capture & multimodal API dispatch
│   └── taskbar_service.py     # Windows taskbar auto-hide controller & Windhawk XAML presets
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
