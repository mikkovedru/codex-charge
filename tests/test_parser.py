"""Parser and reset-resolution smoke tests."""

from __future__ import annotations

import time

from recharge_ai_task.parser import LimitWatcher, resolve_reset_at


def test_limit_in_message() -> None:
    w = LimitWatcher()
    msg = "You've hit your usage limit. Try again in 4 hours 12 minutes."
    result = w.feed(msg)
    assert result is not None
    reset_at, raw = result
    assert "4 hours" in raw
    wake_at, source = resolve_reset_at(reset_at, reset_at + 100, 60)
    assert wake_at > int(time.time())
    assert source in ("terminal message", "quota API")


def test_limit_with_short_duration_units() -> None:
    w = LimitWatcher()
    msg = "Usage limit. Try again in 2 hrs 30 min."
    result = w.feed(msg)
    assert result is not None
    reset_at, raw = result
    assert abs(reset_at - (int(time.time()) + 9000)) <= 1
