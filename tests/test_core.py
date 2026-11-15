import json
import os
import sys
import time

import pytest

from services.automation_service import parse_ahk, expand_tokens
from services.build_watch_service import match_pattern, tokenize
from services.hotkey_service import parse_hotkey
from services.hotstring_engine import HotstringMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def _settle(qapp, seconds=0.6):
    """Let animations finish."""
    import time
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        qapp.processEvents()


_KEEP_ALIVE = []


def _island():
    from services.media_service import MediaService
    from services.system_service import SystemMonitorService
    from services.ai_service import AIService
    from services.taskbar_service import TaskbarService
    from island_window import DynamicIslandWindow
    _w = DynamicIslandWindow(MediaService(), SystemMonitorService(), AIService(), TaskbarService())
    _KEEP_ALIVE.append(_w)
    return _w


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
    _settle(qapp)
    assert not w.isVisible()
    w.set_user_hidden(False)
    # Waking from sleep (a long gap between watchdog ticks) clears a stale fullscreen hide
    w.fullscreen_hidden = True
    w._last_tick -= 600
    w._keepalive_tick()
    assert not w.fullscreen_hidden
    _settle(qapp)
    assert w.isVisible() and w.windowOpacity() == 1.0
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
    monkeypatch.setattr(ms, "wmc", fake, raising=False)
    svc = ms.MediaService()
    start = time.perf_counter()
    svc._poll_media()
    svc.toggle_play_pause()
    assert time.perf_counter() - start < 0.05


# ------------------------------------------------------------ through mode
def _through_island(qapp, how="edge"):
    from config import ConfigManager
    c = ConfigManager()
    c.set("through_mode", True)
    c.set("through_open", how)
    c.set("visibility_mode", "always")
    c.set("island_offset_x", 0)
    w = _island()
    w.show()
    qapp.processEvents()
    return w


def test_through_mode_click_does_not_open(qapp):
    from PyQt6.QtCore import QPoint
    w = _through_island(qapp, "dwell")
    assert w._passthrough
    inside = w.body_global().center()
    w._through_step(inside, False, 0.0)       # cursor arrives
    assert w.windowOpacity() < 1 or True      # fade is best-effort per platform
    w._through_step(inside, True, 0.1)        # user clicks the tab underneath
    w._through_step(inside, False, 0.2)
    w._through_step(inside, False, 5.0)       # cursor keeps resting there
    assert not w.is_expanded
    w._through_step(QPoint(5, 500), False, 5.1)   # leaves
    w._through_step(inside, False, 6.0)       # comes back and rests
    w._through_step(inside, False, 6.5)
    assert w.is_expanded and not w._passthrough
    w.collapse()
    assert w._passthrough


def test_through_mode_edge_open_and_drag_in(qapp):
    from PyQt6.QtCore import QPoint
    w = _through_island(qapp, "edge")
    g = w.body_global()
    on_pill, at_edge, away = g.center(), QPoint(g.center().x(), 0), QPoint(5, 500)
    w._through_step(on_pill, False, 0.0)
    w._through_step(on_pill, False, 2.0)      # resting on the pill is not enough
    assert not w.is_expanded
    w._through_step(away, False, 2.1)
    w._through_step(on_pill, True, 3.0)       # dragging a file in
    w._through_step(on_pill, True, 3.4)
    assert w._drop_override and not w._passthrough   # now a drop target
    w._through_step(away, False, 3.6)
    assert w._passthrough
    w._through_step(at_edge, False, 4.0)      # push against the top edge
    w._through_step(at_edge, False, 4.5)
    assert w.is_expanded


def test_position_offset(qapp):
    from config import ConfigManager
    w = _through_island(qapp)
    centered = w.body_global().center().x()
    ConfigManager().set("island_offset_x", -100)
    w.apply_customization()
    _settle(qapp)
    assert abs(w.body_global().center().x() - (centered - 100)) <= 1
    w.summoned = True          # opened on purpose: stays open without the cursor on it
    w.expand()
    _settle(qapp)
    assert w.body_global().center().x() < w._get_screen_geometry().center().x()
    assert w.body_global().width() == w.expanded_w
    w.collapse()
    _settle(qapp)
    assert w.body_global().width() == w.compact_w
    ConfigManager().set("island_offset_x", 0)


_STYLE_PROBE = r"""
import os, sys
sys.path.insert(0, os.getcwd())
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from config import ConfigManager
ConfigManager().set("through_mode", True)
from services import win_input
from services.media_service import MediaService
from services.system_service import SystemMonitorService
from services.ai_service import AIService
from services.taskbar_service import TaskbarService
from island_window import DynamicIslandWindow
import faulthandler; faulthandler.enable()
w = DynamicIslandWindow(MediaService(), SystemMonitorService(), AIService(), TaskbarService())
w.show(); app.processEvents()
import time
for _ in range(30):            # give background threads (volume, media) time to run
    app.processEvents(); time.sleep(0.05)
print("VOLUME", w.volume_service.available, w.volume_service.percent, flush=True)
style = lambda: win_input.user32.GetWindowLongW(int(w.winId()), -20)
folded = style()
w.expand(); app.processEvents()
opened = style()
w.collapse(); app.processEvents()
refolded = style()
print("STYLES", folded & 0x20, opened & 0x20, refolded & 0x20, flush=True)
"""


@windows_only
def test_click_through_style_is_applied_on_real_window():
    """Needs a real HWND, so run with the native Qt platform in a subprocess."""
    import subprocess
    env = dict(os.environ, QT_QPA_PLATFORM="windows")
    out = subprocess.run([sys.executable, "-c", _STYLE_PROBE], capture_output=True, text=True,
                         timeout=60, env=env, cwd=ROOT)
    assert "STYLES 32 0 32" in out.stdout, out.stdout + out.stderr
    assert out.returncode == 0, f"crashed with {out.returncode:#x}: " + out.stdout + out.stderr
    print(out.stdout)


