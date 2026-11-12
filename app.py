import os
import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from services.media_service import MediaService
from services.system_service import SystemMonitorService
from services.ai_service import AIService
from services.taskbar_service import TaskbarService
from services.clipboard_service import ClipboardService
from services.focus_timer_service import FocusTimerService
from services.build_watch_service import BuildWatchService
from services.hotkey_service import HotkeyService
from services.automation_service import AutomationService
from config import ConfigManager
from island_window import DynamicIslandWindow, TAB_AI, TAB_SHELF
from styles import THEMES
from version import __version__, APP_NAME

SINGLE_INSTANCE_KEY = "DynamicIsland-single-instance"


def resource_path(*parts):
    """Path to a bundled file, both from source and inside a PyInstaller build."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def replace_running_instance():
    """Starting the island again always gives you the newest code: any copy that is
    already running is asked to quit (and force-closed if it is an old version that
    doesn't understand the request), then this one takes over."""
    import time
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"quit")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        time.sleep(0.8)
    # Force-close leftovers: other Python processes running this same app.py
    try:
        import psutil
        me = os.getpid()
        script = os.path.normcase(os.path.abspath(__file__))
        victims = []
        for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
            try:
                if proc.info["pid"] == me or "python" not in (proc.info["name"] or "").lower():
                    continue
                cmd = proc.info["cmdline"] or []
                for arg in cmd[1:]:
                    path = arg if os.path.isabs(arg) else os.path.join(proc.info["cwd"] or "", arg)
                    if os.path.normcase(os.path.abspath(path)) == script and "--selftest" not in cmd:
                        victims.append(proc)
                        break
            except (psutil.Error, OSError, TypeError):
                continue
        for proc in victims:
            try:
                proc.terminate()
            except psutil.Error:
                pass
        if victims:
            psutil.wait_procs(victims, timeout=3)
    except Exception as e:
        print(f"[startup] could not check for older copies: {e}")

