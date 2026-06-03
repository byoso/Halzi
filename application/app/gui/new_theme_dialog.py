import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk


class NewThemeDialog(gtk.Dialog):
    def __init__(self, parent: gtk.Window):
        super().__init__(title="New Theme", transient_for=parent, flags=0)
        self.set_modal(True)
        self.set_default_size(360, 120)

        self.add_button("Cancel", gtk.ResponseType.CANCEL)
        create_button = self.add_button("Create", gtk.ResponseType.OK)
        create_button.get_style_context().add_class("halzi-create-theme-button")

        box = self.get_content_area()
        box.set_spacing(8)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)

        label = gtk.Label(label="Theme name")
        label.set_xalign(0.0)

        self.entry = gtk.Entry()
        self.entry.set_activates_default(True)

        box.pack_start(label, False, False, 0)
        box.pack_start(self.entry, False, False, 0)

        self.set_default_response(gtk.ResponseType.OK)
        self.show_all()

    def get_theme_name(self) -> str:
        return self.entry.get_text().strip()
