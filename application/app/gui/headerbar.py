from typing import Optional, Tuple
from pathlib import Path
import subprocess

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk

from app.config import APP_NAME

def _sync_toggle_style(button: gtk.ToggleButton) -> None:
    context = button.get_style_context()
    if button.get_active():
        context.add_class("halzi-header-toggle-on")
    else:
        context.remove_class("halzi-header-toggle-on")


def _on_toggle(button: gtk.ToggleButton) -> None:
    _sync_toggle_style(button)


def _build_toggle_button(icon_name: str) -> gtk.ToggleButton:
    button = gtk.ToggleButton()
    button.set_relief(gtk.ReliefStyle.NORMAL)
    button.set_focus_on_click(False)
    button.get_style_context().add_class("halzi-header-toggle")

    icon = gtk.Image.new_from_icon_name(icon_name, gtk.IconSize.BUTTON)
    button.add(icon)

    button.connect("toggled", _on_toggle)
    _sync_toggle_style(button)
    return button


def _open_memory_folder() -> None:
    project_memory = Path("~/.local/share/geninstaller-applications/.data/halzimir").expanduser()
    memory_dir = project_memory / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["xdg-open", str(memory_dir)], check=False)


def _build_folder_button() -> gtk.Button:
    button = gtk.Button()
    button.set_relief(gtk.ReliefStyle.NORMAL)
    button.set_focus_on_click(False)
    icon = gtk.Image.new_from_icon_name("folder-symbolic", gtk.IconSize.BUTTON)
    button.add(icon)
    button.connect("clicked", lambda _btn: _open_memory_folder())
    return button


def build_headerbar(
    title: str = f"{APP_NAME} GUI",
    stack_switcher: Optional[gtk.Widget] = None,
) -> Tuple[gtk.HeaderBar, gtk.Button, gtk.ToggleButton, gtk.ToggleButton]:
    header = gtk.HeaderBar()
    header.set_show_close_button(True)
    header.props.title = title

    folder_button = _build_folder_button()
    mic_button = _build_toggle_button("audio-input-microphone-symbolic")
    speaker_button = _build_toggle_button("audio-volume-high-symbolic")

    header.pack_start(folder_button)
    if stack_switcher is not None:
        header.pack_start(stack_switcher)
    header.pack_end(speaker_button)
    header.pack_end(mic_button)

    return header, folder_button, mic_button, speaker_button
