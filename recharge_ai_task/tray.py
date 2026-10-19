"""System-tray UI for recharge-ai-task (Windows + Linux)."""

from __future__ import annotations

import errno
import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from .autostart import is_autostart_enabled, sync_autostart, set_autostart
from .config import AppConfig, config_dir
from .i18n import t
from .pty_backend import StopEvent
from .quota import discover_codex, fetch_quota, format_quota
from .watch import WatchConfig, WatchState, run_desktop_watch

from .tray_backend import prepare_backend, icon_class
from .branding import tray_image

prepare_backend()

try:
    import pystray
    from PIL import Image
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Tray app requires: pip install 'recharge-ai-task[tray]'") from exc

CREATE_NEW_CONSOLE = 0x00000010
_log = logging.getLogger("recharge-ai-task.tray")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.FileHandler(config_dir() / "tray.log", encoding="utf-8")],
    )


def _resolve_cli_exe() -> list[str]:
    if getattr(sys, "frozen", False):
        name = "recharge-ai-task.exe" if sys.platform == "win32" else "recharge-ai-task"
        cli = Path(sys.executable).with_name(name)
        if cli.exists():
            return [str(cli)]
        raise FileNotFoundError(f"Missing companion CLI executable: {cli}")
    return [sys.executable, "-m", "recharge_ai_task.cli"]


def _console_command(args):
    if sys.platform == "win32":
        return args
    for name, flags in (("x-terminal-emulator", ["-e"]), ("gnome-terminal", ["--wait", "--"]), ("konsole", ["-e"]), ("xterm", ["-e"])):
        path = shutil.which(name)
        if path:
            return [path, *flags, *args]
    raise FileNotFoundError("Install a terminal emulator to open Codex or Settings")


