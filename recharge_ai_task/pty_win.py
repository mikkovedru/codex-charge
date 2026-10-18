"""Windows PTY backend via pywinpty."""

from __future__ import annotations

import msvcrt
import sys
import time

try:
    from winpty.ptyprocess import PtyProcess
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "Windows PTY support requires pywinpty. Install with: pip install 'recharge-ai-task[windows]'"
    ) from exc

from .pty_backend import StopEvent


class WinPtySession:
    def __init__(self, proc: PtyProcess) -> None:
        self._proc = proc

    def read(self, size: int) -> str:
        return self._proc.read(size)

    def write(self, data: str) -> None:
        self._proc.write(data)

    def isalive(self) -> bool:
        return self._proc.isalive()

    @property
    def exitstatus(self) -> int | None:
        return self._proc.exitstatus


def spawn_pty(argv: list[str], dimensions: tuple[int, int]) -> WinPtySession:
    rows, cols = dimensions
    proc = PtyProcess.spawn(argv, dimensions=(rows, cols))
    return WinPtySession(proc)


def _stdin_is_tty() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def forward_stdin(pty: WinPtySession, stop: StopEvent) -> None:
    if not _stdin_is_tty():
        return
    while not stop.is_set() and pty.isalive():
        if not msvcrt.kbhit():
            time.sleep(0.05)
            continue
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            msvcrt.getwch()
            continue
        if ch == "\x03":
            stop.set()
            break
        pty.write(ch)


def sleep_with_proxy(pty: WinPtySession, stop: StopEvent, wake_at: int) -> bool:
    while not stop.is_set() and pty.isalive():
        remaining = wake_at - int(time.time())
        if remaining <= 0:
            return True
        try:
            data = pty.read(4096)
        except EOFError:
            return False
        if data:
            sys.stdout.write(data)
            sys.stdout.flush()
        stop.wait(min(1.0, float(remaining)))
    return pty.isalive() and not stop.is_set()
