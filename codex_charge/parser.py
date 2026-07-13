"""Parse Codex usage-limit messages from terminal output."""

from __future__ import annotations

import datetime as dt
import re
import time

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

LIMIT_MARKERS = (
    "you've hit your usage limit",
    "you’ve hit your usage limit",
    "usage limit",
    "rate limit",
    "限额",
    "usage limit exceeded",
    "rate_limit_reached",
)

LIMIT_AT_RE = re.compile(
    r"(?:you[’']ve hit your usage limit|usage limit|rate limit|限额).*?"
    r"(?:try again|重试|恢复)\s+(?:at|在)\s+([^\r\n.]+)",
    re.IGNORECASE | re.DOTALL,
)

LIMIT_IN_RE = re.compile(
    r"(?:you[’']ve hit your usage limit|usage limit|rate limit|限额).*?"
    r"(?:try again|重试|恢复)\s+(?:in|还有|约)\s+([^\r\n.]+)",
    re.IGNORECASE | re.DOTALL,
)

LIMIT_IN_CN_RE = re.compile(
    r"(?:usage limit|rate limit|限额).*?(?:还有|约)\s*([0-9][^\r\n.]*?(?:小时|分钟|分|秒|天|周)[^\r\n.]*)",
    re.IGNORECASE | re.DOTALL,
)

DURATION_RE = re.compile(
    r"(\d+)\s*"
    r"(weeks?|w|days?|d|hours?|hrs?|hr|h|minutes?|mins?|min|m|seconds?|secs?|sec|s|小时|分钟|分|秒|天|周)",
    re.IGNORECASE,
)

ORDINAL_RE = re.compile(r"(?<=\d)(st|nd|rd|th)\b", re.IGNORECASE)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)


def parse_duration(text: str) -> dt.timedelta:
    total = dt.timedelta()
    found = False
    for amount, unit in DURATION_RE.findall(text):
        found = True
        n = int(amount)
        unit = unit.lower()
        if unit in {"w", "week", "weeks", "周"}:
            total += dt.timedelta(weeks=n)
        elif unit in {"d", "day", "days", "天"}:
            total += dt.timedelta(days=n)
        elif unit in {"h", "hr", "hrs", "hour", "hours", "小时"}:
            total += dt.timedelta(hours=n)
        elif unit in {"m", "min", "mins", "minute", "minutes", "分钟", "分"}:
            total += dt.timedelta(minutes=n)
        elif unit in {"s", "sec", "secs", "second", "seconds", "秒"}:
            total += dt.timedelta(seconds=n)
    if not found:
        raise ValueError(f"could not parse duration: {text!r}")
    return total


def parse_absolute_time(text: str, now: dt.datetime | None = None) -> dt.datetime:
    now = now or dt.datetime.now().astimezone()
    cleaned = strip_ansi(text).strip().rstrip(" .)")
    cleaned = ORDINAL_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)

    formats = [
        "%I:%M %p",
        "%I %p",
        "%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
    ]

    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=now.year)
        if "%b" not in fmt and "%B" not in fmt and "%Y-%m-%d" not in fmt and "%Y/%m/%d" not in fmt:
            parsed = parsed.replace(month=now.month, day=now.day)
        parsed = parsed.replace(tzinfo=now.tzinfo)
        if "%b" not in fmt and "%B" not in fmt and "%Y-%m-%d" not in fmt and "%Y/%m/%d" not in fmt:
            if parsed <= now:
                parsed += dt.timedelta(days=1)
        return parsed

    raise ValueError(f"could not parse absolute reset time: {text!r}")


class LimitWatcher:
    def __init__(self) -> None:
        self._buf = ""

    def feed(self, chunk: str) -> tuple[int, str] | None:
        """Return (unix_reset_at, raw_match) when a limit message is detected."""
        self._buf = (self._buf + strip_ansi(chunk))[-20000:]
        lowered = self._buf.lower()
        if not any(marker in lowered for marker in LIMIT_MARKERS):
            return None

        now = dt.datetime.now().astimezone()

        match = LIMIT_AT_RE.search(self._buf)
        if match:
            raw = match.group(1).strip().rstrip(" .)")
            reset_at = int(parse_absolute_time(raw, now).timestamp())
            return reset_at, raw

        match = LIMIT_IN_RE.search(self._buf)
        if match:
            raw = match.group(1).strip().rstrip(" .)")
            reset_at = int((now + parse_duration(raw)).timestamp())
            return reset_at, raw

        match = LIMIT_IN_CN_RE.search(self._buf)
        if match:
            raw = match.group(1).strip().rstrip(" .)")
            reset_at = int((now + parse_duration(raw)).timestamp())
            return reset_at, raw

        return None

    def reset(self) -> None:
        self._buf = ""


def resolve_reset_at(
    parsed_reset_at: int | None,
    quota_resets_at: int | None,
    grace_seconds: int,
) -> tuple[int, str]:
    """Pick the best reset timestamp and return (wake_at, source)."""
    now = int(time.time())
    candidates: list[tuple[int, str]] = []

    if parsed_reset_at is not None:
        candidates.append((parsed_reset_at, "terminal message"))
    if quota_resets_at is not None:
        candidates.append((quota_resets_at, "quota API"))

    if not candidates:
        raise RuntimeError("limit detected but no reset time could be resolved")

    reset_at, source = max(candidates, key=lambda item: item[0])
    wake_at = max(now, reset_at) + grace_seconds
    return wake_at, source