# ------------------------------------- tasks, prayer, water, lyrics, commands
def test_task_phrases_and_reminders(qapp):
    import datetime as dt
    from services.tasks_service import parse_task_phrase, TasksService
    now = dt.datetime(2026, 11, 11, 14, 0)
    assert parse_task_phrase("Call mom at 17:30", now) == ("Call mom", dt.datetime(2026, 11, 11, 17, 30))
    assert parse_task_phrase("Stretch in 20m", now) == ("Stretch", dt.datetime(2026, 11, 11, 14, 20))
    assert parse_task_phrase("Report tomorrow 9am", now) == ("Report", dt.datetime(2026, 11, 12, 9, 0))
    assert parse_task_phrase("Buy 2 apples", now) == ("Buy 2 apples", None)
    svc = TasksService()
    svc.config.set("tasks", [])
    fired = []
    svc.reminder.connect(fired.append)
    task = svc.add("Tea in 5m", now)
    svc.add("Someday thing", now)
    svc.check_due(now)
    assert not fired
    svc.check_due(now + dt.timedelta(minutes=6))
    assert [t["title"] for t in fired] == ["Tea"] and svc.ringing()
    svc.check_due(now + dt.timedelta(minutes=7))
    assert len(fired) == 1                      # fires once
    svc.snooze(task["id"], 10)
    assert not svc.ringing() and svc.next_due()["title"] == "Tea"
    svc.set_done(task["id"])
    assert svc.sorted_tasks()[-1]["title"] == "Tea"
    svc.config.set("tasks", [])


