# 🏝️ Dynamic Island for Windows (Antigravity & Claude Code Edition)

<p align="center">
  <b>A fluid, glassmorphic Dynamic Island overlay for Windows 10 & 11, featuring native media controls, real-time hardware telemetry, quick utilities, and an integrated AI Companion Hub for Antigravity & Claude Code.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078d4?style=for-the-badge&logo=windows" />
  <img src="https://img.shields.io/badge/Language-Python%203.12-3776ab?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/UI-PyQt6-41cd52?style=for-the-badge&logo=qt" />
  <img src="https://img.shields.io/badge/AI-Antigravity%20%26%20Claude-00f0ff?style=for-the-badge" />
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

### 2. 🎵 Native Windows Media Transport Controls
* Integrates directly with Windows System Media Transport Controls (`winsdk`) to detect music playing from **Spotify**, **Chrome**, **Edge**, **Apple Music**, or **Windows Media Player**.
* **Controls:** One-tap Play/Pause, Next Track, Previous Track.
* **Audio Visualizer:** Dynamic multi-bar animated waveform reacting during playback.
* **Progress Bar:** Real-time track timeline tracking.

### 3. ⚡ Real-Time Hardware Performance Telemetry
* Circular animated SVG/Canvas gauges for:
  * **CPU Load %**
  * **RAM Usage %** (with live used / total GB)
  * **Battery %** (with charging status & power source indicator)
* System uptime monitor.

### 4. 🤖 AI Companion Hub (Antigravity & Claude Code Integration)
* **Real-Time Agent Status:** Glowing indicator tracking agent states:
  * 🟢 `Idle (Ready)`
  * 🟡 `Thinking...`
  * 🔵 `Coding...`
  * 🟣 `Auditing (CodeRabbit)...`
  * 🟠 `Ralph Loop Running...`
* **Command Bar & Quick Prompt:** Type questions or terminal commands directly into the island without opening another window.
* **📋 Explain / Fix Clipboard:** One-click button that reads code snippets or stack traces on your Windows clipboard, analyzes them, and suggests instant fixes.
* **🐰 CodeRabbit Quality Audit:** Direct one-click trigger to run `coderabbit review --agent` on your local workspace.
* **🔄 Ralph Loop Trigger:** One-click trigger to execute the autonomous `ralph.ps1` loop over `prd.json`.

### 5. 🛠️ Quick Utilities & Shortcuts
* Master **Volume Slider** with live percentage and instant mute toggle.
* One-click **Windows Snipping Tool** (`ms-screenclip:`).
* One-click **PowerShell Terminal** launcher.
* One-click **Task Manager** launcher.
* **Focus / Do Not Disturb Mode** toggle.

### 6. 🎨 5 Curated Themes
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

## ⌨️ Controls & Interactions

| Action | How to Trigger |
|---|---|
| **Expand Dashboard** | Hover your cursor over the compact pill |
| **Collapse Dashboard** | Move your cursor away from the expanded card |
| **Move / Reposition** | Left-click and drag the pill across the top edge |
| **Snap to Center** | Release the pill near the center of your screen |
| **Switch Tabs** | Click `🎵 Media`, `⚡ System`, `🤖 AI Companion`, or `🛠️ Tools` |
| **Context Menu** | Right-click the pill or the Windows System Tray icon |
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
│   ├── ai_agent_widget.py     # AI Companion Hub (prompt bar, clipboard fixer, Ralph & CodeRabbit)
│   └── quick_tools_widget.py  # Quick Utilities HUD (volume slider, screenshot, terminal)
├── services/
│   ├── media_service.py       # Winsdk Windows Media Session integration + demo fallback
│   ├── system_service.py      # Psutil hardware metrics collector
│   └── ai_service.py          # AI agent status publisher & CLI trigger service
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
