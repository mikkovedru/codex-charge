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

_log = logging.getLogger("recharge-ai-task.delivery")


@dataclass(frozen=True)
class DeliveryResult:
    target: Target
    success: bool
    detail: str
    retryable: bool = True
    skipped: bool = False


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


def recover_target(target, text, *, manual=False, send_prompt=True, require_goal=False, enter_presses=1, key_delay=.12):
    """Activate quota-stopped goals, then continue in the desktop owner.

    Explicit manual recovery may also resume paused goals. Automatic recovery
    respects pauses. Window identities cannot identify an individual goal.
    """
    if target.kind != "thread":
        return DeliveryResult(target, False,
            "Native goal recovery requires a chat ID; select a chat or turn off Goal for this recipient", retryable=False)
    from .goal_control import NativeGoals
    try:
        if not target.instance or Path(target.endpoint).resolve() != (Path(target.instance) / "ipc/ipc.sock").resolve():
            raise ValueError("Desktop endpoint does not match the selected Codex profile")
        if send_prompt and not text.strip():
            raise ValueError("Signal text cannot be empty")
        with NativeGoals(target.instance) as goals:
            goal = goals.get(target.id)
            if require_goal and goal is None:
                return DeliveryResult(target, True, "Skipped — chat has no goal", skipped=True)
            protected = {"blocked", "budgetLimited", "complete"}
            if not manual:
                protected.add("paused")
            if goal is not None and goal["status"] in protected:
                return DeliveryResult(target, True, f"Skipped — goal is {goal['status']}", skipped=True)
            if not target.endpoint:
                raise RuntimeError("Desktop routing unavailable; open Codex and refresh targets")
            with DesktopIPC(target.endpoint, timeout=5) as desktop:
                owner = _owner_for_delivery(desktop, target)
                snapshot = desktop.status_snapshot(target.id, owner)
                task = snapshot.get("task")
                if not isinstance(task, dict) or task.get("type") not in {"active", "idle", "systemError", "notLoaded"}:
                    raise RuntimeError("Current task status is unavailable; no signal sent")
                if task["type"] == "active" and not manual:
                    return DeliveryResult(target, True, "Skipped — task is already running or waiting for input", skipped=True)
                if goal is None and snapshot.get("goal") == "complete":
                    return DeliveryResult(target, True, "Skipped — goal is complete", skipped=True)
                resumed = False
                if not manual and snapshot.get("goal") == "paused":
                    return DeliveryResult(target, True, "Skipped — desktop goal is paused", skipped=True)
                if goal is not None and (goal["status"] in {"usageLimited", "paused"}
                        or manual and snapshot.get("goal") in {"paused", "usageLimited"}):
                    resumed = goals.resume(target.id, goal, allow_paused=manual, allow_active=manual,
                        activate=lambda: desktop.resume_goal(target, goal))
                    if not resumed:
                        return DeliveryResult(target, True, "Skipped — goal changed before recovery", skipped=True)
                else:
                    # Respect a pause or replacement that occurred during the
                    # owner/status lookup even when this began as a normal send.
                    fresh = goals.get(target.id)
                    if fresh is not None and fresh["status"] != "active":
                        return DeliveryResult(target, True, f"Skipped — goal is {fresh['status']}", skipped=True)
                    if goal is None and fresh is not None:
                        return DeliveryResult(target, True, "Skipped — a new goal appeared before recovery", skipped=True)
                    if goal is not None and (fresh is None or fresh.get("createdAt") != goal.get("createdAt")
                            or fresh.get("objective") != goal.get("objective")):
                        return DeliveryResult(target, True, "Skipped — goal changed before recovery", skipped=True)
                if goal is not None:
                    snapshot = desktop.status_snapshot(target.id, owner)
                    if snapshot.get("goal") not in {"active", "complete"}:
                        raise DeliveryUncertain("Native Goal activation was not visible in the desktop; no prompt sent")
                    task = snapshot.get("task")
                    if not isinstance(task, dict) or task.get("type") not in {"active", "idle", "systemError"}:
                        raise DeliveryUncertain("Native Goal was activated, but its task state could not be verified; no prompt sent")
                if send_prompt:
                    if goal is not None and task["type"] == "active":
                        desktop.steer(target.id, text, owner)
                    else:
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
                if not send_prompt:
                    return DeliveryResult(target, True,
                        "Native goal activation verified; current turn continues, no prompt sent" if task["type"] == "active" else
                        "Native goal activation verified in the desktop; no prompt sent")
                return DeliveryResult(target, True,
                    "Native goal activation verified; continuation accepted" if resumed else
                    "No goal; continuation accepted" if goal is None else "Goal already active; continuation accepted")
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


def send_signals(targets, text, *, manual=False, enter_presses=1, key_delay=.12):
    """Honor each recipient's actions. Goal activation precedes its prompt."""
    results, seen = [], set()
    for target in targets:
        if target.key in seen:
            continue
        seen.add(target.key)
        prompt, goal = target.signal_actions()
        if not prompt and not goal:
            result = DeliveryResult(target, True, "Skipped — no signals selected", skipped=True)
        elif prompt and not text.strip():
            result = DeliveryResult(target, False, "Prompt message cannot be empty", retryable=False)
        elif goal:
            result = recover_target(target, text, manual=manual, send_prompt=prompt,
                require_goal=True, enter_presses=enter_presses, key_delay=key_delay)
            if result.skipped and prompt:
                # Independent Prompt selection still applies if no resumable
                # goal exists. A failed/unconfirmed goal action never falls through.
                sent = deliver_targets([target], text, enter_presses=enter_presses, key_delay=key_delay)[0]
                result = DeliveryResult(target, sent.success,
                    f"Goal: {result.detail}; Prompt: {sent.detail}", sent.retryable, sent.skipped)
        else:
            result = deliver_targets([target], text, enter_presses=enter_presses, key_delay=key_delay)[0]
        results.append(result)
    return results
