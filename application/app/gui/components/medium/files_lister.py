import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GObject

class FileListerRow(Gtk.ListBoxRow):
    """
    A custom row representing a single file with its path,
    a selection checkbox, and a dedicated removal button.
    """
    def __init__(self, full_path, short_path_length=120):
        super().__init__()
        self.full_path = full_path
        self.short_path_length = short_path_length

        # Main horizontal container for the row elements
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        hbox.set_margin_start(5)
        hbox.set_margin_end(5)
        self.add(hbox)

        # 1. Path Label (left-aligned, expands to occupy available space)
        self.label = Gtk.Label(label=self.short_path(self.full_path), xalign=0)
        hbox.pack_start(self.label, True, True, 0)

        # 2. Checkbox (fixed width)
        self.checkbox = Gtk.CheckButton()
        hbox.pack_start(self.checkbox, False, False, 0)

        # 3. Remover Button (fixed width, native button with system icon)
        self.remove_button = Gtk.Button()
        self.remove_button.set_relief(Gtk.ReliefStyle.NONE) # Makes it look like a flat icon
        icon = Gtk.Image.new_from_icon_name("window-close", Gtk.IconSize.BUTTON)
        self.remove_button.add(icon)
        hbox.pack_start(self.remove_button, False, False, 0)

    def short_path(self, path):
        if len(path) > self.short_path_length:
            return f"...{path[-(self.short_path_length - 3):]}"
        return path


class FileListerHeader(Gtk.Box):
    """
    Top header bar providing 'Select All' and 'Remove All' controls.
    """
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.set_margin_start(5)
        self.set_margin_end(5)

        # Title placeholder matching the path column layout
        title_label = Gtk.Label(label="File Path", xalign=0)
        self.pack_start(title_label, True, True, 0)

        # 'Select All' Checkbox
        self.select_all_check = Gtk.CheckButton()
        self.select_all_check.set_tooltip_text("Select/Deselect All")
        self.pack_start(self.select_all_check, False, False, 0)

        # 'Remove All' Button
        self.remove_all_button = Gtk.Button()
        self.remove_all_button.set_relief(Gtk.ReliefStyle.NONE)
        icon = Gtk.Image.new_from_icon_name("edit-clear", Gtk.IconSize.BUTTON)
        self.remove_all_button.add(icon)
        self.remove_all_button.set_tooltip_text("Remove All Files")
        self.pack_start(self.remove_all_button, False, False, 0)


class FileLister(Gtk.Box):
    __gsignals__ = {
        "removed": (
            GObject.SignalFlags.RUN_FIRST,
            None,
            (str,),  # Emits the absolute path of the removed file
        ),
    }

    def __init__(self, files=None, short_path_length=120):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        self.short_path_length = short_path_length

        # 1. Add Header Controls at the top
        self.header = FileListerHeader()
        self.header.select_all_check.connect("toggled", self.on_select_all_toggled)
        self.header.remove_all_button.connect("clicked", self.on_remove_all_clicked)
        self.pack_start(self.header, False, False, 0)

        # separator line between header and content
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.pack_start(separator, False, False, 0)

        # 2. Setup Scrollable Area
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(self.scrolled_window, True, True, 0)

        # 3. Setup ListBox Container
        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE) # Row selection disabled, we use checkboxes instead
        self.scrolled_window.add(self.list_box)

        # Flag to prevent recursion loops during batch toggle operations
        self._is_updating_toggles = False

        # Populate initial files if provided
        if files:
            for f in files:
                self.add_file(f)

        self.show_all()

    def add_file(self, path):
        """ Public method to dynamically insert a new file row """
        if path in [child.full_path for child in self.list_box.get_children()]:
            return  # Avoid adding duplicate paths
        row = FileListerRow(path, self.short_path_length)
        # Connect row button and checkbox signals natively
        row.remove_button.connect("clicked", self.on_row_remove_clicked, row)
        row.checkbox.connect("toggled", self.on_row_checkbox_toggled)

        self.list_box.add(row)
        self.show_all()

    def on_row_remove_clicked(self, button, row):
        """ Handles individual row deletion """
        file_path = row.full_path
        self.list_box.remove(row)
        row.destroy()
        self.emit("removed", file_path)

    def on_row_checkbox_toggled(self, checkbox):
        """ Updates Header state when a row checkbox status changes manually """
        if self._is_updating_toggles:
            return

        children = self.list_box.get_children()
        if not children:
            return

        # Check if all row checkboxes are currently checked
        all_checked = all(child.checkbox.get_active() for child in children)

        self._is_updating_toggles = True
        self.header.select_all_check.set_active(all_checked)
        self._is_updating_toggles = False

    def on_select_all_toggled(self, header_checkbox):
        """ Toggles all row checkboxes simultaneously """
        if self._is_updating_toggles:
            return

        self._is_updating_toggles = True
        target_state = header_checkbox.get_active()

        for child in self.list_box.get_children():
            child.checkbox.set_active(target_state)

        self._is_updating_toggles = False

    def on_remove_all_clicked(self, button):
        """ Clears all rows inside the list box container """
        for child in self.list_box.get_children():
            file_path = child.full_path
            self.list_box.remove(child)
            child.destroy()
            self.emit("removed", file_path)

        self.header.select_all_check.set_active(False)

    def get_selected_files(self):
        """ Returns a list of absolute paths for all currently selected files """
        selected_files = []
        for child in self.list_box.get_children():
            if child.checkbox.get_active():
                selected_files.append(child.full_path)
        return selected_files

    def get_files_list(self):
        """ Returns a list of absolute paths for all files currently in the list, regardless of selection state """
        return [child.full_path for child in self.list_box.get_children()]

    def clear_files(self):
        """ Removes all file rows from the list box container """
        for child in self.list_box.get_children():
            self.list_box.remove(child)
            child.destroy()
        self.header.select_all_check.set_active(False)