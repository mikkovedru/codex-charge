"""Deliver once per explicit target; retain individual failures for retry."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
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


def _owner_for_delivery(desktop, target):
    try:
        return desktop.owner(target.id)
    except RuntimeError as exc:
        if str(exc) != "no-client-found":
            raise
    # Open only this explicitly selected chat; its native owner handles loading.
    open_target(target)
    deadline = time.monotonic() + 10
    while True:
        try:
            return desktop.owner(target.id)
        except RuntimeError as exc:
            if str(exc) != "no-client-found" or time.monotonic() >= deadline:
                raise RuntimeError("Chat did not become available in the desktop") from exc
            time.sleep(.3)


def _send_thread(target, text):
    if not target.endpoint:
        raise RuntimeError("Desktop chat routing unavailable; open Codex and refresh targets")
    with DesktopIPC(target.endpoint, timeout=5) as desktop:
        desktop.send(target.id, text, _owner_for_delivery(desktop, target))


def recover_target(target, text, *, enter_presses=1, key_delay=.12):
    """Resume only quota-stopped goals, then continue in the desktop owner.

    This is automatic quota recovery. Manual Send signal now remains an explicit
    text send. Window identities cannot safely identify an individual goal.
    """
    if target.kind != "thread":
        return DeliveryResult(target, False,
            "Native goal recovery requires a chat ID; select a chat or disable goal recovery", retryable=False)
    from .goal_control import NativeGoals
    try:
        if not target.instance or Path(target.endpoint).resolve() != (Path(target.instance) / "ipc/ipc.sock").resolve():
            raise ValueError("Desktop endpoint does not match the selected Codex profile")
        if not text.strip():
            raise ValueError("Signal text cannot be empty")
        with NativeGoals(target.instance) as goals:
            goal = goals.get(target.id)
            if goal is not None and goal["status"] in {"paused", "blocked", "budgetLimited", "complete"}:
                return DeliveryResult(target, True, f"Skipped — goal is {goal['status']}")
            if not target.endpoint:
                raise RuntimeError("Desktop routing unavailable; open Codex and refresh targets")
            with DesktopIPC(target.endpoint, timeout=5) as desktop:
                owner = _owner_for_delivery(desktop, target)
                snapshot = desktop.status_snapshot(target.id, owner)
                task = snapshot.get("task")
                if not isinstance(task, dict) or task.get("type") not in {"active", "idle", "systemError", "notLoaded"}:
                    raise RuntimeError("Current task status is unavailable; no automatic signal sent")
                if task["type"] == "active":
                    return DeliveryResult(target, True, "Skipped — task is already running or waiting for input")
                if goal is None and snapshot.get("goal") == "complete":
                    return DeliveryResult(target, True, "Skipped — goal is complete")
                resumed = False
                if goal is not None and goal["status"] == "usageLimited":
                    resumed = goals.resume(target.id, goal)
                    if not resumed:
                        return DeliveryResult(target, True, "Skipped — goal changed before recovery")
                else:
                    # Respect a pause or replacement that occurred during the
                    # owner/status lookup even when this began as a normal send.
                    fresh = goals.get(target.id)
                    if fresh is not None and fresh["status"] != "active":
                        return DeliveryResult(target, True, f"Skipped — goal is {fresh['status']}")
                    if goal is None and fresh is not None:
                        return DeliveryResult(target, True, "Skipped — a new goal appeared before recovery")
                    if goal is not None and (fresh is None or fresh.get("createdAt") != goal.get("createdAt")
                            or fresh.get("objective") != goal.get("objective")):
                        return DeliveryResult(target, True, "Skipped — goal changed before recovery")
                desktop.send(target.id, text, owner)
                if goal is not None:
                    try:
                        after = goals.get(target.id)
                        if after is None or after["status"] not in {"active", "complete"}:
                            raise ValueError("Goal did not remain active after continuation")
                        if any(after.get(k) != goal.get(k) for k in ("threadId", "objective", "createdAt")):
                            raise ValueError("Goal changed after continuation")
                    except Exception as exc:
                        raise DeliveryUncertain("Continuation accepted, but the resulting goal state was not confirmed; check this chat") from exc
                return DeliveryResult(target, True,
                    "Native goal activation verified; continuation accepted" if resumed else "Continuation accepted")
    except DeliveryUncertain as exc:
        return DeliveryResult(target, False, str(exc), retryable=False)
    except Exception as exc:
        return DeliveryResult(target, False, str(exc))


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
