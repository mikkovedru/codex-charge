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
from codex_charge.tray import TrayApp
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
