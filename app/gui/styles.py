from pathlib import Path

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk, Gdk


def load_css() -> None:
    css_path = Path(__file__).with_name("style.css")
    if not css_path.exists():
        return

    provider = gtk.CssProvider()
    provider.load_from_path(str(css_path))
    screen = Gdk.Screen.get_default()
    gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
