"""Desktop quota-reset delivery state transitions, without real waits."""
from dataclasses import replace

from codex_charge.quota import Quota, RateWindow
from codex_charge import watch
from codex_charge.targets import Target
from codex_charge.target_delivery import DeliveryResult

A = Target("thread", "a", "A")
B = Target("thread", "b", "B")
BLOCKED = Quota("test", RateWindow(100, 300, 100), None, True)
AVAILABLE = replace(BLOCKED, primary=RateWindow(0, 300, 200), rate_limit_reached=False)


def run_snapshots(monkeypatch, snapshots, *, selected=(A,), grace=0, outcomes=(), goal=False):
    sequence = iter(snapshots)
    quota = [snapshots[-1]]
    now = [100.0]
    sent = []
    replies = iter(outcomes)
    waits = []
    class Stop:
        def is_set(self): return len(waits) >= len(snapshots)
        def wait(self, seconds):
            waits.append(seconds)
            now[0] += seconds
    def fetch(_):
        value = next(sequence, quota[0])
        if isinstance(value, Exception):
            raise value
        quota[0] = value
        return value
    def deliver(targets, text, **_):
        sent.append((targets[0].id, text, now[0]))
        success, retryable = next(replies, (True, True))
        return [DeliveryResult(targets[0], success, "result", retryable)]
    monkeypatch.setattr(watch, "discover_codex", lambda _: "codex")
    monkeypatch.setattr(watch, "fetch_quota", fetch)
    monkeypatch.setattr(watch, "deliver_targets", deliver)
    monkeypatch.setattr(watch.time, "time", lambda: now[0])
    config = watch.WatchConfig(desktop_targets=selected, grace_seconds=grace, goal_mode=goal)
    assert watch.run_desktop_watch(config, Stop()) == 0
    return sent, waits


def test_desktop_watch_sends_after_confirmed_reset(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, AVAILABLE, AVAILABLE], goal=True)
    assert [(target, text) for target, text, _ in sent] == [("a", "/goal resume")]


def test_no_signal_while_api_still_reports_exhaustion(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED] * 3)
    assert sent == []


def test_weekly_limit_must_also_reset(monkeypatch):
    both = replace(BLOCKED, secondary=RateWindow(100, 10080, 160))
    weekly = replace(AVAILABLE, secondary=both.secondary, rate_limit_reached=True)
    sent, waits = run_snapshots(monkeypatch, [both, weekly, AVAILABLE, AVAILABLE], grace=10)
    assert waits[0] == 60
    assert waits[1] == 10
    assert len(sent) == 1 and sent[0][2] >= 170


def test_failed_target_retries_after_quota_becomes_available(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, AVAILABLE, AVAILABLE, AVAILABLE],
        selected=(A, B), outcomes=[(True, True), (False, True), (True, True)], goal=True)
    assert [(target, text) for target, text, _ in sent] == [
        ("a", "/goal resume"), ("b", "/goal resume"), ("b", "/goal resume")]


def test_uncertain_target_is_not_repeated_after_reset(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, AVAILABLE, AVAILABLE], outcomes=[(False, False)])
    assert len(sent) == 1


def test_quota_error_at_reset_does_not_send(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, RuntimeError("offline"), AVAILABLE])
    assert len(sent) == 1 and sent[0][2] >= 165


def test_new_reset_sends_once_again(monkeypatch):
    blocked_again = replace(BLOCKED, primary=RateWindow(100, 300, 200))
    available_again = replace(AVAILABLE, primary=RateWindow(0, 300, 300))
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, AVAILABLE, AVAILABLE, blocked_again, available_again], goal=True)
    assert [(target, text) for target, text, _ in sent] == [("a", "/goal resume"), ("a", "继续")]


def test_grace_period_is_retained_after_api_recovers(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, AVAILABLE, AVAILABLE], grace=90)
    assert len(sent) == 1 and sent[0][2] >= 190


def test_available_quota_without_observed_block_does_not_send(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [AVAILABLE, AVAILABLE])
    assert sent == []


def test_limit_flag_without_full_window_blocks_delivery(monkeypatch):
    sent, _ = run_snapshots(monkeypatch, [BLOCKED, replace(AVAILABLE, rate_limit_reached=True), AVAILABLE])
    assert len(sent) == 1 and sent[0][2] >= 135


def test_partial_stale_snapshot_does_not_rearm_completed_reset(monkeypatch):
    both = replace(BLOCKED, secondary=RateWindow(100, 10080, 160))
    weekly_stale = replace(AVAILABLE, secondary=both.secondary, rate_limit_reached=True)
    sent, _ = run_snapshots(monkeypatch, [both, AVAILABLE, weekly_stale, AVAILABLE, AVAILABLE])
    assert len(sent) == 1
