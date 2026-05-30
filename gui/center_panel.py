import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk, Gdk, GLib
from pathlib import Path
import sys
import threading
from typing import Callable, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OLLAMA_DIR = PROJECT_ROOT / "ollama"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))
if str(OLLAMA_DIR) not in sys.path:
    sys.path.append(str(OLLAMA_DIR))

try:
    from core import process_prompt  # type: ignore
except Exception:
    process_prompt = None


class CenterPanel(gtk.Box):
    def __init__(
        self,
        on_status: Optional[Callable[[str], None]] = None,
        on_voice_stopped: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("jarvis-panel")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_status = on_status
        self.on_voice_stopped = on_voice_stopped
        self.voice_active = False
        self.voice_stop_event: Optional[threading.Event] = None
        self.voice_thread: Optional[threading.Thread] = None
        self.is_processing_response = False

        split = gtk.Paned.new(gtk.Orientation.VERTICAL)
        split.set_hexpand(True)
        split.set_vexpand(True)

        self.top_scroll = gtk.ScrolledWindow()
        self.top_scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        self.top_scroll.get_style_context().add_class("jarvis-scroll")
        self.top_scroll.set_hexpand(True)
        self.top_scroll.set_vexpand(True)

        self.top_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        self.top_box.set_margin_top(12)
        self.top_box.set_margin_bottom(12)
        self.top_box.set_margin_start(12)
        self.top_box.set_margin_end(12)
        self.top_box.get_style_context().add_class("jarvis-output")

        self.top_scroll.add(self.top_box)
        split.add1(self.top_scroll)

        bottom_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        bottom_box.set_margin_top(10)
        bottom_box.set_margin_bottom(10)
        bottom_box.set_margin_start(10)
        bottom_box.set_margin_end(10)
        bottom_box.get_style_context().add_class("jarvis-input-area")

        input_label = gtk.Label(label="User input")
        input_label.set_xalign(0.0)
        input_label.get_style_context().add_class("jarvis-input-label")

        self.input_view = gtk.TextView()
        self.input_view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
        self.input_view.get_style_context().add_class("jarvis-input-text")

        input_scroll = gtk.ScrolledWindow()
        input_scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        input_scroll.set_hexpand(True)
        input_scroll.set_vexpand(True)
        input_scroll.add(self.input_view)

        bottom_box.pack_start(input_label, False, False, 0)
        bottom_box.pack_start(input_scroll, True, True, 0)

        split.add2(bottom_box)
        split.set_position(500)

        self.pack_start(split, True, True, 0)
        self.clear_conversation_view()
        self.input_view.connect("key-press-event", self.on_input_key_press)

    def scroll_to_bottom(self) -> bool:
        vadj = self.top_scroll.get_vadjustment()
        vadj.set_value(max(0.0, vadj.get_upper() - vadj.get_page_size()))
        return False

    def clear_conversation_view(self) -> None:
        for child in self.top_box.get_children():
            self.top_box.remove(child)

        self.output_hint = gtk.Label(label="Scrollable area for LLM responses")
        self.output_hint.set_xalign(0.0)
        self.output_hint.set_line_wrap(True)
        self.output_hint.get_style_context().add_class("jarvis-output-text")
        self.top_box.pack_start(self.output_hint, False, False, 0)
        self.top_box.show_all()
        GLib.idle_add(self.scroll_to_bottom)

    def append_message(self, text: str, is_user: bool) -> None:
        if self.output_hint.get_parent() is not None:
            self.top_box.remove(self.output_hint)

        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=0)
        row.set_hexpand(True)

        label = gtk.Label(label=text)
        label.set_line_wrap(True)
        label.set_selectable(True)
        label.set_xalign(1.0 if is_user else 0.0)
        label.set_halign(gtk.Align.END if is_user else gtk.Align.START)
        label.get_style_context().add_class("jarvis-output-text")

        if is_user:
            row.pack_end(label, False, False, 6)
        else:
            row.pack_start(label, False, False, 6)

        self.top_box.pack_start(row, False, False, 0)
        self.top_box.show_all()
        GLib.idle_add(self.scroll_to_bottom)

    def submit_prompt(self) -> None:
        buffer_ = self.input_view.get_buffer()
        start_iter = buffer_.get_start_iter()
        end_iter = buffer_.get_end_iter()
        prompt = buffer_.get_text(start_iter, end_iter, True).strip()

        if not prompt:
            return

        if self.on_status is not None:
            self.on_status("User input sent.")
            # Force UI refresh before the blocking LLM request starts.
            while gtk.events_pending():
                gtk.main_iteration_do(False)

        self.append_message(prompt, is_user=True)
        buffer_.set_text("")

        if process_prompt is None:
            self.append_message("Error: unable to import ollama core.", is_user=False)
            return

        try:
            self.is_processing_response = True
            _, response = process_prompt(prompt, display=False)
            self.append_message(response, is_user=False)
        except Exception as exc:
            self.append_message(f"Error: {exc}", is_user=False)
        finally:
            self.is_processing_response = False

    def start_voice_input(self) -> None:
        if self.voice_active:
            return

        self.voice_active = True
        self.voice_stop_event = threading.Event()
        self.voice_thread = threading.Thread(target=self._voice_input_loop, daemon=True)
        self.voice_thread.start()
        if self.on_status is not None:
            self.on_status("Voice mode active.")

    def stop_voice_input(self) -> None:
        if self.voice_stop_event is not None:
            self.voice_stop_event.set()

    def _voice_input_loop(self) -> None:
        try:
            from vad import load_vad, iter_voice_prompts
        except Exception as exc:
            GLib.idle_add(self._on_voice_error, f"Voice mode unavailable: {exc}")
            return

        skipped_while_busy_notified = False

        try:
            vad_iterator = load_vad()
            for transcript in iter_voice_prompts(vad_iterator, stop_event=self.voice_stop_event):
                if self.voice_stop_event is not None and self.voice_stop_event.is_set():
                    break

                prompt = transcript.strip()
                if not prompt:
                    continue

                if self.is_processing_response:
                    if not skipped_while_busy_notified and self.on_status is not None:
                        GLib.idle_add(self.on_status, "Voice ignored: response in progress.")
                        skipped_while_busy_notified = True
                    continue

                skipped_while_busy_notified = False
                GLib.idle_add(self._submit_voice_prompt, prompt)
        except Exception as exc:
            GLib.idle_add(self._on_voice_error, f"Voice error: {exc}")
        finally:
            GLib.idle_add(self._finalize_voice_stopped)

    def _submit_voice_prompt(self, prompt: str) -> bool:
        buffer_ = self.input_view.get_buffer()
        buffer_.set_text(prompt)
        self.submit_prompt()
        return False

    def _on_voice_error(self, message: str) -> bool:
        if self.on_status is not None:
            self.on_status(message)
        return False

    def _finalize_voice_stopped(self) -> bool:
        self.voice_active = False
        self.voice_stop_event = None
        self.voice_thread = None
        if self.on_status is not None:
            self.on_status("Voice mode stopped.")
        if self.on_voice_stopped is not None:
            self.on_voice_stopped()
        return False

    def on_input_key_press(self, _widget: gtk.Widget, event: Gdk.EventKey) -> bool:
        is_enter = event.keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter)
        if not is_enter:
            return False

        if event.state & Gdk.ModifierType.SHIFT_MASK:
            return False

        self.submit_prompt()
        return True


def build_center_panel(
    on_status: Optional[Callable[[str], None]] = None,
    on_voice_stopped: Optional[Callable[[], None]] = None,
) -> gtk.Widget:
    return CenterPanel(on_status=on_status, on_voice_stopped=on_voice_stopped)
