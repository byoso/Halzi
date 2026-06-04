import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from typing import Callable, Optional
from app import status_state
from app import core
from app.silly_engine.silly_orm.item import QItem

from app.store import store


def build_right_panel(on_memory_saved: Optional[Callable[[QItem], None]] = None) -> gtk.Widget:
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
        history_snapshot = list(core.session_memory)
        source_session = store.active_session
        if not history_snapshot:
            set_status("No active conversation to memorize.")
            return

        if source_session is None:
            set_status("No active session selected. Create or select a session first.")
            return

        try:
            assert store.active_theme is not None
            saved_session = core.save_memory(
                history_snapshot,
                theme=store.active_theme,
                topic=source_session.q.name,
                source_session=source_session,
            )
            if saved_session is not None and on_memory_saved is not None:
                on_memory_saved(saved_session)
            set_status(f"Conversation memorized in theme: {store.active_theme.q.name}")
        except Exception as exc:
            set_status(f"Memorize failed: {exc}")

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
