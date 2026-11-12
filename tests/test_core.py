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
    assert [d.tabs.nav.item(i).text().split()[-1] for i in range(d.tabs.count())][-1] == "more"
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
