import gi

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject


from gui.components.small.checkable_label import CheckableLabel
from gui.components.medium.files_cherry_picker import FilesCherryPicker
from gui.components.medium.files_lister import FileLister



class FilesCherryPickerLister(Gtk.Box):
    __gsignals__ = {
        "selected": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
        "folder-updated": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # that means one argument sent with the signal
        ),
    }
    def __init__(self, short_path_length=120, files=None, folders=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.folders = folders or []
        self.short_path_length = short_path_length

        self.state = False  # for checkable label

        # checkable button
        self.checkable_label = CheckableLabel(text="Send")
        self.pack_start(self.checkable_label, False, False, 0)
        self.checkable_label.connect("toggled", self.on_check_toggled)

        # files lister
        self.file_lister = FileLister(files=files, short_path_length=35)
        self.file_lister.set_size_request(-1, 150)
        self.pack_start(self.file_lister, True, True, 0)

        # files cherry picker
        self.file_cherry_picker = FilesCherryPicker(short_path_length=35, folders=folders)
        self.pack_start(self.file_cherry_picker, True, True, 0)
        self.file_cherry_picker.set_size_request(-1, 200)
        self.file_cherry_picker.connect("selected", self.file_picked)
        self.file_cherry_picker.connect("folder-added", self.on_folder_added)
        self.file_cherry_picker.connect("folder-removed", self.on_folder_removed)

    def on_check_toggled(self, widget):
        self.state = self.checkable_label.check_button.get_active()


    def file_picked(self, widget, path: str):
        self.file_lister.add_file(path)


    def short_path(self, path: str) -> str:
        if len(path) <= self.short_path_length:
            return path
        else:
            return "..." + path[-(self.short_path_length-3):]

    def get_selected_files(self) -> list[str]:
        return self.file_lister.get_selected_files()

    def get_selected_folders(self) -> list[str]:
        return self.file_cherry_picker.get_selected_folders()

    def get_allowed_files(self) -> list[str]:
        if self.state:
            return self.file_lister.get_selected_files()
        else:
            return []

    def get_files_list(self) -> list[str]:
        return self.file_lister.get_files_list()

    def get_folders_list(self) -> list[str]:
        return self.file_cherry_picker.get_folder_list()

    def on_folder_added(self, widget, folder_path: str):
        print(f"Folder added: {folder_path}")

    def on_folder_removed(self, widget, folder_path: str):
        print(f"Folder removed: {folder_path}")