class TrayApp:
    def __init__(self, *, launched_at_startup=False) -> None:
        self.config = AppConfig.load()
        self.launched_at_startup = launched_at_startup
        self._watch_error = ""
        self._watch_settings = None
        self._watch_state = None
        self._watch_requested = False
        self._restart_pending = False
        self._restart_timer = None
        self._restart_revision = 0
        self._queued_watch_settings = None
        self._watch_pause_reason = ""
        self._icon: pystray.Icon | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._watch_stop = StopEvent()
        self._watch_thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._picker = None

    def _set_status(self, running: bool) -> None:
        if self._icon is None:
            return
        self._icon.icon = tray_image(running=running)
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
        _log.info("recharge-ai-task exited code=%s", code)
        with self._lock:
            if self._proc is proc:
                self._proc = None
        self._set_status(self._is_running())

    def _start_cli(self, goal: bool) -> None:
        with self._lock:
            self._start_cli_locked(goal)

    def _start_cli_locked(self, goal: bool) -> None:
        if self._is_running():
            return

        self._cancel_restart_locked()
        args = [*_resolve_cli_exe(), "run"]
        args.append("--goal" if goal else "--no-goal")
        if self.config.grace_seconds != 60:
            args.extend(["--grace", str(self.config.grace_seconds)])
        if self.config.continue_prompt != "Continue":
            args.extend(["--continue", self.config.continue_prompt])
        if self.config.codex_path:
            args.extend(["--codex", self.config.codex_path])
        if self.config.codex_args:
            args.extend(["--", *self.config.codex_args])

        creationflags = CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        with self._lock:
            self._proc = subprocess.Popen(_console_command(args), creationflags=creationflags)
        self._set_status(True)
        threading.Thread(target=self._watch_process, daemon=True).start()

    def start_goal(self, _icon=None, _item=None) -> None:
        self._start_cli(goal=True)

    def start_normal(self, _icon=None, _item=None) -> None:
        self._start_cli(goal=False)

    def start_desktop(self, _icon=None, _item=None) -> None:
        with self._lock:
            self._start_desktop_locked()

    def _start_desktop_locked(self, *, restarting=False) -> None:
        if self._is_running():
            return
        self.config = AppConfig.load()
        if not self.config.targets():
            self.open_targets()
            return
        if any(t.signal_actions()[0] for t in self.config.targets()) and not self.config.continue_prompt.strip():
            raise RuntimeError("Enter a prompt message for recipients with Prompt enabled")
        if not restarting or self._watch_state is None:
            self._watch_state = WatchState()
        self._watch_requested = True
        self._watch_pause_reason = ""
        self._watch_stop = StopEvent()
        cfg = WatchConfig(
            codex_path=self.config.codex_path,
            continue_prompt=self.config.continue_prompt,
            goal_mode=self.config.goal_mode,
            grace_seconds=self.config.grace_seconds,
            poll_seconds=self.config.poll_seconds,
            desktop_window_titles=self.config.window_titles(),
            desktop_targets=tuple(self.config.targets()),
            state=self._watch_state,
        )

        self._watch_error = ""
        from .tray_control import watch_settings
        self._watch_settings = watch_settings(self.config)
        def runner() -> None:
            try:
                code = run_desktop_watch(cfg, self._watch_stop)
                if code:
                    self._watch_error = f"Desktop watch exited with code {code}"
            except Exception as exc:
                self._watch_error = str(exc)
                _log.exception("Desktop watch failed")
            finally:
                with self._lock:
                    self._watch_thread = None
                    if not self._restart_pending:
                        self._watch_requested = False
                self._set_status(False)

        self._watch_thread = threading.Thread(target=runner, daemon=True)
        self._watch_thread.start()
        self._set_status(self._is_running())

    def _cancel_restart_locked(self):
        self._restart_revision += 1
        if self._restart_timer is not None:
            self._restart_timer.cancel()
            self._restart_timer = None
        self._restart_pending = False
        self._watch_requested = False
        self._watch_pause_reason = ""

    def _sync_saved_watch(self, config):
        from .tray_control import watch_settings
        settings = watch_settings(config)
        with self._lock:
            if not self._watch_requested:
                return
            if settings == self._watch_settings and not self._restart_pending and not self._watch_pause_reason:
                return
            if settings == self._queued_watch_settings and (self._restart_pending or self._watch_pause_reason):
                return
            self._restart_revision += 1
            revision = self._restart_revision
            if self._restart_timer is not None:
                self._restart_timer.cancel()
            self._queued_watch_settings = settings
            self._watch_pause_reason = ""
            self._restart_pending = True
            # Coalesce checkbox changes and prompt keystrokes. A stopped watch
            # never starts merely because settings were saved.
            self._restart_timer = threading.Timer(.6, self._restart_watch, args=(revision,))
            self._restart_timer.daemon = True
            self._restart_timer.start()

    def _restart_watch(self, revision):
        with self._lock:
            if revision != self._restart_revision or not self._watch_requested:
                return
            previous = self._watch_thread
            self._watch_stop.set()
        # Join outside the lock: the old worker needs it during cleanup. Even a
        # slow delivery must finish before a replacement can send anything.
        if previous is not None:
            previous.join()
        with self._lock:
            if revision != self._restart_revision or not self._watch_requested:
                return
            try:
                config = AppConfig.load()
                targets = config.targets()
                if not targets:
                    self._watch_pause_reason = "Choose at least one recipient; watch will resume automatically."
                elif any(t.signal_actions()[0] for t in targets) and not config.continue_prompt.strip():
                    self._watch_pause_reason = "Enter a prompt message; watch will resume automatically."
                else:
                    discover_codex(config.codex_path)
                    self._start_desktop_locked(restarting=True)
            except Exception as exc:
                self._watch_error = f"Could not apply saved watch settings: {exc}"
                self._watch_pause_reason = self._watch_error
                _log.exception("Automatic watch restart failed")
            finally:
                self._restart_pending = False
                self._restart_timer = None

    def stop_service(self, _icon=None, _item=None) -> None:
        with self._lock:
            self._cancel_restart_locked()
            self._watch_stop.set()
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
        if sys.platform == "linux":
            self.open_targets(settings=True)
            return
        def worker() -> None:
            flags = CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            subprocess.run(_console_command([*_resolve_cli_exe(), "configure"]), creationflags=flags, check=True)
            self.config = AppConfig.load()
            if self._icon is not None:
                self._icon.menu = self._build_menu()
                self._icon.update_menu()

        threading.Thread(target=worker, daemon=True).start()

    def toggle_targets(self, _icon=None, _item=None):
        self.open_targets(toggle=True)

    def open_targets(self, _icon=None, _item=None, *, settings=False, toggle=False):
        if sys.platform != "linux":
            return
        from gi.repository import GLib
        def show():
            from .target_ui import TargetPicker
            if toggle and self._picker is not None and not self._picker.closed and self._picker.get_visible():
                self._picker.hide()
                return False
            if self._picker is None or self._picker.closed:
                self._picker = TargetPicker(quit_on_close=False)
                self._picker.show_all()
            self._picker.show()
            self._picker.present()
            if settings:
                self._picker.settings()
            return False
        GLib.idle_add(show)

    def toggle_autostart(self, _icon=None, item=None) -> None:
        self.config = AppConfig.load()
        self.config.autostart = not is_autostart_enabled()
        sync_autostart(self.config.autostart)
        self.config.save()
        if self._icon is not None:
            self._icon.update_menu()

    def exit_app(self, icon: pystray.Icon, _item=None) -> None:
        self.stop_service()
        icon.stop()

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem("Toggle dashboard", self.toggle_targets,
                             default=sys.platform == "linux", visible=False),
            pystray.MenuItem("Open Recharge AI-task…", self.open_targets, visible=sys.platform == "linux"),
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
                enabled=lambda _: self._is_running() or self._watch_requested,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.show_quota"), self.show_quota),
            pystray.MenuItem(t("tray.configure"), self.open_configure),
            pystray.MenuItem(
                t("tray.autostart"),
                self.toggle_autostart,
                checked=lambda _: is_autostart_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(t("tray.exit"), self.exit_app),
        )

    def control(self, command):
        if command == "start-watch":
            if self._proc is not None and self._proc.poll() is None:
                raise RuntimeError("Stop the CLI service before starting Desktop watch")
            config = AppConfig.load()
            if not config.targets():
                raise RuntimeError("Save at least one target before starting Desktop watch")
            discover_codex(config.codex_path)
            self.start_desktop()
        elif command == "stop-watch":
            with self._lock:
                self._cancel_restart_locked()
                self._watch_stop.set()
        elif command == "reload":
            self.config = AppConfig.load()
            if self._icon:
                self._icon.menu = self._build_menu()
                self._icon.update_menu()
        elif command in {"open-gui", "open-settings"}:
            self.open_targets(settings=command == "open-settings")
        elif command != "status":
            raise ValueError("Unknown tray command")
        # Polling also applies settings saved by another GUI or CLI process.
        try:
            self._sync_saved_watch(AppConfig.load())
        except Exception as exc:
            self._watch_error = f"Could not read saved watch settings: {exc}"
        thread = self._watch_thread
        alive = thread is not None and thread.is_alive()
        return {"pid": os.getpid(), "desktop_watch": alive, "native_goal_recovery": True, "gui_control": True, "per_target_signals": True, "auto_watch_restart": True,
                "restarting": self._restart_pending, "watch_requested": self._watch_requested,
                "watch_pause_reason": self._watch_pause_reason,
                "stopping": alive and self._watch_stop.is_set(),
                "cli_running": self._proc is not None and self._proc.poll() is None,
                "launched_at_startup": self.launched_at_startup,
                "autostart": is_autostart_enabled(), "watch_error": self._watch_error,
                "watch_progress": dict(self._watch_state.progress) if alive and self._watch_state else None,
                "watch_settings": self._watch_settings if alive else None}

    def run(self, *, show_gui=False, settings=False) -> None:
        _setup_logging()
        controller = None
        if sys.platform == "linux":
            from .tray_control import ControlServer
            controller = ControlServer(self.control)
            controller.start()
        try:
            if is_autostart_enabled():
                set_autostart(True)  # Update enabled entries with the startup marker.
            self._icon = icon_class(pystray.Icon)(
                "recharge-ai-task",
                tray_image(),
                t("app.name"),
                menu=self._build_menu(),
            )
            _log.info("tray started mode=%s backend=%s", self.config.mode, type(self._icon).__name__)
            if show_gui:
                self.open_targets(settings=settings)
            self._icon.run()
        finally:
            self.stop_service()
            if self._picker is not None and not self._picker.closed:
                self._picker.destroy()
            if controller:
                controller.close()


def main() -> int:
    if sys.argv[1:] == ["--resume-goal-ui"]:
        from .desktop_goal_ui import main as goal_ui
        return goal_ui()
    if sys.platform not in {"win32", "linux"}:
        sys.stderr.write("recharge-ai-task tray supports Windows and Linux only.\n")
        return 1
    show_gui = sys.argv[1:] in (["--targets"], ["--settings"])
    settings = sys.argv[1:] == ["--settings"]
    command = ("open-settings" if settings else "open-gui") if show_gui else "status"
    if sys.platform == "linux":
        from .tray_control import request
        try:
            request(command)
            return 0
        except OSError:
            pass  # No listening tray; this process will own the icon and GUI.
        except RuntimeError as exc:
            sys.stderr.write(f"Could not open the running tray: {exc}. Restart the tray to update it.\n")
            return 1
    try:
        TrayApp(launched_at_startup="--autostart" in sys.argv[1:]).run(show_gui=show_gui, settings=settings)
    except (RuntimeError, OSError) as exc:
        if sys.platform == "linux" and (str(exc) == "Another tray is already running"
                or isinstance(exc, OSError) and exc.errno == errno.EADDRINUSE):
            # A simultaneous launch won the socket between our probe and bind.
            request(command)
            return 0
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
