"""Overview messages distinguish monitoring, quota checks and recovery."""
import pytest

from recharge_ai_task.status_display import watch_check_summary


@pytest.mark.parametrize("runtime,value,detail", [
    (None, "Unavailable", "tray could not be reached"),
    ({}, "—", "monitoring is off"),
    ({"desktop_watch": True, "stopping": True}, "Stopping…", "being stopped"),
    ({"desktop_watch": True, "restarting": True}, "Updating…", "Applying saved"),
    ({"desktop_watch": True, "watch_error": "offline"}, "Needs attention", "activity messages"),
    ({"watch_pause_reason": "empty"}, "Waiting", "valid recipients"),
    ({"cli_running": True}, "CLI mode", "terminal"),
    ({"desktop_watch": True}, "Waiting…", "monitoring update"),
    ({"desktop_watch": True, "watch_progress": {"phase": "checking_quota"}}, "Checking…", "quota availability"),
    ({"desktop_watch": True, "watch_progress": {"phase": "delivering"}}, "Sending…", "selected signals"),
])
def test_overview_does_not_confuse_monitoring_with_task_activity(runtime, value, detail):
    actual, explanation = watch_check_summary(runtime, 100)
    assert actual == value
    assert detail in explanation


@pytest.mark.parametrize("phase,explanation", [
    ("waiting_quota", "Waiting for quota"),
    ("quota_unavailable", "could not be read"),
    ("grace_period", "grace period"),
    ("retry_pending", "delivery failure"),
    ("monitoring", "Watching for quota changes"),
])
def test_countdown_uses_worker_deadline_and_keeps_reason(phase, explanation):
    runtime = {"desktop_watch": True,
               "watch_progress": {"phase": phase, "next_check_at": 130}}
    assert watch_check_summary(runtime, 100.1)[0] == "In 00:30"
    assert watch_check_summary(runtime, 115)[0] == "In 00:15"
    assert watch_check_summary(runtime, 135)[0] == "Due now"
    assert explanation in watch_check_summary(runtime, 135)[1]


def test_stopped_watch_does_not_display_an_old_countdown():
    runtime = {"desktop_watch": False,
               "watch_progress": {"phase": "waiting_quota", "next_check_at": 150}}
    assert watch_check_summary(runtime, 100) == ("—", "Desktop monitoring is off.")
