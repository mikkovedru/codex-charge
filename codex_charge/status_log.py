"""A bounded, selectable, scrollable GTK message log with per-message colors."""
from gi.repository import GLib, Gtk
from .status_display import COLORS


class StatusLog(Gtk.ScrolledWindow):
    def __init__(self):
        super().__init__()
        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.set_size_request(-1, 96)
        self.view = Gtk.TextView(editable=False, cursor_visible=False, wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(8)
        self.view.set_right_margin(8)
        self.view.set_top_margin(6)
        self.view.set_bottom_margin(6)
        self.buffer = self.view.get_buffer()
        for level, color in COLORS.items():
            self.buffer.create_tag(level, foreground=color)
        self.buffer.create_tag("normal")  # Inherit the normal theme text color.
        self.add(self.view)
        self.latest_text = ""
        self.latest_level = "normal"
        self._scroll_pending = False
        self._closed = False
        self.connect("destroy", self._destroy)

    def write(self, message, level="normal"):
        if not message:
            return
        adjustment = self.get_vadjustment()
        follow = adjustment.get_value() + adjustment.get_page_size() >= adjustment.get_upper() - 2
        self.latest_text, self.latest_level = message, level
        if self.buffer.get_char_count():
            self.buffer.insert(self.buffer.get_end_iter(), "\n")
        self.buffer.insert_with_tags_by_name(self.buffer.get_end_iter(), message, level)
        # Bound memory while preserving recent text and its tags.
        if self.buffer.get_line_count() > 1000:
            end = self.buffer.get_iter_at_line(self.buffer.get_line_count() - 1000)
            self.buffer.delete(self.buffer.get_start_iter(), end)
        if follow and not self._scroll_pending:
            self._scroll_pending = True
            GLib.idle_add(self._scroll_to_end)

    def _scroll_to_end(self):
        self._scroll_pending = False
        if not self._closed:
            self.view.scroll_to_iter(self.buffer.get_end_iter(), 0, False, 0, 0)
        return False

    def _destroy(self, *_):
        self._closed = True
