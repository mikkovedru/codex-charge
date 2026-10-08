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

    def request(self, method, params, *, version=0, target_client=None):
        request_id = str(uuid.uuid4())
        request = dict(type="request", requestId=request_id,
                       sourceClientId=self.client_id, method=method, params=params,
                       version=version, timeoutMs=int(self.timeout * 1000))
        if target_client:
            request["targetClientId"] = target_client
        payload = json.dumps(request).encode()
        self.socket.sendall(struct.pack("<I", len(payload)) + payload)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            self.socket.settimeout(max(.01, deadline - time.monotonic()))
            size = struct.unpack("<I", self._read(4, deadline))[0]
            if not 0 < size <= 16 * 1024 * 1024:
                raise ValueError("Invalid Codex IPC frame size")
            message = json.loads(self._read(size, deadline))
            if message.get("type") == "client-discovery-request":
                # We only consume requests; never claim ownership of a chat.
                answer = json.dumps(dict(type="client-discovery-response",
                    requestId=message["requestId"], response={"canHandle": False})).encode()
                self.socket.sendall(struct.pack("<I", len(answer)) + answer)
            if message.get("requestId") != request_id or message.get("type") != "response":
                continue
            if message.get("resultType") != "success":
                raise RuntimeError(message.get("error", "Codex IPC request failed"))
            return message
        raise TimeoutError("Codex desktop did not respond")

    def owner(self, thread_id, host_id="local"):
        response = self.request("thread-owner-discovery",
            {"hostId": host_id, "conversationId": thread_id}, version=1)
        if response["result"].get("supportsUntrustedAppInput") is not True:
            raise RuntimeError("Desktop version does not support external chat input")
        return response["handledByClientId"]

    def send(self, thread_id, text, owner):
        # Request routing is pinned to the owner discovered for this exact ID.
        # No model, permissions or workspace overrides are sent.
        try:
            response = self.request("thread-follower-start-turn", {
                "conversationId": thread_id,
                "turnStart": {"request": {"threadId": thread_id,
                    "input": [{"type": "text", "text": text, "text_elements": []}],
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
        if not isinstance(result, dict) or not isinstance(result.get("result"), dict) or "turn" not in result["result"]:
            raise DeliveryUncertain("Desktop did not acknowledge a turn; check the chat before retrying")
        return result
