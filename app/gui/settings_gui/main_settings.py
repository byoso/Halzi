from dataclasses import asdict, fields

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk


from app.database.models.models_settings import SettingsModel
from app.gui.error_dialogue import show_error_dialog
from app.settings import get_settings, update_settings
from app.ollama.core import list_installed_models


FIELD_CHOICES = {
    "voice_gender": ["f", "m"],
    "voice_language": ["fr", "en"],
    "language": ["fr", "en"],
    "whisper_model_size": ["tiny", "base", "small", "medium", "large"],
    "device": ["cpu", "cuda"],
    "compute_type": ["int8", "float16", "float32"],
    "ollama_model": list_installed_models(),
}


EDITABLE_FIELDS = [
    field.name
    for field in fields(SettingsModel)
    if field.name != "_id" and not field.name.startswith("_")
]


def _humanize(name: str) -> str:
    return name.replace("_", " ").strip().title()


class MainSettingsPage(gtk.Box):
    def __init__(self):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=10)

        self.get_style_context().add_class("halzi-settings-page")
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)

        all_defaults = asdict(SettingsModel())
        self._default_values = {name: all_defaults[name] for name in EDITABLE_FIELDS}
        self._field_types = {name: type(value) for name, value in self._default_values.items()}
        self._inputs = {}
        self._original_values = {}

        title = gtk.Label(label="Settings")
        title.set_xalign(0.0)
        title.get_style_context().add_class("halzi-settings-title")
        self.pack_start(title, False, False, 0)

        scrolled = gtk.ScrolledWindow()
        scrolled.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)

        form_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        form_box.set_hexpand(True)
        form_box.set_vexpand(True)
        form_box.get_style_context().add_class("halzi-panel")
        form_box.set_margin_top(4)
        form_box.set_margin_bottom(4)
        form_box.set_margin_start(4)
        form_box.set_margin_end(4)

        grid = gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(8)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)

        for row, field_name in enumerate(EDITABLE_FIELDS):
            label = gtk.Label(label=f"{_humanize(field_name)}:")
            label.set_xalign(0.0)
            label.get_style_context().add_class("halzi-settings-field-label")

            input_widget = self._build_input_widget(field_name, self._default_values[field_name])
            input_widget.set_hexpand(True)
            self._inputs[field_name] = input_widget

            grid.attach(label, 0, row, 1, 1)
            grid.attach(input_widget, 1, row, 1, 1)

        form_box.pack_start(grid, False, False, 0)
        scrolled.add(form_box)
        self.pack_start(scrolled, True, True, 0)

        actions = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_halign(gtk.Align.END)

        self.default_button = gtk.Button(label="Default")
        self.cancel_button = gtk.Button(label="Cancel")
        self.validate_button = gtk.Button(label="Validate")

        self.default_button.get_style_context().add_class("halzi-settings-button")
        self.cancel_button.get_style_context().add_class("halzi-settings-button")
        self.validate_button.get_style_context().add_class("halzi-settings-button-primary")

        self.default_button.connect("clicked", self._on_default_clicked)
        self.cancel_button.connect("clicked", self._on_cancel_clicked)
        self.validate_button.connect("clicked", self._on_validate_clicked)

        actions.pack_start(self.default_button, False, False, 0)
        actions.pack_start(self.cancel_button, False, False, 0)
        actions.pack_start(self.validate_button, False, False, 0)
        self.pack_start(actions, False, False, 0)

        self.reload_from_database()

    def _build_input_widget(self, field_name: str, default_value):
        if field_name in FIELD_CHOICES:
            combo = gtk.ComboBoxText()
            for choice in FIELD_CHOICES[field_name]:
                combo.append_text(str(choice))
            combo.set_active(0)
            return combo

        if isinstance(default_value, int):
            spin = gtk.SpinButton()
            spin.set_numeric(True)
            spin.set_increments(1, 10)
            spin.set_range(0, 1_000_000)
            return spin

        if isinstance(default_value, float):
            spin = gtk.SpinButton()
            spin.set_digits(3)
            spin.set_numeric(True)
            spin.set_increments(0.1, 1.0)
            spin.set_range(0.0, 10_000.0)
            return spin

        entry = gtk.Entry()
        return entry

    def reload_from_database(self) -> None:
        settings = get_settings()
        all_values = asdict(settings)
        self._original_values = {name: all_values[name] for name in EDITABLE_FIELDS}
        self._apply_values(self._original_values)

    def _apply_values(self, values: dict) -> None:
        for field_name, value in values.items():
            widget = self._inputs.get(field_name)
            if widget is None:
                continue

            if isinstance(widget, gtk.ComboBoxText):
                options = FIELD_CHOICES.get(field_name, [])
                try:
                    widget.set_active(options.index(str(value)))
                except ValueError:
                    widget.set_active(0 if options else -1)
                continue

            if isinstance(widget, gtk.SpinButton):
                widget.set_value(float(value))
                continue

            if isinstance(widget, gtk.Entry):
                widget.set_text(str(value))

    def _collect_values(self) -> dict:
        data = {}
        for field_name, widget in self._inputs.items():
            if isinstance(widget, gtk.ComboBoxText):
                value = widget.get_active_text()
                if value is None:
                    raise ValueError(f"No selected value for field: {field_name}")
                data[field_name] = value
                continue

            if isinstance(widget, gtk.SpinButton):
                if self._field_types.get(field_name) is int:
                    data[field_name] = int(widget.get_value_as_int())
                else:
                    data[field_name] = float(widget.get_value())
                continue

            if isinstance(widget, gtk.Entry):
                data[field_name] = widget.get_text().strip()

        return data

    def _on_default_clicked(self, _button: gtk.Button) -> None:
        self._apply_values(self._default_values)

    def _on_cancel_clicked(self, _button: gtk.Button) -> None:
        self._apply_values(self._original_values)

    def _on_validate_clicked(self, _button: gtk.Button) -> None:
        try:
            values = self._collect_values()
            update_settings(**values)
            self._original_values = dict(values)
            self._show_restart_info_dialog()
        except Exception as exc:
            show_error_dialog(str(exc), title="Settings update failed")

    def _show_restart_info_dialog(self) -> None:
        dialog = gtk.MessageDialog(
            transient_for=self.get_toplevel() if isinstance(self.get_toplevel(), gtk.Window) else None,
            flags=0,
            type=gtk.MessageType.INFO,
            buttons=gtk.ButtonsType.OK,
            message_format="Settings saved. Changes will be applied after restarting the application.",
        )
        dialog.set_title("Restart required")
        dialog.run()
        dialog.destroy()


def build_settings_page() -> MainSettingsPage:
    return MainSettingsPage()
