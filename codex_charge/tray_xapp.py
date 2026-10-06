"""Native Cinnamon tray backend, sharing pystray's GTK menus and lifecycle."""
import logging

import gi
gi.require_version("XApp", "1.0")
from gi.repository import GLib, XApp
from pystray._util.gtk import GtkIcon, mainloop

_log = logging.getLogger("codex-charge.tray")


class XAppIcon(GtkIcon):
    HAS_DEFAULT_ACTION = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._status_icon = XApp.StatusIcon.new_with_name(self.name)
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
        self._status_icon.set_primary_menu(self._menu_handle)
        self._status_icon.set_secondary_menu(self._menu_handle)

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
