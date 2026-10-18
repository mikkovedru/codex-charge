import json
import socket
import sqlite3
import struct
import threading
from dataclasses import replace

import pytest

from recharge_ai_task import targets, target_delivery as delivery, watch
from recharge_ai_task.codex_ipc import DesktopIPC
from recharge_ai_task.config import AppConfig
from recharge_ai_task.quota import RateWindow
from recharge_ai_task.targets import Target


def test_saved_metadata_read_only_and_distinct_ids(tmp_path):
    path = tmp_path / "state_5.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("create table threads(id text, title text, name text, cwd text, source text, archived int, updated_at int)")
        db.executemany("insert into threads values (?,?,?,?,?,?,?)", [
            ("a", "First prompt", "Same title", "/one", "vscode", 0, 3),
            ("b", "Other prompt", "Same title", "/two", "vscode", 0, 2),
            ("archived", "Old", "Old", "/old", "vscode", 1, 1),
            ("agent", "Hidden", "Hidden", "/one", '{"subagent":{}}', 0, 4)])
    before = path.read_bytes()
    records = targets._saved_threads(tmp_path)
    assert [r["id"] for r in records] == ["a", "b"]
    objects = [targets._thread_target(r, tmp_path, "") for r in records]
    assert objects[0].title == objects[1].title == "Same title"
    assert objects[0].key != objects[1].key
    assert objects[0].deeplink == "codex://threads/a"
    assert path.read_bytes() == before


def test_discovery_partial_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(targets, "discover_homes", lambda: {tmp_path})
    monkeypatch.setattr(targets.sys, "platform", "win32")
    monkeypatch.setattr(targets, "discover_windows", lambda: (_ for _ in ()).throw(RuntimeError("No display")))
    monkeypatch.setattr(targets, "_saved_threads", lambda _: [{"id": "one", "name": "A chat"}])
    inventory = targets.discover_targets()
    assert len(inventory.targets) == 1
    assert "No display" in inventory.warnings[0]


def test_pagination():
    server = targets.AppServer("unused")
    calls = []
    def call(method, params):
        calls.append((method, params))
        return {"data": [{"id": "a" if params["cursor"] is None else "b"}],
                "nextCursor": "next" if params["cursor"] is None else None}
    server.call = call
    assert [r["id"] for r in server.threads()] == ["a", "b"]
    assert calls[1][1]["cursor"] == "next"
    assert all(c[0] == "thread/list" and c[1]["useStateDbOnly"] for c in calls)


def test_config_roundtrip():
    a = Target("thread", "a", "Same", instance="/profile/one", deeplink="codex://threads/a")
    b = replace(a, instance="/profile/two")
    config = AppConfig(desktop_targets=[a.to_dict(), b.to_dict()])
    config.save()
    assert AppConfig.load().targets() == [replace(t, send_prompt=True, send_goal=True) for t in (a, b)]
    assert a.key != b.key


def test_multi_delivery_deduplicates_and_keeps_failures(monkeypatch):
    a, b = Target("thread", "a", "Same"), Target("thread", "b", "Same")
    called = []
    def send(target, text):
        called.append((target.id, text))
        if target.id == "b":
            raise RuntimeError("Disconnected")
    monkeypatch.setattr(delivery, "_send_thread", send)
    result = delivery.deliver_targets([a, b, a], "Continue")
    assert called == [("a", "Continue"), ("b", "Continue")]
    assert [r.success for r in result] == [True, False]
    assert result[1].detail == "Disconnected"


def test_stale_window_never_types(monkeypatch):
    a = Target("window", "42", "Codex", instance=":0:7", pid=7)
    monkeypatch.setattr(delivery, "discover_windows", lambda: [replace(a, pid=8)])
    monkeypatch.setattr(delivery.subprocess, "run", lambda *a, **k: pytest.fail("Typed into stale window"))
    assert not delivery.deliver_targets([a], "Continue")[0].success