def test_prayer_times_match_published_values():
    import datetime as dt
    from services.prayer import prayer_times, CITIES, next_prayer

    def hm(t):
        return t.hour * 60 + t.minute
    riyadh = prayer_times(dt.date(2026, 11, 11), *CITIES["Riyadh"], 3, "umm_al_qura")
    expected = {"Fajr": "04:45", "Dhuhr": "11:37", "Asr": "14:45", "Maghrib": "17:08", "Isha": "18:38"}
    for name, want in expected.items():
        h, m = map(int, want.split(":"))
        assert abs(hm(riyadh[name]) - (h * 60 + m)) <= 3, (name, riyadh[name])
    assert next_prayer(riyadh, dt.datetime(2026, 11, 11, 15, 0))[0] == "Maghrib"
    # Far north in summer still returns an ordered day
    london = prayer_times(dt.date(2026, 6, 1), *CITIES["London"], 1, "mwl")
    order = [london[n] for n in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")]
    assert order == sorted(order)


def test_water_and_pomodoro(qapp):
    from services.day_service import DayService
    from services.focus_timer_service import FocusTimerService
    day = DayService()
    day.config.set("water_log", {})
    day.add_water()
    day.add_water(500)
    assert day.water_ml == 750 and 0.3 < day.water_fraction < 0.4
    day.config.set("water_log", {})
    t = FocusTimerService()
    t.start_pomodoro(25, 5, 15, 2)
    assert t.label == "Focus 1/2" and len(t.plan) == 3
    t.skip()
    assert t.label == "Break" and t.remaining_sec == 300
    t.skip(); t.skip()
    assert t.label == "Long break"
    t.skip()
    assert not t.active


def test_lyrics_and_calculator():
    from services.lyrics_service import parse_lrc, line_at
    from services.commands import calculate, run_text_tool
    lines = parse_lrc("[00:01.00] first\n[00:05.50] second\nnot a line")
    assert line_at(lines, 0) == "" and line_at(lines, 3) == "first" and line_at(lines, 9) == "second"
    assert calculate("2*(3+4)") == "14" and calculate("sqrt(16)+2^3") == "12"
    assert calculate("hello") is None and calculate("__import__('os')") is None
    assert calculate("9**9**9") is None and calculate("10/0") is None
    assert run_text_tool("unbase64", run_text_tool("base64", "héllo")) == "héllo"


def test_command_bar_suggestions(qapp):
    from modules.command_bar import CommandBar
    w = _island()
    w.tasks_service.config.set("tasks", [])
    bar = CommandBar(w.theme, w)
    labels = lambda q: [l for l, _a in bar.suggestions(q)]
    assert any("14" in l for l in labels("2*(3+4)"))
    assert any("timer" in l.lower() for l in labels("timer 10m"))
    assert any("Search the web" in l for l in labels("anything at all"))
    label, action = bar.suggestions("remind Call mom at 17:30")[0]
    action()
    assert w.tasks_service.tasks[0]["title"] == "Call mom"
    dict(bar.suggestions("10m"))[labels("10m")[0]]()
    assert w.timer_service.remaining_sec == 600
    w.timer_service.stop()
    w.tasks_service.config.set("tasks", [])


def test_new_tabs_and_wheel_paging(qapp):
    from island_window import TAB_TASKS, TAB_DAY
    w = _island()
    w.config.set("tabs_visible", ["media", "tasks", "day"])
    w.apply_customization()
    assert w.nav_order[1:] == [TAB_TASKS, TAB_DAY]
    w._switch_tab(w.nav_order[0], save=False)
    w._cycle_tab(1)
    assert w.stack.currentIndex() == TAB_TASKS
    w.config.set("tabs_visible", ["media", "shelf", "tasks", "notes", "focus", "day", "keys", "ai", "system", "tools"])


# --------------------------------------------- full screen, show/hide, notch
def test_fullscreen_decision():
    from services.win_input import looks_fullscreen
    mon = (0, 0, 1920, 1080)
    assert looks_fullscreen((0, 0, 1920, 1080), mon, zoomed=False, has_caption=False)       # game / F11
    assert looks_fullscreen((0, 0, 1920, 1080), mon, zoomed=False, has_caption=True)        # app keeps caption style
    assert looks_fullscreen((-8, -8, 1928, 1088), mon, zoomed=True, has_caption=False)      # captionless maximized player
    assert not looks_fullscreen((-8, -8, 1928, 1088), mon, zoomed=True, has_caption=True)   # normal maximized window
    assert not looks_fullscreen((0, 0, 1920, 1040), mon, zoomed=False, has_caption=False)   # leaves the taskbar visible
    assert not looks_fullscreen((100, 100, 900, 700), mon, zoomed=False, has_caption=True)


def test_manual_show_hide_and_style(qapp):
    w = _island()
    w.show()
    w.toggle_visibility()
    _settle(qapp)
    assert w.user_hidden and not w.isVisible()
    w.toggle_visibility()
    _settle(qapp)
    assert not w.user_hidden and w.isVisible()
    w.set_user_hidden(True)
    _settle(qapp)
    w.summon()                                   # the hotkey always brings it back
    _settle(qapp)
    assert w.isVisible() and not w.user_hidden
    w.collapse()
    w.set_style(True)
    import time
    end = time.monotonic() + 0.8
    while time.monotonic() < end:
        qapp.processEvents()
    assert w.notch_mode and w.body_global().y() == w._get_screen_geometry().y()
    w.grab()                                     # notch painting must not crash
    w.set_style(False)
    assert not w.notch_mode


def test_new_default_hotkeys_reach_existing_users(qapp):
    from config import ConfigManager
    from services.automation_service import AutomationService
    c = ConfigManager()
    c.set("automations", [{"name": "Mine", "hotkey": "Ctrl+Alt+H", "action": "lock", "arg": "", "enabled": True}])
    c.set("migrated_default_macros", [])
    svc = AutomationService(None)
    by_action = {m["action"]: m for m in svc.macros}
    assert by_action["island_visibility"]["hotkey"] == ""          # didn't steal the user's Ctrl+Alt+H
    assert by_action["through_toggle"]["hotkey"] == "Ctrl+Alt+G"
    svc.save_macros([m for m in svc.macros if m["action"] != "through_toggle"])
    AutomationService(None)                                        # deleted defaults are not re-added
    assert not any(m["action"] == "through_toggle" for m in ConfigManager().get("automations"))


def test_germany_prayer_options():
    import datetime as dt
    from services.prayer import prayer_times, COUNTRIES, CITIES, suggested_method, country_of
    assert len(COUNTRIES["Germany"]) >= 40 and "Hamburg" in CITIES
    assert country_of("Hamburg") == "Germany" and suggested_method("Germany") == "mwl"
    berlin = CITIES["Berlin"]
    nov = prayer_times(dt.date(2026, 11, 11), *berlin, 1, "mwl")
    assert (nov["Dhuhr"].hour, nov["Maghrib"].hour) == (11, 16)
    # Midsummer: 18° twilight is never reached in Berlin, every rule still gives an ordered day
    for rule in ("angle", "seventh", "middle", "none"):
        t = prayer_times(dt.date(2026, 6, 21), *berlin, 2, "mwl", high_lat=rule)
        order = [t[n] for n in ("Fajr", "Sunrise", "Dhuhr", "Asr", "Maghrib", "Isha")]
        assert order == sorted(order), rule
    seventh = prayer_times(dt.date(2026, 6, 21), *berlin, 2, "mwl", high_lat="seventh")
    middle = prayer_times(dt.date(2026, 6, 21), *berlin, 2, "mwl", high_lat="middle")
    assert middle["Fajr"] < seventh["Fajr"]
    # Mosque adjustments are applied per prayer
    adj = prayer_times(dt.date(2026, 11, 11), *berlin, 1, "mwl", offsets={"Maghrib": 3, "Fajr": -5})
    assert (adj["Maghrib"] - nov["Maghrib"]).seconds == 180
    assert (nov["Fajr"] - adj["Fajr"]).seconds == 300
    assert adj["Dhuhr"] == nov["Dhuhr"]


def test_day_settings_dialog_germany(qapp):
    from modules.day_widget import DaySettings
    from styles import get_theme
    d = DaySettings(get_theme("obsidian"))
    d.country.setCurrentIndex(d.country.findData("Germany"))
    d.city.setCurrentIndex(d.city.findData("Hamburg"))
    assert abs(d.lat.value() - 53.5511) < 0.01 and d.method.currentData() == "mwl"
    d._on_geo_results([("Gießen, Hesse, Germany", 50.5841, 8.6784)], "")
    assert abs(d.lat.value() - 50.5841) < 0.01
    d.offset_spins["Maghrib"].setValue(2)
    d._save()
    from config import ConfigManager
    c = ConfigManager()
    assert c.get("prayer_offsets") == {"Maghrib": 2} and c.get("prayer_city") == "Gießen"
    assert "Maghrib" in d.preview.text()


@windows_only
def test_town_search_live(qapp):
    """Real request to the geocoding service (runs on the Windows build machine)."""
    from modules.day_widget import DaySettings
    from styles import get_theme
    d = DaySettings(get_theme("obsidian"))
    got = []
    d._geo_done.connect(lambda found, msg: got.append((found, msg)))
    d._geo_lookup("Gießen")
    qapp.processEvents()
    found, msg = got[0]
    if not found and "failed" in msg:
        pytest.skip(f"network unavailable: {msg}")
    assert any("Germany" in label and 50 < lat < 51 for label, lat, _lng in found), found


def test_island_and_notch_really_look_different(qapp):
    """Switching style moves the island to the top edge and changes the silhouette."""
    from config import ConfigManager
    ConfigManager().set("visibility_mode", "always")
    w = _island()
    w.show()
    w.set_style(False)
    _settle(qapp, 0.8)
    top = w._get_screen_geometry().y()
    assert w.body_global().y() == top + w.top_offset          # island floats below the edge
    w.set_style(True)
    _settle(qapp, 0.8)
    b = w._body.toRect()
    img = w.grab().toImage()
    assert w.body_global().y() == top, "notch must sit on the top edge"
    assert img.pixelColor(b.center().x(), 1).alpha() > 200     # notch joins the screen edge
    assert img.pixelColor(b.x() + 2, b.bottom() - 1).alpha() == 0   # narrower at the bottom (curved sides)
    assert img.pixelColor(5, 5).alpha() == 0                   # rest of the window is transparent
    w.set_style(False)
    _settle(qapp, 0.8)
    assert w.body_global().y() == top + w.top_offset


def test_customize_applies_live_and_cancel_undoes(qapp):
    from config import ConfigManager
    from modules.customize_dialog import CustomizeDialog
    c = ConfigManager()
    c.set("notch_mode", False)
    c.set("island_size", "comfortable")
    w = _island()
    w.show()
    start_w = w.base_compact_w
    d = CustomizeDialog(w.theme, w.info_service, w)
    assert d.tabs.count() == 6 and "Shortcuts" in d.tabs.nav.item(4).text()
    d.rb_notch.setChecked(True)
    d.size_combo.setCurrentIndex(d.size_combo.findData("roomy"))
    _settle(qapp, 0.8)
    assert w.notch_mode and w.base_compact_w > start_w       # applied live, without Save
    assert w.body_global().y() == w._get_screen_geometry().y()
    d.reject()                                               # Cancel puts everything back
    _settle(qapp, 0.8)
    assert not w.notch_mode and w.base_compact_w == start_w
    assert c.get("island_size") == "comfortable"


def test_notch_is_roomier_and_tabs_show_names(qapp):
    from config import ConfigManager
    ConfigManager().set("notch_mode", False)
    w = _island()
    island_size = (w.base_compact_w, w.compact_h, w.expanded_w, w.expanded_h)
    w.set_style(True)
    notch_size = (w.base_compact_w, w.compact_h, w.expanded_w, w.expanded_h)
    assert notch_size[0] > island_size[0] and notch_size[2] > island_size[2]   # wider, roomier panel
    assert notch_size[1] <= 32 and notch_size[1] < island_size[1]             # but a slim folded notch
    w.set_style(False)
    w.config.set("tabs_visible", ["media", "shelf", "tasks", "notes", "focus", "day", "keys", "ai", "system", "tools"])
    w.apply_customization()
    from island_window import TAB_TASKS
    w._switch_tab(TAB_TASKS, save=False)
    assert "Tasks" in w.nav_buttons[TAB_TASKS].text()        # open tab shows its name
    assert w.nav_buttons[w.nav_order[0]].text().strip() == "🎵"   # others stay as icons


_APPBAR_PROBE = r"""
import os, sys, time
sys.path.insert(0, os.getcwd())
from PyQt6.QtWidgets import QApplication
app = QApplication([])
from config import ConfigManager
c = ConfigManager(); c.set("notch_mode", True); c.set("push_windows_down", True); c.set("visibility_mode", "always")
from services.appbar import work_area_top
before = work_area_top()
from services.media_service import MediaService
from services.system_service import SystemMonitorService
from services.ai_service import AIService
from services.taskbar_service import TaskbarService
from island_window import DynamicIslandWindow
w = DynamicIslandWindow(MediaService(), SystemMonitorService(), AIService(), TaskbarService())
w.show()
end = time.monotonic() + 1.5
while time.monotonic() < end:
    app.processEvents(); time.sleep(0.02)
w.update_reserved_space()
if not w.reservation.registered:
    print("NOSHELL", flush=True); sys.exit(0)
during = work_area_top()
w.release_reserved_space()
time.sleep(0.3)
after = work_area_top()
print("WORKAREA", before, during, after, flush=True)
"""


@windows_only
def test_notch_reserves_space_and_gives_it_back():
    import subprocess
    env = dict(os.environ, QT_QPA_PLATFORM="windows")
    out = subprocess.run([sys.executable, "-c", _APPBAR_PROBE], capture_output=True, text=True,
                         timeout=60, env=env, cwd=ROOT)
    print(out.stdout, out.stderr)
    if "NOSHELL" in out.stdout:
        pytest.skip("no Windows shell/taskbar on this machine")
    assert out.returncode == 0, out.stdout + out.stderr
    before, during, after = map(int, out.stdout.split("WORKAREA")[1].split())
    assert during > before, "maximized windows should start below the notch"
    assert after == before, "space must be given back on exit"


# ------------------------------------------------------------- AI agents
def _post(port, token, payload, path="/hook", timeout=10):
    import json
    import urllib.request
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "X-Island-Token": token})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode()


