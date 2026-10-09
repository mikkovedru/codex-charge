"""Bounded, versioned access to the running Codex desktop router.

This is a private desktop protocol, isolated here so incompatible releases
fail with an error rather than falling back to typing in another chat.
"""
from __future__ import annotations

import json
import os
import socket
import stat
import struct
import time
import uuid
from pathlib import Path


class DeliveryUncertain(RuntimeError):
    """A request may have been accepted; do not automatically repeat it."""


class DesktopIPC:
    def __init__(self, endpoint: str, timeout: float = 8):
        self.endpoint = endpoint
        self.timeout = timeout
        self.client_id = "initializing-client"
        self.socket = None

    def __enter__(self):
        info = Path(self.endpoint).stat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise OSError("Codex IPC endpoint must be a socket owned by the current user")
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.settimeout(self.timeout)
        try:
            self.socket.connect(self.endpoint)
            response = self.request("initialize", {"clientType": "codex-charge"})
            self.client_id = response["result"]["clientId"]
        except Exception:
            self.socket.close()
            raise
        return self

    def __exit__(self, *_):
        self.socket.close()

    def _read(self, size, deadline):
        data = bytearray()
        while len(data) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Codex desktop response timed out")
            self.socket.settimeout(remaining)
            chunk = self.socket.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Codex desktop disconnected")
            data.extend(chunk)
        return bytes(data)

    def _write(self, message):
        payload = json.dumps(message).encode()
        self.socket.sendall(struct.pack("<I", len(payload)) + payload)

    def _message(self, deadline, max_size=16 * 1024 * 1024):
        size = struct.unpack("<I", self._read(4, deadline))[0]
        if not 0 < size <= max_size:
            raise ValueError("Invalid Codex IPC frame size")
        message = json.loads(self._read(size, deadline))
        if not isinstance(message, dict):
            raise ValueError("Invalid Codex IPC message")
        if message.get("type") == "client-discovery-request":
            # We only consume requests; never claim ownership of a chat.
            self._write(dict(type="client-discovery-response",
                requestId=message["requestId"], response={"canHandle": False}))
        return message

    def request(self, method, params, *, version=0, target_client=None):
        request_id = str(uuid.uuid4())
        request = dict(type="request", requestId=request_id,
                       sourceClientId=self.client_id, method=method, params=params,
                       version=version, timeoutMs=int(self.timeout * 1000))
        if target_client:
            request["targetClientId"] = target_client
        self._write(request)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            message = self._message(deadline)
            if message.get("requestId") != request_id or message.get("type") != "response":
                continue
            if message.get("resultType") != "success":
                raise RuntimeError(message.get("error", "Codex IPC request failed"))
            return message
        raise TimeoutError("Codex desktop did not respond")

    def status_snapshot(self, thread_id, owner):
        """Observe the owner's current state, then detach. Never resume a chat.

        Snapshot version 11 is private desktop IPC. Validate the owner and chat
        identity, retain only status fields, and fail visibly on incompatibility.
        """
        def follow(enabled):
            self._write(dict(type="broadcast", method="thread-stream-following-changed",
                version=1, sourceClientId=self.client_id, targetClientIds=[owner],
                params={"hostId": "local", "conversationId": thread_id, "following": enabled}))
        follow(True)
        deadline = time.monotonic() + self.timeout
        try:
            while time.monotonic() < deadline:
                # Desktop snapshots include history; use a bounded larger frame.
                message = self._message(deadline, max_size=64 * 1024 * 1024)
                if (message.get("type") != "broadcast" or
                        message.get("method") != "thread-stream-state-changed" or
                        message.get("sourceClientId") != owner):
                    continue
                params = message.get("params", {})
                if params.get("conversationId") != thread_id or params.get("hostId") != "local":
                    continue
                if message.get("version") != 11:
                    raise ValueError("Unsupported Codex desktop status version")
                change = params.get("change", {})
                if change.get("type") != "snapshot":
                    continue
                state = change.get("conversationState")
                if not isinstance(state, dict) or state.get("id") != thread_id or state.get("hostId") != "local":
                    raise ValueError("Invalid Codex desktop status identity")
                runtime = state.get("threadRuntimeStatus")
                goal = state.get("threadGoal") or state.get("completedThreadGoal")
                # Do not retain conversation histories, prompts, or objectives.
                return {"task": {k: runtime[k] for k in ("type", "activeFlags") if k in runtime}
                            if isinstance(runtime, dict) else None,
                        "goal": goal.get("status") if isinstance(goal, dict) else None,
                        "goal_available": "threadGoal" in state or "completedThreadGoal" in state,
                        "goal_current": isinstance(state.get("threadGoal"), dict)}
            raise TimeoutError("Codex desktop status timed out")
        finally:
            try:
                follow(False)
            except OSError:
                pass  # Disconnect also removes this observer from the owner.

    def owner(self, thread_id, host_id="local"):
        response = self.request("thread-owner-discovery",
            {"hostId": host_id, "conversationId": thread_id}, version=1)
        if response["result"].get("supportsUntrustedAppInput") is not True:
            raise RuntimeError("Desktop version does not support external chat input")
        return response["handledByClientId"]

    def send(self, thread_id, text, owner):
        return self._start_turn(thread_id, [{"type": "text", "text": text, "text_elements": []}], owner)

    def continue_goal(self, thread_id, owner):
        """Wake the existing active goal without adding a user prompt."""
        return self._start_turn(thread_id, [], owner)

    def _start_turn(self, thread_id, inputs, owner):
        # Request routing is pinned to the owner discovered for this exact ID.
        # No model, permissions or workspace overrides are sent.
        try:
            response = self.request("thread-follower-start-turn", {
                "conversationId": thread_id,
                "turnStart": {"request": {"threadId": thread_id,
                    "input": inputs,
                    "clientUserMessageId": str(uuid.uuid4())},
                    "context": {"inheritThreadSettings": True}},
            }, version=2, target_client=owner)
        except (OSError, TimeoutError, ConnectionError, ValueError, TypeError, AttributeError) as exc:
            raise DeliveryUncertain("Delivery was not confirmed; check the chat before retrying manually") from exc
        except RuntimeError as exc:
            if any(reason in str(exc).lower() for reason in ("timeout", "timed out", "disconnected", "connection-closed")):
                raise DeliveryUncertain("Desktop delivery timed out or disconnected; check the chat before retrying manually") from exc
            raise
        if response.get("handledByClientId") != owner:
            raise DeliveryUncertain("Codex response came from a different chat owner; check the chat before retrying")
        result = response.get("result")
        inner = result.get("result") if isinstance(result, dict) else None
        turn = inner.get("turn") if isinstance(inner, dict) else None
        if not isinstance(turn, dict) or not isinstance(turn.get("id"), str) or not turn["id"]:
            raise DeliveryUncertain("Desktop did not acknowledge a turn; check the chat before retrying")
        return result
