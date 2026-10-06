"""Command-line entry for codex-charge."""

from __future__ import annotations

import argparse
import sys

from .config import AppConfig, config_path
from .configure import run_configure
from .i18n import init_locale_from_env, t
from .quota import discover_codex, fetch_quota, format_quota
from .watch import WatchConfig, run_desktop_watch
from .wrapper import WrapperConfig, run_wrapper


def _build_run_parser(prog: str = "codex-charge") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description=t("cli.description"),
    )
    parser.add_argument("--codex", metavar="PATH", help="Path to codex executable")
    goal = parser.add_mutually_exclusive_group()
    goal.add_argument("--goal", dest="goal_mode", action="store_true", help="First auto-continue sends /goal resume")
    goal.add_argument("--no-goal", dest="goal_mode", action="store_false", help="Use the normal continue prompt")
    parser.set_defaults(goal_mode=None)
    parser.add_argument(
        "--continue",
        dest="continue_prompt",
        default=None,
        metavar="TEXT",
        help='Text to send after reset (default from config or "继续")',
    )
    parser.add_argument("--grace", type=int, default=None, metavar="SECONDS")
    parser.add_argument("--enter-presses", type=int, default=1, metavar="N")
    parser.add_argument(
        "codex_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed to codex (prefix with -- if needed)",
    )
    return parser


def _normalize_codex_args(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def _load_user_config() -> AppConfig:
    config = AppConfig.load()
    config.apply_locale()
    return config


def _cmd_quota(codex_path: str | None) -> int:
    try:
        codex = discover_codex(codex_path)
        quota = fetch_quota(codex)
    except Exception as exc:
        sys.stderr.write(f"codex-charge: {exc}\n")
        return 1
    print(format_quota(quota))
    return 0


def _cmd_configure(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="codex-charge configure")
    parser.add_argument("--lang", choices=["en", "zh"])
    parser.add_argument("--mode", choices=["cli", "desktop"])
    parser.add_argument("--goal", action="store_true")
    parser.add_argument("--no-goal", action="store_true")
    parser.add_argument("--grace", type=int)
    parser.add_argument("--continue", dest="continue_prompt")
    ns = parser.parse_args(argv)

    overrides = {}
    if ns.lang:
        overrides["language"] = ns.lang
    if ns.mode:
        overrides["mode"] = ns.mode
    if ns.goal:
        overrides["goal_mode"] = True
    if ns.no_goal:
        overrides["goal_mode"] = False
    if ns.grace is not None:
        overrides["grace_seconds"] = ns.grace
    if ns.continue_prompt:
        overrides["continue_prompt"] = ns.continue_prompt

    run_configure(non_interactive=overrides or None)
    return 0


def _cmd_watch(argv: list[str]) -> int:
    user = _load_user_config()
    parser = argparse.ArgumentParser(prog="codex-charge watch", description=t("help.desktop_mode"))
    parser.add_argument("--desktop", action="store_true", default=True)
    parser.add_argument("--codex", metavar="PATH")
    parser.add_argument("--goal", action="store_true", default=None)
    parser.add_argument("--grace", type=int, default=None)
    parser.add_argument("--continue", dest="continue_prompt", default=None)
    ns = parser.parse_args(argv)

    config = WatchConfig(
        codex_path=ns.codex or user.codex_path,
        continue_prompt=ns.continue_prompt or user.continue_prompt,
        goal_mode=user.goal_mode if ns.goal is None else ns.goal,
        grace_seconds=ns.grace if ns.grace is not None else user.grace_seconds,
        poll_seconds=user.poll_seconds,
        desktop_window_titles=user.window_titles(),
    )
    return run_desktop_watch(config)


def _cmd_run(argv: list[str]) -> int:
    user = _load_user_config()
    parser = _build_run_parser("codex-charge run")
    ns = parser.parse_args(argv)

    config = WrapperConfig(
        codex_path=ns.codex or user.codex_path,
        codex_args=_normalize_codex_args(ns.codex_args) or user.codex_args,
        continue_prompt=ns.continue_prompt or user.continue_prompt,
        goal_mode=user.goal_mode if ns.goal_mode is None else ns.goal_mode,
        grace_seconds=ns.grace if ns.grace is not None else user.grace_seconds,
        enter_presses=ns.enter_presses,
    )
    try:
        return run_wrapper(config)
    except FileNotFoundError as exc:
        sys.stderr.write(f"codex-charge: {exc}\n")
        return 1


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    init_locale_from_env()

    if (
        not config_path().exists()
        and sys.stdin.isatty()
        and (not argv or argv[0] not in {"configure", "quota", "help", "-h", "--help"})
    ):
        run_configure()

    user = _load_user_config()

    if not argv:
        if user.mode == "desktop":
            return _cmd_watch([])
        return _cmd_run([])

    head = argv[0]
    tail = argv[1:]

    if head == "quota":
        parser = argparse.ArgumentParser(prog="codex-charge quota")
        parser.add_argument("--codex", metavar="PATH")
        ns = parser.parse_args(tail)
        return _cmd_quota(ns.codex)

    if head == "configure":
        return _cmd_configure(tail)

    if head == "watch":
        return _cmd_watch(tail)

    if head == "run":
        return _cmd_run(tail)

    return _cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
