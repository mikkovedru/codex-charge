"""Deliver once per explicit target; retain individual failures for retry."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass

from .codex_ipc import DesktopIPC, DeliveryUncertain
from .targets import Target, discover_windows

_log = logging.getLogger("codex-charge.delivery")


@dataclass(frozen=True)
class DeliveryResult:
    target: Target
    success: bool
    detail: str
    retryable: bool = True


def open_target(target):
    if target.kind != "thread" or not target.deeplink:
        raise ValueError("This target has no chat link")
    if sys.platform == "win32":
        os.startfile(target.deeplink)
    else:
        subprocess.run(["xdg-open", target.deeplink], check=True, timeout=10,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _send_thread(target, text):
    if not target.endpoint:
        raise RuntimeError("Desktop chat routing unavailable; open Codex and refresh targets")
    with DesktopIPC(target.endpoint, timeout=5) as desktop:
        try:
            owner = desktop.owner(target.id)
        except RuntimeError as exc:
            if str(exc) != "no-client-found":
                raise
            # Open only the explicitly selected chat; never resume it in another server.
            open_target(target)
            deadline = time.monotonic() + 10
            while True:
                try:
                    owner = desktop.owner(target.id)
                    break
                except RuntimeError as exc:
                    if str(exc) != "no-client-found" or time.monotonic() >= deadline:
                        raise RuntimeError("Chat did not become available in the desktop") from exc
                    time.sleep(.3)
        desktop.send(target.id, text, owner)


def _send_window(target, text, enter_presses, key_delay):
    current = {w.key: w for w in discover_windows()}.get(target.key)
    if target.pid is None or current is None or current.pid != target.pid:
        raise RuntimeError("Selected window closed or its ID was reused; refresh targets")
    if sys.platform == "win32":
        import ctypes
        from .desktop_input import _win_paste_text
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.GetForegroundWindow.restype = wintypes.HWND
        hwnd = int(target.id)
        user32.SetForegroundWindow(hwnd)
        time.sleep(.2)
        if user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("Selected Codex window could not be activated")
        _win_paste_text(text)
        for _ in range(max(1, enter_presses)):
            if user32.GetForegroundWindow() != hwnd:
                raise RuntimeError("Focus changed before sending")
            user32.keybd_event(0x0D, 0, 0, 0)
            user32.keybd_event(0x0D, 0, 2, 0)
            time.sleep(key_delay)
    else:
        subprocess.run(["xdotool", "windowactivate", "--sync", target.id], check=True, timeout=5)
        def check_focus():
            active = subprocess.check_output(["xdotool", "getactivewindow"], text=True, timeout=3).strip()
            if active != target.id:
                raise RuntimeError("Focus moved away from the selected Codex window")
        check_focus()
        try:
            subprocess.run(["xdotool", "type", "--clearmodifiers", "--delay", "0", "--", text], check=True, timeout=10)
            for _ in range(max(1, enter_presses)):
                check_focus()
                subprocess.run(["xdotool", "key", "--clearmodifiers", "Return"], check=True, timeout=3)
                time.sleep(key_delay)
        except Exception as exc:
            raise DeliveryUncertain("Window input may have been entered; check its composer before retrying manually") from exc


def deliver_targets(targets, text, *, enter_presses=1, key_delay=.12):
    if not text.strip():
        raise ValueError("Signal text cannot be empty")
    results = []
    seen = set()
    for target in targets:
        if target.key in seen:
            continue
        seen.add(target.key)
        try:
            if target.kind == "thread":
                _send_thread(target, text)
            elif target.kind == "window":
                _send_window(target, text, enter_presses, key_delay)
            else:
                raise ValueError(f"Unsupported target kind: {target.kind}")
            result = DeliveryResult(target, True, "Signal accepted")
        except DeliveryUncertain as exc:
            result = DeliveryResult(target, False, str(exc), retryable=False)
        except Exception as exc:
            result = DeliveryResult(target, False, str(exc))
        _log.info("target=%s success=%s detail=%s", target.id, result.success, result.detail)
        results.append(result)
    return results
