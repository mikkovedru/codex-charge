"""English application messages shared by the CLI and tray."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def _load_messages() -> dict[str, str]:
    # PyInstaller preserves the package directory for collected data files.
    path = Path(__file__).resolve().parent / "locales" / "en.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, **kwargs: Any) -> str:
    template = _load_messages().get(key, key)
    return template.format(**kwargs) if kwargs else template