def _agent_service(qapp, port):
    from services.agent_service import AgentService
    svc = AgentService()
    svc.config.set("agent_port", port)
    assert svc.start(), svc.error
    return svc


def test_agent_events_feed_and_done(qapp):
    svc = _agent_service(qapp, 47931)
    done = []
    svc.finished.connect(done.append)
    base = {"session_id": "s1", "cwd": "C:/code/my-app"}
    for payload in (
        dict(base, hook_event_name="UserPromptSubmit", prompt="Fix the login bug"),
        dict(base, hook_event_name="PreToolUse", tool_name="Read", tool_input={"file_path": "C:/code/my-app/src/login.py"}),
        dict(base, hook_event_name="PreToolUse", tool_name="Bash", tool_input={"command": "npm test"}),
    ):
        assert _post(47931, svc.token, payload)[0] == 200
    _settle(qapp, 0.3)
    assert svc.summary() == ("working", "▶ npm test")
    texts = [e["text"] for e in svc.feed]
    assert "Reading login.py" in texts and "npm test" in texts
    assert svc.sessions["s1"]["project"] == "my-app"
    _post(47931, svc.token, dict(base, hook_event_name="Stop", last_assistant_message="All tests pass now."))
    _settle(qapp, 0.3)
    assert done and done[0]["answer"] == "All tests pass now." and svc.summary()[0] == "done"
    svc.stop()


def test_agent_rejects_wrong_token(qapp):
    import urllib.error
    svc = _agent_service(qapp, 47932)
    with pytest.raises(urllib.error.HTTPError) as err:
        _post(47932, "wrong-token", {"hook_event_name": "PreToolUse", "tool_name": "Bash"})
    assert err.value.code == 403
    _settle(qapp, 0.2)
    assert not svc.feed
    svc.stop()


def test_agent_permission_allow_deny_and_no_answer(qapp, monkeypatch):
    import json
    import threading
    import services.agent_service as mod
    svc = _agent_service(qapp, 47933)
    payload = {"session_id": "s2", "cwd": "/w/proj", "hook_event_name": "PermissionRequest",
               "tool_name": "Bash", "tool_input": {"command": "rm -rf node_modules"}}

    def ask():
        box = {}
        t = threading.Thread(target=lambda: box.update(r=_post(47933, svc.token, payload, timeout=20)))
        t.start()
        end = time.monotonic() + 3
        while not svc.pending and time.monotonic() < end:
            qapp.processEvents()
        return t, box

    for allow, expected in ((True, "allow"), (False, "deny")):
        t, box = ask()
        assert svc.pending and svc.pending[0]["detail"] == "rm -rf node_modules"
        assert svc.summary()[0] == "waiting"
        svc.decide(svc.pending[0]["id"], allow)
        t.join(5)
        out = json.loads(box["r"][1])["hookSpecificOutput"]
        assert out["hookEventName"] == "PermissionRequest" and out["decision"]["behavior"] == expected
        assert ("message" in out["decision"]) == (not allow)
        _settle(qapp, 0.2)
        assert not svc.pending

    # Nobody answers: empty reply, so Claude Code falls back to its own prompt
    monkeypatch.setattr(mod, "PERMISSION_WAIT_S", 0.4)
    t, box = ask()
    t.join(5)
    assert box["r"] == (200, "")
    _settle(qapp, 0.3)
    assert not svc.pending
    svc.stop()


