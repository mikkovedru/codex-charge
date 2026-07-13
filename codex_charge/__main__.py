"""Make codex-charge runnable as python -m codex_charge."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
