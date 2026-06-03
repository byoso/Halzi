import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from pathlib import Path
from typing import Callable, Optional
import sys
from app import status_state

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_DIR = PROJECT_ROOT / "ollama"
if str(OLLAMA_DIR) not in sys.path:
    sys.path.append(str(OLLAMA_DIR))

try:
    import core  # type: ignore
except Exception:
    core = None

from .new_theme_dialog import NewThemeDialog


class ThemePanel(gtk.Box):
    def __init__(
        self,
        on_theme_changed: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("halzi-panel")
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.on_theme_changed = on_theme_changed
        self._syncing = False
        self._theme_buttons = {}

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class("halzi-scroll")
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        self.box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.box.set_margin_top(10)
        self.box.set_margin_bottom(10)
        self.box.set_margin_start(10)
        self.box.set_margin_end(10)

        self.add_button = gtk.Button(label="+ theme")
        self.add_button.get_style_context().add_class("halzi-add-theme-button")
        self.add_button.connect("clicked", self._on_add_theme_clicked)
        self.box.pack_start(self.add_button, False, False, 0)

        self.theme_list_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        self.box.pack_start(self.theme_list_box, False, False, 0)

        scroll.add(self.box)
        self.pack_start(scroll, True, True, 0)

        self.refresh()

    def _set_status(self, text: str) -> None:
        status_state.set_status(text)

    def _notify_theme_changed(self, theme: str) -> None:
        if self.on_theme_changed is not None:
            self.on_theme_changed(theme)

    def _set_theme_button_active_style(self, button: gtk.ToggleButton) -> None:
        context = button.get_style_context()
        if button.get_active():
            context.add_class("halzi-theme-button-on")
        else:
            context.remove_class("halzi-theme-button-on")

    def _sync_buttons_for_active_theme(self, active_theme: str) -> None:
        self._syncing = True
        for theme, button in self._theme_buttons.items():
            button.set_active(theme == active_theme)
            self._set_theme_button_active_style(button)
        self._syncing = False

    def _on_theme_toggled(self, button: gtk.ToggleButton, theme: str) -> None:
        if core is None or self._syncing:
            return

        if not button.get_active():
            # Keep one theme always active.
            if theme == core.get_active_theme():
                self._syncing = True
                button.set_active(True)
                self._syncing = False
            self._set_theme_button_active_style(button)
            return

        try:
            selected = core.set_active_theme(theme)
            self._sync_buttons_for_active_theme(selected)
            self._notify_theme_changed(selected)
            self._set_status(f"Active theme: {selected}")
        except Exception as exc:
            self._set_status(f"Theme selection failed: {exc}")

    def _on_delete_theme_clicked(self, _button: gtk.Button, theme: str) -> None:
        if core is None:
            self._set_status("Theme delete failed: cannot import ollama core.")
            return

        try:
            previous_active = core.get_active_theme()
            new_active = core.delete_theme(theme)
            self.refresh(active_theme=new_active)
            if new_active != previous_active:
                self._notify_theme_changed(new_active)
            self._set_status(f"Theme deleted: {theme}")
        except Exception as exc:
            self._set_status(f"Theme delete failed: {exc}")

    def _on_add_theme_clicked(self, _button: gtk.Button) -> None:
        if core is None:
            self._set_status("Theme creation failed: cannot import ollama core.")
            return

        parent = self.get_toplevel()
        if not isinstance(parent, gtk.Window):
            self._set_status("Theme creation failed: parent window not found.")
            return

        dialog = NewThemeDialog(parent)
        response = dialog.run()
        raw_name = dialog.get_theme_name()
        dialog.destroy()

        if response != gtk.ResponseType.OK:
            return

        try:
            created = core.create_theme(raw_name)
            active = core.set_active_theme(created)
            self.refresh(active_theme=active)
            self._notify_theme_changed(active)
            self._set_status(f"Theme created: {created}")
        except Exception as exc:
            self._set_status(f"Theme creation failed: {exc}")

    def refresh(self, active_theme: Optional[str] = None) -> None:
        while self.theme_list_box.get_children():
            child = self.theme_list_box.get_children()[0]
            self.theme_list_box.remove(child)

        self._theme_buttons = {}

        if core is None:
            info = gtk.Label(label="Unable to load themes.")
            info.set_xalign(0.0)
            self.theme_list_box.pack_start(info, False, False, 0)
            self.show_all()
            return

        themes = core.list_themes()
        active = active_theme or core.get_active_theme()
        if active not in themes:
            active = core.set_active_theme("just_chat")

        for theme in themes:
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)

            theme_button = gtk.ToggleButton(label=theme)
            theme_button.set_hexpand(True)
            theme_button.set_halign(gtk.Align.FILL)
            theme_button.get_style_context().add_class("halzi-theme-button")
            theme_button.connect("toggled", self._on_theme_toggled, theme)
            row.pack_start(theme_button, True, True, 0)

            if theme != "just_chat":
                delete_button = gtk.Button(label="X")
                delete_button.get_style_context().add_class("halzi-theme-delete-button")
                delete_button.connect("clicked", self._on_delete_theme_clicked, theme)
                row.pack_start(delete_button, False, False, 0)

            self.theme_list_box.pack_start(row, False, False, 0)
            self._theme_buttons[theme] = theme_button

        self._sync_buttons_for_active_theme(active)
        self.show_all()


def build_left_panel(
    on_theme_changed: Optional[Callable[[str], None]] = None,
) -> gtk.Widget:
    return ThemePanel(on_theme_changed=on_theme_changed)
