"""Native goal control and automatic recovery, with no real chat mutations."""
from copy import deepcopy
from dataclasses import replace
import socket
import os
import sys

import pytest

from codex_charge import goal_control, target_delivery as delivery
from codex_charge.codex_ipc import DeliveryUncertain
from codex_charge.goal_control import NativeGoals
from codex_charge.targets import Target

GOAL = {"threadId": "chosen", "objective": "Original objective", "createdAt": 1,
        "updatedAt": 2, "status": "usageLimited", "tokenBudget": 200,
        "tokensUsed": 75, "timeUsedSeconds": 123}
TARGET = Target("thread", "chosen", "Chosen chat", instance="/profile", endpoint="/profile/ipc/ipc.sock")


class GoalServer:
    def __init__(self, goal=None):
        self.goal = deepcopy(GOAL if goal is None else goal)
        self.calls = []
    def call(self, method, params):
        self.calls.append((method, params))
        if method == "thread/goal/set":
            self.goal["status"] = params["status"]
        return {"goal": deepcopy(self.goal)}


def controller(server):
    result = NativeGoals("/profile")
    result.server = server
    return result


def test_native_resume_verifies_identity_accounting_and_status():
    server = GoalServer()
    assert controller(server).resume("chosen", GOAL)
    assert server.calls == [
        ("thread/goal/get", {"threadId": "chosen"}),
        ("thread/goal/set", {"threadId": "chosen", "status": "active"}),
        ("thread/goal/get", {"threadId": "chosen"})]
    assert server.goal == {**GOAL, "status": "active"}


@pytest.mark.parametrize("change", [
    {"status": "paused"}, {"status": "blocked"}, {"status": "complete"},
    {"status": "budgetLimited"}, {"objective": "Replacement"},
    {"createdAt": 5}, {"tokenBudget": 10}])
def test_recheck_respects_user_changes(change):
    server = GoalServer({**GOAL, **change})
    assert not controller(server).resume("chosen", GOAL)
    assert not any(method.endswith("/set") for method, _ in server.calls)


@pytest.mark.parametrize("failure", ["timeout", "wrong-thread", "not-active", "accounting", "budget", "malformed"])
def test_unconfirmed_activation_is_never_success(failure):
    class Broken(GoalServer):
        def call(self, method, params):
            result = super().call(method, params)
            if method == "thread/goal/set":
                if failure == "timeout": raise TimeoutError("lost response")
                if failure == "wrong-thread": result["goal"]["threadId"] = "other"
                if failure == "not-active": result["goal"]["status"] = "paused"
                if failure == "accounting": result["goal"]["tokensUsed"] = 0
                if failure == "budget": result["goal"]["tokenBudget"] = 999
                if failure == "malformed": result = {}
            return result
    with pytest.raises(DeliveryUncertain):
        controller(Broken()).resume("chosen", GOAL)


@pytest.mark.parametrize("response", [{}, {"goal": []}, {"goal": {"threadId": "other", "status": "active"}}, {"goal": {"threadId": "chosen", "status": "future"}}])
def test_unknown_goal_state_is_not_no_goal(response):
    server = GoalServer()
    server.call = lambda *args: response
    with pytest.raises(ValueError): controller(server).get("chosen")


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux daemon sockets")
def test_profile_is_verified_before_using_daemon(monkeypatch, tmp_path):
    first, second = tmp_path / "a.sock", tmp_path / "b.sock"
    sockets = []
    for path in (first, second):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(str(path)); sockets.append(sock)
    entered, closed = [], []
    class Server:
        def __init__(self, path): self.path = path
        def __enter__(self):
            from pathlib import Path
            entered.append(self.path)
            self.home = Path("/wrong" if self.path == str(first) else "/profile")
            return self
        def __exit__(self, *args): closed.append(self.path)
    monkeypatch.setattr(goal_control.Path, "glob", lambda *args: [first, second])
    monkeypatch.setattr(goal_control, "AppServer", Server)
    try:
        with NativeGoals("/profile") as goals: assert goals.server.path == str(second)
        assert entered == [str(first), str(second)] and closed == entered
    finally:
        for sock in sockets: sock.close()


