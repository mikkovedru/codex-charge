"""Local control, startup truth, and failure recovery without sending signals."""
import os
import stat
import sys
import time

import pytest

from recharge_ai_task import autostart, config, quota, tray_control
from recharge_ai_task.config import AppConfig
from recharge_ai_task.targets import Target

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
    from recharge_ai_task import tray
    monkeypatch.setattr(tray, "discover_codex", lambda _: "codex")
    monkeypatch.setattr(tray, "is_autostart_enabled", lambda: False)
    def watch(_cfg, stop):
        _cfg.state.progress = {"phase": "waiting_quota", "next_check_at": 1234}
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
        assert status["watch_progress"] == {"phase": "waiting_quota", "next_check_at": 1234}
        assert status["watch_settings"]["targets"] == [[Target("thread", "a", "A").key, True, True]]
        changed = AppConfig.load()
        changed.continue_prompt = "New signal"
        changed.save()
        tray_control.request("reload")
        deadline = time.monotonic() + 3
        while tray_control.request()["watch_settings"]["signal"] != "New signal":
            assert time.monotonic() < deadline
            time.sleep(.02)
        assert tray_control.request()["auto_watch_restart"]
        tray_control.request("stop-watch")
        deadline = time.monotonic() + 2
        while tray_control.request()["desktop_watch"] and time.monotonic() < deadline:
            time.sleep(.02)
        assert not tray_control.request()["desktop_watch"]
        assert tray_control.request()["watch_progress"] is None
    finally:
        app.stop_service()
        server.close()


def test_watch_controller_rejects_empty_selection(monkeypatch):
    from recharge_ai_task import tray
    app = tray.TrayApp()
    with pytest.raises(RuntimeError, match="at least one target"):
        app.control("start-watch")
    assert not app.control("status")["desktop_watch"]