def test_focus_change_never_types(monkeypatch):
    a = Target("window", "42", "Codex", instance=":0:7", pid=7)
    monkeypatch.setattr(delivery.sys, "platform", "linux")
    monkeypatch.setattr(delivery, "discover_windows", lambda: [a])
    commands = []
    monkeypatch.setattr(delivery.subprocess, "run", lambda args, **kwargs: commands.append(args))
    monkeypatch.setattr(delivery.subprocess, "check_output", lambda *a, **k: "99\n")
    assert not delivery.deliver_targets([a], "Continue")[0].success
    assert commands == [["xdotool", "windowactivate", "--sync", "42"]]


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Requires Unix sockets")
def test_desktop_router_exact_owner_and_unicode(tmp_path):
    path = str(tmp_path / "ipc.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen()
    received = []
    errors = []
    def peer():
        try:
            with listener.accept()[0] as connection:
                def read(n):
                    data = b""
                    while len(data) < n:
                        chunk = connection.recv(n - len(data))
                        if not chunk: raise EOFError()
                        data += chunk
                    return data
                for _ in range(3):
                    message = json.loads(read(struct.unpack("<I", read(4))[0]))
                    received.append(message)
                    method = message["method"]
                    result = {"clientId": "sender"} if method == "initialize" else {"supportsUntrustedAppInput": True} if method == "thread-owner-discovery" else {"result": {"turn": {"id": "accepted-turn"}}}
                    response = dict(type="response", requestId=message["requestId"], resultType="success", handledByClientId="owner", result=result)
                    payload = json.dumps(response).encode()
                    frame = struct.pack("<I", len(payload)) + payload
                    connection.sendall(frame[:2]); connection.sendall(frame[2:])
        except Exception as exc:
            errors.append(exc)
        finally:
            listener.close()
    worker = threading.Thread(target=peer, daemon=True)
    worker.start()
    with DesktopIPC(path) as desktop:
        owner = desktop.owner("chosen-id")
        desktop.send("chosen-id", "继续 — continue", owner)
    worker.join(5)
    assert not errors
    request = received[2]
    assert request["targetClientId"] == "owner"
    assert request["version"] == 2
    assert request["params"]["turnStart"]["request"]["threadId"] == "chosen-id"
    assert request["params"]["turnStart"]["request"]["input"][0]["text"] == "继续 — continue"
    assert "model" not in request["params"]["turnStart"]["request"]


def test_partial_reset_retries_only_failed_target(monkeypatch):
    a, b = Target("thread", "a", "A"), Target("thread", "b", "B")
    exhausted = RateWindow(used_percent=100, window_duration_mins=300, resets_at=0)
    class Quota:
        primary = exhausted
        secondary = None
        def exhausted_window(self): return exhausted
    class Stop:
        attempts = 0
        def is_set(self): return self.attempts >= 4
        def wait(self, seconds): self.attempts += 1
    monkeypatch.setattr(watch, "discover_codex", lambda _: "codex")
    snapshots = iter([Quota()])
    class Available:
        primary = replace(exhausted, used_percent=0, resets_at=9999999999)
        secondary = None
    monkeypatch.setattr(watch, "fetch_quota", lambda _: next(snapshots, Available()))
    calls = []
    def send(targets, text, **kwargs):
        target = targets[0]
        calls.append((target.id, text))
        success = target.id == "a" or len(calls) > 2
        return [delivery.DeliveryResult(target, success, "Accepted" if success else "Offline")]
    monkeypatch.setattr(watch, "deliver_targets", send)
    monkeypatch.setattr(watch, "recover_target", lambda target, text, **kwargs: send([target], text, **kwargs)[0])
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=(a,b), goal_mode=True, grace_seconds=0), Stop())
    assert calls == [("a", "Continue"), ("b", "Continue"), ("b", "Continue")]


def test_no_selection_does_not_send(monkeypatch):
    monkeypatch.setattr(watch, "discover_codex", lambda _: "codex")
    monkeypatch.setattr(watch, "deliver_targets", lambda *a, **k: pytest.fail("Sent without selection"))
    assert watch.run_desktop_watch(watch.WatchConfig()) == 1


def test_uncertain_acknowledgment_is_not_retryable(monkeypatch):
    from recharge_ai_task.codex_ipc import DeliveryUncertain
    desktop = DesktopIPC("unused")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(DeliveryUncertain):
        desktop.send("a", "Continue", "owner")
    monkeypatch.setattr(delivery, "_send_thread", lambda *a: (_ for _ in ()).throw(DeliveryUncertain("Check chat")))
    result = delivery.deliver_targets([Target("thread", "a", "A")], "Continue")[0]
    assert not result.success
    assert not result.retryable


