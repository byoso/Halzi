import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GObject, Gtk

from gui.components.medium.folder_tree_view import FolderTreeView
from gui.components.small.file_selector import FileSelector


class FilesCherryPicker(Gtk.Box):
    """
    Reminder:
        - folder_selector.button: clicked
        - folder_selector.entry: activate -> entry.get_text()
    """

    __gsignals__ = {
        "selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
        "folder-removed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
        "folder-added": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
    }

    def __init__(self, folders=None, short_path_length=120):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.short_path_length = short_path_length

        # 1. FIXED: Top area for the selector (always visible, outside the scroll area)
        self.selector_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.folder_selector = FileSelector(
            folder_selector=True, placeholder="Add a folder"
        )
        self.selector_box.pack_start(self.folder_selector, True, True, 0)
        self.pack_start(self.selector_box, False, False, 5)
        self.folder_selector.connect("selected", self.add_folder)

        # 2. FIXED: Use a Gtk.ScrolledWindow as the scrolling foundation
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(
            Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC
        )
        self.pack_start(self.scrolled_window, True, True, 0)

        # 3. FIXED: Box container inside the ScrolledWindow to hold the multiple tree views
        self.box_folder_containers = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=10
        )

        # In GTK 3, containers without native scrolling capabilities (like Gtk.Box)
        # must be added to a ScrolledWindow using a Viewport placeholder container.
        # .add() does this automatically for us behind the scenes.
        self.scrolled_window.add(self.box_folder_containers)

        # 4. FIXED: Populate initial folders AFTER all containers are initialized
        if folders is not None:
            for folder in folders:
                self.add_folder(widget=None, folder_path=folder)

        self.show_all()

    def add_folder(self, widget, folder_path: str):
        # Create and connect the new custom tree view component
        folder_tree_view = FolderTreeView(
            folder=folder_path, short_path_length=self.short_path_length
        )
        folder_tree_view.connect("selected", self.on_path_selected)
        folder_tree_view.set_margin_left(15)
        folder_tree_view.set_margin_right(25)
        folder_tree_view.connect("destroy", lambda w: self.on_folder_removed(folder_path))

        # Dynamically pack it into our scrolling box layout
        self.box_folder_containers.pack_start(folder_tree_view, True, True, 0)

        self.emit("folder-added", folder_path)
        self.show_all()

    def get_selected_folders(self) -> list[str]:
        selected_folders = []
        for child in self.box_folder_containers.get_children():
            if isinstance(child, FolderTreeView):
                selected_folders.append(child.folder_path)
        return selected_folders

    def on_folder_removed(self, folder_path: str):
        self.emit("folder-removed", folder_path)

    def on_path_selected(self, widget, path: str):
        self.emit("selected", path)

    def get_folder_list(self) -> list[str]:
        folders = []
        for child in self.box_folder_containers.get_children():
            if isinstance(child, FolderTreeView):
                folders.append(child.folder_path)
        return folders

    def clear_folders(self):
        for child in self.box_folder_containers.get_children():
            if isinstance(child, FolderTreeView):
                self.box_folder_containers.remove(child)
                child.destroy()