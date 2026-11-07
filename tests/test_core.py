import sys
import time

import pytest

from services.automation_service import parse_ahk, expand_tokens
from services.build_watch_service import match_pattern, tokenize
from services.hotkey_service import parse_hotkey
from services.hotstring_engine import HotstringMatcher

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_hotkey_parsing():
    assert parse_hotkey("Ctrl+Alt+Space") == (0x3, 0x20)
    assert parse_hotkey("Win+Left") == (0x8, 0x25)
    assert parse_hotkey("F9") == (0, 0x78)
    assert parse_hotkey("a") is None
    assert parse_hotkey("Ctrl+A+B") is None


def test_build_matcher():
    pats = ["npm run build", "pytest", "cmake --build", "make"]
    assert match_pattern(tokenize(["node", r"C:\npm\npm-cli.js", "run", "build"]), pats) == "npm run build"
    assert match_pattern(tokenize(["python", "-m", "pytest"]), pats) == "pytest"
    assert match_pattern(tokenize(["cmake", "--build", "."]), pats) == "cmake --build"
    assert match_pattern(tokenize(["npm", "run", "dev"]), pats) is None


def test_hotstrings():
    m = HotstringMatcher()
    m.set_hotstrings([{"trigger": ";d", "replacement": "X"},
                      {"trigger": "@@", "replacement": "Y", "instant": True}])
    for c in ";d":
        assert m.feed_char(c) is None
    assert m.feed_end() == (";d", "X")
    m.feed_char("@")
    assert m.feed_char("@") == ("@@", "Y")


def test_ahk_import():
    macros, hs, skipped = parse_ahk('^!e::Run "explorer.exe"\n::btw::by the way\nCapsLock::Esc\nF9::\n{\nMsgBox 1\n}\n')
    assert {(m["hotkey"], m["action"]) for m in macros} == {("Ctrl+Alt+e", "run"), ("CapsLock", "send")}
    assert hs[0]["replacement"] == "by the way"
    assert skipped == ["F9::"]


def test_tokens(qapp):
    assert expand_tokens("{date}") == time.strftime("%Y-%m-%d")


def test_island_builds(qapp):
    from services.media_service import MediaService
    from services.system_service import SystemMonitorService
    from services.ai_service import AIService
    from services.taskbar_service import TaskbarService
    from island_window import DynamicIslandWindow, TAB_KEYS
    w = DynamicIslandWindow(MediaService(), SystemMonitorService(), AIService(), TaskbarService())
    w.show()
    w.expand()
    w._switch_tab(TAB_KEYS)
    w.automation_service.run_action("focus", "1")
    assert w.timer_service.remaining_sec == 60
    w.timer_service.stop()


# ---------------------------------------------------------- real Windows APIs
@windows_only
def test_vk_lookup_uses_keyboard_layout():
    from services.win_input import key_to_vk
    assert key_to_vk("/") is not None
    assert key_to_vk("F12") == 0x7B


@windows_only
def test_register_and_release_global_hotkey(qapp):
    from services.hotkey_service import HotkeyService
    svc = HotkeyService(qapp)
    assert svc.register(4242, "Ctrl+Alt+Shift+F12"), svc.last_error
    svc.unregister_all()


@windows_only
def test_keep_awake_and_foreground_calls():
    from services import win_input
    assert win_input.set_keep_awake(True)
    assert win_input.set_keep_awake(False)
    win_input.foreground_window()  # must not raise
    assert win_input.app_launch_command().startswith('"')