def install_recovery(monkeypatch, *, status="usageLimited", task="systemError", snapshot_goal=None, send_error=None):
    state = {"goal": None if status is None else {**GOAL, "status": status}, "resumes": 0, "sent": []}
    class Goals:
        def __init__(self, *args): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, thread): return deepcopy(state["goal"])
        def resume(self, thread, expected, *, allow_paused=False):
            assert expected["status"] == "usageLimited" or allow_paused
            state["resumes"] += 1
            state["goal"]["status"] = "active"
            return True
    class Desktop:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def owner(self, thread): assert thread == "chosen"; return "exact-owner"
        def status_snapshot(self, thread, owner): return {"task": None if task is None else {"type": task}, "goal": snapshot_goal}
        def send(self, thread, text, owner):
            assert owner == "exact-owner" and thread == "chosen"
            state["sent"].append(text)
            if send_error: raise send_error
    monkeypatch.setattr(goal_control, "NativeGoals", Goals)
    monkeypatch.setattr(delivery, "DesktopIPC", Desktop)
    return state


def test_quota_goal_uses_native_activation_and_normal_text(monkeypatch):
    state = install_recovery(monkeypatch)
    result = delivery.recover_target(TARGET, "Continue")
    assert result.success and "verified" in result.detail
    assert state["resumes"] == 1 and state["sent"] == ["Continue"]
    assert state["goal"]["status"] == "active"


@pytest.mark.parametrize("status", ["paused", "blocked", "budgetLimited", "complete"])
def test_non_quota_goals_are_left_alone(monkeypatch, status):
    state = install_recovery(monkeypatch, status=status)
    result = delivery.recover_target(TARGET, "Continue")
    assert result.success and "Skipped" in result.detail
    assert not state["sent"] and not state["resumes"]


@pytest.mark.parametrize("status", [None, "active"])
def test_no_goal_and_active_goal_use_normal_continuation(monkeypatch, status):
    state = install_recovery(monkeypatch, status=status, task="idle")
    assert delivery.recover_target(TARGET, "Custom signal").success
    assert state["sent"] == ["Custom signal"] and not state["resumes"]


def test_running_tasks_and_completed_cache_are_not_disturbed(monkeypatch):
    state = install_recovery(monkeypatch, task="active")
    assert "already running" in delivery.recover_target(TARGET, "Continue").detail
    assert not state["sent"] and not state["resumes"]
    state = install_recovery(monkeypatch, status=None, snapshot_goal="complete", task="idle")
    assert "complete" in delivery.recover_target(TARGET, "Continue").detail
    assert not state["sent"]


def test_unavailable_task_state_fails_closed(monkeypatch):
    state = install_recovery(monkeypatch, task=None)
    assert not delivery.recover_target(TARGET, "Continue").success
    assert not state["sent"] and not state["resumes"]


def test_confirmed_send_failure_does_not_repeat_native_activation(monkeypatch):
    state = install_recovery(monkeypatch, send_error=RuntimeError("no-client-found"))
    result = delivery.recover_target(TARGET, "Continue")
    assert not result.success and result.retryable and state["resumes"] == 1
    delivery.recover_target(TARGET, "Continue")
    assert state["resumes"] == 1


def test_uncertain_continuation_is_not_retryable(monkeypatch):
    state = install_recovery(monkeypatch, send_error=DeliveryUncertain("Lost acknowledgement"))
    result = delivery.recover_target(TARGET, "Continue")
    assert not result.success and not result.retryable and state["resumes"] == 1


def test_unknown_profile_goal_state_does_not_fall_back_to_text(monkeypatch):
    install_recovery(monkeypatch)
    class Missing:
        def __init__(self, *args): pass
        def __enter__(self): raise RuntimeError("Profile daemon unavailable")
        def __exit__(self, *args): pass
    monkeypatch.setattr(goal_control, "NativeGoals", Missing)
    result = delivery.recover_target(TARGET, "Continue")
    assert not result.success and "unavailable" in result.detail


def test_window_target_cannot_guess_goal(monkeypatch):
    monkeypatch.setattr(delivery, "_send_window", lambda *args: pytest.fail("Typed into a window"))
    result = delivery.recover_target(replace(TARGET, kind="window"), "Continue")
    assert not result.success and not result.retryable and "chat ID" in result.detail


