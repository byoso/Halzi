import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject


class ClosableLabel(Gtk.Box):
    """
    Emits "closed" when the close button is clicked.
    Uses a middle spring layout to force strict left/right alignment.
    """

    __gsignals__ = {
        "closed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (),
        ),
    }

    def __init__(self, text):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.set_margin_start(20)
        self.set_margin_end(5)
        self.set_margin_top(5)
        self.set_margin_bottom(5)

        # 1. Label on the far left (No expansion, takes exactly its text width)
        self.label = Gtk.Label(label=text)
        self.pack_start(self.label, False, False, 0)

        # 2. The Spring: An empty container that absorbs all extra horizontal space
        spring = Gtk.Box()
        self.pack_start(spring, True, True, 0)

        # 3. Close button on the far right (No expansion)
        self.close_button = Gtk.Button(label="X")
        self.close_button.set_size_request(10, 10)
        self.pack_start(self.close_button, False, False, 0)

        self.close_button.connect("clicked", self.on_close_clicked)

    def on_close_clicked(self, widget):
        self.emit("closed")