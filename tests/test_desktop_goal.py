"""Isolated native helper protocol and uncertainty checks."""
import json
import os
import sys
import struct
import subprocess
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

if not sys.platform.startswith("linux"):
    pytest.skip("Linux native desktop helper", allow_module_level=True)

from codex_charge import desktop_goal as control
from codex_charge.codex_ipc import DeliveryUncertain
from codex_charge.targets import Target

TARGET = Target("thread", "chosen", "A chat", instance="/fixture")
GOAL = {"threadId": "chosen", "status": "paused"}


def helper(monkeypatch, *, response=None, returncode=0, timeout=False):
    calls = []
    class Process:
        def __init__(self, command, **kwargs):
            self.returncode = returncode
            calls.append((command, kwargs))
        def communicate(self, data=None, timeout=None):
            if data is not None:
                calls.append(json.loads(data))
                if timeout_expired: raise subprocess.TimeoutExpired("fixture", timeout)
            return response or '{"success": true}', ""
        def terminate(self): calls.append("terminate")
    timeout_expired = timeout
    peer = SimpleNamespace(getsockopt=lambda *a: struct.pack("3i", 123, os.getuid(), 0))
    monkeypatch.setattr(control, "ui_lock", nullcontext)
    monkeypatch.setattr(control.subprocess, "Popen", Process)
    return SimpleNamespace(socket=peer), calls


def test_helper_uses_socket_peer_pid_and_contains_no_prompt(monkeypatch):
    desktop, calls = helper(monkeypatch)
    control.activate(TARGET, GOAL, desktop)
    assert calls[0][0][-2:] == ["-m", "codex_charge.desktop_goal_ui"]
    assert calls[1] == {"target": TARGET.to_dict(), "goal": GOAL, "pid": 123}


@pytest.mark.parametrize("response", ['invalid', '{}', '[]', '{"success": "yes"}', '{"success":false,"uncertain":true,"detail":"Unconfirmed"}'])
def test_missing_or_uncertain_acknowledgement_never_retries(monkeypatch, response):
    desktop, calls = helper(monkeypatch, response=response)
    with pytest.raises(DeliveryUncertain): control.activate(TARGET, GOAL, desktop)
    assert len(calls) == 2


def test_timeout_requests_helper_cleanup_and_remains_uncertain(monkeypatch):
    desktop, calls = helper(monkeypatch, timeout=True)
    with pytest.raises(DeliveryUncertain, match="timed out"):
        control.activate(TARGET, GOAL, desktop)
    assert calls[-1] == "terminate"


def test_confirmed_helper_failure_is_visible(monkeypatch):
    desktop, calls = helper(monkeypatch, response='{"success":false,"detail":"No native control"}')
    with pytest.raises(RuntimeError, match="No native control") as error:
        control.activate(TARGET, GOAL, desktop)
    assert not isinstance(error.value, DeliveryUncertain)


def test_wrong_user_peer_never_starts_helper(monkeypatch):
    desktop, calls = helper(monkeypatch)
    desktop.socket.getsockopt = lambda *a: struct.pack("3i", 123, os.getuid()+1, 0)
    with pytest.raises(RuntimeError, match="same-user"):
        control.activate(TARGET, GOAL, desktop)
    assert calls == []
