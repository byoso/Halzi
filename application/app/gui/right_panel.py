import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk, GLib
import threading
from pathlib import Path
import sys
from app import status_state
from app import core

from app.store import store


def build_right_panel() -> gtk.Widget:
    panel = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)
    panel.get_style_context().add_class("halzi-panel")
    panel.set_hexpand(True)
    panel.set_vexpand(True)

    box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)
    box.set_margin_start(10)
    box.set_margin_end(10)

    def set_status(text: str) -> None:
        status_state.set_status(text)

    def on_memorize_clicked(_button: gtk.Button) -> None:
        history_snapshot = core.session_memory
        if not history_snapshot:
            set_status("No active conversation to memorize.")
            return

        def worker():
            try:
                _, topic = core.process_prompt(
                    "Answer with only 3 word to describe the topic of our last conversation:",
                    display=False,
                    record=False,
                )

                # Save memory and update status on GTK thread
                def _save_and_status():
                    try:
                        assert store.active_theme is not None
                        core.save_memory(history_snapshot, theme=store.active_theme, topic=topic)
                        set_status(f"Conversation memorized in theme: {store.active_theme.q.name}")
                    except Exception as exc:
                        set_status(f"Memorize failed: {exc}")
                    return False

                GLib.idle_add(_save_and_status)
            except Exception as exc:
                GLib.idle_add(set_status, f"Memorize failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    memorize_button = gtk.Button(label="memorize session")
    memorize_button.get_style_context().add_class("halzi-memorize-button")
    memorize_button.connect("clicked", on_memorize_clicked)
    box.pack_start(memorize_button, False, False, 0)

    for text in [
        "Future option A",
        "Future option B",
        "Future option C",
        "Future option D",
    ]:
        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class("halzi-option-row")
        label = gtk.Label(label=text)
        label.set_xalign(0.0)
        row.pack_start(label, True, True, 0)
        box.pack_start(row, False, False, 0)

    panel.pack_start(box, True, True, 0)
    return panel
