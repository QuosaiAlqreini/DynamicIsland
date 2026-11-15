"""Real X11 checks for the Linux build (run under xvfb-run in CI, not by pytest):
global hotkeys fire, click-through toggles, mouse buttons are seen, fullscreen apps are found."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PyQt6.QtCore import Qt                                    # noqa: E402
from PyQt6.QtWidgets import QApplication, QWidget              # noqa: E402

wm = subprocess.Popen(["openbox"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
app = QApplication([])
from services import win_input                                 # noqa: E402
from services.hotkey_service import HotkeyService              # noqa: E402


def pump(t):
    end = time.time() + t
    while time.time() < end:
        app.processEvents()
        time.sleep(0.02)


failures = []


def check(name, ok):
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok:
        failures.append(name)


hk = HotkeyService(app)
got = []
hk.activated.connect(got.append)
for i, combo in enumerate(["Ctrl+Alt+Space", "Ctrl+Alt+H"] + [f"Ctrl+Alt+F{n}" for n in range(1, 10)], 1):
    hk.register(i, combo)
pump(1.0)
subprocess.run(["xdotool", "key", "ctrl+alt+space"])
pump(0.5)
subprocess.run(["xdotool", "key", "ctrl+alt+h"])
pump(0.5)
check("global hotkeys", got[:2] == [1, 2])

w = QWidget()
w.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
w.resize(200, 40)
w.show()
pump(0.3)
flag = lambda: bool(w.windowHandle().flags() & Qt.WindowType.WindowTransparentForInput)
check("click-through on", win_input.set_click_through(int(w.winId()), True) and flag() and w.isVisible())
check("click-through off", win_input.set_click_through(int(w.winId()), False) and not flag())

subprocess.run(["xdotool", "mousedown", "1"])
down = win_input.mouse_button_down()
subprocess.run(["xdotool", "mouseup", "1"])
check("mouse button seen", down and not win_input.mouse_button_down())

other = subprocess.Popen([sys.executable, "-c",
                          "from PyQt6.QtWidgets import QApplication, QWidget\n"
                          "from PyQt6.QtCore import QTimer\n"
                          "a = QApplication([]); w = QWidget(); w.showFullScreen()\n"
                          "QTimer.singleShot(3000, a.quit); a.exec()"])
pump(1.8)
check("fullscreen app found", win_input.fullscreen_app_active())
other.wait()
pump(0.5)
check("no fullscreen after it closed", not win_input.fullscreen_app_active())
wm.terminate()
sys.exit(1 if failures else 0)
