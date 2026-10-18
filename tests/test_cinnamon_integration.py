"""Opt-in check against the real Cinnamon panel, without changing its settings."""
import os
import subprocess
import sys
import pytest


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_GUI_TESTS") != "1", reason="Requires an active Cinnamon panel")
def test_real_cinnamon_icon():
    env = dict(os.environ)
    env.pop("PYSTRAY_BACKEND", None)
    result = subprocess.run([sys.executable, "-c", r"""
from codex_charge import tray
from codex_charge.tray import TrayApp
tray.is_autostart_enabled = lambda: False
from gi.repository import GLib, Gtk
app = TrayApp()
errors = []
def check(running=False):
    try:
        icon = app._icon
        assert icon._menu_handle is not None
        if type(icon).__name__ == 'CinnamonGtkIcon':
            assert icon._plug.get_embedded()
            assert icon._rendered_size == icon._allocated_size()
            window = icon._xdisplay.create_resource_object('window', icon._plug.get_id())
            geometry = window.get_geometry()
            image = window.get_image(0, 0, geometry.width, geometry.height, 2, 0xffffffff)
            from PIL import Image
            pixels = list(Image.frombytes('RGB', (geometry.width, geometry.height), image.data, 'raw', 'BGRX').getdata())
            assert any(min(pixel) > 220 for pixel in pixels), 'White half was not painted'
            assert any(max(pixel) < 30 for pixel in pixels), 'Black half was not painted'
            if running:
                assert any(pixel[0] < 80 and pixel[1] > 150 and pixel[2] < 180 for pixel in pixels), 'Running strip did not update'
            else:
                assert any(pixel[0] > 180 and pixel[1] > 150 and pixel[2] < 80 for pixel in pixels), 'Status strip was clipped'
        else:
            assert type(icon).__name__ == 'XAppIcon'
            assert icon._status_icon.get_state().value_nick == 'native'
    except Exception as exc:
        errors.append(str(exc))
    if not errors and not running:
        app._set_status(True)
        GLib.timeout_add_seconds(1, lambda: check(True))
    else:
        app.exit_app(app._icon)
    return False
GLib.timeout_add_seconds(3, check)
app.run()
assert not errors, errors
"""], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "CRITICAL" not in result.stderr, result.stderr


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_GUI_TESTS") != "1", reason="Requires an active Cinnamon panel")
def test_double_click_toggles_shared_dashboard_and_close_keeps_tray():
    env = dict(os.environ)
    env.pop("PYSTRAY_BACKEND", None)
    result = subprocess.run([sys.executable, "-c", r'''
import subprocess, sys
from codex_charge import tray, target_ui, tray_control
from codex_charge.targets import Inventory
from gi.repository import GLib
import time
# No live quota queries, chat discovery, startup changes or chat messages.
tray.is_autostart_enabled = lambda: False
target_ui.discover_targets = lambda: Inventory([])
target_ui.discover_codex = lambda _: "offline"
target_ui.fetch_quota = lambda _: (_ for _ in ()).throw(RuntimeError("offline fixture"))
app, errors, windows = tray.TrayApp(), [], []
def stage(callback):
    def run():
        try: callback()
        except Exception as exc:
            import traceback
            errors.append(traceback.format_exc())
            app.exit_app(app._icon)
        return False
    return run
def click_icon():
    icon = app._icon
    if type(icon).__name__ == 'CinnamonGtkIcon':
        assert icon._plug.get_embedded()
        _, x, y = icon._plug.get_window().get_origin()
        size = icon._allocated_size()
        subprocess.run(['xdotool', 'mousemove', str(x + size//2), str(y + size//2)], check=True, timeout=3)
        subprocess.run(['xdotool', 'click', '--repeat', '2', '--delay', '80', '1'], check=True, timeout=3)
    else:
        assert type(icon).__name__ == 'XAppIcon'
        assert icon._status_icon.get_primary_menu() is None
        assert icon._status_icon.get_secondary_menu() is not None
        timestamp = int(time.monotonic()*1000) % (2**32)
        icon._status_icon.emit('button-press-event', 0, 0, 1, timestamp, 0)
        icon._status_icon.emit('button-press-event', 0, 0, 1, (timestamp+80) % (2**32), 0)
def double_click():
    assert app._picker is None
    click_icon()
    GLib.timeout_add(500, stage(hide))
def hide():
    picker = app._picker
    assert picker is not None and picker.get_visible()
    picker.signal_buffer.set_text("Keep this\nmultiline prompt")
    windows.append(picker)
    click_icon()
    GLib.timeout_add(500, stage(hidden))
def hidden():
    assert app._picker is windows[0] and not app._picker.get_visible()
    assert not app._picker.closed and app._icon._loop.is_running()
    assert app._picker._prompt_text() == "Keep this\nmultiline prompt"
    assert tray_control.request()["gui_control"]
    click_icon()
    GLib.timeout_add(500, stage(reuse))
def reuse():
    picker = app._picker
    assert picker is not None and picker.get_visible()
    assert not picker.quit_on_close
    assert picker is windows[0]
    assert picker._prompt_text() == 'Keep this\nmultiline prompt'
    picker.hide()  # CLI launch restores a hidden dashboard and never toggles it off.
    for command in ([sys.executable, '-m', 'codex_charge.gui'],
                    [sys.executable, '-m', 'codex_charge.cli', 'gui'],
                    [sys.executable, '-m', 'codex_charge.cli', 'targets', '--gui']):
        call = subprocess.run(command, capture_output=True, text=True, timeout=8)
        assert call.returncode == 0, call.stderr
    GLib.timeout_add(300, stage(close))
def close():
    assert app._picker is windows[0] and app._picker.get_visible()
    assert app._picker._prompt_text() == 'Keep this\nmultiline prompt'
    app._picker.destroy()
    assert app._picker.closed
    assert app._icon._loop.is_running()
    assert tray_control.request()['gui_control']
    app.open_targets()
    GLib.timeout_add(300, stage(reopened))
def reopened():
    assert app._picker is not windows[0] and app._picker.get_visible()
    assert app._picker._prompt_text() == 'Keep this\nmultiline prompt'
    assert app._icon._loop.is_running()
    app.exit_app(app._icon)
GLib.timeout_add_seconds(2, stage(double_click))
app.run()
assert not errors, errors
assert not tray_control.control_path().exists()
'''], env=env, capture_output=True, text=True, timeout=25)
    assert result.returncode == 0, result.stderr
    assert "CRITICAL" not in result.stderr, result.stderr
