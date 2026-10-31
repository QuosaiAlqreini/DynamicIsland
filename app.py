import sys
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

from services.media_service import MediaService
from services.system_service import SystemMonitorService
from services.ai_service import AIService
from services.taskbar_service import TaskbarService
from island_window import DynamicIslandWindow
from styles import THEMES

def create_tray_icon():
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
    app = QApplication(sys.argv)
    app.setApplicationName("Dynamic Island for Windows")
    app.setQuitOnLastWindowClosed(False)

    # Initialize Services
    media_service = MediaService(interval_ms=1000)
    sys_service = SystemMonitorService(interval_ms=1000)
    ai_service = AIService()
    taskbar_service = TaskbarService()

    # Initialize Main Island Window
    island = DynamicIslandWindow(media_service, sys_service, ai_service, taskbar_service)
    island.show()

    # Initialize System Tray
    tray_icon = QSystemTrayIcon(create_tray_icon(), app)
    tray_icon.setToolTip("Dynamic Island for Windows (Antigravity & Claude Code)")

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

    show_action = tray_menu.addAction("👁️ Toggle Island")
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
        island.show()
        island.expand()
        island._switch_tab(2)

    ai_action = tray_menu.addAction("🤖 Open AI Companion")
    ai_action.triggered.connect(open_ai)

    # Screen Vision Trigger
    def capture_screen_ai():
        island.show()
        island.expand()
        island._switch_tab(2)
        ai_service.analyze_screen()

    vision_action = tray_menu.addAction("👀 See Screen & Analyze")
    vision_action.triggered.connect(capture_screen_ai)

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

    # Start services
    media_service.start()
    sys_service.start()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