def create_tray_icon():
    ico = resource_path("assets", "icon.ico")
    if os.path.exists(ico):
        return QIcon(ico)
    # Generate clean 32x32 vector pill icon
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Dark background pill
    painter.setBrush(QColor("#0a0b0e"))
    painter.setPen(QColor("#00f0ff"))
    painter.drawRoundedRect(2, 8, 28, 16, 8, 8)

    # Mini glowing core
    painter.setBrush(QColor("#00f0ff"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(6, 12, 8, 8)

    painter.end()
    return QIcon(pixmap)

def main():
    selftest = "--selftest" in sys.argv
    app = QApplication(sys.argv)
    app.setApplicationName("Dynamic Island for Windows")
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(create_tray_icon())

    # Only one island at a time (e.g. autostart + double-clicking the shortcut)
    if not selftest:
        replace_running_instance()
    instance_server = QLocalServer(app)
    QLocalServer.removeServer(SINGLE_INSTANCE_KEY)
    instance_server.listen(SINGLE_INSTANCE_KEY)

    # Initialize Services
    media_service = MediaService(interval_ms=1000)
    sys_service = SystemMonitorService(interval_ms=1000)
    ai_service = AIService()
    taskbar_service = TaskbarService()
    clipboard_service = ClipboardService()
    timer_service = FocusTimerService()
    build_service = BuildWatchService(interval_ms=3000)
    hotkey_service = HotkeyService(app)
    automation_service = AutomationService(hotkey_service, clipboard_service=clipboard_service)

    # Initialize Main Island Window
    island = DynamicIslandWindow(media_service, sys_service, ai_service, taskbar_service,
                                 clipboard_service, timer_service, build_service, automation_service)
    island.show()

    # Global hotkey: summon the island from anywhere (default Ctrl+Alt+Space)
    config = ConfigManager()
    # Open island (id 1) and command bar (id 2); can be changed live from Customize → Shortcuts
    hotkey_text = config.get("global_hotkey", "Ctrl+Alt+Space")
    island.hotkey_service = hotkey_service
    hotkey_service.activated.connect(lambda hid: island.summon() if hid == 1 else None)
    hotkey_service.activated.connect(lambda hid: island.toggle_command_bar() if hid == 2 else None)
    # shortcuts another app already owns: tell the user instead of failing silently
    hotkey_problems = island.rebind_core_hotkeys()

    # AutoHotkey-style automations: user hotkeys + hotstrings
    automation_service.apply()
    app.aboutToQuit.connect(automation_service.shutdown)
    app.aboutToQuit.connect(island.release_reserved_space)
    import atexit
    atexit.register(island.release_reserved_space)
    app.aboutToQuit.connect(hotkey_service.unregister_all)

    # Initialize System Tray
    tray_icon = QSystemTrayIcon(create_tray_icon(), app)
    tray_icon.setToolTip(f"{APP_NAME} {__version__}")

    tray_menu = QMenu()
    tray_menu.setStyleSheet("""
        QMenu {
            background-color: #0b0c10;
            color: #f8fafc;
            border: 1px solid #232733;
            border-radius: 8px;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 16px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #151821;
            color: #00f0ff;
        }
    """)

    # Toggle action
    def toggle_island():
        island.set_user_hidden(not island.user_hidden)

    header = tray_menu.addAction(f"{APP_NAME} {__version__}")
    header.setEnabled(False)
    tray_menu.addSeparator()

    style_menu = tray_menu.addMenu("📱 Look: Island or Notch")
    island_look = style_menu.addAction("🏝️ Floating island")
    notch_look = style_menu.addAction("📱 Smooth notch")
    for act in (island_look, notch_look):
        act.setCheckable(True)
    island_look.triggered.connect(lambda: island.set_style(False))
    notch_look.triggered.connect(lambda: island.set_style(True))

    def sync_tray():
        island_look.setChecked(not island.notch_mode)
        notch_look.setChecked(island.notch_mode)
    tray_menu.aboutToShow.connect(sync_tray)

    show_action = tray_menu.addAction("🙈 Hide Island")
    show_action.triggered.connect(toggle_island)
    tray_menu.aboutToShow.connect(lambda: show_action.setText(
        "👁️ Show Island" if island.user_hidden else "🙈 Hide Island"))

    # Settings & Accounts Action
    settings_action = tray_menu.addAction("⚙ Settings…")
    settings_action.triggered.connect(island.open_customize)
    tray_menu.addAction("⬆ Update && restart").triggered.connect(island.self_update)

    # MacBook Mode (Taskbar Auto-Hide) Action
    def toggle_macbook_mode():
        cur = taskbar_service.is_autohide_enabled()
        taskbar_service.set_autohide(not cur)

    mb_action = tray_menu.addAction("🍏 MacBook Mode (Auto-Hide Taskbar)")
    mb_action.setCheckable(True)
    mb_action.setChecked(taskbar_service.is_autohide_enabled())
    mb_action.triggered.connect(toggle_macbook_mode)

    # AI companion
    def open_ai():
        island.open_tab(TAB_AI)

    ai_action = tray_menu.addAction("🤖 Open AI Companion")
    ai_action.triggered.connect(open_ai)

    # Screen Vision Trigger
    def capture_screen_ai():
        island.open_tab(TAB_AI)
        ai_service.analyze_screen()

    vision_action = tray_menu.addAction("👀 See Screen & Analyze")
    vision_action.triggered.connect(capture_screen_ai)

    tray_menu.addAction("📥 Open Shelf").triggered.connect(lambda: island.open_tab(TAB_SHELF))
    tray_menu.addAction("📝 Quick Note").triggered.connect(island.quick_note)
    tray_menu.addAction("✅ Add Task / Reminder").triggered.connect(lambda: island.open_tab_by_key("tasks"))
    tray_menu.addAction("🔎 Command Bar").triggered.connect(island.toggle_command_bar)
    tray_menu.addAction("👻 Click-Through Pill on / off").triggered.connect(lambda: island.toggle_through_mode())
    tray_menu.addAction("⌨️ Automations & Hotkeys…").triggered.connect(island.open_automations)

    # Themes submenu
    theme_menu = tray_menu.addMenu("🎨 Themes")
    for key, val in THEMES.items():
        action = theme_menu.addAction(val["name"])
        action.triggered.connect(lambda checked, k=key: island.set_theme(k))

    tray_menu.addSeparator()
    quit_action = tray_menu.addAction("❌ Exit")
    quit_action.triggered.connect(app.quit)

    tray_icon.setContextMenu(tray_menu)
    tray_icon.show()

    # Left-click the tray icon = open the island (no hunting for the pill)
    tray_icon.activated.connect(
        lambda reason: island.summon() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)

    # Timer / build completion toasts
    island.notify.connect(
        lambda title, msg: tray_icon.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 5000))

    # Shortcuts that another program already uses (e.g. another app's quick-open key)
    hotkey_problems += [f"{m.get('name', 'Automation')}: {hk}" for hk, m in
                        ((hk, next((m for m in automation_service.macros if m.get("hotkey") == hk), {}))
                         for hk in automation_service.status)]
    if hotkey_problems and not selftest:
        QTimer.singleShot(1500, lambda: tray_icon.showMessage(
            "⚠️ Shortcut already taken",
            "Another program uses:\n" + "\n".join(hotkey_problems[:4]) +
            "\nPick a different one in ⚙ Settings → Shortcuts.",
            QSystemTrayIcon.MessageIcon.Warning, 10000))

    # Local listener for Claude Code / Codex (only on this PC)
    if not selftest:
        island.agent_service.start()
        app.aboutToQuit.connect(island.agent_service.stop)

    # Start services
    media_service.start()
    sys_service.start()
    build_service.start()

    def on_second_instance():
        conn = instance_server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(lambda: app.quit() if b"quit" in bytes(conn.readAll())
                                   else island.summon())
            conn.disconnected.connect(conn.deleteLater)
    instance_server.newConnection.connect(on_second_instance)

    if selftest:
        # Used by CI: start everything, then exit cleanly after a few seconds
        # ...and measure how long the UI thread ever stalls while everything runs
        import time as _t
        gaps, last = [], [_t.perf_counter()]

        def beat():
            now = _t.perf_counter()
            gaps.append(now - last[0])
            last[0] = now
        heartbeat = QTimer(app)
        heartbeat.timeout.connect(beat)
        QTimer.singleShot(1500, lambda: (last.__setitem__(0, _t.perf_counter()), heartbeat.start(10)))
        QTimer.singleShot(2500, island.expand)
        QTimer.singleShot(4000, island.collapse)
        QTimer.singleShot(5500, island.expand)

        def finish():
            worst = max(gaps) * 1000 if gaps else 0
            slow = sum(g > 0.05 for g in gaps)
            print(f"SELFTEST stalls: worst={worst:.0f}ms frames_over_50ms={slow} of {len(gaps)}")
            if worst > 500:
                print("SELFTEST FAILED: UI thread stalled")
                app.exit(1)
                return
            print(f"SELFTEST OK {__version__}")
            app.quit()
        QTimer.singleShot(8000, finish)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
