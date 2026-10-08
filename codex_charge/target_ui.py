"""GTK target picker; discovery and delivery run outside the UI thread."""
from __future__ import annotations

import threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from .config import AppConfig
from .target_delivery import deliver_targets, open_target
from .targets import Target, discover_targets


class TargetPicker(Gtk.Window):
    def __init__(self):
        super().__init__(title="Codex Charge — Choose targets")
        self.set_default_size(1120, 580)
        self.config = AppConfig.load()
        self.selected = {t.key: t for t in self.config.targets()}
        self.targets = dict(self.selected)
        self.busy = False
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_border_width(14)
        self.add(box)
        intro = Gtk.Label(label="Choose chats by ID, or windows for the chat currently shown there. You can select several.")
        intro.set_xalign(0)
        box.pack_start(intro, False, False, 0)
        self.search = Gtk.SearchEntry(placeholder_text="Search title, ID, project, process, or link…")
        self.search.connect("search-changed", lambda _: self.filtered.refilter())
        box.pack_start(self.search, False, False, 0)
        self.store = Gtk.ListStore(bool, str, str, str, str, str, str, str, str, str)
        self.filtered = self.store.filter_new()
        self.filtered.set_visible_func(self._visible)
        self.table = Gtk.TreeView(model=self.filtered)
        self.table.set_has_tooltip(True)
        self.table.connect("query-tooltip", self._tooltip)
        checkbox = Gtk.CellRendererToggle()
        checkbox.connect("toggled", self._toggle)
        self.table.append_column(Gtk.TreeViewColumn("Select", checkbox, active=0))
        widths = [300, 80, 160, 295, 95, 260, 400, 300, 300]
        for index, name in enumerate(("Title", "Kind", "Availability", "ID", "PID", "Instance", "Deep link", "Project", "Desktop client"), 1):
            renderer = Gtk.CellRendererText()
            renderer.set_property("ellipsize", 3)
            column = Gtk.TreeViewColumn(name, renderer, text=index)
            column.set_resizable(True)
            column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
            column.set_fixed_width(widths[index - 1])
            self.table.append_column(column)
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.table)
        box.pack_start(scroller, True, True, 0)
        self.summary = Gtk.Label(xalign=0, selectable=True)
        box.pack_start(self.summary, False, False, 0)
        prompt = Gtk.Box(spacing=8)
        prompt.pack_start(Gtk.Label(label="Signal text:"), False, False, 0)
        self.signal = Gtk.Entry(text=self.config.continue_prompt)
        prompt.pack_start(self.signal, True, True, 0)
        box.pack_start(prompt, False, False, 0)
        self.goal = Gtk.CheckButton(label="First quota-reset signal: /goal resume")
        self.goal.set_active(self.config.goal_mode)
        box.pack_start(self.goal, False, False, 0)
        self.status = Gtk.Label(label="Discovering targets…", xalign=0, selectable=True)
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
        self.connect("destroy", Gtk.main_quit)
        self.refresh()

    def _tooltip(self, table, x, y, keyboard, tooltip):
        context = table.get_tooltip_context(x, y, keyboard)
        if not context or not context[0]:
            return False
        _valid, _x, _y, model, path, iterator = context
        row = model[iterator]
        tooltip.set_text(f"{row[1]}\nID: {row[4]}\nPID: {row[5] or '—'}\nInstance: {row[6]}\n{row[7]}\nProject: {row[8]}\nDesktop client: {row[9]}")
        table.set_tooltip_row(tooltip, path)
        return True

    def _visible(self, model, iterator, _data):
        query = self.search.get_text().casefold()
        return not query or query in " ".join(str(model[iterator][i]) for i in range(1, 10)).casefold()

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

    def _summary(self):
        self.summary.set_text(f"{len(self.selected)} target(s) selected. Chat signals go to those IDs; window signals go to their current chat.")

    def _busy(self, active):
        self.busy = active
        for button in self.buttons:
            button.set_sensitive(not active)
        self.signal.set_sensitive(not active)
        self.goal.set_sensitive(not active)
        self.table.set_sensitive(not active)

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

    def refresh(self, *_):
        self.status.set_text("Discovering targets…")
        def show(inventory):
            self.store.clear()
            self.targets = {}
            live = {t.key: t for t in inventory.targets}
            for key, saved in list(self.selected.items()):
                self.selected[key] = live.get(key, saved)
            for target in [*inventory.targets, *(t for key, t in self.selected.items() if key not in live)]:
                self.targets[target.instance + "\0" + target.id] = target
                availability = target.status if target.key in live else "Unavailable — saved selection"
                self.store.append([target.key in self.selected, target.title, target.kind, availability,
                    target.id, str(target.pid or ""), target.instance, target.deeplink, target.cwd, target.owner_id])
            self.status.set_text(f"Found {len(inventory.targets)} targets. " + " ".join(inventory.warnings))
            self._summary()
        self._work(discover_targets, show)

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
        config.save()
        self.status.set_text(f"Saved {len(self.selected)} targets for quota-reset signals.")

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


def main():
    TargetPicker().show_all()
    Gtk.main()
    return 0
