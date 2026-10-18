"""End-to-end wrapper tests (Fake PTY; avoids Windows Python stdin quirks)."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

from recharge_ai_task.pty_backend import StopEvent
from recharge_ai_task.wrapper import WrapperConfig, run_wrapper

ROOT = Path(__file__).resolve().parents[1]
LIMIT_LINE = "You've hit your usage limit. Try again in 1 second.\r\n"


class FakePty:
    def __init__(self, limit_line: str = LIMIT_LINE) -> None:
        self._chunks = [limit_line]
        self._alive = True
        self.written: list[str] = []
        self._lock = threading.Lock()

    def read(self, size: int) -> str:
        with self._lock:
            if self._chunks:
                return self._chunks.pop(0)
        time.sleep(0.05)
        return ""

    def write(self, data: str) -> None:
        self.written.append(data)
        with self._lock:
            self._alive = False

    def isalive(self) -> bool:
        with self._lock:
            return self._alive

    @property
    def exitstatus(self) -> int | None:
        return 0


def test_goal_mode_auto_continue(monkeypatch) -> None:
    fake = FakePty()
    monkeypatch.setattr(
        "recharge_ai_task.wrapper.spawn_pty",
        lambda argv, dims: fake,
    )
    monkeypatch.setattr(
        "recharge_ai_task.wrapper.sleep_with_proxy",
        lambda pty, stop, wake_at: True,
    )
    monkeypatch.setattr(
        "recharge_ai_task.wrapper.forward_stdin",
        lambda pty, stop: None,
    )

    monkeypatch.setattr(
        "recharge_ai_task.wrapper.discover_codex",
        lambda explicit=None: explicit or "codex",
    )
    config = WrapperConfig(
        goal_mode=True,
        grace_seconds=1,
        enter_presses=1,
        key_delay=0.01,
    )
    assert run_wrapper(config) == 0
    joined = "".join(fake.written)
    assert "/goal resume" in joined


def test_normal_mode_auto_continue(monkeypatch) -> None:
    fake = FakePty()
    monkeypatch.setattr("recharge_ai_task.wrapper.spawn_pty", lambda argv, dims: fake)
    monkeypatch.setattr("recharge_ai_task.wrapper.sleep_with_proxy", lambda *a: True)
    monkeypatch.setattr("recharge_ai_task.wrapper.forward_stdin", lambda *a: None)

    monkeypatch.setattr("recharge_ai_task.wrapper.discover_codex", lambda explicit=None: explicit or "codex")
    config = WrapperConfig(
        codex_path="codex",
        goal_mode=False,
        continue_prompt="继续",
        grace_seconds=1,
        enter_presses=1,
        key_delay=0.01,
    )
    assert run_wrapper(config) == 0
    assert "继续" in "".join(fake.written)


def test_real_codex_spawn_smoke() -> None:
    """Spawn real codex via wrapper; exit quickly if codex is installed."""
    try:
        from recharge_ai_task.quota import discover_codex

        discover_codex()
    except FileNotFoundError:
        return

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "recharge_ai_task.cli",
            "run",
            "--goal",
            "--grace",
            "60",
            "--",
            "--version",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        stdout, stderr = proc.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=5)
    combined = f"{stdout}\n{stderr}"
    assert "running" in combined.lower() or "recharge-ai-task" in combined.lower()
