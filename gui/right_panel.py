import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from pathlib import Path
from typing import Callable, Optional
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_DIR = PROJECT_ROOT / "ollama"
if str(OLLAMA_DIR) not in sys.path:
    sys.path.append(str(OLLAMA_DIR))

try:
    import core  # type: ignore
except Exception:
    core = None


def build_right_panel(on_status: Optional[Callable[[str], None]] = None) -> gtk.Widget:
    panel = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)
    panel.get_style_context().add_class("jarvis-panel")
    panel.set_hexpand(True)
    panel.set_vexpand(True)

    box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(10)
    box.set_margin_bottom(10)
    box.set_margin_start(10)
    box.set_margin_end(10)

    def set_status(text: str) -> None:
        if on_status is not None:
            on_status(text)

    def on_memorize_clicked(_button: gtk.Button) -> None:
        if core is None:
            set_status("Memorize failed: cannot import ollama core.")
            return

        history_snapshot = list(core.session_memory)
        if not history_snapshot:
            set_status("No active conversation to memorize.")
            return

        try:
            active_theme = core.get_active_theme()
            _, topic = core.process_prompt(
                "Answer with only 3 word to describe the topic of our last conversation:",
                display=False,
                record=False,
            )
            core.save_memory(history_snapshot, topic, theme=active_theme)
            set_status(f"Conversation memorized in theme: {active_theme}")
        except Exception as exc:
            set_status(f"Memorize failed: {exc}")

    memorize_button = gtk.Button(label="memorize session")
    memorize_button.get_style_context().add_class("jarvis-memorize-button")
    memorize_button.connect("clicked", on_memorize_clicked)
    box.pack_start(memorize_button, False, False, 0)

    for text in [
        "Future option A",
        "Future option B",
        "Future option C",
        "Future option D",
    ]:
        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        row.get_style_context().add_class("jarvis-option-row")
        label = gtk.Label(label=text)
        label.set_xalign(0.0)
        row.pack_start(label, True, True, 0)
        box.pack_start(row, False, False, 0)

    panel.pack_start(box, True, True, 0)
    return panel
