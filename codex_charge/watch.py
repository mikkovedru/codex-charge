"""Quota watcher for ChatGPT Codex desktop app (no PTY)."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass

from .desktop_input import DEFAULT_WINDOW_TITLES, send_to_desktop
from .i18n import t
from .quota import discover_codex, fetch_quota
from .pty_backend import StopEvent

_log = logging.getLogger("codex-charge.watch")


@dataclass
class WatchConfig:
    codex_path: str | None = None
    continue_prompt: str = "继续"
    goal_mode: bool = False
    grace_seconds: int = 60
    enter_presses: int = 1
    key_delay: float = 0.12
    poll_seconds: int = 30
    desktop_window_titles: tuple[str, ...] = DEFAULT_WINDOW_TITLES


def _continue_prompt(config: WatchConfig, first_goal_resume: bool) -> str:
    if config.goal_mode and first_goal_resume:
        return "/goal resume"
    return config.continue_prompt


def _poll_interval(used_percent: float, default: int) -> int:
    if used_percent >= 100:
        return 5
    if used_percent >= 95:
        return 10
    if used_percent >= 80:
        return 20
    return default


def _log_status(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.stderr.flush()
    _log.info(message)


def run_desktop_watch(config: WatchConfig, stop: StopEvent | None = None) -> int:
    stop = stop or StopEvent()
    codex = discover_codex(config.codex_path)
    goal_resume_pending = config.goal_mode

    _log_status(t("watch.started"))

    while not stop.is_set():
        try:
            quota = fetch_quota(codex)
        except Exception as exc:
            _log_status(t("cli.quota_fallback_failed", error=exc))
            stop.wait(60)
            continue

        exhausted = quota.exhausted_window()
        used = max(quota.primary.used_percent, quota.secondary.used_percent if quota.secondary else 0)

        if not exhausted:
            _log_status(t("watch.polling", percent=used))
            stop.wait(_poll_interval(used, config.poll_seconds))
            continue

        wake_at = exhausted.resets_at + config.grace_seconds
        prompt = _continue_prompt(config, goal_resume_pending)
        wake_local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wake_at))
        _log_status(t("watch.blocked", prompt=prompt, time=wake_local))

        while not stop.is_set():
            remaining = wake_at - int(time.time())
            if remaining <= 0:
                break
            stop.wait(min(1.0, float(remaining)))

        if stop.is_set():
            break

        if config.goal_mode and goal_resume_pending:
            goal_resume_pending = False

        ok = send_to_desktop(
            prompt,
            window_titles=config.desktop_window_titles,
            enter_presses=config.enter_presses,
            key_delay=config.key_delay,
        )
        if ok:
            _log_status(t("watch.sent_desktop", prompt=prompt))
        else:
            _log_status(t("watch.window_not_found"))

        stop.wait(30)

    return 0
