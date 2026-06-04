import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject

import os

from gui.components.small.file_selector_button import FileSelectorButton


class FileSelector(Gtk.Box):
    """
    Emits "selected" signal when a path is selected, either by entering it in the entry or by using the file chooser dialog.
    """
    __gsignals__ = {
        "selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
    }
    def __init__(self, label="", folder_selector=False, placeholder="Enter a path"):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL)
        self.set_can_focus(True)
        self.folder_selector = folder_selector
        self.entry = Gtk.Entry(placeholder_text=placeholder)
        self.entry.connect("activate", self.on_entry_entered)
        self.pack_start(self.entry, True, True, 0)

        # Create a button to open the folder chooser dialog
        button = FileSelectorButton(folder_selector=folder_selector)
        button.connect("selected", self.on_button_clicked)
        self.pack_start(button, False, True, 0)

    def on_button_clicked(self, widget, path=None):
        self.entry.set_text(path if path else "")
        self.path_validation()

    def on_entry_entered(self, widget):
        self.grab_focus()
        self.path_validation()

    def path_validation(self):
        path = self.entry.get_text()
        if not os.path.exists(path):
            self.entry.set_text("")
            return
        self.emit("selected", path)

    def clear(self):
        self.entry.set_text("")
