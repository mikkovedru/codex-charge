"""PTY wrapper that auto-continues Codex CLI after quota resets."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass

from .i18n import t
from .parser import LimitWatcher, resolve_reset_at
from .pty_backend import StopEvent, forward_stdin, sleep_with_proxy, spawn_pty
from .quota import discover_codex, fetch_quota, looks_like_codex_cli


@dataclass
class WrapperConfig:
    codex_path: str | None = None
    codex_args: list[str] | None = None
    continue_prompt: str = "继续"
    goal_mode: bool = False
    grace_seconds: int = 60
    enter_presses: int = 1
    key_delay: float = 0.12


def _log(message: str) -> None:
    sys.stderr.write(message + "\n")
    sys.stderr.flush()


def _submit(pty, text: str, enter_presses: int, key_delay: float) -> None:
    pty.write(text)
    time.sleep(key_delay)
    for _ in range(max(1, enter_presses)):
        pty.write("\r" if sys.platform == "win32" else "\n")
        time.sleep(key_delay)


def _continue_prompt(config: WrapperConfig, first_goal_resume: bool) -> str:
    if config.goal_mode and first_goal_resume:
        return "/goal resume"
    return config.continue_prompt


def run_wrapper(config: WrapperConfig) -> int:
    codex = discover_codex(config.codex_path)
    args = config.codex_args or []
    argv = [codex, *args]
    cmdline = " ".join(argv)

    _log(f"[recharge-ai-task] {t('cli.running')}: {cmdline}")

    rows, cols = 24, 120
    try:
        from shutil import get_terminal_size

        size = get_terminal_size(fallback=(rows, cols))
        rows, cols = size.lines, size.columns
    except Exception:
        pass

    try:
        pty = spawn_pty(argv, (rows, cols))
    except FileNotFoundError:
        _log(f"[recharge-ai-task] {t('cli.not_found')}")
        return 1

    watcher = LimitWatcher()
    stop = StopEvent()
    goal_resume_pending = config.goal_mode
    limit_lock = threading.Lock()
    waiting_for_reset = False

    def reader() -> None:
        while not stop.is_set() and pty.isalive():
            try:
                data = pty.read(4096)
            except EOFError:
                break
            if not data:
                continue
            sys.stdout.write(data)
            sys.stdout.flush()
            detected = watcher.feed(data)
            if detected:
                handle_limit(detected)

    def handle_limit(detected: tuple[int, str]) -> None:
        nonlocal goal_resume_pending, waiting_for_reset
        with limit_lock:
            if waiting_for_reset or stop.is_set() or not pty.isalive():
                return
            waiting_for_reset = True

        parsed_reset_at, raw = detected
        quota_reset_at = None
        if looks_like_codex_cli(codex):
            try:
                quota = fetch_quota(codex)
                exhausted = quota.exhausted_window()
                if exhausted:
                    quota_reset_at = exhausted.resets_at
            except Exception as exc:
                _log(f"[recharge-ai-task] {t('cli.quota_fallback_failed', error=exc)}")

        try:
            wake_at, source = resolve_reset_at(
                parsed_reset_at=parsed_reset_at,
                quota_resets_at=quota_reset_at,
                grace_seconds=config.grace_seconds,
            )
        except RuntimeError as exc:
            _log(f"[recharge-ai-task] {exc}")
            with limit_lock:
                waiting_for_reset = False
            return
        prompt = _continue_prompt(config, goal_resume_pending)
        if config.goal_mode and goal_resume_pending:
            goal_resume_pending = False

        wake_local = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(wake_at))
        _log(
            f"[recharge-ai-task] {t('cli.limit_detected', raw=raw, source=source, prompt=prompt, time=wake_local)}"
        )
        watcher.reset()

        try:
            if not sleep_with_proxy(pty, stop, wake_at):
                _log(f"[recharge-ai-task] {t('cli.exited_before_continue')}")
                stop.set()
                return

            _submit(pty, prompt, config.enter_presses, config.key_delay)
            _log(f"[recharge-ai-task] {t('cli.auto_continue_sent')}")
        finally:
            with limit_lock:
                waiting_for_reset = False

    stdin_thread = threading.Thread(target=forward_stdin, args=(pty, stop), daemon=True)
    reader_thread = threading.Thread(target=reader, daemon=True)

    stdin_thread.start()
    reader_thread.start()

    try:
        while pty.isalive() and not stop.is_set():
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop.set()

    stop.set()
    reader_thread.join(timeout=2)
    stdin_thread.join(timeout=1)

    try:
        return pty.exitstatus or 0
    except Exception:
        return 0
