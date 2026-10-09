import os
os.environ["PYSTRAY_BACKEND"] = "dummy"

from codex_charge import tray_backend, tray


def test_cinnamon_detection(monkeypatch):
    monkeypatch.setattr(tray_backend.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Cinnamon")
    assert tray_backend.is_cinnamon()
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    assert not tray_backend.is_cinnamon()


def test_backend_override(monkeypatch):
    monkeypatch.setattr(tray_backend.sys, "platform", "linux")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "X-Cinnamon")
    monkeypatch.setenv("PYSTRAY_BACKEND", "dummy")
    tray_backend.prepare_backend()
    assert tray_backend.os.environ["PYSTRAY_BACKEND"] == "dummy"


def test_terminal_arguments(monkeypatch):
    monkeypatch.setattr(tray.sys, "platform", "linux")
    monkeypatch.setattr(tray.shutil, "which", lambda name: "/usr/bin/xterm" if name == "xterm" else None)
    assert tray._console_command(["codex-charge", "configure"]) == ["/usr/bin/xterm", "-e", "codex-charge", "configure"]


def test_autostart_checkbox(monkeypatch):
    monkeypatch.setattr(tray, "is_autostart_enabled", lambda: False)
    monkeypatch.setattr(tray, "sync_autostart", lambda enabled: None)
    app = tray.TrayApp()
    item = tray.pystray.MenuItem("Autostart", lambda *_: None, checked=lambda _: app.config.autostart)
    app.toggle_autostart(item=item)
    assert item.checked
