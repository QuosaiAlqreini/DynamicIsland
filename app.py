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


def notify_running_instance():
    """If Dynamic Island is already running, ask it to show itself. Returns True if so."""
    sock = QLocalSocket()
    sock.connectToServer(SINGLE_INSTANCE_KEY)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.waitForBytesWritten(300)
        sock.disconnectFromServer()
        return True
    return False

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
    if not selftest and notify_running_instance():
        return 0
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
    build_service = BuildWatchService(interval_ms=2000)
    hotkey_service = HotkeyService(app)
    automation_service = AutomationService(hotkey_service, clipboard_service=clipboard_service)

    # Initialize Main Island Window
    island = DynamicIslandWindow(media_service, sys_service, ai_service, taskbar_service,
                                 clipboard_service, timer_service, build_service, automation_service)
    island.show()

    # Global hotkey: summon the island from anywhere (default Ctrl+Alt+Space)
    config = ConfigManager()
    hotkey_text = config.get("global_hotkey", "Ctrl+Alt+Space")
    if hotkey_text and hotkey_service.register(1, hotkey_text):
        hotkey_service.activated.connect(lambda hid: island.summon() if hid == 1 else None)

    # AutoHotkey-style automations: user hotkeys + hotstrings
    automation_service.apply()
    app.aboutToQuit.connect(automation_service.shutdown)
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
        if island.isVisible():
            island.hide()
        else:
            island.show()

    show_action = tray_menu.addAction(f"👁️ Toggle Island" + (f"\t{hotkey_text}" if hotkey_service.available else ""))
    show_action.triggered.connect(toggle_island)

    # Settings & Accounts Action
    settings_action = tray_menu.addAction("⚙️ Preferences & AI Accounts")
    settings_action.triggered.connect(island.open_settings_dialog)

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

    # Start services
    media_service.start()
    sys_service.start()
    build_service.start()

    def on_second_instance():
        conn = instance_server.nextPendingConnection()
        if conn is not None:
            conn.readyRead.connect(lambda: (conn.readAll(), island.summon()))
            conn.disconnected.connect(conn.deleteLater)
    instance_server.newConnection.connect(on_second_instance)

    if selftest:
        # Used by CI: start everything, then exit cleanly after a few seconds
        def finish():
            print(f"SELFTEST OK {__version__}")
            app.quit()
        QTimer.singleShot(4000, finish)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
