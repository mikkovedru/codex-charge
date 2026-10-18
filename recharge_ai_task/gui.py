"""Open the GTK dashboard from the CLI or dedicated GUI executable."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="recharge-ai-task gui", description="Open the Recharge AI-task dashboard and system tray; closing the window keeps the tray running.")
    parser.parse_args(argv)
    if sys.platform != "linux":
        parser.error("The graphical dashboard requires Linux GTK")
    if getattr(sys, "frozen", False):
        tray = Path(sys.executable).with_name("recharge-ai-task-tray")
        if not tray.is_file():
            sys.stderr.write(f"Missing companion GUI executable: {tray}\nKeep the three release executables in the same folder.\n")
            return 1
        command = [str(tray)]
    else:
        command = [sys.executable, "-m", "recharge_ai_task.tray"]
    return subprocess.call([*command, "--targets"])


if __name__ == "__main__":
    raise SystemExit(main())
