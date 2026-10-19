"""GTK settings editor; shared configuration is reloaded before saving."""
from __future__ import annotations

import shlex
from gi.repository import Gtk

from .autostart import is_autostart_enabled, set_autostart
from .config import AppConfig
from .branding import set_window_icon


class SettingsDialog(Gtk.Dialog):
    def __init__(self, parent):
        super().__init__(title="Recharge AI-task — Settings", transient_for=parent, modal=True)
        set_window_icon(self)
        self.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "Save settings", Gtk.ResponseType.OK)
        self.set_default_size(540, 390)
        config = AppConfig.load()
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin=18)
        self.get_content_area().add(grid)
        self.mode = Gtk.ComboBoxText()
        for key, label in (("desktop", "Desktop watch"), ("cli", "Codex CLI")):
            self.mode.append(key, label)
        self.mode.set_active_id(config.mode)
        self.path = Gtk.Entry(text=config.codex_path or "", placeholder_text="Auto-detect Codex CLI")
        self.args = Gtk.Entry(text=shlex.join(config.codex_args or []), placeholder_text="Optional CLI arguments")
        self.grace = Gtk.SpinButton.new_with_range(0, 86400, 1)
        self.grace.set_value(config.grace_seconds)
        self.poll = Gtk.SpinButton.new_with_range(1, 3600, 1)
        self.poll.set_value(config.poll_seconds)
        self.autostart = Gtk.CheckButton(label="Run the tray when I log in")
        self.autostart.set_active(is_autostart_enabled())
        for index, (name, widget) in enumerate((("Default mode", self.mode),
            ("Codex CLI path", self.path), ("CLI arguments", self.args),
            ("Reset grace (seconds)", self.grace), ("Quota polling (seconds)", self.poll))):
            grid.attach(Gtk.Label(label=name, xalign=0), 0, index, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, index, 1, 1)
        grid.attach(self.autostart, 0, 5, 2, 1)
        note = Gtk.Label(label="Message text and each recipient’s Send message / Resume goal choices are in the main window.\nThose choices save automatically for future quota recovery; Send now acts immediately.\nStartup launches the tray; Desktop watch starts when you turn it on.\nChanges to an active watch apply automatically.", xalign=0)
        note.set_line_wrap(True)
        note.set_max_width_chars(64)
        grid.attach(note, 0, 6, 2, 1)
        self.error = Gtk.Label(xalign=0)
        self.error.set_line_wrap(True)
        grid.attach(self.error, 0, 7, 2, 1)
        self.show_all()

    def save_settings(self):
        args = shlex.split(self.args.get_text())
        config = AppConfig.load()
        config.mode = self.mode.get_active_id()
        config.codex_path = self.path.get_text().strip() or None
        config.codex_args = args or None
        config.grace_seconds = self.grace.get_value_as_int()
        config.poll_seconds = self.poll.get_value_as_int()
        config.autostart = self.autostart.get_active()
        # Recreate an enabled entry to update its executable/launch marker.
        set_autostart(config.autostart)
        config.save()
        return config

    def edit(self):
        while self.run() == Gtk.ResponseType.OK:
            try:
                result = self.save_settings()
            except Exception as exc:
                self.error.set_text(str(exc))
            else:
                self.destroy()
                return result
        self.destroy()
        return None
