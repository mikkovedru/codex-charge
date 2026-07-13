"""System-tray UI for codex-charge (Windows + Linux)."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path

from .autostart import is_autostart_enabled, sync_autostart
from .config import AppConfig, config_dir
from .configure import run_configure
from .i18n import t
from .pty_backend import StopEvent
from .quota import discover_codex, fetch_quota, format_quota
from .watch import WatchConfig, run_desktop_watch

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Tray app requires: pip install 'codex-charge[tray]'") from exc

CREATE_NEW_CONSOLE = 0x00000010
_log = logging.getLogger("codex-charge.tray")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(config_dir() / "tray.log", encoding="utf-8")],
    )


def _make_icon(color: str) -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((8, 8, 56, 56), fill=color)
    draw.rectangle((28, 20, 36, 34), fill="white")
    draw.polygon([(24, 34), (40, 34), (32, 48)], fill="white")
    return image


def _resolve_cli_exe() -> list[str]:
    if getattr(sys, "frozen", False):
        name = "codex-charge.exe" if sys.platform == "win32" else "codex-charge"
        cli = Path(sys.executable).with_name(name)
        if cli.exists():
            return [str(cli)]
    return [sys.executable, "-m", "codex_charge.cli"]


class TrayApp:
    def __init__(self) -> None:
        self.config = AppConfig.load()
        self.config.apply_locale()
        self._icon: pystray.Icon | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._watch_stop = StopEvent()
        self._watch_thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _set_status(self, running: bool) -> None:
        if self._icon is None:
            return
        self._icon.icon = _make_icon("#22c55e" if running else "#6b7280")
        title = t("app.status.running") if running else t("app.status.idle")
        self._icon.title = f"{t('app.name')} - {title}"

    def _is_running(self) -> bool:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return True
            if self._watch_thread is not None and self._watch_thread.is_alive():
                return True
        return False

    def _watch_process(self) -> None:
        proc = self._proc
        if proc is None:
            return
        code = proc.wait()
        _log.info("codex-charge exited code=%s", code)
        with self._lock:
            if self._proc is proc:
                self._proc = None
        self._set_status(self._is_running())

    def _start_cli(self, goal: bool) -> None:
        if self._is_running():
            return

        args = [*_resolve_cli_exe(), "run"]
        if goal:
            args.append("--goal")
        if self.config.grace_seconds != 60:
            args.extend(["--grace", str(self.config.grace_seconds)])
        if self.config.continue_prompt != "继续":
            args.extend(["--continue", self.config.continue_prompt])
        if self.config.codex_path:
            args.extend(["--codex", self.config.codex_path])
        if self.config.codex_args:
            args.extend(["--", *self.config.codex_args])

        creationflags = CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        with self._lock:
            self._proc = subprocess.Popen(args, creationflags=creationflags)
        self._set_status(True)
        threading.Thread(target=self._watch_process, daemon=True).start()

    def start_goal(self, _icon=None, _item=None) -> None:
        self._start_cli(goal=True)

    def start_normal(self, _icon=None, _item=None) -> None:
        self._start_cli(goal=False)

    def start_desktop(self, _icon=None, _item=None) -> None:
        if self._is_running():
            return
        self._watch_stop = StopEvent()
        cfg = WatchConfig(
            codex_path=self.config.codex_path,
            continue_prompt=self.config.continue_prompt,
            goal_mode=self.config.goal_mode,
            grace_seconds=self.config.grace_seconds,
            poll_seconds=self.config.poll_seconds,
            desktop_window_titles=self.config.window_titles(),
        )

        def runner() -> None:
            try:
                run_desktop_watch(cfg, self._watch_stop)
            finally:
                self._set_status(False)

        self._watch_thread = threading.Thread(target=runner, daemon=True)
        self._watch_thread.start()
        self._set_status(True)

    def stop_service(self, _icon=None, _item=None) -> None:
        self._watch_stop.set()
        with self._lock:
            proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        self._set_status(False)

    def show_quota(self, _icon=None, _item=None) -> None:
        def worker() -> None:
            try:
                text = format_quota(fetch_quota(discover_codex(self.config.codex_path)))
            except Exception as exc:
                text = t("tray.quota_unavailable", error=exc)
            if self._icon is not None:
                self._icon.notify(text, t("cli.quota_title"))

        threading.Thread(target=worker, daemon=True).start()

    def open_configure(self, _icon=None, _item=None) -> None:
        def worker() -> None:
            run_configure()
            self.config = AppConfig.load()
            self.config.apply_locale()
            if self._icon is not None:
                self._icon.menu = self._build_menu()
                self._icon.update_menu()

        threading.Thread(target=worker, daemon=True).start()

    def toggle_autostart(self, _icon=None, item=None) -> None:
        self.config.autostart = not self.config.autostart
        sync_autostart(self.config.autostart)
        if item is not None:
            item.checked = self.config.autostart
        self.config.save()

    def exit_app(self, icon: pystray.Icon, _item=None) -> None:
        self.stop_service()
        icon.stop()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                t("tray.start_goal"),
                self.start_goal,
                enabled=lambda _: not self._is_running(),
            ),
            pystray.MenuItem(
                t("tray.start_normal"),
                self.start_normal,
                enabled=lambda _: not self._is_running(),
            ),
            pystray.MenuItem(
                t("tray.start_desktop"),
                self.start_desktop,
                enabled=lambda _: not self._is_running(),
            ),
            pystray.MenuItem(
                t("tray.stop"),
                self.stop_service,
                enabled=lambda _: self._is_running(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.show_quota"), self.show_quota),
            pystray.MenuItem(t("tray.configure"), self.open_configure),
            pystray.MenuItem(
                t("tray.autostart"),
                self.toggle_autostart,
                checked=lambda _: self.config.autostart,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.exit"), self.exit_app),
        )

    def run(self) -> None:
        _setup_logging()
        if self.config.autostart and not is_autostart_enabled():
            sync_autostart(True)
        self._icon = pystray.Icon(
            "codex-charge",
            _make_icon("#6b7280"),
            t("app.name"),
            menu=self._build_menu(),
        )
        _log.info("tray started locale=%s mode=%s", self.config.language, self.config.mode)
        self._icon.run()


def main() -> int:
    if sys.platform not in {"win32", "linux"}:
        sys.stderr.write("codex-charge tray supports Windows and Linux only.\n")
        return 1
    TrayApp().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
