"""Lightweight gettext-style i18n for codex-charge."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_LOCALE_DIR = Path(__file__).resolve().parent / "locales"
_current_locale = "en"


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
    env = os.environ.get("CODEX_CHARGE_LANG") or os.environ.get("LANG")
    if env:
        set_locale(env)
    return get_locale()


@lru_cache(maxsize=8)
def _load_messages(locale: str) -> dict[str, str]:
    path = _LOCALE_DIR / f"{locale}.json"
    if not path.exists():
        path = _LOCALE_DIR / "en.json"
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
