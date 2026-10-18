"""Interactive first-run configuration."""

from __future__ import annotations

from .config import AppConfig, config_path
from .i18n import t


def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{text}{suffix}: ").strip()
    except EOFError:
        return default
    return value or default


def _prompt_yes_no(text: str, default_yes: bool = True) -> bool:
    default = "Y" if default_yes else "n"
    value = _prompt(text, default).lower()
    if not value:
        return default_yes
    return value in {"y", "yes", "1", "true"}


def run_configure(*, non_interactive: dict | None = None) -> AppConfig:
    config = AppConfig.load()

    if non_interactive:
        for key, value in non_interactive.items():
            if hasattr(config, key):
                setattr(config, key, value)
        config.save()
        print(t("configure.saved", path=config_path()))
        return config

    print(t("configure.welcome"))

    mode = _prompt(t("configure.mode_prompt"), config.mode).lower()
    if mode not in {"cli", "desktop"}:
        mode = config.mode

    goal_mode = _prompt_yes_no(t("configure.goal_prompt"), config.goal_mode)
    grace = _prompt(t("configure.grace_prompt"), str(config.grace_seconds))
    continue_prompt = _prompt(t("configure.continue_prompt"), config.continue_prompt)

    try:
        grace_seconds = int(grace)
    except ValueError:
        grace_seconds = config.grace_seconds

    config.mode = mode  # type: ignore[assignment]
    config.goal_mode = goal_mode
    config.grace_seconds = grace_seconds
    config.continue_prompt = continue_prompt
    config.save()

    print(t("configure.saved", path=config_path()))
    print(f"  mode: {t('mode.cli') if config.mode == 'cli' else t('mode.desktop')}")
    return config


def main() -> int:
    run_configure()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
