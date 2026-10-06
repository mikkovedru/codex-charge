"""Smoke tests for codex-charge (no live quota wait)."""

from __future__ import annotations

import subprocess
import os
import pytest
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


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_LIVE_TESTS") != "1", reason="Requires a signed-in Codex CLI")
def test_quota_api() -> None:
    codex = discover_codex()
    quota = fetch_quota(codex)
    text = format_quota(quota)
    assert "Codex" in text or "额度" in text
    assert "%" in text
    print(text)


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_LIVE_TESTS") != "1", reason="Requires a signed-in Codex CLI")
def test_spawn_goal_mode(timeout: float = 20) -> None:
    result = subprocess.run([sys.executable, "-m", "codex_charge.cli", "run", "--goal", "--", "--version"], capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, result.stderr
    assert "codex" in result.stdout.lower()


if __name__ == "__main__":
    test_parser_detects_limit()
    test_quota_api()
    test_spawn_goal_mode()
    print("ALL SMOKE TESTS PASSED")
