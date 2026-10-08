"""Persistent user settings."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from .desktop_input import DEFAULT_WINDOW_TITLES
from .i18n import normalize_locale, set_locale

Mode = Literal["cli", "desktop"]
Language = Literal["en", "zh"]


def config_dir() -> Path:
    root = Path(os.environ["CODEX_CHARGE_CONFIG_DIR"]).expanduser() if os.environ.get("CODEX_CHARGE_CONFIG_DIR") else Path.home() / ".codex-charge"
    root.mkdir(parents=True, exist_ok=True)
    return root


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    language: Language = "en"
    mode: Mode = "cli"
    goal_mode: bool = True
    grace_seconds: int = 60
    continue_prompt: str = "继续"
    autostart: bool = False
    codex_path: str | None = None
    codex_args: list[str] | None = None
    desktop_window_titles: list[str] | None = None
    poll_seconds: int = 30
    desktop_targets: list[dict] | None = None

    @classmethod
    def load(cls) -> AppConfig:
        path = config_path()
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            language=normalize_locale(data.get("language", "en")),  # type: ignore[arg-type]
            mode=data.get("mode", "cli"),
            goal_mode=bool(data.get("goal_mode", True)),
            grace_seconds=int(data.get("grace_seconds", 60)),
            continue_prompt=str(data.get("continue_prompt", "继续")),
            autostart=bool(data.get("autostart", False)),
            codex_path=data.get("codex_path"),
            codex_args=data.get("codex_args"),
            desktop_window_titles=data.get("desktop_window_titles"),
            poll_seconds=int(data.get("poll_seconds", 30)),
            desktop_targets=data.get("desktop_targets"),
        )

    def save(self) -> None:
        config_path().write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        set_locale(self.language)

    def apply_locale(self) -> None:
        set_locale(self.language)

    def window_titles(self) -> tuple[str, ...]:
        if self.desktop_window_titles:
            return tuple(self.desktop_window_titles)
        return DEFAULT_WINDOW_TITLES

    def targets(self):
        from .targets import Target
        return [Target.from_dict(value) for value in (self.desktop_targets or [])]
