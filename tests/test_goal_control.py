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
        def continue_goal(self, thread, owner):
            assert owner == "exact-owner" and thread == "chosen"
            state["sent"].append(None)
            if send_error: raise send_error
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
@pytest.mark.parametrize("goal_only,active_turn", [(False, False), (True, False), (True, True)])
def test_native_api_reactivates_shared_goal_without_loading_second_copy(tmp_path, monkeypatch, status, goal_only, active_turn):
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
    # A local HTTP fixture holds a real turn open for the active-prompt case.
    # No request can reach an external model service.
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    entered, release = threading.Event(), threading.Event()
    class HoldRequest(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", "0")))
            entered.set()
            release.wait(20)
            self.send_response(503)
            self.end_headers()
        def log_message(self, *args): pass
    http = ThreadingHTTPServer(("127.0.0.1", 0), HoldRequest) if active_turn else None
    http_thread = threading.Thread(target=http.serve_forever, daemon=True) if http else None
    if http_thread: http_thread.start()
    base_url = f"http://127.0.0.1:{http.server_port}/v1" if http else "http://127.0.0.1:9/v1"
    # Both backend processes and all goal data belong to the fixture.
    (tmp_path / "config.toml").write_text(
        'model="fixture"\nmodel_provider="fixture"\n[model_providers.fixture]\n'
        f'name="Offline fixture"\nbase_url="{base_url}"\n'
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
        active_id = None
        if active_turn:
            active_id = original.call("turn/start", {"threadId": thread_id,
                "input": [{"type": "text", "text": "Hold this fixture turn", "text_elements": []}]})["turn"]["id"]
            assert entered.wait(5), "Offline model fixture never received the turn"
        native = NativeGoals(str(tmp_path))
        native.server = control
        before = native.get(thread_id)
        assert before["status"] == status
        assert control.call("thread/loaded/list", {})["data"] == []
        if active_turn:
            class ExistingNative:
                def __init__(self, *_): pass
                def __enter__(self): return native
                def __exit__(self, *_): pass
            class ExistingOwner:
                def __init__(self, *args, **kwargs): pass
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def owner(self, thread):
                    assert thread == thread_id
                    return "fixture-owner"
                def status_snapshot(self, thread, owner):
                    current = original.call("thread/read", {"threadId": thread, "includeTurns": True})["thread"]
                    assert current["status"]["type"] == "active"
                    return {"task": current["status"], "goal": status}
                def continue_goal(self, *args): pytest.fail("Started a competing empty turn")
                def send(self, *args): pytest.fail("Sent an unwanted prompt")
            monkeypatch.setattr(goal_control, "NativeGoals", ExistingNative)
            monkeypatch.setattr(delivery, "DesktopIPC", ExistingOwner)
            target = Target("thread", thread_id, "Fixture", instance=str(tmp_path),
                endpoint=str(tmp_path / "ipc/ipc.sock"), send_prompt=False, send_goal=True)
            result = delivery.send_signals([target], "", manual=True)[0]
            assert result.success and not result.skipped, result.detail
            assert "current turn continues" in result.detail
        else:
            assert native.resume(thread_id, before, allow_paused=(status == "paused"))
        after = original.call("thread/goal/get", {"threadId": thread_id})["goal"]
        assert after["status"] == "active"
        for key in ("threadId", "objective", "createdAt", "tokenBudget", "tokensUsed", "timeUsedSeconds"):
            if active_turn and key in ("tokensUsed", "timeUsedSeconds"):
                assert after[key] >= before[key]
            else:
                assert after[key] == before[key]
        assert control.call("thread/loaded/list", {})["data"] == []
        if active_turn:
            current = original.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
            assert current["status"]["type"] == "active"
            assert current["turns"][-1]["id"] == active_id
        else:
            turn = original.call("turn/start", {"threadId": thread_id,
                "input": [] if goal_only else [{"type": "text", "text": "Continue", "text_elements": []}]})["turn"]
            assert turn["status"] == "inProgress"
        assert original.call("thread/goal/get", {"threadId": thread_id})["goal"]["status"] == "active"
        assert control.call("thread/loaded/list", {})["data"] == []
    finally:
        original.close()
        if control is not None: control.close()
        release.set()
        if http:
            http.shutdown(); http.server_close(); http_thread.join(2)


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


@pytest.mark.parametrize("prompt,goal,expected", [(True, False, ["Custom"]), (False, True, [None]), (True, True, ["Custom"]), (False, False, [])])
def test_independent_signal_actions(monkeypatch, prompt, goal, expected):
    state = install_recovery(monkeypatch, status="paused", task="idle")
    target = replace(TARGET, send_prompt=prompt, send_goal=goal)
    result = delivery.send_signals([target], "Custom", manual=True)[0]
    assert result.success and state["sent"] == expected
    assert state["resumes"] == int(goal)
    assert result.skipped == (not prompt and not goal)


def test_goal_only_accepts_empty_prompt_and_never_sends_text(monkeypatch):
    state = install_recovery(monkeypatch, status="paused", task="idle")
    result = delivery.send_signals([replace(TARGET, send_prompt=False, send_goal=True)], "", manual=True)[0]
    assert result.success and state["sent"] == [None] and "no prompt" in result.detail


def test_goal_activation_precedes_prompt(monkeypatch):
    state = install_recovery(monkeypatch, status="paused", task="idle")
    original = delivery.DesktopIPC
    class Ordered(original):
        def send(self, *args):
            assert state["goal"]["status"] == "active" and state["resumes"] == 1
            super().send(*args)
    monkeypatch.setattr(delivery, "DesktopIPC", Ordered)
    result = delivery.send_signals([replace(TARGET, send_prompt=True, send_goal=True)], "Custom", manual=True)[0]
    assert result.success and state["sent"] == ["Custom"]


def test_goal_failure_does_not_fall_back_to_prompt(monkeypatch):
    state = install_recovery(monkeypatch, status="paused", task=None)
    result = delivery.send_signals([replace(TARGET, send_prompt=True, send_goal=True)], "Custom", manual=True)[0]
    assert not result.success and not state["sent"]


@pytest.mark.parametrize("prompt", [False, True])
def test_missing_goal_never_uses_empty_continuation(monkeypatch, prompt):
    state = install_recovery(monkeypatch, status=None, task="idle")
    result = delivery.send_signals([replace(TARGET, send_prompt=prompt, send_goal=True)], "Custom", manual=True)[0]
    assert result.success and state["sent"] == (["Custom"] if prompt else [])
    assert result.skipped == (not prompt)


def test_goal_continuation_ipc_contains_no_user_message(monkeypatch):
    from codex_charge.codex_ipc import DesktopIPC
    ipc, calls = DesktopIPC("unused"), []
    def request(method, params, **kwargs):
        calls.append((method, params, kwargs))
        return {"handledByClientId": "owner", "result": {"result": {"turn": {"id": "goal-turn"}}}}
    monkeypatch.setattr(ipc, "request", request)
    ipc.continue_goal("chosen", "owner")
    assert calls[0][1]["turnStart"]["request"]["input"] == []
    assert calls[0][1]["turnStart"]["context"] == {"inheritThreadSettings": True}
    assert calls[0][2]["target_client"] == "owner"


@pytest.mark.parametrize("prompt", [False, True])
def test_manual_goal_resumes_during_active_prompt_without_competing_empty_turn(monkeypatch, prompt):
    state = install_recovery(monkeypatch, status="paused", task="active")
    result = delivery.send_signals([replace(TARGET, send_prompt=prompt, send_goal=True)], "Custom", manual=True)[0]
    assert result.success and not result.skipped and state["resumes"] == 1
    assert state["goal"] == {**GOAL, "status": "active"}
    assert state["sent"] == (["Custom"] if prompt else [])
    if not prompt:
        assert "current turn continues" in result.detail
    # An automatic signal never overrides a pause even during an active turn.
    state = install_recovery(monkeypatch, status="paused", task="active")
    result = delivery.send_signals([replace(TARGET, send_prompt=False, send_goal=True)], "", manual=False)[0]
    assert result.skipped and not state["resumes"] and not state["sent"]


def test_active_turn_can_advance_usage_during_native_goal_resume():
    class Growing(GoalServer):
        def call(self, method, params):
            if method == "thread/goal/set":
                self.goal["tokensUsed"] += 1
                self.goal["timeUsedSeconds"] += 1
            return super().call(method, params)
    before = {**GOAL, "status": "paused"}
    server = Growing(before)
    assert controller(server).resume("chosen", before, allow_paused=True)
    assert server.goal["tokenBudget"] == before["tokenBudget"]
    assert server.goal["tokensUsed"] == before["tokensUsed"] + 1
