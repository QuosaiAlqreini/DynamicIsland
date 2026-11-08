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


# ------------------------------------------------- customization & visibility
def test_info_values():
    import datetime as dt
    from services.info_service import world_clock_text, countdown_text
    noon = dt.datetime(2026, 11, 8, 12, 0, tzinfo=dt.timezone.utc)
    assert world_clock_text("+3", noon) == "15:00"
    assert world_clock_text("Asia/Tokyo", noon) == "21:00"   # needs tzdata on Windows
    assert world_clock_text("Mars/Base", noon) == "bad zone"
    assert countdown_text("2026-12-25", dt.datetime(2026, 11, 8, 12)) == "46d 12h"


def _island():
    from services.media_service import MediaService
    from services.system_service import SystemMonitorService
    from services.ai_service import AIService
    from services.taskbar_service import TaskbarService
    from island_window import DynamicIslandWindow
    return DynamicIslandWindow(MediaService(), SystemMonitorService(), AIService(), TaskbarService())


def test_customization_applies(qapp):
    from config import ConfigManager
    from island_window import TAB_INFO, TAB_MEDIA
    c = ConfigManager()
    w = _island()
    c.set("info_items", [{"id": "a1", "type": "text", "label": "Today", "value": "Gym 6pm"}])
    w.info_service.refresh()
    c.set("pill_center", "info:a1")
    c.set("tabs_visible", ["info", "media"])
    w.apply_customization()
    assert w.nav_order == [TAB_INFO, TAB_MEDIA]
    assert w.idle_pill.slots[1] == "info:a1"
    assert w.info_service.slot_text("info:a1") == "Gym 6pm"
    c.set("tabs_visible", ["media", "shelf", "notes", "focus", "keys", "ai", "system", "tools"])
    c.set("pill_center", "clock")


def test_autohide_tuck_and_reveal(qapp):
    from config import ConfigManager
    c = ConfigManager()
    c.set("visibility_mode", "autohide")
    w = _island()
    w.show()
    w._tuck()
    assert w.tucked
    w._reveal(animate=False)
    assert not w.tucked and w.isVisible()
    w.set_user_hidden(True)
    assert not w.isVisible()
    w.set_user_hidden(False)
    c.set("visibility_mode", "always")


@windows_only
def test_fullscreen_check_does_not_crash():
    from services import win_input
    assert win_input.fullscreen_app_active(None) in (True, False)


def test_media_polling_never_blocks_ui_thread(qapp, monkeypatch):
    """Regression: Windows media calls used to run on the UI thread (~400ms freezes)."""
    import types
    import services.media_service as ms

    class Mgr:
        @staticmethod
        async def request_async():
            time.sleep(0.3)  # slow WinRT call
            return types.SimpleNamespace(get_current_session=lambda: None)
    fake = types.SimpleNamespace(GlobalSystemMediaTransportControlsSessionManager=Mgr)
    monkeypatch.setattr(ms, "HAS_WINSDK", True)
    monkeypatch.setattr(ms, "wmc", fake)
    svc = ms.MediaService()
    start = time.perf_counter()
    svc._poll_media()
    svc.toggle_play_pause()
    assert time.perf_counter() - start < 0.05
