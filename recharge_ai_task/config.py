"""Persistent user settings."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from ._migration import LEGACY_CONTINUE_PROMPT, environment_value, import_settings
from .desktop_input import DEFAULT_WINDOW_TITLES

Mode = Literal["cli", "desktop"]


def config_dir() -> Path:
    explicit = environment_value("CONFIG_DIR")
    root = Path(explicit).expanduser() if explicit else Path.home() / ".recharge-ai-task"
    root.mkdir(parents=True, exist_ok=True)
    if not explicit:
        import_settings(root)
    return root


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    mode: Mode = "cli"
    goal_mode: bool = True
    grace_seconds: int = 60
    continue_prompt: str = "Continue"
    autostart: bool = False
    codex_path: str | None = None
    codex_args: list[str] | None = None
    desktop_window_titles: list[str] | None = None
    poll_seconds: int = 30
    desktop_targets: list[dict] | None = None
    show_technical_columns: bool = False

    @classmethod
    def load(cls) -> AppConfig:
        path = config_path()
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        prompt = str(data.get("continue_prompt", "Continue"))
        if prompt == LEGACY_CONTINUE_PROMPT:
            prompt = "Continue"
        return cls(
            mode=data.get("mode", "cli"),
            goal_mode=bool(data.get("goal_mode", True)),
            grace_seconds=int(data.get("grace_seconds", 60)),
            continue_prompt=prompt,
            autostart=bool(data.get("autostart", False)),
            codex_path=data.get("codex_path"),
            codex_args=data.get("codex_args"),
            desktop_window_titles=data.get("desktop_window_titles"),
            poll_seconds=int(data.get("poll_seconds", 30)),
            desktop_targets=data.get("desktop_targets"),
            show_technical_columns=bool(data.get("show_technical_columns", False)),
        )

    def save(self) -> None:
        path = config_path()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix="config-", suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(asdict(self), stream, ensure_ascii=False, indent=2)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def window_titles(self) -> tuple[str, ...]:
        if self.desktop_window_titles:
            return tuple(self.desktop_window_titles)
        return DEFAULT_WINDOW_TITLES

    def targets(self):
        from .targets import Target
        result = []
        for value in self.desktop_targets or []:
            target = Target.from_dict(value)
            prompt, goal = target.signal_actions(self.goal_mode)
            if prompt or goal:
                result.append(replace(target, send_prompt=prompt, send_goal=goal))
        return result
