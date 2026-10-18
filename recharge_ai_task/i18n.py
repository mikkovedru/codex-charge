"""Lightweight gettext-style i18n for recharge-ai-task."""

from __future__ import annotations

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from ._migration import environment_value

_current_locale = "en"


def _locale_dir() -> Path:
    """Resolve locales/ in dev installs and PyInstaller one-file bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
        for candidate in (
            base / "recharge_ai_task" / "locales",
            base / "locales",
        ):
            if candidate.is_dir():
                return candidate
    return Path(__file__).resolve().parent / "locales"


def normalize_locale(value: str | None) -> str:
    if not value:
        return "en"
    lowered = value.strip().lower().replace("_", "-")
    if lowered.startswith("zh"):
        return "zh"
    return "en"


def set_locale(locale: str) -> None:
    global _current_locale
    _current_locale = normalize_locale(locale)
    _load_messages.cache_clear()


def get_locale() -> str:
    return _current_locale


def init_locale_from_env() -> str:
    env = environment_value("LANG") or os.environ.get("LANG")
    if env:
        set_locale(env)
    return get_locale()


@lru_cache(maxsize=8)
def _load_messages(locale: str) -> dict[str, str]:
    path = _locale_dir() / f"{locale}.json"
    if not path.exists():
        path = _locale_dir() / "en.json"
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, **kwargs: Any) -> str:
    messages = _load_messages(get_locale())
    template = messages.get(key) or _load_messages("en").get(key) or key
    if kwargs:
        return template.format(**kwargs)
    return template


def choose_language_interactive() -> str:
    prompt = "Language / 语言 [en/zh] (default: en): "
    try:
        value = input(prompt).strip()
    except EOFError:
        return "en"
    if not value:
        return "en"
    return normalize_locale(value)
