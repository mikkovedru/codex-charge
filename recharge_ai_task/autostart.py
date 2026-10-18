"""Cross-platform autostart helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from ._migration import LEGACY_TRAY_NAME

_BAT_NAME = "recharge-ai-task-tray.bat"
_DESKTOP_NAME = "recharge-ai-task-tray.desktop"


def _tray_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" --autostart'
    return f'"{sys.executable}" -m recharge_ai_task.tray --autostart'


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


def _legacy_target(target: Path) -> Path:
    return target.with_name(LEGACY_TRAY_NAME + target.suffix)


def is_autostart_enabled() -> bool:
    target = autostart_target()
    if target is None:
        return False
    if not target.exists():
        target = _legacy_target(target)
    if not target.exists():
        return False
    if sys.platform.startswith("linux"):
        entries = dict(line.split("=", 1) for line in target.read_text().splitlines() if "=" in line)
        if entries.get("Hidden", "false").lower() == "true":
            return False
        if entries.get("X-GNOME-Autostart-enabled", "true").lower() == "false":
            return False
    return True


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
                        "Name=Recharge AI-task",
                        f"Exec={_tray_command()}",
                        "X-GNOME-Autostart-enabled=true",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
    elif target.exists():
        target.unlink()
    # Only retire the old entry once its replacement is written successfully,
    # or when the user explicitly disables startup. Avoid two login launches.
    _legacy_target(target).unlink(missing_ok=True)


def sync_autostart(enabled: bool) -> None:
    current = is_autostart_enabled()
    target = autostart_target()
    if current != enabled or target is not None and _legacy_target(target).exists():
        set_autostart(enabled)
