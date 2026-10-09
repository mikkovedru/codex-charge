"""Native persisted goal control, without loading or forking desktop chats."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

from .codex_ipc import DeliveryUncertain
from .targets import AppServer


class NativeGoals:
    """Use an existing same-user daemon sharing the selected Codex profile.

    Goal get/set operate on shared persisted state even for unloaded threads.
    No thread/start, thread/resume, objective or budget override is ever sent.
    Actual continuation is routed separately to the desktop's current owner.
    """
    def __init__(self, home):
        if not home:
            raise RuntimeError("Native goal control needs a chat with a Codex profile")
        self.home = Path(home).resolve()
        self.server = None

    def __enter__(self):
        if not sys.platform.startswith("linux"):
            raise RuntimeError("Native goal recovery currently supports Linux chat-ID targets")
        directory = Path(f"/tmp/codex-daemon-{os.getuid()}")
        for endpoint in sorted(directory.glob("*")):
            try:
                info = endpoint.stat()
                if info.st_uid != os.getuid() or not stat.S_ISSOCK(info.st_mode):
                    continue
                server = AppServer(str(endpoint))
                server.__enter__()
            except Exception:
                continue
            if server.home.resolve() == self.home:
                self.server = server
                return self
            server.__exit__()
        raise RuntimeError("Native goal control unavailable for this profile; start its Codex daemon and retry")

    def __exit__(self, *args):
        self.server.__exit__(*args)

    def get(self, thread_id):
        result = self.server.call("thread/goal/get", {"threadId": thread_id})
        if not isinstance(result, dict) or "goal" not in result:
            raise ValueError("Codex did not return a goal state")
        goal = result["goal"]
        if goal is not None and (not isinstance(goal, dict) or goal.get("threadId") != thread_id
                or goal.get("status") not in {"active", "paused", "blocked", "usageLimited", "budgetLimited", "complete"}):
            raise ValueError("Codex returned an invalid goal identity or status")
        return goal

    def resume(self, thread_id, expected, *, allow_paused=False):
        # Recheck after desktop owner discovery, which can take time. A goal
        # edited, cleared or replaced in the meantime is left alone. Only an
        # explicit manual action may resume a goal already observed as paused.
        current = self.get(thread_id)
        allowed = {"usageLimited", "paused"} if allow_paused else {"usageLimited"}
        if (current is None or current.get("status") not in allowed
                or current.get("status") != expected.get("status")):
            return False
        identity = ("threadId", "objective", "createdAt", "tokenBudget")
        if any(current.get(k) != expected.get(k) for k in identity):
            return False
        try:
            result = self.server.call("thread/goal/set", {"threadId": thread_id, "status": "active"})
        except RuntimeError as exc:
            if not any(word in str(exc).lower() for word in ("timeout", "disconnected", "closed")):
                raise
            raise DeliveryUncertain("Native goal resume was not confirmed; check the goal before retrying") from exc
        except Exception as exc:
            raise DeliveryUncertain("Native goal resume was not confirmed; check the goal before retrying") from exc
        try:
            acknowledged = result["goal"]
            verified = self.get(thread_id)
            for goal in (acknowledged, verified):
                if not isinstance(goal, dict) or goal.get("status") != "active":
                    raise ValueError("Goal did not become active")
                if any(goal.get(k) != current.get(k) for k in identity):
                    raise ValueError("Goal identity or budget changed")
                if any(goal.get(k) != current.get(k) for k in ("tokensUsed", "timeUsedSeconds")):
                    raise ValueError("Goal accounting changed during resume")
        except Exception as exc:
            raise DeliveryUncertain("Native goal activation could not be verified; no continuation was sent") from exc
        return True


def quota_stopped_targets(targets, stop=None):
    """Find startup recovery candidates; failures are explicit, never no-goal."""
    from contextlib import ExitStack
    candidates, errors = set(), []
    with ExitStack() as stack:
        profiles = {}
        for target in targets:
            if stop is not None and stop.is_set():
                break
            if target.kind != "thread":
                continue
            try:
                if target.instance not in profiles:
                    try:
                        profiles[target.instance] = stack.enter_context(NativeGoals(target.instance))
                    except Exception as exc:
                        profiles[target.instance] = str(exc)
                profile = profiles[target.instance]
                if isinstance(profile, str):
                    raise RuntimeError(profile)
                goal = profile.get(target.id)
                if goal is not None and goal["status"] == "usageLimited":
                    candidates.add(target.key)
            except Exception as exc:
                errors.append(f"{target.title} [{target.id}]: goal recovery check failed: {exc}")
    return candidates, errors
