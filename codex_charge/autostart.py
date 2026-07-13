"""Cross-platform autostart helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_BAT_NAME = "codex-charge-tray.bat"
_DESKTOP_NAME = "codex-charge-tray.desktop"


def _tray_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}"'
    return f'"{sys.executable}" -m codex_charge.tray'


def _windows_startup_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        raise RuntimeError("APPDATA is not set")
    return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"


def _linux_autostart_dir() -> Path:
    return Path.home() / ".config" / "autostart"


def autostart_target() -> Path | None:
    if sys.platform == "win32":
        return _windows_startup_dir() / _BAT_NAME
    if sys.platform.startswith("linux"):
        return _linux_autostart_dir() / _DESKTOP_NAME
    return None


def is_autostart_enabled() -> bool:
    target = autostart_target()
    return target is not None and target.exists()


def set_autostart(enabled: bool) -> None:
    target = autostart_target()
    if target is None:
        raise RuntimeError("autostart is not supported on this platform")

    if enabled:
        target.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            target.write_text(f"@echo off\r\nstart \"\" {_tray_command()}\r\n", encoding="utf-8")
        else:
            target.write_text(
                "\n".join(
                    [
                        "[Desktop Entry]",
                        "Type=Application",
                        "Name=Codex Charge",
                        f"Exec={_tray_command()}",
                        "X-GNOME-Autostart-enabled=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
    elif target.exists():
        target.unlink()


def sync_autostart(enabled: bool) -> None:
    current = is_autostart_enabled()
    if current != enabled:
        set_autostart(enabled)
