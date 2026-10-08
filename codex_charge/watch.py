"""Quota watcher for ChatGPT Codex desktop app (no PTY)."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass

from .desktop_input import DEFAULT_WINDOW_TITLES
from .targets import Target
from .target_delivery import deliver_targets, recover_target
from .goal_control import quota_stopped_targets
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
    desktop_targets: tuple[Target, ...] = ()


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
    if not config.desktop_targets:
        _log_status("Choose signal targets first: codex-charge targets --gui")
        return 1
    startup_checked = False
    delivered = set()
    seen_resets = set()
    pending = False
    wake_at = 0

    _log_status(t("watch.started"))

    while not stop.is_set():
        try:
            quota = fetch_quota(codex)
        except Exception as exc:
            _log_status(t("cli.quota_fallback_failed", error=exc))
            stop.wait(60)
            continue

        exhausted = [window for window in (quota.primary, quota.secondary)
                     if window is not None and window.used_percent >= 100]
        used = max(quota.primary.used_percent, quota.secondary.used_percent if quota.secondary else 0)

        if exhausted:
            startup_checked = True
            # Both short and weekly limits must recover before any recipient can
            # continue. Keep the reset identity after delivery to reject stale
            # snapshots of an already completed reset.
            reset_cycle = {(w.window_duration_mins, w.resets_at) for w in exhausted}
            next_wake = max(w.resets_at for w in exhausted) + config.grace_seconds
            if reset_cycle - seen_resets:
                seen_resets.update(reset_cycle)
                delivered.clear()
                pending = True
                wake_at = next_wake
            else:
                wake_at = max(wake_at, next_wake)
            prompt = "native goal recovery / continuation" if config.goal_mode else config.continue_prompt
            wake_local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wake_at))
            _log_status(t("watch.blocked", prompt=prompt, time=wake_local))
            # Refresh quota after waiting; a passed reset timestamp alone does
            # not prove that quota is available. Keep waits bounded for shutdown.
            stop.wait(min(60, max(5, wake_at - time.time())))
            continue

        if getattr(quota, "rate_limit_reached", False):
            _log_status("Codex still reports a quota limit; waiting for availability.")
            stop.wait(30)
            continue

        if not startup_checked and not pending:
            startup_checked = True
            if config.goal_mode:
                candidates, errors = quota_stopped_targets(config.desktop_targets, stop=stop)
                startup_checked = not errors
                for error in errors:
                    _log_status(error)
                if candidates:
                    delivered = {target.key for target in config.desktop_targets} - candidates
                    pending = True
                    wake_at = time.time() + config.grace_seconds
                    _log_status("Quota is available; recovering selected quota-stopped goals after the grace period.")

        if not pending:
            _log_status(t("watch.polling", percent=used))
            stop.wait(_poll_interval(used, config.poll_seconds))
            continue

        remaining = wake_at - time.time()
        if remaining > 0:
            stop.wait(min(60, remaining))
            continue

        for target in config.desktop_targets:
            if stop.is_set():
                break
            if target.key in delivered:
                continue
            if config.goal_mode:
                result = recover_target(target, config.continue_prompt,
                    enter_presses=config.enter_presses, key_delay=config.key_delay)
            else:
                result = deliver_targets([target], config.continue_prompt,
                    enter_presses=config.enter_presses, key_delay=config.key_delay)[0]
            if result.success or not result.retryable:
                delivered.add(target.key)
            _log_status(f"{target.title} [{target.id}]: {result.detail}")

        pending = any(target.key not in delivered for target in config.desktop_targets)
        stop.wait(30)

    return 0
