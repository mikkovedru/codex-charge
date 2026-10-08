"""Read-only goal metadata and live desktop status regression tests."""
import json
import socket
import sqlite3
import struct
import threading

import pytest

from codex_charge import targets
from codex_charge.codex_ipc import DesktopIPC


@pytest.mark.parametrize("state,label", [
    ({"type": "active", "activeFlags": []}, "Running"),
    ({"type": "active", "activeFlags": ["waitingOnApproval"]}, "Waiting for approval"),
    ({"type": "active", "activeFlags": ["waitingOnUserInput"]}, "Waiting for input"),
    ({"type": "active", "activeFlags": ["waitingOnApproval", "waitingOnUserInput"]}, "Waiting for approval / Waiting for input"),
    ({"type": "idle"}, "Idle"), ({"type": "systemError"}, "Error"),
    ({"type": "notLoaded"}, "Not loaded"), (None, "Unavailable"),
    ({"type": "future"}, "Unavailable"),
])
def test_task_labels(state, label):
    assert targets.task_status(state) == label


@pytest.mark.parametrize("state,label", [
    ("active", "Active"), ("paused", "Paused"), ("blocked", "Blocked"),
    ("usageLimited", "Usage limited"), ("usage_limited", "Usage limited"),
    ("budgetLimited", "Budget limited"), ("budget_limited", "Budget limited"),
    ("complete", "Complete"), (None, "Unavailable"), ("future", "Unavailable"),
])
def test_goal_labels(state, label):
    assert targets.goal_status(state) == label


def test_goal_database_read_only_and_schema_fallback(tmp_path):
    path = tmp_path / "goals_1.sqlite"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE thread_goals(thread_id TEXT,status TEXT,objective TEXT)")
        db.execute("INSERT INTO thread_goals VALUES ('one','usage_limited','Private objective')")
    with sqlite3.connect(tmp_path / "goals_2.sqlite") as db:
        db.execute("CREATE TABLE unrelated(id TEXT)")
    before = path.read_bytes()
    assert targets._saved_goals(tmp_path) == {"one": "usage_limited"}
    assert path.read_bytes() == before


def test_goal_database_absent_and_corrupt_are_not_no_goal(tmp_path):
    assert targets._saved_goals(tmp_path) is None
    (tmp_path / "goals_1.sqlite").write_bytes(b"corrupt")
    with pytest.raises(sqlite3.DatabaseError):
        targets._saved_goals(tmp_path)


@pytest.mark.parametrize("snapshot_error", [False, True])
@pytest.mark.parametrize("cached_goal", [False, True])
def test_live_status_overrides_unloaded_metadata(monkeypatch, tmp_path, snapshot_error, cached_goal):
    from codex_charge import codex_ipc
    (tmp_path / "ipc").mkdir()
    (tmp_path / "ipc/ipc.sock").touch()
    monkeypatch.setattr(targets, "discover_homes", lambda: {tmp_path})
    monkeypatch.setattr(targets, "discover_windows", lambda: [])
    monkeypatch.setattr(targets, "_saved_threads", lambda _: [
        {"id": "one", "status": {"type": "notLoaded"}},
        {"id": "two", "status": {"type": "notLoaded"}}])
    monkeypatch.setattr(targets, "_saved_goals", lambda _: {"one": "usage_limited"})
    # Ignore actual daemon sockets; only this synthetic profile is read.
    monkeypatch.setattr(targets.stat, "S_ISSOCK", lambda _: False)
    class Desktop:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def owner(self, thread):
            if thread == "two": raise RuntimeError("no-client-found")
            return "owner"
        def status_snapshot(self, thread, owner):
            if snapshot_error: raise TimeoutError("offline")
            return {"task": {"type": "active"}, "goal": "complete" if cached_goal else "paused", "goal_current": not cached_goal}
    monkeypatch.setattr(codex_ipc, "DesktopIPC", Desktop)
    inventory = targets.discover_targets()
    one, two = inventory.targets
    assert one.status == "Open in desktop"
    assert one.task_status == ("Unavailable" if snapshot_error else "Running")
    assert one.goal_status == "Usage limited"
    assert two.task_status == "Not loaded" and two.goal_status == "No goal"
    assert bool(inventory.warnings) == snapshot_error


