"""Make recharge-ai-task runnable as python -m recharge_ai_task."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
