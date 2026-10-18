"""Fetch Codex 5-hour / 7-day quota via app-server JSON-RPC."""

from __future__ import annotations

import json
import os
import queue
import threading
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .i18n import t


@dataclass(frozen=True)
class RateWindow:
    used_percent: float
    window_duration_mins: int
    resets_at: int  # unix seconds

    @property
    def resets_in_seconds(self) -> int:
        return max(0, self.resets_at - int(time.time()))


@dataclass(frozen=True)
class Quota:
    plan_type: str
    primary: RateWindow
    secondary: RateWindow | None
    rate_limit_reached: bool

    def exhausted_window(self) -> RateWindow | None:
        if self.primary.used_percent >= 100:
            return self.primary
        if self.secondary is not None and self.secondary.used_percent >= 100:
            return self.secondary
        return None


def looks_like_codex_cli(path: str) -> bool:
    """Heuristic: skip app-server quota calls for fake/test executables."""
    p = Path(path)
    if not p.exists():
        return False
    name = p.name.lower()
    return name in {"codex", "codex.exe"} or name.startswith("codex")


def discover_codex(explicit: str | None = None) -> str:
    if explicit:
        path = Path(explicit)
        if path.exists():
            return str(path)
        raise FileNotFoundError(f"codex executable not found: {explicit}")

    env_path = os.environ.get("CODEX_CLI_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    config = Path.home() / ".codex" / "config.toml"
    if config.exists():
        for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("CODEX_CLI_PATH"):
                _, _, value = stripped.partition("=")
                value = value.strip().strip("'\"")
                if value and Path(value).exists():
                    return value

    which = shutil.which("codex")
    if which:
        return which

    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        if local.exists():
            for exe in sorted(local.rglob("codex.exe"), reverse=True):
                return str(exe)
    else:
        for candidate in (
            Path.home() / ".local" / "bin" / "codex",
            Path.home() / ".npm-global" / "bin" / "codex",
            Path("/usr/local/bin/codex"),
        ):
            if candidate.exists():
                return str(candidate)

    raise FileNotFoundError(
        "Could not find codex executable. Install Codex CLI or pass --codex PATH."
    )


def _rpc(proc: subprocess.Popen[str], pending: dict[int, Any], method: str, params: dict | None = None, *, responses, timeout=15) -> Any:
    req_id = len(pending) + 1
    payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    pending[req_id] = None
    proc.stdin.write(json.dumps(payload) + "\n")
    proc.stdin.flush()

    deadline = time.monotonic() + timeout
    while pending[req_id] is None:
        if time.monotonic() > deadline:
            raise TimeoutError(f"Timeout waiting for RPC response: {method}")
        try:
            line = responses.get(timeout=max(.001, deadline - time.monotonic()))
        except queue.Empty as exc:
            raise TimeoutError(f"Timeout waiting for RPC response: {method}") from exc
        if not line:
            raise RuntimeError("codex app-server closed stdout unexpectedly")
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        cb_id = msg.get("id")
        if cb_id in pending:
            pending[cb_id] = msg

    msg = pending.pop(req_id)
    if msg.get("error"):
        raise RuntimeError(msg["error"].get("message", str(msg["error"])))
    return msg.get("result")


def fetch_quota(codex_path: str | None = None, timeout: float = 15) -> Quota:
    codex = discover_codex(codex_path)
    pending: dict[int, Any] = {}
    proc = subprocess.Popen(
        [codex, "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    responses = queue.Queue()
    def read_responses():
        try:
            for line in proc.stdout:
                responses.put(line)
        finally:
            responses.put(None)
    reader = threading.Thread(target=read_responses, daemon=True)
    reader.start()
    try:
        _rpc(
            proc,
            pending,
            "initialize",
            {"clientInfo": {"name": "recharge-ai-task", "version": "1.0.0"}},
            responses=responses, timeout=timeout,
        )
        result = _rpc(proc, pending, "account/rateLimits/read", responses=responses, timeout=timeout)
        if not result:
            raise RuntimeError("account/rateLimits/read returned empty result")
        limits = result.get("rateLimits")
        if not limits:
            raise RuntimeError("account/rateLimits/read missing rateLimits field")

        primary = limits.get("primary")
        if not primary:
            raise RuntimeError("account/rateLimits/read missing primary window")

        secondary_raw = limits.get("secondary")
        secondary = None
        if secondary_raw:
            secondary = RateWindow(
                used_percent=float(secondary_raw["usedPercent"]),
                window_duration_mins=int(secondary_raw["windowDurationMins"]),
                resets_at=int(secondary_raw["resetsAt"]),
            )

        return Quota(
            plan_type=limits.get("planType", "unknown"),
            primary=RateWindow(
                used_percent=float(primary["usedPercent"]),
                window_duration_mins=int(primary["windowDurationMins"]),
                resets_at=int(primary["resetsAt"]),
            ),
            secondary=secondary,
            rate_limit_reached=limits.get("rateLimitReachedType") is not None,
        )
    finally:
        proc.kill()
        proc.wait(timeout=max(1, timeout))
        reader.join(timeout=1)
        proc.stdin.close()
        proc.stdout.close()


def _window_label(duration_mins: int) -> str:
    if duration_mins <= 360:
        return t("quota.short")
    if duration_mins <= 10080:
        return t("quota.long")
    hours = duration_mins // 60
    return f"{hours}h-window"


def format_quota(quota: Quota) -> str:
    def remaining(resets_at: int) -> str:
        secs = max(0, resets_at - int(time.time()))
        hours, rem = divmod(secs, 3600)
        if hours >= 24:
            days, hours = divmod(hours, 24)
            return f"{days}d{hours}h"
        mins = rem // 60
        return f"{hours}h{mins}m"

    lines = [
        t("quota.plan", plan=quota.plan_type),
        "─" * 40,
        t(
            "quota.used",
            label=_window_label(quota.primary.window_duration_mins),
            percent=quota.primary.used_percent,
            remaining=remaining(quota.primary.resets_at),
        ),
    ]
    if quota.secondary is not None:
        lines.append(
            t(
                "quota.used",
                label=_window_label(quota.secondary.window_duration_mins),
                percent=quota.secondary.used_percent,
                remaining=remaining(quota.secondary.resets_at),
            )
        )
    exhausted = quota.exhausted_window()
    if exhausted:
        reset_dt = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.localtime(exhausted.resets_at),
        )
        lines.append(t("quota.blocked", time=reset_dt))
    return "\n".join(lines)
