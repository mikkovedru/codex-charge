"""GTK target picker; discovery and delivery run outside the UI thread."""
from __future__ import annotations

from dataclasses import replace

import threading
import subprocess
import sys
import time
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .config import AppConfig, config_path
from .autostart import is_autostart_enabled
from .quota import discover_codex, fetch_quota
from . import tray_control
from .target_delivery import deliver_targets, open_target
from .targets import Target, discover_targets


class TargetPicker(Gtk.Window):
    def __init__(self):
        super().__init__(title="Codex Charge — Choose targets")
        self.set_default_size(1120, 740)
        self.config = AppConfig.load()
        self.selected = {t.key: t for t in self.config.targets()}
        self.targets = dict(self.selected)
        self.busy = False
        self.closed = False
        self.runtime = None
        self.runtime_busy = False
        self.quota_busy = False
        self.discovery_busy = False
        self.quota = None
        self.quota_error = ""
        self.quota_updated = None
        self.saved_signature = self._signature(self.config.targets(), self.config.continue_prompt, self.config.goal_mode) if config_path().exists() else None
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(14)
        self.add(box)
        intro = Gtk.Label(label="Choose chats by ID, or windows for the chat currently shown there. You can select several.")
        intro.set_xalign(0)
        box.pack_start(intro, False, False, 0)
        dashboard = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.watch_label = Gtk.Label(label="Desktop watch: checking…", xalign=0)
        self.startup_label = Gtk.Label(label="Startup: checking…", xalign=0)
        self.quota_label = Gtk.Label(label="Quota: loading…", xalign=0, selectable=True)
        self.quota_label.set_line_wrap(True)
        for widget in (self.watch_label, self.startup_label, self.quota_label):
            dashboard.pack_start(widget, False, False, 0)
        controls = Gtk.Box(spacing=8)
        self.watch_button = Gtk.Button(label="Start Desktop watch")
        self.watch_button.connect("clicked", self.toggle_watch)
        self.watch_button.set_sensitive(False)
        self.quota_button = Gtk.Button(label="Refresh quota")
        self.quota_button.connect("clicked", self.refresh_quota)
        self.settings_button = Gtk.Button(label="Settings…")
        self.settings_button.connect("clicked", self.settings)
        for widget in (self.watch_button, self.quota_button, self.settings_button):
            controls.pack_start(widget, False, False, 0)
        dashboard.pack_start(controls, False, False, 0)
        box.pack_start(dashboard, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Search title, status, ID, project, process, or link…")
        self.search.connect("search-changed", lambda _: self.filtered.refilter())
        box.pack_start(self.search, False, False, 0)
        self.store = Gtk.ListStore(bool, str, str, str, str, str, str, str, str, str, str, str)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(self._visible)
        self.table = Gtk.TreeView(model=self.filtered)
        self.table.set_has_tooltip(True)
        self.table.connect("query-tooltip", self._tooltip)
        checkbox = Gtk.CellRendererToggle()
        checkbox.connect("toggled", self._toggle)
        self.table.append_column(Gtk.TreeViewColumn("Select", checkbox, active=0))
        columns = [("Title", 1, 270), ("Task status", 10, 170), ("Goal status", 11, 140),
                   ("Kind", 2, 80), ("Availability", 3, 160), ("ID", 4, 295),
                   ("PID", 5, 95), ("Instance", 6, 260), ("Deep link", 7, 400),
                   ("Project", 8, 300), ("Desktop client", 9, 300)]
        for name, index, width in columns:
            renderer = Gtk.CellRendererText()
            renderer.set_property("ellipsize", 3)
            column = Gtk.TreeViewColumn(name, renderer, text=index)
            column.set_resizable(True)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(width)
            self.table.append_column(column)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.table)
        box.pack_start(scroller, True, True, 0)
        self.inventory_status = Gtk.Label(label="Discovering targets…", xalign=0)
        self.inventory_status.set_line_wrap(True)
        self.inventory_status.set_tooltip_text("Chat statuses refresh every 15 seconds. Task state comes from Codex's live desktop owner when available; goal state also uses the saved goal database. Windows do not identify a fixed chat. Unavailable means the state could not be read.")
        box.pack_start(self.inventory_status, False, False, 0)
        self.summary = Gtk.Label(xalign=0, selectable=True)
        box.pack_start(self.summary, False, False, 0)
        self.save_state = Gtk.Label(xalign=0)
        box.pack_start(self.save_state, False, False, 0)
        prompt = Gtk.Box(spacing=8)
        prompt.pack_start(Gtk.Label(label="Signal text:"), False, False, 0)
        self.signal = Gtk.Entry(text=self.config.continue_prompt)
        prompt.pack_start(self.signal, True, True, 0)
        box.pack_start(prompt, False, False, 0)
        self.goal = Gtk.CheckButton(label="First quota-reset signal: /goal resume")
        self.goal.set_active(self.config.goal_mode)
        self.signal.connect("changed", lambda _: self._summary())
        self.goal.connect("toggled", lambda _: self._summary())
        box.pack_start(self.goal, False, False, 0)
        self.status = Gtk.Label(label="Choose recipients, then save your selection.", xalign=0, selectable=True)
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)
        buttons = Gtk.Box(spacing=8)
        self.buttons = []
        for label, action in (("Refresh", self.refresh), ("Open selected row", self.open_row),
                              ("Copy link / ID", self.copy_row), ("Save selection", self.save),
                              ("Send signal now", self.send)):
            button = Gtk.Button(label=label)
            button.connect("clicked", action)
            buttons.pack_start(button, False, False, 0)
            self.buttons.append(button)
        box.pack_start(buttons, False, False, 0)
        self.connect("delete-event", lambda *_: self.busy)
        self.connect("destroy", self._destroy)
        self._timers = [GLib.timeout_add_seconds(2, self.poll_runtime),
                        GLib.timeout_add_seconds(60, self.refresh_quota),
                        GLib.timeout_add_seconds(1, self.render_quota),
                        GLib.timeout_add_seconds(15, self.refresh_statuses)]
        self.refresh()
        self.poll_runtime()
        self.refresh_quota()

    def _tooltip(self, table, x, y, keyboard, tooltip):
        context = table.get_tooltip_context(x, y, keyboard)
        if not context or not context[0]:
            return False
        _valid, _x, _y, model, path, iterator = context
        row = model[iterator]
        tooltip.set_text(f"{row[1]}\nTask: {row[10]}\nGoal: {row[11]}\nID: {row[4]}\nPID: {row[5] or '—'}\nInstance: {row[6]}\n{row[7]}\nProject: {row[8]}\nDesktop client: {row[9]}")
        table.set_tooltip_row(tooltip, path)
        return True

    def _visible(self, model, iterator, _data):
        query = self.search.get_text().casefold()
        return not query or query in " ".join(str(model[iterator][i]) for i in range(1, 12)).casefold()

    def _toggle(self, _renderer, path):
        if self.busy:
            return
        row = self.filtered[path]
        target = self.targets[row[6] + "\0" + row[4]]
        row[0] = not row[0]
        if row[0]:
            self.selected[target.key] = target
        else:
            self.selected.pop(target.key, None)
        self._summary()

    @staticmethod
    def _signature(targets, text, goal):
        return (frozenset(t.key for t in targets), text, goal)

    def dirty(self):
        return self._signature(self.selected.values(), self.signal.get_text(), self.goal.get_active()) != self.saved_signature

    def _summary(self):
        self.summary.set_text(f"{len(self.selected)} target(s) selected. Chat signals go to those IDs; window signals go to their current chat.")
        dirty = self.dirty()
        self.save_state.set_markup("<b>Unsaved changes — click Save selection.</b>" if dirty else "<b>Saved — selection and signal match your settings.</b>")
        self._render_runtime()

    def _destroy(self, *_):
        self.closed = True
        for timer in self._timers:
            GLib.source_remove(timer)
        Gtk.main_quit()

    def _background(self, job, done):
        def worker():
            try:
                value, error = job(), None
            except Exception as exc:
                value, error = None, str(exc)
            def finish():
                if not self.closed:
                    done(value, error)
                return False
            GLib.idle_add(finish)
        threading.Thread(target=worker, daemon=True).start()

    def poll_runtime(self):
        if self.closed:
            return False
        if self.runtime_busy:
            return True
        self.runtime_busy = True
        def show(value, error):
            self.runtime_busy = False
            self.runtime = value
            try:
                saved = AppConfig.load()
                self.saved_signature = self._signature(saved.targets(), saved.continue_prompt, saved.goal_mode) if config_path().exists() else None
                self._summary()
            except Exception as exc:
                self.status.set_text(f"Could not read settings: {exc}")
            self._render_runtime()
        self._background(lambda: tray_control.request(timeout=1), show)
        return True

    def _render_runtime(self):
        if not hasattr(self, "watch_button"):
            return
        runtime = self.runtime or {}
        alive = runtime.get("desktop_watch", False)
        stopping = runtime.get("stopping", False)
        state = "Stopping…" if stopping else "On" if alive else "Off"
        if self.runtime is None:
            state += " — tray is not running or is unavailable"
        elif runtime.get("watch_error"):
            state += " — " + runtime["watch_error"]
        elif runtime.get("cli_running"):
            state += " — CLI service is running"
        elif alive:
            try:
                if runtime.get("watch_settings") != tray_control.watch_settings(AppConfig.load()):
                    state += " — saved changes need a watch restart"
            except Exception:
                state += " — saved settings could not be read"
        self.watch_label.set_text("Desktop watch: " + state)
        self.watch_button.set_label("Stop Desktop watch" if alive else "Start Desktop watch")
        self.watch_button.set_sensitive(not self.busy and not self.runtime_busy and not stopping and not runtime.get("cli_running", False))
        try:
            startup = "Enabled" if is_autostart_enabled() else "Disabled"
        except OSError:
            startup = "Unavailable"
        launched = "Yes" if runtime.get("launched_at_startup") else "No" if self.runtime else "Unknown (tray unavailable)"
        self.startup_label.set_text(f"Run at login: {startup} · This tray started at login: {launched}")

    def toggle_watch(self, *_):
        if self.runtime and self.runtime.get("desktop_watch"):
            command = "stop-watch"
        else:
            if self.dirty():
                self.status.set_text("Save selection before starting Desktop watch.")
                return
            if not self.selected:
                self.status.set_text("Select and save at least one target before starting Desktop watch.")
                return
            command = "start-watch"
        def control():
            try:
                tray_control.request(timeout=1)
            except OSError:
                if command != "start-watch":
                    raise
                args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "codex_charge.tray"]
                subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                deadline = time.monotonic() + 10
                while True:
                    try:
                        tray_control.request(timeout=1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError("Tray did not start; check the tray log")
                        time.sleep(.2)
            return tray_control.request(command)
        def show(value):
            self.runtime = value
            self._render_runtime()
            self.status.set_text("Desktop watch is stopping." if value.get("stopping") else "Desktop watch started." if value.get("desktop_watch") else "Desktop watch is off.")
        self._work(control, show)

    def refresh_quota(self, *_):
        if self.closed:
            return False
        if self.quota_busy:
            return True
        self.quota_busy = True
        self.quota_button.set_sensitive(False)
        def show(value, error):
            self.quota_busy = False
            self.quota_button.set_sensitive(True)
            self.quota_error = error or ""
            if value:
                self.quota = value
                self.quota_updated = time.time()
            self.render_quota()
        self._background(lambda: fetch_quota(discover_codex(AppConfig.load().codex_path)), show)
        return True

    def render_quota(self):
        if self.closed:
            return False
        if self.quota is None:
            self.quota_label.set_text("Quota unavailable: " + self.quota_error if self.quota_error else "Quota: loading…")
            return True
        def window_text(window):
            label = "5-hour" if window.window_duration_mins == 300 else "Weekly" if window.window_duration_mins == 10080 else f"{window.window_duration_mins}-minute"
            remaining = max(0, int(window.resets_at - time.time()))
            days, remainder = divmod(remaining, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, seconds = divmod(remainder, 60)
            countdown = (f"{days}d " if days else "") + f"{hours:02}:{minutes:02}:{seconds:02}"
            reset = time.strftime("%a %d %b %H:%M:%S", time.localtime(window.resets_at))
            return f"{label}: {window.used_percent:g}% used · resets {reset} ({countdown})"
        lines = [window_text(w) for w in (self.quota.primary, self.quota.secondary) if w is not None]
        age = max(0, int(time.time() - self.quota_updated))
        lines.append(f"Quota refreshed {age}s ago · automatic refresh every 60s" + (" · Latest refresh failed: " + self.quota_error if self.quota_error else ""))
        self.quota_label.set_text("\n".join(lines))
        return True

    def settings(self, *_):
        from .settings_ui import SettingsDialog
        config = SettingsDialog(self).edit()
        if config is not None:
            self.config = config
            self.status.set_text("Settings saved. Stop and start an active watch to apply them.")
            self._background(lambda: tray_control.request("reload"), lambda *_: self.poll_runtime())
            self.refresh_quota()
            self._render_runtime()

    def _busy(self, active):
        self.busy = active
        for button in self.buttons:
            button.set_sensitive(not active)
        self.signal.set_sensitive(not active)
        self.goal.set_sensitive(not active)
        self.table.set_sensitive(not active)
        self.settings_button.set_sensitive(not active)
        self._render_runtime()

    def _work(self, job, done):
        self._busy(True)
        def worker():
            try:
                result, error = job(), None
            except Exception as exc:
                result, error = None, str(exc)
            def finish():
                self._busy(False)
                if error:
                    self.status.set_text(error)
                else:
                    done(result)
                return False
            GLib.idle_add(finish)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_inventory(self, inventory):
        live = {t.key: t for t in inventory.targets}
        for key, saved in list(self.selected.items()):
            self.selected[key] = live.get(key, replace(saved, task_status="Unavailable", goal_status="Unavailable"))
        targets = {**live, **{k: t for k, t in self.selected.items() if k not in live}}
        self.targets = {t.instance + "\0" + t.id: t for t in targets.values()}
        # Update existing rows in place so refresh preserves focus and scrolling.
        rows = {}
        for index in range(len(self.store) - 1, -1, -1):
            row = self.store[index]
            key = Target(row[2], row[4], row[1], instance=row[6]).key
            if key not in targets:
                self.store.remove(row.iter)
            else:
                rows[key] = row.iter
        for key, target in targets.items():
            values = [key in self.selected, target.title, target.kind,
                target.status if key in live else "Unavailable — saved selection",
                target.id, str(target.pid or ""), target.instance, target.deeplink, target.cwd,
                target.owner_id, target.task_status, target.goal_status]
            iterator = rows.get(key)
            if iterator is None:
                self.store.append(values)
            else:
                self.store.set(iterator, list(range(len(values))), values)
        self.filtered.refilter()
        self.inventory_status.set_text(f"{len(inventory.targets)} targets · Status refreshed {time.strftime('%H:%M:%S')} · Every 15 seconds"
            + ("\n" + " ".join(inventory.warnings) if inventory.warnings else ""))
        self._summary()

    def refresh(self, *_, automatic=False):
        if self.closed or self.discovery_busy or self.busy:
            return
        self.discovery_busy = True
        if not automatic:
            self.inventory_status.set_text("Refreshing targets and statuses…")
        def show(inventory, error):
            self.discovery_busy = False
            if error:
                # Retain the recipients, but never display stale state as current.
                for row in self.store:
                    row[10], row[11] = "Unavailable", "Unavailable"
                self.filtered.refilter()
                self.inventory_status.set_text(f"Status refresh failed: {error}")
            else:
                self._apply_inventory(inventory)
        self._background(discover_targets, show)

    def refresh_statuses(self):
        if self.closed:
            return False
        self.refresh(automatic=True)
        return True

    def _row_target(self):
        model, iterator = self.table.get_selection().get_selected()
        if iterator is None:
            raise ValueError("Choose a row first")
        row = model[iterator]
        return self.targets[row[6] + "\0" + row[4]]

    def open_row(self, *_):
        try:
            target = self._row_target()
            self._work(lambda: open_target(target), lambda _: self.status.set_text("Chat opened in Codex. Refresh to update the list."))
        except Exception as exc:
            self.status.set_text(str(exc))

    def copy_row(self, *_):
        try:
            target = self._row_target()
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(target.deeplink or target.id, -1)
            self.status.set_text("Copied.")
        except Exception as exc:
            self.status.set_text(str(exc))

    def save(self, *_):
        if not self.signal.get_text().strip():
            self.status.set_text("Enter a signal before saving.")
            return
        config = AppConfig.load()
        config.desktop_targets = [t.to_dict() for t in self.selected.values()]
        config.continue_prompt = self.signal.get_text()
        config.goal_mode = self.goal.get_active()
        config.mode = "desktop"
        try:
            config.save()
        except Exception as exc:
            self.status.set_text(f"Could not save selection: {exc}")
            return
        self.config = config
        self.saved_signature = self._signature(self.selected.values(), config.continue_prompt, config.goal_mode)
        self._summary()
        self.status.set_text(f"Saved {len(self.selected)} targets for quota-reset signals." + (" Stop and start the active watch to apply changes." if self.runtime and self.runtime.get("desktop_watch") else ""))
        self._background(lambda: tray_control.request("reload"), lambda *_: self.poll_runtime())

    def send(self, *_):
        if not self.selected:
            self.status.set_text("Select at least one target before sending.")
            return
        selected = list(self.selected.values())
        text = self.signal.get_text()
        self.status.set_text(f"Sending to {len(selected)} selected targets…")
        def show(results):
            accepted = sum(r.success for r in results)
            detail = "\n".join(f"{r.target.title} [{r.target.id}]: {r.detail}" for r in results)
            self.status.set_text(f"Signal accepted by {accepted}/{len(results)} targets. Hover here for each result.")
            self.status.set_tooltip_text(detail)
        self._work(lambda: deliver_targets(selected, text), show)


def main(*, settings=False):
    window = TargetPicker()
    window.show_all()
    if settings:
        GLib.idle_add(lambda: window.settings() or False)
    Gtk.main()
    return 0
