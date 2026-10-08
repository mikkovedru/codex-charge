"""Opt-in GTK regression using synthetic targets and isolated settings."""
import os
import subprocess
import sys
import pytest


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_GUI_TESTS") != "1", reason="Requires Linux GTK and a display")
def test_picker_filters_selects_and_saves():
    result = subprocess.run([sys.executable, "-c", r'''
from codex_charge import target_ui
from codex_charge.targets import Inventory, Target
from codex_charge.config import AppConfig, config_dir
from codex_charge.quota import Quota, RateWindow
from codex_charge import autostart
from pathlib import Path
from dataclasses import replace
import time
# Keep GUI tests offline and startup changes confined to this test directory.
autostart.autostart_target = lambda: config_dir() / "test.desktop"
target_ui.discover_codex = lambda _: "codex"
current_quota = Quota("test", RateWindow(42,300,int(time.time())+3600), RateWindow(23,10080,int(time.time())+86400),False)
target_ui.fetch_quota = lambda _: current_quota
runtime = {"desktop_watch": False, "launched_at_startup": True}
commands = []
def control(command="status", **kwargs):
    commands.append(command)
    if command == "start-watch":
        runtime["desktop_watch"] = True
        runtime["watch_settings"] = target_ui.tray_control.watch_settings(AppConfig.load())
    if command == "stop-watch": runtime["desktop_watch"] = False
    return dict(runtime)
target_ui.tray_control.request = control
from gi.repository import GLib, Gtk
alpha = Target("thread", "alpha", "Same title", instance="profile", deeplink="codex://threads/alpha", task_status="Running", goal_status="Active")
beta = Target("thread", "beta", "Same title", instance="profile", deeplink="codex://threads/beta", task_status="Idle", goal_status="Paused")
target_ui.discover_targets = lambda: Inventory([alpha, beta])
AppConfig().save()
window = target_ui.TargetPicker()
window.show_all()
errors = []
def idle():
    deadline = time.monotonic() + 3
    while window.busy or window.runtime_busy or window.quota_busy or window.discovery_busy:
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        assert time.monotonic() < deadline
        time.sleep(.005)
def check():
    if window.busy or window.runtime_busy or window.quota_busy or window.discovery_busy:
        return True
    try:
        assert "Saved" in window.save_state.get_text()
        assert "42%" in window.quota_label.get_text()
        assert "Weekly" in window.quota_label.get_text() and "resets" in window.quota_label.get_text()
        assert "started at login: Yes" in window.startup_label.get_text()
        window.search.set_text("beta")
        window.filtered.refilter()
        assert len(window.filtered) == 1
        window._toggle(None, "0")
        assert list(window.selected.values()) == [beta]
        assert window.dirty() and "Unsaved" in window.save_state.get_text()
        assert [c.get_title() for c in window.table.get_columns()][2:4] == ["Task status", "Goal status"]
        window.table.get_selection().select_path("0")
        target_ui.discover_targets = lambda: Inventory([alpha, replace(beta, task_status="Waiting for input", goal_status="Blocked")])
        window.refresh_statuses()
        assert not window.busy and window.table.get_sensitive()
        idle()
        assert window._row_target().id == "beta"
        assert window.dirty() and list(window.selected) == [beta.key]
        assert window.filtered[0][10:12] == ["Waiting for input", "Blocked"]
        assert "Every 15 seconds" in window.inventory_status.get_text()
        window.search.set_text("blocked")
        window.filtered.refilter()
        assert len(window.filtered) == 1
        # Selected recipients remain visible when discovery no longer finds them.
        target_ui.discover_targets = lambda: Inventory([alpha])
        window.search.set_text("beta")
        window.filtered.refilter()
        window.refresh_statuses()
        idle()
        assert list(window.selected) == [beta.key]
        assert window.filtered[0][10:12] == ["Unavailable", "Unavailable"]
        assert window.filtered[0][3] == "Unavailable — saved selection"
        target_ui.discover_targets = lambda: Inventory([alpha, beta])
        window.refresh_statuses()
        idle()
        window.toggle_watch()
        assert "Save selection" in window.status.get_text()
        assert "start-watch" not in commands
        window.search.set_text("")
        window.filtered.refilter()
        window._toggle(None, "0")
        window.goal.set_active(False)
        window.signal.set_text("Continue")
        window.save()
        saved = AppConfig.load()
        assert {t.id for t in saved.targets()} == {"alpha", "beta"}
        assert saved.continue_prompt == "Continue"
        assert not saved.goal_mode
        assert not window.dirty() and "Saved" in window.save_state.get_text()
        window.signal.set_text("Edited")
        assert window.dirty()
        window.signal.set_text("Continue")
        assert not window.dirty()
        window.goal.set_active(True)
        window.save()
        idle()
        window.toggle_watch()
        idle()
        assert "Restart the tray" in window.status.get_text()
        assert "start-watch" not in commands
        window.goal.set_active(False)
        window.save()
        idle()
        # A failed automatic refresh must not show the last statuses as live.
        target_ui.discover_targets = lambda: (_ for _ in ()).throw(RuntimeError("disconnected"))
        window.refresh_statuses()
        idle()
        assert all(row[10:12] == ["Unavailable", "Unavailable"] for row in window.store)
        assert "disconnected" in window.inventory_status.get_text()
        assert not window.dirty()
        from codex_charge.settings_ui import SettingsDialog
        dialog = SettingsDialog(window)
        dialog.grace.set_value(37)
        dialog.poll.set_value(9)
        dialog.autostart.set_active(True)
        dialog.save_settings()
        dialog.destroy()
        settings = AppConfig.load()
        assert settings.grace_seconds == 37 and settings.poll_seconds == 9
        assert {t.id for t in settings.targets()} == {"alpha", "beta"}
        assert "--autostart" in autostart.autostart_target().read_text()
        window._render_runtime()
        assert "Run at login: Enabled" in window.startup_label.get_text()
        idle()
        window.toggle_watch()
        idle()
        assert "Desktop watch: On" in window.watch_label.get_text()
        assert window.watch_button.get_label() == "Stop Desktop watch"
        changed = AppConfig.load()
        changed.poll_seconds += 1
        changed.save()
        window.poll_runtime()
        idle()
        assert "restart" in window.watch_label.get_text()
        window.toggle_watch()
        idle()
        assert "Desktop watch: Off" in window.watch_label.get_text()
        changed = AppConfig.load()
        changed.continue_prompt = "External edit"
        changed.save()
        window.poll_runtime()
        idle()
        assert window.dirty() and "Unsaved" in window.save_state.get_text()
        target_ui.fetch_quota = lambda _: (_ for _ in ()).throw(RuntimeError("offline"))
        window.refresh_quota()
        idle()
        assert "42%" in window.quota_label.get_text()
        assert "Latest refresh failed: offline" in window.quota_label.get_text()
    except Exception as exc:
        errors.append(str(exc))
    finally:
        window.destroy()
    return False
GLib.timeout_add(100, check)
Gtk.main()
assert not errors, errors
'''], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert "CRITICAL" not in result.stderr, result.stderr
