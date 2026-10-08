"""Same-user local control channel between the tray and its GTK windows."""
from __future__ import annotations

import json
import os
import socket
import socketserver
import stat
import struct
import threading

from .config import config_dir

MAX_MESSAGE = 65536


def watch_settings(config):
    return {"targets": sorted(t.key for t in config.targets()),
            "signal": config.continue_prompt, "goal": config.goal_mode,
            "grace": config.grace_seconds, "poll": config.poll_seconds,
            "codex_path": config.codex_path}


def control_path():
    return config_dir() / "tray-control.sock"


def request(command="status", *, timeout=3):
    path = control_path()
    info = path.lstat()
    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
        raise RuntimeError("Tray control endpoint is not a socket owned by this user")
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(str(path))
        connection.sendall(json.dumps({"command": command}).encode() + b"\n")
        stream = connection.makefile("rb")
        try:
            line = stream.readline(MAX_MESSAGE + 1)
        finally:
            stream.close()
        if not line.endswith(b"\n") or len(line) > MAX_MESSAGE:
            raise RuntimeError("Invalid tray control response")
        response = json.loads(line)
        if response.get("error"):
            raise RuntimeError(response["error"])
        return response["status"]


class ControlServer:
    def __init__(self, handler):
        self.handler = handler
        self.server = None
        self.thread = None

    def start(self):
        path = control_path()
        if path.exists() or path.is_symlink():
            info = path.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                raise RuntimeError("Refusing to replace an unrelated tray control file")
            try:
                request(timeout=1)
            except (OSError, RuntimeError):
                # Only remove an endpoint proven stale, never a live busy server.
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(1)
                    try:
                        probe.connect(str(path))
                    except ConnectionRefusedError:
                        path.unlink()
                    else:
                        raise RuntimeError("Another tray is already running")
            else:
                raise RuntimeError("Another tray is already running")
        handler = self.handler
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(3)
                if hasattr(socket, "SO_PEERCRED"):
                    _, uid, _ = struct.unpack("3i", self.request.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                    if uid != os.getuid():
                        return
                try:
                    line = self.rfile.readline(MAX_MESSAGE + 1)
                    if len(line) > MAX_MESSAGE or not line.endswith(b"\n"):
                        raise ValueError("Invalid tray control request")
                    command = json.loads(line)["command"]
                    response = {"status": handler(command)}
                except Exception as exc:
                    response = {"error": str(exc)}
                try:
                    self.wfile.write(json.dumps(response).encode() + b"\n")
                except OSError:
                    pass
        self.server = socketserver.UnixStreamServer(str(path), Handler)
        path.chmod(0o600)
        self.inode = path.stat().st_ino
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": .1}, daemon=True)
        self.thread.start()

    def close(self):
        if self.server is None:
            return
        self.server.shutdown()
        self.server.server_close()
        path = control_path()
        try:
            if path.lstat().st_ino == self.inode:
                path.unlink()
        except FileNotFoundError:
            pass
