"""Opaque XEmbed tray surface for legacy Cinnamon status applets."""
import logging
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_foreign("cairo")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk
from PIL import Image
from Xlib import display, protocol
from pystray._util.gtk import GtkIcon, mainloop


class CinnamonGtkIcon(GtkIcon):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rendered_size = None
        self._size_timer = None
        self._xdisplay = display.Display()
        self._plug = Gtk.Plug.new(0)
        self._plug.set_title("codex-charge-tray")
        self._area = Gtk.DrawingArea()
        self._area.set_size_request(16, 16)
        self._area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._area.connect("draw", self._draw_icon)
        self._area.connect("button-press-event", self._button_press)
        self._plug.add(self._area)
        self._plug.realize()
        self._plug.set_tooltip_text(self.title)
        self._owner = None

    def _allocated_size(self):
        geometry = self._xdisplay.create_resource_object("window", self._plug.get_id()).get_geometry()
        return max(1, min(geometry.width, geometry.height))

    def _draw_icon(self, _area, cr):
        size = self._allocated_size()
        image = self.icon.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(image.tobytes()), GdkPixbuf.Colorspace.RGB, True, 8, size, size, size * 4)
        Gdk.cairo_set_source_pixbuf(cr, pixbuf, 0, 0)
        cr.paint()
        self._rendered_size = size
        return True

    def _button_press(self, _area, event):
        if event.button == 1 and event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
            self()
            return True
        if event.button == 3 and self._menu_handle is not None:
            self._menu_handle.popup_at_pointer(event)
            return True
        return False

    def _dock(self):
        selection = self._xdisplay.intern_atom(f"_NET_SYSTEM_TRAY_S{self._xdisplay.get_default_screen()}")
        owner = self._xdisplay.get_selection_owner(selection)
        if owner.id and owner.id != self._owner:
            request = protocol.event.ClientMessage(window=owner, client_type=self._xdisplay.intern_atom("_NET_SYSTEM_TRAY_OPCODE"), data=(32, [0, 0, self._plug.get_id(), 0, 0]))
            owner.send_event(request)
            self._xdisplay.flush()
            self._owner = owner.id

    def _refresh(self):
        self._dock()
        size = self._allocated_size()
        if size != self._rendered_size:
            self._area.queue_draw()
        return True

    @mainloop
    def _show(self):
        self._plug.show_all()
        self._dock()
        self._area.queue_draw()

    @mainloop
    def _hide(self):
        self._plug.hide()

    @mainloop
    def _update_icon(self):
        self._remove_fs_icon()
        self._update_fs_icon()
        self._area.queue_draw()

    @mainloop
    def _update_title(self):
        self._plug.set_tooltip_text(self.title)

    @mainloop
    def _update_menu(self):
        self._menu_handle = self._create_menu(self.menu)

    def _initialize(self):
        super()._initialize()
        self._size_timer = GLib.timeout_add(500, self._refresh)
        logging.getLogger("codex-charge.tray").info("Using direct XEmbed drawing for Cinnamon's legacy tray")

    def _finalize(self):
        if self._size_timer is not None:
            GLib.source_remove(self._size_timer)
        self._plug.destroy()
        self._xdisplay.close()
        super()._finalize()
