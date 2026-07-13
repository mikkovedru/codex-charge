"""Smoke tests for codex-charge (no live quota wait)."""

from __future__ import annotations

import subprocess
import sys
import time

from codex_charge.parser import LimitWatcher, resolve_reset_at
from codex_charge.quota import discover_codex, fetch_quota, format_quota


def test_parser_detects_limit() -> None:
    watcher = LimitWatcher()
    chunk = "You've hit your usage limit. Try again in 4 hours 12 minutes."
    result = watcher.feed(chunk)
    assert result is not None
    reset_at, raw = result
    wake_at, source = resolve_reset_at(reset_at, reset_at + 60, grace_seconds=60)
    assert wake_at > int(time.time())
    assert source in {"terminal message", "quota API"}
    print(f"parser OK: raw={raw!r}, source={source}")


def test_quota_api() -> None:
    codex = discover_codex()
    quota = fetch_quota(codex)
    text = format_quota(quota)
    assert "Codex" in text or "额度" in text
    assert "%" in text
    print(text)


def test_spawn_goal_mode(timeout: float = 12.0) -> None:
    """Start codex-charge --goal briefly; verify wrapper spawns codex."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "codex_charge.cli", "--goal"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    deadline = time.monotonic() + timeout
    stderr_lines: list[str] = []
    while time.monotonic() < deadline:
        line = proc.stderr.readline()
        if line:
            stderr_lines.append(line.rstrip())
            try:
                print(line, end="")
            except UnicodeEncodeError:
                print(line.encode("utf-8", errors="replace").decode("ascii", errors="replace"), end="")
            if "codex-charge" in line.lower() and (
                "running" in line.lower() or "运行" in line
            ):
                print("spawn OK")
                proc.terminate()
                proc.wait(timeout=5)
                return
        if proc.poll() is not None:
            break
        time.sleep(0.1)

    proc.kill()
    proc.wait(timeout=3)
    joined = "\n".join(stderr_lines)
    raise AssertionError(f"codex-charge did not report running within {timeout}s:\n{joined}")


if __name__ == "__main__":
    test_parser_detects_limit()
    test_quota_api()
    test_spawn_goal_mode()
    print("ALL SMOKE TESTS PASSED")
