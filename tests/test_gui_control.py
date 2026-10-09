"""Local control, startup truth, and failure recovery without sending signals."""
import os
import stat
import sys
import time

import pytest

from codex_charge import autostart, config, quota, tray_control
from codex_charge.config import AppConfig
from codex_charge.targets import Target

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux tray control and startup integration")


def test_local_control_roundtrip_and_cleanup():
    calls = []
    def handler(command):
        calls.append(command)
        if command != "status":
            raise ValueError("unknown command")
        return {"desktop_watch": False}
    server = tray_control.ControlServer(handler)
    server.start()
    try:
        assert stat.S_IMODE(tray_control.control_path().stat().st_mode) == 0o600
        assert tray_control.request() == {"desktop_watch": False}
        with pytest.raises(RuntimeError, match="unknown command"):
            tray_control.request("wrong")
        with pytest.raises(RuntimeError, match="already running"):
            tray_control.ControlServer(handler).start()
        assert tray_control.request()["desktop_watch"] is False
    finally:
        server.close()
    assert not tray_control.control_path().exists()


def test_control_does_not_replace_unrelated_file():
    path = tray_control.control_path()
    path.write_text("keep me")
    with pytest.raises(RuntimeError, match="unrelated"):
        tray_control.ControlServer(lambda _: {}).start()
    assert path.read_text() == "keep me"


def test_atomic_save_preserves_old_settings_if_replace_fails(monkeypatch):
    AppConfig(continue_prompt="old").save()
    before = config.config_path().read_bytes()
    def fail(*_): raise OSError("disk error")
    monkeypatch.setattr(config.os, "replace", fail)
    with pytest.raises(OSError):
        AppConfig(continue_prompt="new").save()
    assert config.config_path().read_bytes() == before
    assert not list(config.config_dir().glob("*.tmp"))


def test_startup_entry_has_marker_and_respects_disabled_os_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    path = tmp_path / "tray.desktop"
    monkeypatch.setattr(autostart, "autostart_target", lambda: path)
    autostart.set_autostart(True)
    assert autostart.is_autostart_enabled()
    assert "--autostart" in path.read_text()
    path.write_text(path.read_text() + "Hidden=true\n")
    assert not autostart.is_autostart_enabled()
    autostart.set_autostart(True)
    path.write_text(path.read_text().replace("Autostart-enabled=true", "Autostart-enabled=false"))
    assert not autostart.is_autostart_enabled()
    autostart.set_autostart(False)
    assert not path.exists()


def test_quiet_quota_server_times_out_and_is_killed(tmp_path):
    executable = tmp_path / "codex"
    pidfile = tmp_path / "pid"
    executable.write_text(f"#!/usr/bin/env python3\nimport os,time\nopen({str(pidfile)!r},'w').write(str(os.getpid()))\ntime.sleep(60)\n")
    executable.chmod(0o700)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="initialize"):
        quota.fetch_quota(str(executable), timeout=.3)
    assert time.monotonic() - started < 3
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


def test_watch_controller_tracks_actual_thread_and_settings(monkeypatch):
    from codex_charge import tray
    monkeypatch.setattr(tray, "discover_codex", lambda _: "codex")
    monkeypatch.setattr(tray, "is_autostart_enabled", lambda: False)
    def watch(_cfg, stop):
        stop.wait(5)
        return 0
    monkeypatch.setattr(tray, "run_desktop_watch", watch)
    AppConfig(desktop_targets=[Target("thread", "a", "A").to_dict()]).save()
    app = tray.TrayApp(launched_at_startup=True)
    server = tray_control.ControlServer(app.control)
    server.start()
    try:
        assert not tray_control.request()["desktop_watch"]
        status = tray_control.request("start-watch")
        assert status["desktop_watch"] and status["launched_at_startup"]
        assert status["watch_settings"]["targets"] == [Target("thread", "a", "A").key]
        changed = AppConfig.load()
        changed.continue_prompt = "New signal"
        changed.save()
        tray_control.request("reload")
        assert tray_control.request()["watch_settings"]["signal"] != "New signal"
        tray_control.request("stop-watch")
        deadline = time.monotonic() + 2
        while tray_control.request()["desktop_watch"] and time.monotonic() < deadline:
            time.sleep(.02)
        assert not tray_control.request()["desktop_watch"]
    finally:
        app.stop_service()
        server.close()


def test_watch_controller_rejects_empty_selection(monkeypatch):
    from codex_charge import tray
    app = tray.TrayApp()
    with pytest.raises(RuntimeError, match="at least one target"):
        app.control("start-watch")
    assert not app.control("status")["desktop_watch"]


def test_simultaneous_gui_and_menu_start_create_one_watch(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from codex_charge import tray
    calls = []
    def watch(_cfg, stop):
        calls.append(1)
        stop.wait(5)
        return 0
    monkeypatch.setattr(tray, "run_desktop_watch", watch)
    AppConfig(desktop_targets=[Target("thread", "a", "A").to_dict()]).save()
    app = tray.TrayApp()
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: app.start_desktop(), range(4)))
        assert calls == [1]
        assert app.control("status")["desktop_watch"]
    finally:
        thread = app._watch_thread
        app.stop_service()
        if thread:
            thread.join(2)


@pytest.mark.parametrize("args,command", [(["--targets"], "open-gui"), (["--settings"], "open-settings"), ([], "status")])
def test_tray_launch_reuses_existing_application(monkeypatch, args, command):
    from codex_charge import tray
    calls = []
    monkeypatch.setattr(tray.sys, "argv", ["codex-charge-tray", *args])
    monkeypatch.setattr(tray_control, "request", lambda action: calls.append(action) or {"pid": 123})
    monkeypatch.setattr(tray.TrayApp, "run", lambda *a, **kw: pytest.fail("Created a duplicate tray"))
    assert tray.main() == 0
    assert calls == [command]


@pytest.mark.parametrize("args,options", [(["--targets"], {"show_gui": True, "settings": False}),
                                        (["--settings"], {"show_gui": True, "settings": True})])
def test_first_gui_launch_runs_full_tray(monkeypatch, args, options):
    from codex_charge import tray
    calls = []
    monkeypatch.setattr(tray.sys, "argv", ["codex-charge-tray", *args])
    def missing(_): raise FileNotFoundError("no tray")
    monkeypatch.setattr(tray_control, "request", missing)
    monkeypatch.setattr(tray.TrayApp, "run", lambda self, **kw: calls.append(kw))
    assert tray.main() == 0
    assert calls == [options]


def test_gui_control_queues_the_right_window_action(monkeypatch):
    from codex_charge import tray
    app, calls = tray.TrayApp(), []
    monkeypatch.setattr(app, "open_targets", lambda **kw: calls.append(kw))
    assert app.control("open-gui")["gui_control"]
    assert app.control("open-settings")["gui_control"]
    assert calls == [{"settings": False}, {"settings": True}]
    assert not app.control("status")["desktop_watch"]


def test_icon_default_toggles_but_open_menu_always_opens(monkeypatch):
    from codex_charge import tray
    app, calls = tray.TrayApp(), []
    monkeypatch.setattr(app, "open_targets", lambda *a, **kw: calls.append(kw))
    menu = app._build_menu()
    menu(None)  # Icon activation invokes the hidden default action.
    assert calls == [{"toggle": True}]
    calls.clear()
    next(item for item in menu if item.text == "Open Codex Charge…")(None)
    assert calls == [{}]
