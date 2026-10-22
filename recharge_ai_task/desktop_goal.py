"""Run native desktop Goal actions in an isolated GTK helper process."""
from __future__ import annotations

import json
import os
import fcntl
from contextlib import contextmanager
from pathlib import Path
import socket
import stat
import struct
import subprocess
import sys

from .codex_ipc import DeliveryUncertain

@contextmanager
def ui_lock():
    # Serialize native controls across tray, CLI, and separate configurations.
    directory = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
    path = directory / f"recharge-ai-task-goal-ui-{os.getuid()}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode):
            raise RuntimeError("Native Goal control lock is not owned by this user")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def activate(target, expected, desktop):
    if getattr(sys, "frozen", False):
        from .desktop_launch import desktop_command
        command = [*desktop_command(), "--resume-goal-ui"]
    else:
        command = [sys.executable, "-m", "recharge_ai_task.desktop_goal_ui"]
    pid, uid, _gid = struct.unpack("3i", desktop.socket.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if uid != os.getuid() or pid <= 0:
        raise RuntimeError("Native Goal controls require a same-user desktop owner")
    payload = {"target": target.to_dict(), "goal": expected, "pid": pid}
    with ui_lock():
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        try:
            output, _errors = process.communicate(json.dumps(payload), timeout=45)
        except subprocess.TimeoutExpired as exc:
            process.terminate()  # The helper restores the clipboard in finally.
            try:
                process.communicate(timeout=12)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
            raise DeliveryUncertain("Native Goal control timed out; check this chat before retrying") from exc
        try:
            response = json.loads(output)
            if not isinstance(response, dict) or type(response.get("success")) is not bool:
                raise ValueError("Invalid Goal control acknowledgement")
        except (ValueError, TypeError) as exc:
            raise DeliveryUncertain("Native Goal control was not confirmed; check this chat before retrying") from exc
        if process.returncode or not response["success"]:
            detail = response.get("detail", "Native Goal control failed")
            if response.get("uncertain"):
                raise DeliveryUncertain(detail)
            raise RuntimeError(detail)