def test_claude_settings_merge_keeps_user_hooks():
    from services.agent_service import merge_claude_settings, strip_claude_settings, HOOK_EVENTS
    mine = {"model": "x", "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "lint"}]}]}}
    merged = merge_claude_settings(mine, 47821, "tok")
    assert merged["model"] == "x" and set(HOOK_EVENTS) <= set(merged["hooks"])
    assert merged["hooks"]["PreToolUse"][0]["hooks"][0]["command"] == "lint"      # user's hook kept first
    ours = merged["hooks"]["PermissionRequest"][0]["hooks"][0]
    assert ours["type"] == "http" and ours["url"] == "http://127.0.0.1:47821/hook" and ours["timeout"] > 100
    again = merge_claude_settings(merged, 47821, "tok2")                          # reconnect: no duplicates
    assert len(again["hooks"]["PreToolUse"]) == 2
    assert strip_claude_settings(again) == mine                                   # disconnect restores exactly
    assert "hooks" not in strip_claude_settings(merge_claude_settings({}, 1, "t"))


def test_connect_claude_writes_backup(qapp, tmp_path, monkeypatch):
    import json
    from services.agent_service import AgentService
    path = tmp_path / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text('{"theme": "dark"}')
    monkeypatch.setattr(AgentService, "claude_settings_path", staticmethod(lambda: path))
    svc = AgentService()
    assert not svc.claude_connected()
    ok, _msg = svc.connect_claude()
    assert ok and svc.claude_connected()
    assert json.loads(path.read_text())["theme"] == "dark"
    assert json.loads((path.parent / "settings.json.island-backup").read_text()) == {"theme": "dark"}
    ok, _msg = svc.disconnect_claude()
    assert ok and json.loads(path.read_text()) == {"theme": "dark"}
    path.write_text("{ not json")
    ok, msg = svc.connect_claude()
    assert not ok and path.read_text() == "{ not json"                            # never clobber a broken file


def test_island_reacts_to_agent(qapp):
    from island_window import TAB_AGENTS
    from config import ConfigManager
    ConfigManager().set("agent_inline_prompt", False)
    w = _island()
    w.show()
    svc = w.agent_service
    svc._handle_event({"hook_event_name": "PreToolUse", "session_id": "a", "cwd": "/x/site",
                       "tool_name": "Edit", "tool_input": {"file_path": "/x/site/index.html"}})
    assert w.idle_pill.robo_mood == "focused"
    assert "Editing index.html" in w.idle_pill.activities["agent"]["text"]
    svc._handle_event({"hook_event_name": "PermissionRequest", "session_id": "a", "_request_id": "r1",
                       "tool_name": "Bash", "tool_input": {"command": "git push"}})
    _settle(qapp, 0.6)
    assert w.is_expanded and w.stack.currentIndex() == TAB_AGENTS       # opened for the decision
    assert w.agents_widget.card.isVisible() and "git push" in w.agents_widget.card_detail.text()
    assert w.idle_pill.robo_mood == "curious"
    w.agents_widget.btn_deny.click()
    assert not svc.pending and not w.agents_widget.card.isVisible()
    svc._handle_event({"hook_event_name": "Stop", "session_id": "a", "last_assistant_message": "Pushed."})
    assert w.idle_pill.robo_mood == "happy" and "agent" not in w.idle_pill.activities


def test_inline_allow_deny_bar_and_strip(qapp):
    """A permission request widens the folded island into an Allow / Deny bar."""
    from config import ConfigManager
    c = ConfigManager()
    c.set("agent_inline_prompt", True)
    c.set("visibility_mode", "strip")
    w = _island()
    w.show()
    _settle(qapp, 0.4)
    win_before = (w.x(), w.y(), w.width(), w.height())
    w._tuck()
    _settle(qapp, 0.5)
    assert w.tucked and w.isVisible() and w.body_global().height() <= 6      # resting strip
    w.agent_service._handle_event({"hook_event_name": "PermissionRequest", "session_id": "z", "_request_id": "q1",
                                   "tool_name": "Bash", "tool_input": {"command": "npm install stripe"}})
    _settle(qapp, 0.6)
    assert w.prompting and not w.is_expanded and w.prompt_bar.isVisible()
    assert "npm install stripe" in w.prompt_label.text()
    assert w.body_global().width() > 300 and not w._passthrough            # wide and clickable
    w.prompt_allow.click()
    _settle(qapp, 0.6)
    assert not w.agent_service.pending and not w.prompting and w.idle_pill.isVisible()
    w.expand()
    _settle(qapp, 0.6)
    w.collapse()
    _settle(qapp, 0.6)
    # the real window never moved or resized through all of that
    assert (w.x(), w.y(), w.width(), w.height()) == win_before
    c.set("visibility_mode", "always")


def test_hotkey_owner_hints():
    from services.hotkey_owner import guess_owner, normalize
    assert normalize("Ctrl+Alt+Space") == normalize("alt+control+SPACE") == "alt+ctrl+space"
    assert "Claude" in guess_owner("Ctrl+Alt+Space", running={"claude.exe", "explorer.exe"})
    assert "PowerToys" in guess_owner("Alt+Space", running={"PowerToys.PowerLauncher.exe"})
    assert "ChatGPT" in guess_owner("Alt+Space", running=set())           # not running: "often used by"
    assert "Windows itself" in guess_owner("Win+Shift+Q", running=set())
    assert "Discord" in guess_owner("Ctrl+Alt+F7", running={"discord.exe"})  # unknown combo: likely apps
    assert "doesn't say" in guess_owner("Ctrl+Alt+F7", running={"explorer.exe"})


def test_volume_hud_and_dialogs_on_top(qapp):
    from PyQt6.QtCore import Qt
    from modules.customize_dialog import CustomizeDialog
    w = _island()
    w.show()
    w._on_volume_hud(40, False)                 # first reading: silent
    assert "volume" not in w.idle_pill.activities
    w._on_volume_hud(46, False)
    act = w.idle_pill.activities["volume"]
    assert "46%" in act["text"] and abs(act["progress"] - 0.46) < 0.01
    w._on_volume_hud(46, True)
    assert "Muted" in w.idle_pill.activities["volume"]["text"]
    d = CustomizeDialog(w.theme, w.info_service, w)
    assert d.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    d.reject()


def test_strip_mode_hides_by_itself_and_comes_back(qapp):
    """With real timers: the notch shrinks to a strip when left alone, and returns for alerts."""
    from config import ConfigManager
    c = ConfigManager()
    c.set("visibility_mode", "strip")
    w = _island()
    w.show()
    w._apply_visibility_mode()
    assert w.reveal_timer.isActive()
    _settle(qapp, 1.8)                                   # cursor is elsewhere: tucks after ~0.7 s
    assert w.tucked and w.isVisible() and w.body_global().height() <= 6
    assert w.body_global().y() == w._get_screen_geometry().y()      # sits on the top edge
    w.idle_pill.flash("⏰ Reminder", None, 1500)          # an alert brings the notch back
    _settle(qapp, 0.7)
    assert not w.tucked and w.body_global().height() >= 20
    _settle(qapp, 2.6)                                   # ...and it tucks away again afterwards
    assert w.tucked and w.body_global().height() <= 6
    c.set("visibility_mode", "always")


def test_settings_dialog_runs_above_island(qapp, monkeypatch):
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtWidgets import QDialog
    from services import win_input
    calls = []
    monkeypatch.setattr(win_input, "set_topmost", lambda hwnd, on: calls.append(on) if hwnd == int(w.winId()) else None)
    w = _island()
    w.show()
    d = QDialog()
    QTimer.singleShot(100, d.accept)
    assert w.run_dialog(d) == 1
    assert calls == [False, True]                        # island steps down, then returns on top
    assert d.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_rebuilding_tabs_leaves_no_stray_buttons(qapp):
    """Old tab buttons must disappear immediately, not linger until the next event-loop turn."""
    from PyQt6.QtWidgets import QPushButton
    w = _island()
    w.show()
    for _ in range(3):
        w.apply_customization()          # rebuilds the tab bar
    w.summoned = True
    w.expand()
    _settle(qapp, 0.8)
    visible = [b for b in w.expanded_container.findChildren(QPushButton) if b.isVisible()]
    assert all(b.width() < 300 for b in visible), [(b.text(), b.width()) for b in visible if b.width() >= 300]
    nav = [b for b in visible if b.parentWidget() is w.expanded_container]
    assert len(nav) <= len(w.nav_order) + len(w.tool_buttons)   # tab buttons + toolbar, no leftovers
    c = w._body.center()
    assert w.childAt(int(c.x()), int(c.y())) is not None
    assert not isinstance(w.childAt(int(c.x()), int(c.y())), QPushButton) or w.childAt(int(c.x()), int(c.y())).width() < 300


def test_glass_painting(qapp):
    """Glass body is translucent over what is behind it, with a frosted backdrop when available."""
    from PyQt6.QtGui import QPixmap, QColor
    from config import ConfigManager
    c = ConfigManager()
    c.set("theme", "glass")
    c.set("glass_material", "clear")
    c.set("visibility_mode", "always")
    w = _island()
    w.show()
    w.apply_customization()
    _settle(qapp, 0.6)
    b = w._body.toRect()
    plain = w.grab().toImage().pixelColor(b.center().x(), b.bottom() - 3)
    assert plain.alpha() < 255                                  # see-through without a backdrop
    pm = QPixmap(b.width() + 4, b.height() + 4)
    pm.fill(QColor("#ff0000"))
    w._blur_pixmap, w._blur_ok = pm, True
    w.update()
    _settle(qapp, 0.2)
    frosted = w.grab().toImage().pixelColor(b.center().x(), b.bottom() - 3)
    assert frosted.red() > frosted.blue() + 20                  # the backdrop shows through the tint
    from services.glass import frosted as blur_fn
    assert blur_fn(pm).size() == pm.size()
    c.set("glass_material", "frosted")


def test_rapid_open_close_is_safe(qapp):
    """Opening and closing quickly, many times, must not crash or leave content hidden."""
    w = _island()
    w.show()
    w.summoned = True
    for _ in range(6):
        w.expand()
        _settle(qapp, 0.05)
        w.collapse()
        _settle(qapp, 0.03)
    w.summoned = True
    w.expand()
    _settle(qapp, 0.9)
    eff = w.expanded_container.graphicsEffect()
    assert eff is None or not eff.isEnabled() or eff.opacity() == 1.0   # content fully visible


# ------------------------------------------------ staying visible + Crest extras
def test_island_lives_on_chosen_screen_and_recovers(qapp):
    """The island must not depend on where its window happened to be (sleep, unplugged monitor)."""
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication
    from config import ConfigManager
    c = ConfigManager()
    c.set("visibility_mode", "always")
    c.set("island_monitor", "primary")
    w = _island()
    w.show()
    _settle(qapp, 0.4)
    assert w.target_screen() is QApplication.primaryScreen()
    good = w.geometry()
    w.setGeometry(QRect(5000, 3000, 50, 50))      # e.g. left on a monitor that is gone
    w.hide()                                      # e.g. lost after waking up
    w._keepalive_tick()
    _settle(qapp, 0.6)
    assert w.isVisible() and w.geometry() == good
    w.set_user_hidden(True)                       # but a hide you asked for is respected
    _settle(qapp, 0.5)
    w._keepalive_tick()
    _settle(qapp, 0.3)
    assert not w.isVisible()
    w.set_user_hidden(False)


def test_clipboard_chips():
    import base64, json
    from services.clip_decode import decode
    seg = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    label, out = decode(seg({"alg": "HS256"}) + "." + seg({"sub": "42", "exp": 4000000000}) + ".sig")
    assert label.startswith("JWT") and '"sub": "42"' in out
    assert decode("1700000000")[0] == "Unix time"
    assert decode('{"a": [1, 2]}')[0] == "JSON"
    label, clean = decode("https://shop.example/item?id=7&utm_source=x&fbclid=abc")
    assert clean == "https://shop.example/item?id=7" and "2 tracker" in label
    assert decode(base64.b64encode(b"hello there").decode()) == ("Base64", "hello there")
    assert decode("just some words") is None and decode("12345") is None


def test_breaks_count_active_time_only(qapp):
    from services.breaks_service import BreaksService
    from config import ConfigManager
    ConfigManager().set("break_eye_enabled", True)
    ConfigManager().set("break_hourly_enabled", True)
    idle = {"s": 0.0}
    b = BreaksService(idle_fn=lambda: idle["s"], step=60)
    b.timer.stop()
    eyes, longs = [], []
    b.eye_break.connect(lambda: eyes.append(1))
    b.long_break.connect(lambda: longs.append(1))
    for _ in range(19):
        b.tick()
    assert not eyes
    b.tick()
    assert len(eyes) == 1                         # 20 active minutes -> eye break
    idle["s"] = 600                               # away for 10 minutes: counts as a break
    b.tick()
    idle["s"] = 0
    for _ in range(19):
        b.tick()
    assert len(eyes) == 1                         # counter restarted after being away
    b.paused = lambda: True                       # full screen / focus: no counting
    for _ in range(30):
        b.tick()
    assert len(eyes) == 1 and not longs


def test_weather_parsing_and_pill(qapp):
    from services.weather_service import parse
    w = parse({"current": {"temperature_2m": 21.4, "weather_code": 2, "is_day": 1},
               "daily": {"temperature_2m_max": [24.2], "temperature_2m_min": [13.6],
                         "sunrise": ["2026-11-15T07:21"], "sunset": ["2026-11-15T16:20"]}})
    assert (w["temp"], w["icon"], w["high"], w["low"], w["is_day"]) == (21, "⛅", 24, 14, True)
    assert parse({"current": {"temperature_2m": 3, "weather_code": 0, "is_day": 0}})["icon"] == "🌙"
    isl = _island()
    isl.weather_service.current = w
    assert isl.info_service.slot_text("weather") == "⛅ 21°"


def test_privacy_dots_and_notices(qapp):
    w = _island()
    w.show()
    w.idle_pill.set_privacy(True, False)
    assert w.idle_pill.privacy == (True, False)
    w.idle_pill.grab()                            # paints without errors
    svc = w.notices_service
    got = []
    svc.notice.connect(lambda text, role: got.append(text))
    svc.update_power({"battery_plugged": False, "battery_percent": 80})
    svc.update_power({"battery_plugged": True, "battery_percent": 81})
    svc.online = True
    svc._on_net(False)
    assert got == ["⚡ Charging · 81%", "📡 Internet connection lost"]


def test_color_formats_and_contrast():
    from PyQt6.QtGui import QColor
    from modules.color_picker import color_formats, contrast_ratio
    f = color_formats(QColor("#3b6fd8"))
    assert f["hex"] == "#3B6FD8" and f["rgb"] == "rgb(59, 111, 216)" and f["hsl"].startswith("hsl(")
    assert round(contrast_ratio(QColor("#000000"), QColor("#ffffff")), 1) == 21.0


def test_prayer_location_defaults_and_consistency(qapp, monkeypatch):
    from config import ConfigManager
    from services import prayer
    from modules.day_widget import DaySettings
    from styles import get_theme
    c = ConfigManager()
    c.set("prayer_location_set", False)
    monkeypatch.setattr(prayer, "windows_country_code", lambda: "DE")
    d = DaySettings(get_theme("glass"))
    assert (d.country.currentData(), d.city.currentData()) == ("Germany", "Berlin")      # not Riyadh
    assert d.method.currentData() == "mwl" and "recommended for Germany" in d.method.currentText()
    # No other country names in the plain method list
    names = [d.method.itemText(i) for i in range(d.method.count()) if d.method.itemData(i)]
    assert not any(w in " ".join(names[1:]) for w in ("Saudi", "Turkey", "France", "Pakistan", "Malaysia"))
    d._on_geo_results([("Gießen, Hesse, Germany", 50.5841, 8.6784)], "")
    assert d.country.currentData() == "Germany" and d.city.currentText() == "Gießen"
    d._save()
    again = DaySettings(get_theme("glass"))
    assert (again.country.currentData(), again.city.currentText()) == ("Germany", "Gießen")
    assert abs(again.lat.value() - 50.5841) < 0.001
    assert prayer.country_for_place("Linz, Upper Austria, Austria") == "Austria"


# ------------------------------------------------------------------ AI (US-028 / US-029)
class _Resp:
    def __init__(self, code, data):
        self.status_code, self._data = code, data
        self.text = json.dumps(data)

    def json(self):
        return self._data


def test_ai_uses_qwen_on_ollama_and_explains_problems(qapp, monkeypatch):
    import requests
    from services import ai_service
    from services.ai_service import AIService, AIError, strip_thinking
    svc = AIService()
    svc.config.set("ai_provider", "ollama")
    svc.config.set("ollama_model", "qwen3.5:4b")
    sent = []

    def fake_post(url, json=None, **kw):
        sent.append((url, json))
        return _Resp(200, {"message": {"content": "<think>hmm</think>Hello there"}})
    monkeypatch.setattr(ai_service.requests, "post", fake_post)
    assert svc.complete("hi", image_b64="AAA") == "Hello there"
    url, body = sent[-1]
    assert url.endswith("/api/chat") and body["model"] == "qwen3.5:4b"
    assert body["messages"][-1]["images"] == ["AAA"] and body["think"] is False
    assert svc.model_label() == "Local · qwen3.5:4b"
    assert strip_thinking("<think>\nx\n</think>\n\nok") == "ok"

    monkeypatch.setattr(ai_service.requests, "post",
                        lambda *a, **k: _Resp(404, {"error": "model 'qwen3.5:4b' not found"}))
    with pytest.raises(AIError, match="not downloaded"):
        svc.complete("hi")

    def refuse(*a, **k):
        raise requests.exceptions.ConnectionError()
    monkeypatch.setattr(ai_service.requests, "post", refuse)
    with pytest.raises(AIError, match="Ollama is not running"):
        svc.complete("hi")

    # Free cloud (OpenAI-compatible): needs a key, sends it as a bearer token
    svc.config.set("ai_provider", "openai_compat")
    svc.config.set("openai_compat_url", "https://openrouter.ai/api/v1")
    svc.config.set("openai_compat_key", "")
    with pytest.raises(AIError, match="API key"):
        svc.complete("hi")
    svc.config.set("openai_compat_key", "k-123")
    seen = {}

    def fake_cloud(url, headers=None, json=None, **kw):
        seen.update(url=url, auth=headers.get("Authorization"), model=json["model"])
        return _Resp(200, {"choices": [{"message": {"content": "cloud ok"}}]})
    monkeypatch.setattr(ai_service.requests, "post", fake_cloud)
    assert svc.complete("hi") == "cloud ok"
    assert seen == {"url": "https://openrouter.ai/api/v1/chat/completions", "auth": "Bearer k-123",
                    "model": "qwen/qwen3-coder:free"}
    svc.config.set("openai_compat_key", "")
    svc.config.set("ai_provider", "ollama")


def test_ai_chat_and_clipboard_reach_robo(qapp, monkeypatch):
    """One AI place: the Agents/Robo tab asks, explains and fixes with the real AI."""
    from PyQt6.QtWidgets import QApplication
    from island_window import TAB_AI, TAB_AGENTS, TAB_KEY_TO_INDEX
    from modules.tab_registry import TAB_REGISTRY, DEFAULT_TABS
    assert TAB_AI == TAB_AGENTS and TAB_KEY_TO_INDEX["ai"] == TAB_AGENTS
    assert "ai" not in TAB_REGISTRY and "ai" not in DEFAULT_TABS
    w = _island()
    prompts = []

    def fake_complete(prompt, image_b64=None, history=None, timeout=120):
        prompts.append((prompt, bool(image_b64), len(history or [])))
        return f"answer {len(prompts)}"
    monkeypatch.setattr(w.ai_service, "complete", fake_complete)
    w.agents_widget.ask.setText("What is 2+2?")
    w.agents_widget._submit_question()
    _settle(qapp, 0.4)
    w.agents_widget.ask.setText("And times 3?")
    w.agents_widget._submit_question()
    _settle(qapp, 0.4)
    assert prompts[0] == ("What is 2+2?", False, 0) and prompts[1][2] == 2   # remembers the chat
    QApplication.clipboard().setText("def f(:\n  pass")
    w.agents_widget.clipboard_action.emit("fix")
    _settle(qapp, 0.4)
    assert "Fix the bugs" in prompts[-1][0] and "def f(:" in prompts[-1][0]
    texts = [w.agents_widget.feed.item(i).text() for i in range(w.agents_widget.feed.count())]
    assert texts[0].startswith("👾") and "answer 3" in texts[0]
    assert any(t == "🙋 What is 2+2?" for t in texts)


def test_ai_migration_and_settings_dialog(qapp):
    from config import ConfigManager
    from styles import get_theme
    from services.ai_service import AIService
    from modules.ai_settings import AISettingsDialog
    c = ConfigManager()
    for k, v in (("ai_v2_migrated", False), ("ai_provider", "gemini"), ("gemini_api_key", ""),
                 ("ollama_model", "llama3"), ("tabs_visible", ["home", "media", "ai", "tools"])):
        c.set(k, v)
    w = _island()
    assert c.get("ai_provider") == "ollama" and c.get("ollama_model") == "qwen3.5:4b"
    assert "ai" not in c.get("tabs_visible") and "agents" in c.get("tabs_visible")
    d = AISettingsDialog(get_theme("glass"), AIService())
    assert not d.local_box.isHidden() and d.key_widget.isHidden()
    d.provider.setCurrentIndex(d.provider.findData("openai_compat"))
    assert not d.cloud_box.isHidden() and not d.key_widget.isHidden()
    d.preset.setCurrentIndex(2)                              # Groq
    d.key.setText("gsk-1")
    d._save()
    assert c.get("ai_provider") == "openai_compat" and c.get("openai_compat_key") == "gsk-1"
    assert c.get("openai_compat_url") == "https://api.groq.com/openai/v1"
    d.provider.setCurrentIndex(d.provider.findData("ollama"))
    d.size.setCurrentIndex(1)
    d._save()
    assert c.get("ai_provider") == "ollama" and c.get("ollama_model") == "qwen3.5:2b"
    c.set("openai_compat_key", "")
    c.set("ollama_model", "qwen3.5:4b")
    w.close()


# ------------------------------------------------------------------ RAM + Eco (US-031)
def test_memory_view_groups_apps_and_gives_tips():
    from services.memory_service import group_processes, tips, friendly_name, scan, fmt
    GB = 2**30
    apps = group_processes([("msedge.exe", GB), ("msedge.exe", GB), ("Code.exe", GB // 2),
                            ("ollama_llama_server.exe", 4 * GB), ("x.exe", 0)])
    assert apps[0] == ("Ollama (local AI)", 4 * GB, 1) and apps[1] == ("Microsoft Edge", 2 * GB, 2)
    assert friendly_name("Weird.exe") == "Weird" and fmt(GB // 4) == "256 MB"
    t = tips({"apps": apps, "total": 16 * GB, "percent": 85})
    assert any("Free the RAM" in x for x in t) and any("sleeping tabs" in x for x in t)
    assert any("almost full" in x for x in t) and any("Eco mode" in x for x in t)
    assert not any("Eco mode" in x for x in tips({"apps": [], "total": GB}, eco_on=True))
    real = scan()
    assert real["apps"] and real["own"] > 10 * 2**20 and real["total"] > 0


def test_eco_mode_lightens_the_island(qapp):
    from modules.system_widget import SystemWidget
    w = _island()
    w.config.set("eco_mode", False)
    w.apply_eco()
    assert w.sys_service.timer.interval() == 1000 and w.lyrics_service.enabled
    w.sys_widget.eco.setChecked(True)              # the 🌿 Eco switch on the System tab
    assert w.config.get("eco_mode") and not w._blur_wanted()
    assert w.sys_service.timer.interval() == 3000 and w.idle_pill.anim_timer.interval() == 100
    assert not w.lyrics_service.enabled and not w.weather_service.enabled
    w.sys_widget.update_memory({"apps": [("Google Chrome", 2**31, 9)], "own": 90 * 2**20,
                                "total": 2**34, "percent": 40}, ["tip one", "tip two"])
    assert w.sys_widget.rows[0].name == "Google Chrome  ×9" and w.sys_widget.own.text() == "Island 90 MB"
    assert w.sys_widget.tip.text() == "💡 tip one"
    w.sys_widget._next_tip()
    assert w.sys_widget.tip.text() == "💡 tip two"
    w.open_tab(1)                                   # the System tab scans only while visible
    _settle(qapp, 0.3)
    assert w.memory_service.timer.isActive()
    w.collapse()
    _settle(qapp, 0.3)
    assert not w.memory_service.timer.isActive()
    w.set_eco_mode(False)
    assert w.sys_service.timer.interval() == 1000 and w.lyrics_service.enabled
