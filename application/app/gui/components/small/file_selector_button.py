import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GObject



class FileSelectorButton(Gtk.Button):
    """
    Emits "selected" signal when a path is selected using the file chooser dialog.
    """
    __gsignals__ = {
        "selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
    }
    def __init__(self, folder_selector=False):
        super().__init__()
        self.folder_selector = folder_selector
        if self.folder_selector:
            icon = Gtk.Image.new_from_icon_name("folder", Gtk.IconSize.BUTTON)
        else:
            icon = Gtk.Image.new_from_icon_name("document-open", Gtk.IconSize.BUTTON)
        self.add(icon)
        self.connect("clicked", self.on_button_clicked)


    def on_button_clicked(self, widget):
        if self.folder_selector:
            dialog = Gtk.FileChooserDialog(title="Please choose a folder",
                                            action=Gtk.FileChooserAction.SELECT_FOLDER)
        else:
            dialog = Gtk.FileChooserDialog(title="Please choose a file",
                                            action=Gtk.FileChooserAction.OPEN)

        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                           Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

        if dialog.run() == Gtk.ResponseType.OK:
            path = dialog.get_filename()
        else:
            path = ""
        self.emit("selected", path)
        dialog.destroy()