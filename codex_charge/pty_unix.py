"""POSIX PTY backend for Linux/macOS."""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import struct
import subprocess
import sys
import termios
import time

from .pty_backend import StopEvent


class UnixPtySession:
    def __init__(self, master_fd: int, proc: subprocess.Popen[bytes]) -> None:
        self._master_fd = master_fd
        self._proc = proc

    def read(self, size: int) -> str:
        try:
            ready, _, _ = select.select([self._master_fd], [], [], 0.1)
            if not ready:
                return ""
            data = os.read(self._master_fd, size)
            return data.decode("utf-8", errors="replace")
        except OSError as exc:
            if exc.errno in {errno.EIO, errno.EBADF}:
                return ""
            raise

    def write(self, data: str) -> None:
        os.write(self._master_fd, data.encode("utf-8"))

    def isalive(self) -> bool:
        return self._proc.poll() is None

    @property
    def exitstatus(self) -> int | None:
        return self._proc.returncode


def _set_winsize(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


def spawn_pty(argv: list[str], dimensions: tuple[int, int]) -> UnixPtySession:
    rows, cols = dimensions
    master_fd, slave_fd = pty.openpty()
    _set_winsize(slave_fd, rows, cols)
    _set_winsize(master_fd, rows, cols)

    proc = subprocess.Popen(
        argv,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)
    return UnixPtySession(master_fd, proc)


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def forward_stdin(pty: UnixPtySession, stop: StopEvent) -> None:
    if not _stdin_is_tty():
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty = termios.tcgetattr(fd)
        tty[3] &= ~(termios.ICANON | termios.ECHO)
        termios.tcsetattr(fd, termios.TCSANOW, tty)
        while not stop.is_set() and pty.isalive():
            ready, _, _ = select.select([fd], [], [], 0.1)
            if not ready:
                continue
            data = os.read(fd, 1)
            if not data:
                break
            if data == b"\x03":
                stop.set()
                break
            pty.write(data.decode("utf-8", errors="replace"))
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def sleep_with_proxy(pty: UnixPtySession, stop: StopEvent, wake_at: int) -> bool:
    while not stop.is_set() and pty.isalive():
        remaining = wake_at - int(time.time())
        if remaining <= 0:
            return True
        data = pty.read(4096)
        if data:
            sys.stdout.write(data)
            sys.stdout.flush()
        stop.wait(min(1.0, float(remaining)))
    return pty.isalive() and not stop.is_set()
