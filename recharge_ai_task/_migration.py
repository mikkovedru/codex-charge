"""Import settings from the previous project identity without overwriting data.

Old spellings live here solely for upgrades; active names use Recharge AI-task.
"""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

LEGACY_CONFIG_DIRECTORY = ".codex-charge"
LEGACY_ENVIRONMENT_PREFIX = "CODEX_CHARGE"
LEGACY_TRAY_NAME = "codex-charge-tray"
# The exact shipped default from versions before the English-only interface.
LEGACY_CONTINUE_PROMPT = "\u7ee7\u7eed"


def environment_value(suffix: str) -> str | None:
    return os.environ.get(f"RECHARGE_AI_TASK_{suffix}") or os.environ.get(f"{LEGACY_ENVIRONMENT_PREFIX}_{suffix}")


def import_settings(root: Path) -> None:
    destination = root / "config.json"
    source = Path.home() / LEGACY_CONFIG_DIRECTORY / "config.json"
    if destination.exists() or not source.is_file():
        return
    # Publish a complete file atomically. A concurrent first launch or an
    # existing new configuration wins; the original settings remain a backup.
    descriptor, name = tempfile.mkstemp(dir=root, prefix="settings-import-", suffix=".tmp")
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(source.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, destination)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)
