"""Desktop watch logic tests."""

from __future__ import annotations

import time
from dataclasses import dataclass

from codex_charge.pty_backend import StopEvent
from codex_charge.quota import Quota, RateWindow
from codex_charge import watch as watch_mod
from codex_charge.targets import Target
from codex_charge.target_delivery import DeliveryResult


@dataclass
class _FakeQuota:
    primary: RateWindow
    secondary: RateWindow | None = None

    def exhausted_window(self):
        if self.primary.used_percent >= 100:
            return self.primary
        if self.secondary and self.secondary.used_percent >= 100:
            return self.secondary
        return None


def test_desktop_watch_sends_on_reset(monkeypatch) -> None:
    now = int(time.time())
    exhausted = RateWindow(used_percent=100, window_duration_mins=300, resets_at=now)
    quota = _FakeQuota(primary=exhausted)

    sent: list[str] = []

    monkeypatch.setattr(watch_mod, "fetch_quota", lambda *_a, **_k: quota)
    monkeypatch.setattr(watch_mod, "discover_codex", lambda *_a, **_k: "/usr/bin/codex")
    monkeypatch.setattr(
        watch_mod,
        "deliver_targets",
        lambda targets, text, **kwargs: sent.append(text) or [DeliveryResult(targets[0], True, "Sent")],
    )

    stop = StopEvent()
    cfg = watch_mod.WatchConfig(goal_mode=True, grace_seconds=1, poll_seconds=1, desktop_targets=(Target("thread", "a", "A"),))

    def stop_soon():
        time.sleep(2.5)
        stop.set()

    import threading

    threading.Thread(target=stop_soon, daemon=True).start()
    watch_mod.run_desktop_watch(cfg, stop)

    assert sent == ["/goal resume"]
