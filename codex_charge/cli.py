"""Command-line entry for codex-charge."""

from __future__ import annotations

from dataclasses import replace
import argparse
import sys
import json
import subprocess
from pathlib import Path

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
    goal.add_argument("--goal", dest="goal_mode", action="store_true", help="CLI: first /goal resume; desktop: native recovery of quota-stopped goals")
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
    goal = parser.add_mutually_exclusive_group()
    goal.add_argument("--goal", action="store_true", dest="goal", help="Verify native recovery of quota-stopped goals for Linux chat IDs")
    goal.add_argument("--no-goal", action="store_false", dest="goal", help="Send only the normal signal text; allows window targets")
    parser.set_defaults(goal=None)
    parser.add_argument("--grace", type=int, default=None)
    parser.add_argument("--continue", dest="continue_prompt", default=None)
    ns = parser.parse_args(argv)

    recipients = user.targets()
    if ns.goal is not None:
        recipients = [replace(target, send_goal=ns.goal and target.kind == "thread",
                              send_prompt=target.send_prompt if ns.goal else True) for target in recipients]
    config = WatchConfig(
        codex_path=ns.codex or user.codex_path,
        continue_prompt=ns.continue_prompt or user.continue_prompt,
        goal_mode=user.goal_mode if ns.goal is None else ns.goal,
        grace_seconds=ns.grace if ns.grace is not None else user.grace_seconds,
        poll_seconds=user.poll_seconds,
        desktop_window_titles=user.window_titles(),
        desktop_targets=tuple(recipients),
    )
    return run_desktop_watch(config)


def _cmd_targets(argv):
    from .targets import discover_targets
    parser = argparse.ArgumentParser(prog="codex-charge targets", description="Discover Codex chats and windows, and select signal recipients")
    parser.add_argument("--json", action="store_true", help="Print all metadata as JSON")
    parser.add_argument("--gui", action="store_true", help="Open the multi-target picker")
    parser.add_argument("--select", action="append", metavar="ID", help="Save this target (repeat for multiple targets)")
    parser.add_argument("--clear", action="store_true", help="Clear saved selection")
    ns = parser.parse_args(argv)
    if ns.gui:
        from .gui import main as gui_main
        return gui_main([])
    inventory = discover_targets()
    config = _load_user_config()
    if ns.select is not None and ns.clear:
        parser.error("--select and --clear cannot be combined")
    if ns.select:
        selection = []
        for value in ns.select:
            matches = [t for t in inventory.targets if value in (t.id, t.key)]
            if len(matches) != 1:
                parser.error(f"Target {value!r} is unavailable or ambiguous; use its full key from --json")
            if matches[0].key not in {t.key for t in selection}:
                selection.append(matches[0])
        previous = {t.key: t for t in config.targets()}
        config.desktop_targets = [replace(t,
            send_prompt=previous[t.key].send_prompt if t.key in previous else True,
            send_goal=previous[t.key].send_goal if t.key in previous else False).to_dict() for t in selection]
        config.mode = "desktop"
        config.save()
    elif ns.clear:
        config.desktop_targets = []
        config.save()
    selected = {t.key: t for t in config.targets()}
    if ns.json:
        print(json.dumps({"targets": [dict(t.to_dict(), key=t.key, selected=t.key in selected,
                send_prompt=selected[t.key].send_prompt if t.key in selected else False,
                send_goal=selected[t.key].send_goal if t.key in selected else False) for t in inventory.targets], "warnings": inventory.warnings}, indent=2, ensure_ascii=False))
    else:
        for t in inventory.targets:
            print(f"{'[x]' if t.key in selected else '[ ]'} {t.kind:6} {t.title}\n    ID: {t.id}  PID: {t.pid or '—'}  Instance: {t.instance}\n    Task: {t.task_status}  Goal: {t.goal_status}\n    {t.deeplink or t.status}")
        for warning in inventory.warnings:
            print(f"Warning: {warning}", file=sys.stderr)
    return 0


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

    if argv and argv[0] in {"--help", "-h", "help"}:
        parser = _build_run_parser()
        parser.usage = "%(prog)s [COMMAND] [OPTIONS] [-- CODEX_ARGS...]"
        parser.formatter_class = argparse.RawDescriptionHelpFormatter
        parser.epilog = """Commands:
  gui              Open the graphical dashboard, targets and settings
  targets --gui    Open the same graphical dashboard
  targets --json   List available Codex targets as JSON
  run              Run Codex CLI with auto-continue
  watch            Watch quota and signal saved desktop recipients
  quota            Show current quota and reset times
  configure        Configure command-line settings

Use codex-charge COMMAND --help for command options.
The codex-charge-gui executable opens the GUI directly."""
        parser.print_help()
        return 0

    if argv and argv[0] == "gui":
        from .gui import main as gui_main
        return gui_main(argv[1:])

    if (
        not config_path().exists()
        and sys.stdin.isatty()
        and (not argv or argv[0] not in {"configure", "quota", "targets", "help", "-h", "--help"})
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

    if head == "targets":
        return _cmd_targets(tail)

    if head == "watch":
        return _cmd_watch(tail)

    if head == "run":
        return _cmd_run(tail)

    return _cmd_run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
