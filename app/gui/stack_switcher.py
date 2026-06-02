from typing import Callable

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk


def _resolve_icon_name(*icon_names: str) -> str:
	theme = gtk.IconTheme.get_default()
	if theme is None:
		return icon_names[0]

	for icon_name in icon_names:
		if icon_name and theme.has_icon(icon_name):
			return icon_name
	return icon_names[0]


class StackSwitcher(gtk.Box):
    def __init__(self, on_show_main: Callable[[], None], on_show_settings: Callable[[], None]):
        super().__init__(orientation=gtk.Orientation.HORIZONTAL, spacing=4)
        self.get_style_context().add_class("halzi-stack-switcher")

        self._on_show_main = on_show_main
        self._on_show_settings = on_show_settings

        self._main_button = self._build_button(
            _resolve_icon_name("emoji-people-symbolic", "avatar-default-symbolic"),
            "Main page",
        )
        self._settings_button = self._build_button(
            _resolve_icon_name("system-settings", "preferences-system-symbolic"),
            "Settings",
        )

        self._main_button.connect("clicked", self._on_main_clicked)
        self._settings_button.connect("clicked", self._on_settings_clicked)

        self.pack_start(self._main_button, False, False, 0)
        self.pack_start(self._settings_button, False, False, 0)
        self.set_active_page("main")

    def _build_button(self, icon_name: str, tooltip: str) -> gtk.Button:
        button = gtk.Button()
        button.set_relief(gtk.ReliefStyle.NORMAL)
        button.set_focus_on_click(False)
        button.set_tooltip_text(tooltip)
        button.get_style_context().add_class("halzi-stack-switcher-button")
        image = gtk.Image.new_from_icon_name(icon_name, gtk.IconSize.BUTTON)
        button.add(image)
        return button

    def _on_main_clicked(self, _button: gtk.Button) -> None:
        self._on_show_main()
        self.set_active_page("main")

    def _on_settings_clicked(self, _button: gtk.Button) -> None:
        self._on_show_settings()
        self.set_active_page("settings")

    def set_active_page(self, page_name: str) -> None:
        main_active = page_name == "main"
        self._sync_button_state(self._main_button, main_active)
        self._sync_button_state(self._settings_button, not main_active)

    @staticmethod
    def _sync_button_state(button: gtk.Button, is_active: bool) -> None:
        context = button.get_style_context()
        if is_active:
            context.add_class("halzi-header-toggle-on")
        else:
            context.remove_class("halzi-header-toggle-on")
