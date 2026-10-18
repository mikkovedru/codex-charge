"""Check that installed artwork remains usable at desktop and tray sizes."""
from PIL import Image, ImageColor
import pytest

from recharge_ai_task.branding import asset_path, tray_image


def test_window_and_windows_executable_icons_include_small_and_large_sizes():
    expected = (16, 24, 32, 48, 64, 128, 256)
    for size in expected:
        with Image.open(asset_path(f"icon-{size}.png")) as icon:
            assert icon.size == (size, size)
    with Image.open(asset_path("recharge-ai-task.ico")) as icon:
        assert icon.ico.sizes() == {(size, size) for size in expected if size <= 256}


@pytest.mark.parametrize("running,color", [(False, "#ffcc00"), (True, "#00df70")])
@pytest.mark.parametrize("size", [16, 24, 32])
def test_tray_logo_and_status_stay_visible_on_light_and_dark_panels(running, color, size):
    icon = tray_image(running=running).resize((size, size), Image.Resampling.LANCZOS)
    assert icon.getchannel("A").getextrema() == (255, 255)
    rgb = icon.convert("RGB")
    pixels = [rgb.getpixel((x,y)) for y in range(size) for x in range(size)]
    assert any(b > 150 and r < 80 for r, g, b in pixels), "Blue recharge ring disappeared"
    assert any(min(pixel) > 220 for pixel in pixels), "White background disappeared"
    assert any(max(pixel) < 90 for pixel in pixels), "Dark detail disappeared"
    status = ImageColor.getrgb(color)
    assert any(max(abs(a-b) for a,b in zip(pixel,status)) < 100 for pixel in pixels), "Status strip disappeared"
    # Compositing cannot recolor the logo on either panel theme.
    for background in ("white", "black"):
        panel = Image.new("RGBA", icon.size, background)
        panel.alpha_composite(icon)
        assert panel.tobytes() == icon.tobytes()


def test_status_updates_do_not_replace_the_logo():
    idle, running = tray_image(), tray_image(running=True)
    assert idle.crop((0,0,64,52)).tobytes() == running.crop((0,0,64,52)).tobytes()
    assert idle.tobytes() != running.tobytes()


def test_enabled_startup_entry_gains_a_persistent_packaged_icon(tmp_path, monkeypatch):
    from recharge_ai_task import autostart
    monkeypatch.setattr(autostart.sys, "platform", "linux")
    target = tmp_path / "startup.desktop"
    target.write_text("[Desktop Entry]\nX-GNOME-Autostart-enabled=true\n")
    monkeypatch.setattr(autostart, "autostart_target", lambda: target)
    autostart.sync_autostart(True)
    entries = dict(line.split("=",1) for line in target.read_text().splitlines() if "=" in line)
    from pathlib import Path
    icon = Path(entries["Icon"])
    assert icon.is_absolute() and icon.read_bytes() == asset_path("icon-256.png").read_bytes()
    assert autostart.is_autostart_enabled()
