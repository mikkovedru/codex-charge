"""Quota watcher for ChatGPT Codex desktop app (no PTY)."""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field

from .desktop_input import DEFAULT_WINDOW_TITLES
from .targets import Target
from .target_delivery import deliver_targets, recover_target, send_signals
from .goal_control import quota_stopped_targets
from .i18n import t
from .quota import discover_codex, fetch_quota
from .pty_backend import StopEvent

_log = logging.getLogger("recharge-ai-task.watch")


@dataclass
class WatchState:
    """Delivery accounting retained when an active watch applies new settings."""
    startup_checked: bool = False
    delivered: set[str] = field(default_factory=set)
    seen_resets: set[tuple[int, int]] = field(default_factory=set)
    pending: bool = False
    wake_at: float = 0


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
    state: WatchState | None = None


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
    targets = tuple(t for t in config.desktop_targets if any(t.signal_actions(config.goal_mode)))
    if not targets:
        _log_status("Choose signal targets first: recharge-ai-task targets --gui")
        return 1
    state = config.state if config.state is not None else WatchState()

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
            state.startup_checked = True
            # Both short and weekly limits must recover before any recipient can
            # continue. Keep the reset identity after delivery to reject stale
            # snapshots of an already completed reset.
            reset_cycle = {(w.window_duration_mins, w.resets_at) for w in exhausted}
            next_wake = max(w.resets_at for w in exhausted) + config.grace_seconds
            if reset_cycle - state.seen_resets:
                state.seen_resets.update(reset_cycle)
                state.delivered.clear()
                state.pending = True
                state.wake_at = next_wake
            else:
                state.wake_at = max(state.wake_at, next_wake)
            prompt = "selected Goal / Prompt signals"
            wake_local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(state.wake_at))
            _log_status(t("watch.blocked", prompt=prompt, time=wake_local))
            # Refresh quota after waiting; a passed reset timestamp alone does
            # not prove that quota is available. Keep waits bounded for shutdown.
            stop.wait(min(60, max(5, state.wake_at - time.time())))
            continue

        if getattr(quota, "rate_limit_reached", False):
            _log_status("Codex still reports a quota limit; waiting for availability.")
            stop.wait(30)
            continue

        if not state.startup_checked and not state.pending:
            state.startup_checked = True
            goal_targets = [t for t in targets if t.signal_actions(config.goal_mode)[1]]
            if goal_targets:
                candidates, errors = quota_stopped_targets(goal_targets, stop=stop)
                state.startup_checked = not errors
                for error in errors:
                    _log_status(error)
                if candidates:
                    state.delivered = {target.key for target in targets} - candidates
                    state.pending = True
                    state.wake_at = time.time() + config.grace_seconds
                    _log_status("Quota is available; recovering selected quota-stopped goals after the grace period.")

        if not state.pending:
            _log_status(t("watch.polling", percent=used))
            stop.wait(_poll_interval(used, config.poll_seconds))
            continue

        remaining = state.wake_at - time.time()
        if remaining > 0:
            stop.wait(min(60, remaining))
            continue

        for target in targets:
            if stop.is_set():
                break
            if target.key in state.delivered:
                continue
            if target.send_goal is not None or target.send_prompt is not None:
                result = send_signals([target], config.continue_prompt,
                    enter_presses=config.enter_presses, key_delay=config.key_delay)[0]
            elif config.goal_mode:
                result = recover_target(target, config.continue_prompt,
                    enter_presses=config.enter_presses, key_delay=config.key_delay)
            else:
                result = deliver_targets([target], config.continue_prompt,
                    enter_presses=config.enter_presses, key_delay=config.key_delay)[0]
            if result.success or not result.retryable:
                state.delivered.add(target.key)
            _log_status(f"{target.title} [{target.id}]: {result.detail}")

        state.pending = any(target.key not in state.delivered for target in targets)
        stop.wait(30)

    return 0
