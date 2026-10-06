"""Select the native Cinnamon backend, retaining pystray elsewhere."""
import os
import sys


def is_cinnamon() -> bool:
    return sys.platform == "linux" and "cinnamon" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def prepare_backend() -> None:
    if is_cinnamon():
        os.environ.setdefault("PYSTRAY_BACKEND", "gtk")
        try:
            from gi.repository import GLib
            GLib.set_prgname("codex-charge-tray")
        except ImportError:
            pass


def icon_class(default):
    if is_cinnamon() and os.environ.get("PYSTRAY_BACKEND") == "gtk":
        try:
            import gi
            gi.require_version("XApp", "1.0")
            from gi.repository import XApp
            if XApp.StatusIcon.any_monitors():
                from .tray_xapp import XAppIcon
                return XAppIcon
            from .tray_gtk import CinnamonGtkIcon
            return CinnamonGtkIcon
        except (ImportError, ValueError):
            import logging
            logging.getLogger("codex-charge.tray").warning("XApp is unavailable; using the GTK tray backend")
    return default
