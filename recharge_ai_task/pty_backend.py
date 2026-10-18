"""Cross-platform PTY factory."""

from __future__ import annotations

import sys
import threading
from typing import Protocol


class StopEvent:
    def __init__(self) -> None:
        self._flag = threading.Event()

    def set(self) -> None:
        self._flag.set()

    def is_set(self) -> bool:
        return self._flag.is_set()

    def wait(self, timeout: float) -> bool:
        return self._flag.wait(timeout)


class PtySession(Protocol):
    def read(self, size: int) -> str: ...
    def write(self, data: str) -> None: ...
    def isalive(self) -> bool: ...
    @property
    def exitstatus(self) -> int | None: ...


def spawn_pty(argv: list[str], dimensions: tuple[int, int]) -> PtySession:
    if sys.platform == "win32":
        from .pty_win import spawn_pty as _spawn

        return _spawn(argv, dimensions)
    from .pty_unix import spawn_pty as _spawn

    return _spawn(argv, dimensions)


def forward_stdin(pty: PtySession, stop: StopEvent) -> None:
    if sys.platform == "win32":
        from .pty_win import forward_stdin as _forward
    else:
        from .pty_unix import forward_stdin as _forward
    _forward(pty, stop)


def sleep_with_proxy(pty: PtySession, stop: StopEvent, wake_at: int) -> bool:
    if sys.platform == "win32":
        from .pty_win import sleep_with_proxy as _sleep
    else:
        from .pty_unix import sleep_with_proxy as _sleep
    return _sleep(pty, stop, wake_at)
