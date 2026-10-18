"""Send keystrokes to the ChatGPT Codex desktop app window."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import time
from typing import Callable

_log = logging.getLogger("recharge-ai-task.desktop")

DEFAULT_WINDOW_TITLES = ("Codex", "ChatGPT", "OpenAI Codex")


def send_to_desktop(
    text: str,
    *,
    window_titles: tuple[str, ...] = DEFAULT_WINDOW_TITLES,
    enter_presses: int = 1,
    key_delay: float = 0.12,
) -> bool:
    if sys.platform == "win32":
        return _send_windows(text, window_titles, enter_presses, key_delay)
    if sys.platform.startswith("linux"):
        return _send_linux(text, window_titles, enter_presses, key_delay)
    _log.warning("desktop input not supported on %s", sys.platform)
    return False


def _send_windows(
    text: str,
    window_titles: tuple[str, ...],
    enter_presses: int,
    key_delay: float,
) -> bool:
    hwnd = _find_windows_window(window_titles)
    if hwnd is None:
        return False

    import ctypes

    user32 = ctypes.windll.user32
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    _win_paste_text(text)
    time.sleep(key_delay)

    for _ in range(max(1, enter_presses)):
        user32.keybd_event(0x0D, 0, 0, 0)
        user32.keybd_event(0x0D, 0, 2, 0)
        time.sleep(key_delay)
    return True


def _win_paste_text(text: str) -> None:
    import ctypes

    CF_UNICODETEXT = 13
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if not user32.OpenClipboard(0):
        return
    try:
        user32.EmptyClipboard()
        payload = (text + "\0").encode("utf-16-le")
        h = kernel32.GlobalAlloc(0x2000, len(payload))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, payload, len(payload))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()

    user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
    user32.keybd_event(0x56, 0, 0, 0)  # V
    user32.keybd_event(0x56, 0, 2, 0)
    user32.keybd_event(0x11, 0, 2, 0)
    time.sleep(0.1)


def _find_windows_window(titles: tuple[str, ...]) -> int | None:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    found: list[int] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        for needle in titles:
            if needle.lower() in title.lower():
                found.append(hwnd)
                return False
        return True

    user32.EnumWindows(callback, 0)
    return found[0] if found else None


def _send_linux(
    text: str,
    window_titles: tuple[str, ...],
    enter_presses: int,
    key_delay: float,
) -> bool:
    if not shutil.which("xdotool"):
        _log.error("xdotool not found; install with: sudo apt install xdotool")
        return False

    window_id = _find_linux_window(window_titles)
    if window_id is None:
        return False

    subprocess.run(["xdotool", "windowactivate", window_id], check=False)
    time.sleep(0.2)
    subprocess.run(["xdotool", "type", "--clearmodifiers", "--", text], check=False)
    time.sleep(key_delay)
    for _ in range(max(1, enter_presses)):
        subprocess.run(["xdotool", "key", "Return"], check=False)
        time.sleep(key_delay)
    return True


def _find_linux_window(titles: tuple[str, ...]) -> str | None:
    for title in titles:
        proc = subprocess.run(
            ["xdotool", "search", "--name", title],
            capture_output=True,
            text=True,
            check=False,
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return line
    return None