def test_uncertain_watch_delivery_is_not_repeated(monkeypatch):
    a = Target("thread", "a", "A")
    exhausted = RateWindow(used_percent=100, window_duration_mins=300, resets_at=0)
    class Quota:
        primary = exhausted
        secondary = None
        def exhausted_window(self): return exhausted
    class Stop:
        attempts = 0
        def is_set(self): return self.attempts >= 4
        def wait(self, seconds): self.attempts += 1
    monkeypatch.setattr(watch, "discover_codex", lambda _: "codex")
    snapshots = iter([Quota()])
    class Available:
        primary = replace(exhausted, used_percent=0, resets_at=9999999999)
        secondary = None
    monkeypatch.setattr(watch, "fetch_quota", lambda _: next(snapshots, Available()))
    calls = []
    def send(selected, text, **kwargs):
        calls.append(text)
        return [delivery.DeliveryResult(a, False, "Uncertain", retryable=False)]
    monkeypatch.setattr(watch, "deliver_targets", send)
    monkeypatch.setattr(watch, "recover_target", lambda target, text, **kwargs: send([target], text, **kwargs)[0])
    watch.run_desktop_watch(watch.WatchConfig(desktop_targets=(a,), grace_seconds=0), Stop())
    assert calls == ["Continue"]


@pytest.mark.parametrize("error", ["request-timeout", "client-disconnected"])
def test_router_timeout_after_submission_is_uncertain(monkeypatch, error):
    from recharge_ai_task.codex_ipc import DeliveryUncertain
    desktop = DesktopIPC("unused")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: (_ for _ in ()).throw(RuntimeError(error)))
    with pytest.raises(DeliveryUncertain):
        desktop.send("a", "Continue", "owner")


def test_focus_lost_after_typing_is_uncertain(monkeypatch):
    a = Target("window", "42", "Codex", instance=":0:7", pid=7)
    monkeypatch.setattr(delivery.sys, "platform", "linux")
    monkeypatch.setattr(delivery, "discover_windows", lambda: [a])
    commands = []
    focus = iter(["42", "99"])
    monkeypatch.setattr(delivery.subprocess, "run", lambda args, **kwargs: commands.append(args))
    monkeypatch.setattr(delivery.subprocess, "check_output", lambda *a, **k: next(focus))
    result = delivery.deliver_targets([a], "Continue")[0]
    assert not result.success and not result.retryable
    assert any("type" in command for command in commands)
    assert not any("Return" in command for command in commands)


def test_cli_selects_ids_with_duplicate_titles(monkeypatch, capsys):
    from recharge_ai_task import cli
    a, b = Target("thread", "a", "Same"), Target("thread", "b", "Same")
    monkeypatch.setattr(targets, "discover_targets", lambda: targets.Inventory([a,b]))
    assert cli.main(["targets", "--select", "a", "--select", "b", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert all(t["selected"] for t in result["targets"])
    assert AppConfig.load().targets() == [replace(t, send_prompt=True, send_goal=False) for t in (a, b)]



def test_malformed_submission_acknowledgment_is_uncertain(monkeypatch):
    from recharge_ai_task.codex_ipc import DeliveryUncertain
    desktop = DesktopIPC("unused")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: {"handledByClientId": "owner"})
    with pytest.raises(DeliveryUncertain):
        desktop.send("a", "Continue", "owner")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: (_ for _ in ()).throw(ValueError("Invalid frame")))
    with pytest.raises(DeliveryUncertain):
        desktop.send("a", "Continue", "owner")


@pytest.mark.parametrize("turn", [None, {}, {"id": ""}, {"id": 42}, []])
def test_missing_turn_identity_is_uncertain(monkeypatch, turn):
    from recharge_ai_task.codex_ipc import DeliveryUncertain
    desktop = DesktopIPC("unused")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: {
        "handledByClientId": "owner", "result": {"result": {"turn": turn}}})
    with pytest.raises(DeliveryUncertain):
        desktop.send("a", "Continue", "owner")


