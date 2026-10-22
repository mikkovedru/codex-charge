"""Launch the combined desktop process without importing its graphical runtime."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def desktop_command() -> list[str]:
    if getattr(sys, "frozen", False):
        name = "recharge-ai-task.exe" if sys.platform == "win32" else "recharge-ai-task"
        desktop = Path(sys.executable).resolve().with_name(name)
        if not desktop.is_file():
            raise FileNotFoundError(f"Missing desktop executable: {desktop}. Keep the CLI and desktop executables in the same folder.")
        return [str(desktop)]
    return [sys.executable, "-m", "recharge_ai_task.gui"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recharge-ai-task", description="Open the Recharge AI-task dashboard and tray. Closing the dashboard keeps the tray running. On Windows, start the tray without a dashboard.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--tray", action="store_true", help="Start directly in the system tray without opening the dashboard")
    mode.add_argument("--settings", action="store_true", help="Open dashboard settings (Linux)")
    mode.add_argument("--targets", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--autostart", action="store_true", help="Start in the tray and record that this launch was at login")
    parser.epilog = "For terminal commands, use recharge-ai-task-cli (for example: recharge-ai-task-cli quota)."
    return parser


def launch(argv=None, *, tray=False):
    """Launch the desktop process from the CLI without importing GTK/pystray."""
    args = list(argv or [])
    if tray:
        args.insert(0, "--tray")
    # Validate and show help before starting a frozen desktop process.
    parser = _parser()
    options = parser.parse_args(args)
    if sys.platform != "linux" and not (tray or options.tray or options.autostart):
        parser.error("The graphical dashboard requires Linux GTK; use recharge-ai-task --tray")
    try:
        command = desktop_command()
    except FileNotFoundError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    return subprocess.call([*command, *args])
