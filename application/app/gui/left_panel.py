import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from pathlib import Path
from typing import Callable, Optional
import sys
from app import status_state
from app import core

from app.store import store

from .new_theme_dialog import NewThemeDialog


class ThemePanel(gtk.Box):
    def __init__(
        self,
        on_theme_changed: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.themes_list = core.list_themes()
        if self.themes_list:
            self.active_theme = self.themes_list[0]
        else:
            self.active_theme = None

        store.active_theme = self.active_theme
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

        self.theme_expander = gtk.Expander(label="Themes")
        self.theme_expander.get_style_context().add_class("halzi-themes-expander")
        self.theme_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        self.theme_expander.add(self.theme_box)
        self.box.pack_start(self.theme_expander, False, True, 0)

        self.add_button = gtk.Button(label="+ theme")
        self.add_button.get_style_context().add_class("halzi-add-theme-button")
        self.add_button.connect("clicked", self._on_add_theme_clicked)

        self.box.pack_start(self.theme_expander, False, True, 0)
        self.theme_list_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)

        self.theme_box.pack_start(self.add_button, False, False, 0)
        self.theme_box.pack_start(self.theme_list_box, False, False, 0)

        scroll.add(self.box)
        self.pack_start(scroll, True, True, 0)

        self.refresh()

    def _set_status(self, text: str) -> None:
        status_state.set_status(text)

    def _notify_theme_changed(self) -> None:
        if self.on_theme_changed is not None:
            self.on_theme_changed()

    def _set_theme_button_active_style(self, button: gtk.ToggleButton) -> None:
        context = button.get_style_context()
        if button.get_active():
            context.add_class("halzi-theme-button-on")
        else:
            context.remove_class("halzi-theme-button-on")

    def _sync_buttons_for_active_theme(self, active_theme) -> None:
        self._syncing = True
        for theme, button in self._theme_buttons.items():
            button.set_active(theme == active_theme)
            self._set_theme_button_active_style(button)
        self._syncing = False

    def _on_theme_toggled(self, button: gtk.ToggleButton, theme) -> None:
        if self._syncing:
            return

        if not button.get_active():
            # Keep one theme always active.
            if theme == self.active_theme:
                self._syncing = True
                button.set_active(True)
                self._syncing = False
            self._set_theme_button_active_style(button)
            return

        try:
            self.active_theme = theme
            store.active_theme = theme
            self._sync_buttons_for_active_theme(self.active_theme)
            self._notify_theme_changed()
            if not self.active_theme:
                self._set_status("No active theme.")
            else:
                self._set_status(f"Active theme: {self.active_theme.q.name}")
        except Exception as exc:
            self._set_status(f"Theme selection failed: {exc}")

    def _on_delete_theme_clicked(self, _button: gtk.Button, theme) -> None:
        try:
            core.delete_theme(theme)
            store.active_theme = None
            self.refresh()
            self._notify_theme_changed()
            self._set_status(f"Theme deleted: {theme.q.name}")
        except Exception as exc:
            self._set_status(f"Theme delete failed: {exc}")

    def _on_add_theme_clicked(self, _button: gtk.Button) -> None:

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
            self.themes_list.append(created)
            self.refresh()
            self._notify_theme_changed()
            self._set_status(f"Theme created: {created.q.name}")
        except Exception as exc:
            self._set_status(f"Theme creation failed: {exc}")

    def refresh(self) -> None:
        while self.theme_list_box.get_children():
            child = self.theme_list_box.get_children()[0]
            self.theme_list_box.remove(child)

        self._theme_buttons = {}

        self.themes_list = core.list_themes()

        if self.active_theme not in self.themes_list:
            self.active_theme = self.themes_list[0] if self.themes_list else None
        store.active_theme = self.active_theme

        for theme in self.themes_list:
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)

            theme_button = gtk.ToggleButton(label=theme.q.name)
            theme_button.set_hexpand(True)
            theme_button.set_halign(gtk.Align.FILL)
            theme_button.get_style_context().add_class("halzi-theme-button")
            theme_button.connect("toggled", self._on_theme_toggled, theme)
            row.pack_start(theme_button, True, True, 0)

            delete_button = gtk.Button(label="X")
            delete_button.get_style_context().add_class("halzi-theme-delete-button")
            delete_button.connect("clicked", self._on_delete_theme_clicked, theme)
            row.pack_start(delete_button, False, False, 0)

            self.theme_list_box.pack_start(row, False, False, 0)
            self._theme_buttons[theme] = theme_button

        self._sync_buttons_for_active_theme(self.active_theme)
        self.show_all()


def build_left_panel(
    on_theme_changed: Optional[Callable[[], None]] = None,
) -> gtk.Widget:
    return ThemePanel(on_theme_changed=on_theme_changed)