def test_saved_project_names_current_and_legacy_membership(tmp_path):
    path = tmp_path / "state_5.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("create table projects(id text, name text)")
        db.execute("create table threads(id text, project_id text)")
        db.executemany("insert into projects values (?,?)", [("new", "Renamed in Codex"), ("other", "Other project")])
        db.executemany("insert into threads values (?,?)", [("native", "other"), ("legacy", None), ("removed", "deleted")])
    state = {
        "local-projects": {"old": {"name": "Stale name"}},
        "thread-project-assignments": {name: {"projectKind": "local", "projectId": "old"}
            for name in ("native", "legacy", "removed", "projectless", "remote")},
        "thread-project-membership-host-ids": {"remote": "ssh:elsewhere"},
        "projectless-thread-ids": ["projectless"],
        "app-server-project-id-by-legacy-project-id-by-host": {f"local:{tmp_path}": {"old": "new"}},
    }
    state_path = tmp_path / ".codex-global-state.json"
    state_path.write_text(json.dumps(state))
    before = path.read_bytes(), state_path.read_bytes()
    assert targets._saved_project_names(tmp_path) == {
        "native": "Other project", "legacy": "Renamed in Codex", "removed": "", "projectless": ""}
    assert (path.read_bytes(), state_path.read_bytes()) == before
    with sqlite3.connect(path) as db:
        db.execute("update projects set name='Latest name' where id='new'")
    assert targets._saved_project_names(tmp_path)["legacy"] == "Latest name"


def test_legacy_project_names_do_not_guess_from_paths(tmp_path):
    state = {
        "local-projects": {"project": {"name": "Custom name", "rootPaths": ["/work/repo"]}},
        "thread-project-assignments": {"assigned": {"projectKind": "local", "projectId": "project"},
            "cloud": {"projectKind": "chatgpt", "projectId": "project"}},
    }
    (tmp_path / ".codex-global-state.json").write_text(json.dumps(state))
    assert targets._saved_project_names(tmp_path) == {"assigned": "Custom name"}
    assert targets.Target.from_dict({"kind": "thread", "id": "old", "title": "Old"}).project_name == ""
    selected = Target("thread", "assigned", "Title", cwd="/different/worktree", project_name="Custom name")
    AppConfig(desktop_targets=[selected.to_dict()]).save()
    assert AppConfig.load().targets()[0].project_name == "Custom name"


def test_discovery_keeps_paths_and_reports_unreadable_project_names(monkeypatch, tmp_path):
    monkeypatch.setattr(targets.sys, "platform", "win32")
    monkeypatch.setattr(targets, "discover_homes", lambda: {tmp_path})
    monkeypatch.setattr(targets, "discover_windows", lambda: [])
    monkeypatch.setattr(targets, "_saved_threads", lambda _: [{"id": "a", "title": "A", "cwd": "/old/path"}])
    state = {"local-projects": {"p": {"name": "Friendly name"}},
        "thread-project-assignments": {"a": {"projectKind": "local", "projectId": "p"}}}
    path = tmp_path / ".codex-global-state.json"
    path.write_text(json.dumps(state))
    found = targets.discover_targets().targets[0]
    assert found.project_name == "Friendly name" and found.cwd == "/old/path"
    path.write_text("{broken")
    inventory = targets.discover_targets()
    assert inventory.targets[0].cwd == "/old/path" and inventory.targets[0].project_name == ""
    assert any("Project names unavailable" in warning for warning in inventory.warnings)


@pytest.mark.parametrize("result", [None, [], {}, {"result": None}, {"result": []}, {"result": {}}, {"result": {"turnId": ""}}])
def test_malformed_steer_acknowledgement_is_uncertain(monkeypatch, result):
    from recharge_ai_task.codex_ipc import DeliveryUncertain
    desktop = DesktopIPC("unused")
    monkeypatch.setattr(desktop, "request", lambda *a, **k: {"handledByClientId": "owner", "result": result})
    with pytest.raises(DeliveryUncertain):
        desktop.steer("chosen", "Prompt", "owner")


def test_steering_is_pinned_to_owner_and_preserves_multiline_prompt(monkeypatch):
    desktop = DesktopIPC("unused")
    calls = []
    def request(method, params, **kwargs):
        calls.append((method, params, kwargs))
        return {"handledByClientId": "owner", "result": {"result": {"turnId": "existing-turn"}}}
    monkeypatch.setattr(desktop, "request", request)
    assert desktop.steer("chosen", "First\nSecond", "owner") == {"turnId": "existing-turn"}
    method, params, kwargs = calls[0]
    assert method == "thread-follower-steer-turn" and kwargs == {"version": 1, "target_client": "owner"}
    assert params["conversationId"] == "chosen"
    assert params["input"] == [{"type": "text", "text": "First\nSecond", "text_elements": []}]
    assert params["restoreMessage"]["id"] == params["clientUserMessageId"]
    assert params["restoreMessage"]["context"] == {"workspaceRoots": [], "commentAttachments": []}
