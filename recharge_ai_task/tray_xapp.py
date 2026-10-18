"""Native Cinnamon tray backend, sharing pystray's GTK menus and lifecycle."""
import logging

import gi
gi.require_version("XApp", "1.0")
from gi.repository import GLib, Gtk, XApp
from pystray._util.gtk import GtkIcon, mainloop

_log = logging.getLogger("recharge-ai-task.tray")


class XAppIcon(GtkIcon):
    HAS_DEFAULT_ACTION = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status_icon = XApp.StatusIcon.new_with_name(self.name)
        self._last_primary_press = None
        self._status_icon.connect("button-press-event", self._button_press)
        self._status_icon.set_visible(False)
        self._status_icon.set_tooltip_text(self.title)
        self._update_icon()

    @mainloop
    def _show(self):
        self._status_icon.set_visible(True)

    @mainloop
    def _hide(self):
        self._status_icon.set_visible(False)

    @mainloop
    def _update_icon(self):
        self._remove_fs_icon()
        self._update_fs_icon()
        # Absolute image path bypasses symbolic recoloring and theme lookup.
        self._status_icon.set_icon_name(self._icon_path)

    @mainloop
    def _update_title(self):
        self._status_icon.set_tooltip_text(self.title)

    @mainloop
    def _update_menu(self):
        self._menu_handle = self._create_menu(self.menu)
        # A primary menu would grab the first click and swallow double-clicks.
        self._status_icon.set_primary_menu(None)
        self._status_icon.set_secondary_menu(self._menu_handle)

    def _button_press(self, _icon, _x, _y, button, timestamp, _position):
        if button != 1:
            self._last_primary_press = None
            return
        settings = Gtk.Settings.get_default()
        interval = settings.get_property("gtk-double-click-time") if settings else 250
        previous = self._last_primary_press
        self._last_primary_press = timestamp
        if previous is not None and (timestamp - previous) % (2**32) <= interval:
            self._last_primary_press = None
            self()  # Invoke the dashboard's default menu action.

    def _initialize(self):
        super()._initialize()
        def report():
            _log.info("XApp panel monitor=%s icon_size=%s state=%s",
                      XApp.StatusIcon.any_monitors(), self._status_icon.get_icon_size(),
                      self._status_icon.get_state().value_nick)
            return False
        GLib.timeout_add_seconds(2, report)

    def _finalize(self):
        self._status_icon.set_visible(False)
        super()._finalize()