def test_simultaneous_gui_and_menu_start_create_one_watch(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from recharge_ai_task import tray
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
    from recharge_ai_task import tray
    calls = []
    monkeypatch.setattr(tray.sys, "argv", ["recharge-ai-task-tray", *args])
    monkeypatch.setattr(tray_control, "request", lambda action: calls.append(action) or {"pid": 123})
    monkeypatch.setattr(tray.TrayApp, "run", lambda *a, **kw: pytest.fail("Created a duplicate tray"))
    assert tray.main() == 0
    assert calls == [command]


@pytest.mark.parametrize("args,options", [(["--targets"], {"show_gui": True, "settings": False}),
                                        (["--settings"], {"show_gui": True, "settings": True})])
def test_first_gui_launch_runs_full_tray(monkeypatch, args, options):
    from recharge_ai_task import tray
    calls = []
    monkeypatch.setattr(tray.sys, "argv", ["recharge-ai-task-tray", *args])
    def missing(_): raise FileNotFoundError("no tray")
    monkeypatch.setattr(tray_control, "request", missing)
    monkeypatch.setattr(tray.TrayApp, "run", lambda self, **kw: calls.append(kw))
    assert tray.main() == 0
    assert calls == [options]


def test_gui_control_queues_the_right_window_action(monkeypatch):
    from recharge_ai_task import tray
    app, calls = tray.TrayApp(), []
    monkeypatch.setattr(app, "open_targets", lambda **kw: calls.append(kw))
    assert app.control("open-gui")["gui_control"]
    assert app.control("open-settings")["gui_control"]
    assert calls == [{"settings": False}, {"settings": True}]
    assert not app.control("status")["desktop_watch"]


def test_icon_default_toggles_but_open_menu_always_opens(monkeypatch):
    from recharge_ai_task import tray
    app, calls = tray.TrayApp(), []
    monkeypatch.setattr(app, "open_targets", lambda *a, **kw: calls.append(kw))
    menu = app._build_menu()
    menu(None)  # Icon activation invokes the hidden default action.
    assert calls == [{"toggle": True}]
    calls.clear()
    next(item for item in menu if item.text == "Open Recharge AI-task…")(None)
    assert calls == [{}]


def wait_until(check, timeout=3):
    deadline = time.monotonic() + timeout
    while not check():
        assert time.monotonic() < deadline
        time.sleep(.01)


def test_automatic_restart_coalesces_edits_and_retains_delivery_state(monkeypatch):
    from recharge_ai_task import tray
    calls, active = [], []
    monkeypatch.setattr(tray, "discover_codex", lambda _: "codex")
    def watch(cfg, stop):
        active.append(cfg)
        assert len(active) == 1, "Overlapping watch workers"
        calls.append(cfg)
        stop.wait(5)
        active.remove(cfg)
        return 0
    monkeypatch.setattr(tray, "run_desktop_watch", watch)
    AppConfig(desktop_targets=[Target("thread", "a", "A", send_prompt=True, send_goal=False).to_dict()]).save()
    app = tray.TrayApp()
    try:
        app.control("start-watch")
        wait_until(lambda:len(calls) == 1)
        calls[0].state.delivered.add("already sent")
        for text in ("Draft", "Second", "Final prompt"):
            config = AppConfig.load(); config.continue_prompt = text; config.save()
            assert app.control("reload")["restarting"]
        time.sleep(.15)
        assert len(calls) == 1
        wait_until(lambda:len(calls) == 2 and not app.control("status")["restarting"])
        assert calls[1].continue_prompt == "Final prompt"
        assert calls[1].state is calls[0].state and "already sent" in calls[1].state.delivered
        app.control("stop-watch")
        wait_until(lambda:not app.control("status")["desktop_watch"])
        config = AppConfig.load(); config.poll_seconds += 1; config.save()
        app.control("reload")
        time.sleep(.7)
        assert len(calls) == 2 and not app.control("status")["watch_requested"]
    finally:
        app.stop_service()
        if app._watch_thread: app._watch_thread.join(2)


def test_stop_cancels_restart_while_previous_worker_is_finishing(monkeypatch):
    from recharge_ai_task import tray
    import threading
    finishing, release = threading.Event(), threading.Event()
    calls = []
    def watch(cfg, stop):
        calls.append(cfg)
        stop.wait(5)
        finishing.set()
        release.wait(3)
        return 0
    monkeypatch.setattr(tray, "run_desktop_watch", watch)
    monkeypatch.setattr(tray, "discover_codex", lambda _: "codex")
    AppConfig(desktop_targets=[Target("thread", "a", "A").to_dict()]).save()
    app = tray.TrayApp()
    try:
        app.control("start-watch")
        config = AppConfig.load(); config.poll_seconds += 1; config.save()
        app.control("reload")
        assert finishing.wait(2)
        assert app.control("status")["stopping"] and app.control("status")["restarting"]
        app.control("stop-watch")
        release.set()
        wait_until(lambda:not app.control("status")["desktop_watch"])
        time.sleep(.1)
        assert len(calls) == 1 and not app.control("status")["watch_requested"]
    finally:
        release.set(); app.stop_service()
        if app._watch_thread: app._watch_thread.join(2)


@pytest.mark.parametrize("empty_selection", [False, True])
def test_invalid_saved_draft_suspends_watch_until_valid(monkeypatch, empty_selection):
    from recharge_ai_task import tray
    calls = []
    def watch(cfg, stop):
        calls.append(cfg)
        stop.wait(5)
        return 0
    monkeypatch.setattr(tray, "run_desktop_watch", watch)
    monkeypatch.setattr(tray, "discover_codex", lambda _: "codex")
    target = Target("thread", "a", "A", send_prompt=True, send_goal=False)
    AppConfig(desktop_targets=[target.to_dict()]).save()
    app = tray.TrayApp()
    try:
        app.control("start-watch")
        config = AppConfig.load()
        if empty_selection: config.desktop_targets = []
        else: config.continue_prompt = " "
        config.save(); app.control("reload")
        wait_until(lambda:bool(app.control("status")["watch_pause_reason"]))
        status = app.control("status")
        assert status["watch_requested"] and not status["desktop_watch"] and not status["restarting"]
        assert next(item for item in app._build_menu() if item.text == tray.t("tray.stop")).enabled
        config.desktop_targets = [target.to_dict()]; config.continue_prompt = "Valid"; config.save()
        app.control("reload")
        wait_until(lambda:len(calls) == 2)
        assert app.control("status")["desktop_watch"] and not app.control("status")["watch_pause_reason"]
    finally:
        app.stop_service()
        if app._watch_thread: app._watch_thread.join(2)


def test_frozen_startup_command_explicitly_starts_only_the_tray(monkeypatch, tmp_path):
    executable = tmp_path / "recharge-ai-task"
    monkeypatch.setattr(autostart.sys, "frozen", True, raising=False)
    monkeypatch.setattr(autostart.sys, "executable", str(executable))
    assert autostart._tray_command() == f'"{executable}" --tray --autostart'


@pytest.mark.parametrize("platform,suffix", [("linux", ""), ("win32", ".exe")])
def test_frozen_desktop_finds_cli_without_relaunching_itself(monkeypatch, tmp_path, platform, suffix):
    from recharge_ai_task import tray
    monkeypatch.setattr(tray.sys, "platform", platform)
    monkeypatch.setattr(tray.sys, "frozen", True, raising=False)
    desktop = tmp_path / ("recharge-ai-task" + suffix)
    desktop.touch()
    cli = tmp_path / ("recharge-ai-task-cli" + suffix)
    cli.touch()
    monkeypatch.setattr(tray.sys, "executable", str(desktop))
    assert tray._resolve_cli_exe() == [str(cli)]
