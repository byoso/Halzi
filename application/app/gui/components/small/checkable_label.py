import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject


class CheckableLabel(Gtk.Box):
    """
    Emits "toggled" when the check button is toggled.
    """
    __gsignals__ = {
        "toggled": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (),  # that means no argument sent with the signal
        ),
    }
    def __init__(self, text):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        self.set_margin_start(20)
        self.set_margin_end(20)
        self.set_margin_top(5)
        self.set_margin_bottom(5)

        # 1. Label on the far left (No expansion, takes exactly its text width)
        self.label = Gtk.Label(label=text)
        self.pack_start(self.label, False, False, 0)

        # 2. The Spring: An empty container that absorbs all extra horizontal space
        spring = Gtk.Box()
        self.pack_start(spring, True, True, 0)

        # 3. Close button on the far right (No expansion)
        self.check_button = Gtk.CheckButton()
        self.pack_start(self.check_button, False, False, 0)
        self.check_button.connect("toggled", self.on_check_toggled)

    def on_check_toggled(self, widget):
        self.emit("toggled")