def test_post_send_goal_verification_failure_does_not_retry(monkeypatch):
    state = install_recovery(monkeypatch)
    original = delivery.DesktopIPC
    class Pausing(original):
        def send(self, *args):
            super().send(*args)
            state["goal"]["status"] = "paused"
    monkeypatch.setattr(delivery, "DesktopIPC", Pausing)
    result = delivery.recover_target(TARGET, "Continue")
    assert not result.success and not result.retryable
    assert state["sent"] == ["Continue"]


@pytest.mark.skipif(os.environ.get("CODEX_CHARGE_LIVE_TESTS") != "1", reason="Requires the installed native Codex backend")
@pytest.mark.parametrize("status", ["usageLimited", "paused"])
def test_native_api_reactivates_shared_goal_without_loading_second_copy(tmp_path, status):
    import json
    import os
    import queue
    import sqlite3
    import subprocess
    import threading
    import time
    from pathlib import Path
    binary = Path("/usr/lib/chatgpt/resources/codex")
    if not binary.exists(): pytest.skip("Installed Codex backend unavailable")
    # No external model service: any continuation can only reach this closed
    # local port. Both backend processes and all goal data belong to the fixture.
    (tmp_path / "config.toml").write_text(
        'model="fixture"\nmodel_provider="fixture"\n[model_providers.fixture]\n'
        'name="Offline fixture"\nbase_url="http://127.0.0.1:9/v1"\n'
        'wire_api="responses"\nrequires_openai_auth=false\n')
    class RPC:
        def __init__(self):
            self.process = subprocess.Popen([str(binary), "app-server"],
                env=dict(os.environ, CODEX_HOME=str(tmp_path)), stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
            self.messages, self.counter = queue.Queue(), 0
            def read():
                for line in self.process.stdout:
                    try: self.messages.put(json.loads(line))
                    except ValueError: continue
            self.reader = threading.Thread(target=read, daemon=True)
            self.reader.start()
        def initialize(self):
            self.call("initialize", {"clientInfo": {"name": "charge-native-fixture", "version": "1"}})
            self.process.stdin.write(json.dumps({"method": "initialized"}) + "\n")
            self.process.stdin.flush()
        def call(self, method, params):
            self.counter += 1
            self.process.stdin.write(json.dumps({"id": self.counter, "method": method, "params": params}) + "\n")
            self.process.stdin.flush()
            deadline = time.monotonic() + 8
            while True:
                result = self.messages.get(timeout=max(.01, deadline - time.monotonic()))
                if result.get("id") == self.counter:
                    assert "error" not in result, result
                    return result["result"]
                assert time.monotonic() < deadline
        def close(self):
            self.process.terminate()
            self.process.wait(timeout=5)
            self.reader.join(2)
    original, control = RPC(), None
    try:
        original.initialize()
        control = RPC()
        control.initialize()
        thread_id = original.call("thread/start", {"cwd": str(tmp_path), "model": "fixture",
            "modelProvider": "fixture", "approvalPolicy": "never", "sandbox": "read-only"})["thread"]["id"]
        original.call("thread/goal/set", {"threadId": thread_id, "objective": "Fixture objective",
            "tokenBudget": 200, "status": "paused"})
        # Seed a quota-stopped fixture; production code never writes SQLite.
        database = next(tmp_path.glob("goals_*.sqlite"))
        with sqlite3.connect(database) as db:
            db.execute("UPDATE thread_goals SET status=?,tokens_used=75,time_used_seconds=123 WHERE thread_id=?",
                       ("usage_limited" if status == "usageLimited" else "paused", thread_id))
        native = NativeGoals(str(tmp_path))
        native.server = control
        before = native.get(thread_id)
        assert before["status"] == status
        assert control.call("thread/loaded/list", {})["data"] == []
        assert native.resume(thread_id, before, allow_paused=(status == "paused"))
        after = original.call("thread/goal/get", {"threadId": thread_id})["goal"]
        assert after["status"] == "active"
        for key in ("threadId", "objective", "createdAt", "tokenBudget", "tokensUsed", "timeUsedSeconds"):
            assert after[key] == before[key]
        assert control.call("thread/loaded/list", {})["data"] == []
        turn = original.call("turn/start", {"threadId": thread_id,
            "input": [{"type": "text", "text": "Continue", "text_elements": []}]})["turn"]
        assert turn["status"] == "inProgress"
        assert original.call("thread/goal/get", {"threadId": thread_id})["goal"]["status"] == "active"
        assert control.call("thread/loaded/list", {})["data"] == []
    finally:
        original.close()
        if control is not None: control.close()


def test_mismatched_desktop_profile_never_changes_a_goal(monkeypatch):
    state = install_recovery(monkeypatch)
    result = delivery.recover_target(replace(TARGET, endpoint="/other/ipc/ipc.sock"), "Continue")
    assert not result.success and "does not match" in result.detail
    assert not state["sent"] and not state["resumes"]


def test_closed_selected_chat_opens_only_its_deeplink(monkeypatch):
    state = install_recovery(monkeypatch)
    original, calls, opened = delivery.DesktopIPC, [], []
    class Closed(original):
        def owner(self, thread):
            calls.append(thread)
            if len(calls) == 1: raise RuntimeError("no-client-found")
            return super().owner(thread)
    monkeypatch.setattr(delivery, "DesktopIPC", Closed)
    monkeypatch.setattr(delivery, "open_target", lambda target: opened.append(target))
    target = replace(TARGET, deeplink="codex://threads/chosen")
    assert delivery.recover_target(target, "Continue").success
    assert opened == [target] and calls == ["chosen", "chosen"]
    assert state["resumes"] == 1


def test_startup_checks_are_cancellable_between_targets(monkeypatch):
    state = install_recovery(monkeypatch)
    class Stop:
        calls = 0
        def is_set(self):
            self.calls += 1
            return self.calls > 1
    candidates, errors = goal_control.quota_stopped_targets([TARGET, replace(TARGET, id="another")], Stop())
    assert candidates == {TARGET.key} and not errors


def test_unavailable_profile_is_checked_once_per_startup_batch(monkeypatch):
    calls = []
    class Missing:
        def __init__(self, home): calls.append(home)
        def __enter__(self): raise RuntimeError("Unavailable")
        def __exit__(self, *args): pass
    monkeypatch.setattr(goal_control, "NativeGoals", Missing)
    candidates, errors = goal_control.quota_stopped_targets([TARGET, replace(TARGET, id="another")])
    assert not candidates and len(errors) == 2 and calls == [TARGET.instance]


def test_manual_action_resumes_paused_goal_preserving_accounting(monkeypatch):
    state = install_recovery(monkeypatch, status="paused", task="idle")
    result = delivery.recover_target(TARGET, "Custom signal", manual=True)
    assert result.success and not result.skipped and "activation verified" in result.detail
    assert state["resumes"] == 1 and state["sent"] == ["Custom signal"]
    assert state["goal"] == {**GOAL, "status": "active"}


def test_native_paused_resume_requires_explicit_permission_and_unchanged_status():
    paused = {**GOAL, "status": "paused"}
    server = GoalServer(paused)
    assert not controller(server).resume("chosen", paused)
    assert controller(server).resume("chosen", paused, allow_paused=True)
    # A fresh pause after a usage-limited snapshot is a new user decision.
    server = GoalServer(paused)
    assert not controller(server).resume("chosen", GOAL, allow_paused=True)
    assert not any(method.endswith("/set") for method, _ in server.calls)


@pytest.mark.parametrize("status", ["blocked", "budgetLimited", "complete"])
def test_manual_recovery_respects_other_protected_states(monkeypatch, status):
    state = install_recovery(monkeypatch, status=status)
    result = delivery.recover_target(TARGET, "Continue", manual=True)
    assert result.success and result.skipped and status in result.detail
    assert not state["sent"] and not state["resumes"]


def test_manual_empty_signal_never_activates_goal(monkeypatch):
    state = install_recovery(monkeypatch, status="paused")
    assert not delivery.recover_target(TARGET, " ", manual=True).success
    assert not state["sent"] and not state["resumes"]
