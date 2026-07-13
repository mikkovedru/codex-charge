"""Minimal fake Codex CLI for end-to-end wrapper tests."""

from __future__ import annotations

import sys
import time

LIMIT_MSG = (
    "You've hit your usage limit. "
    "Try again in 1 second."
)


def main() -> int:
    print("fake-codex: ready", flush=True)
    if "--limit" in sys.argv:
        print(LIMIT_MSG, flush=True)
        time.sleep(0.2)
    received = ""
    try:
        while True:
            chunk = sys.stdin.readline()
            if not chunk:
                break
            received = chunk.strip()
            break
    except KeyboardInterrupt:
        return 130
    print(f"fake-codex: received {received!r}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