@pytest.mark.skipif(not hasattr(socket, "AF_UNIX"), reason="Requires Unix sockets")
@pytest.mark.parametrize("variant", ["live", "complete", "no-goal", "wrong-version", "wrong-identity", "timeout", "oversize"])
def test_snapshot_is_pinned_read_only_and_always_detaches(tmp_path, variant):
    path = str(tmp_path / "ipc.sock")
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    listener.bind(path)
    listener.listen()
    received, errors = [], []
    def peer():
        try:
            with listener.accept()[0] as connection:
                connection.settimeout(2)
                def read(n):
                    data = b""
                    while len(data) < n:
                        chunk = connection.recv(n - len(data))
                        if not chunk: raise EOFError()
                        data += chunk
                    return data
                def recv():
                    value = json.loads(read(struct.unpack("<I", read(4))[0]))
                    received.append(value)
                    return value
                def send(value):
                    payload = json.dumps(value).encode()
                    frame = struct.pack("<I", len(payload)) + payload
                    connection.sendall(frame[:2])
                    connection.sendall(frame[2:])
                init = recv()
                send({"type": "response", "requestId": init["requestId"], "resultType": "success", "result": {"clientId": "observer"}})
                follow = recv()
                assert follow["params"]["following"] is True
                state = {"id": "chosen", "hostId": "local", "threadRuntimeStatus": {"type": "active"},
                         "threadGoal": {"status": "paused", "objective": "Secret"}, "turns": [{"text": "Secret history"}]}
                snapshot = {"type": "broadcast", "method": "thread-stream-state-changed", "version": 11,
                            "sourceClientId": "owner", "params": {"hostId": "local", "conversationId": "chosen",
                            "change": {"type": "snapshot", "conversationState": state}}}
                # Unrelated owner and conversation messages must never supply state.
                send({**snapshot, "sourceClientId": "other-owner", "version": 99})
                send({**snapshot, "params": {**snapshot["params"], "conversationId": "other-chat"}})
                if variant == "complete":
                    state["threadGoal"] = None
                    state["completedThreadGoal"] = {"status": "complete"}
                elif variant == "no-goal": state["threadGoal"] = None
                elif variant == "wrong-version": snapshot["version"] = 99
                elif variant == "wrong-identity": state["id"] = "other-chat"
                if variant == "oversize": connection.sendall(struct.pack("<I", 65*1024*1024))
                elif variant != "timeout": send(snapshot)
                recv()  # The observer unsubscribes even when validation fails.
        except Exception as exc:
            errors.append(exc)
        finally:
            listener.close()
    worker = threading.Thread(target=peer, daemon=True)
    worker.start()
    with DesktopIPC(path, timeout=.5) as desktop:
        if variant in {"wrong-version", "wrong-identity", "timeout", "oversize"}:
            with pytest.raises((ValueError, TimeoutError)):
                desktop.status_snapshot("chosen", "owner")
        else:
            value = desktop.status_snapshot("chosen", "owner")
            assert value == {"task": {"type": "active"}, "goal": {"live": "paused", "complete": "complete", "no-goal": None}[variant], "goal_available": True, "goal_current": variant == "live"}
            assert "Secret" not in json.dumps(value)
    worker.join(3)
    assert not worker.is_alive() and not errors, errors
    assert [m["method"] for m in received] == ["initialize", "thread-stream-following-changed", "thread-stream-following-changed"]
    assert all(m["targetClientIds"] == ["owner"] for m in received[1:])
    assert received[-1]["params"] == {"hostId": "local", "conversationId": "chosen", "following": False}
