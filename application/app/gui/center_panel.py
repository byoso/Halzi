import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk, Gdk, GLib
from pathlib import Path
import sys
import threading
import queue
import re
from typing import Callable, Optional, List, Tuple, Any
import traceback
from app import status_state
from app.silly_engine.text_tools import sanitize_for_tts
from app.gui.markdown_render import markdown_to_pango
from app.core import process_prompt
from app.logger import logger

try:
    from app.piper.main_piper import text_to_speech  # type: ignore
except Exception:
    text_to_speech = None
    logger.warning("Piper TTS functions are not available. TTS features will be disabled.")


try:
    from app.piper.main_piper import stop_all_playback  # type: ignore
except Exception:
    stop_all_playback = None
    logger.warning("Piper stop all playback import failed.")
try:
    from app.piper.main_piper import synthesize_text_to_audio, play_audio_buffer  # type: ignore
except Exception:
    synthesize_text_to_audio = None
    play_audio_buffer = None
    logger.warning("Piper synthesize/playback functions are not available. TTS features will be disabled.")
try:
    from app.vad.vad import set_tts_active  # type: ignore
except Exception:
    set_tts_active = None
    logger.warning("VAD TTS active function import failed. VAD-TTS integration will be disabled.")
try:
    from app.vad.vad import pause_audio_capture, resume_audio_capture  # type: ignore
except Exception:
    pause_audio_capture = None
    resume_audio_capture = None
    logger.warning("VAD audio capture control functions are not available. VAD-TTS integration will be disabled.")

class CenterPanel(gtk.Box):
    def __init__(
        self,
        on_voice_stopped: Optional[Callable[[], None]] = None,
        get_speaker_active: Optional[Callable[[], bool]] = None,
        get_header_mic_active: Optional[Callable[[], bool]] = None,
        set_header_mic_active: Optional[Callable[[bool], None]] = None,
    ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("halzi-panel")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_voice_stopped = on_voice_stopped
        self.get_speaker_active = get_speaker_active
        self.get_header_mic_active = get_header_mic_active
        self.set_header_mic_active = set_header_mic_active
        self.header_mic_active = bool(get_header_mic_active()) if get_header_mic_active is not None else False
        self.voice_active = False
        self.voice_stop_event: Optional[threading.Event] = None
        self.voice_thread: Optional[threading.Thread] = None
        self.response_thread: Optional[threading.Thread] = None
        self.tts_thread: Optional[threading.Thread] = None
        self.tts_queue: Optional[queue.Queue[Optional[str]]] = None
        self.tts_audio_queue: Optional[queue.Queue[Optional[Tuple[Any, int]]]] = None
        self._tts_user_interrupt_requested = threading.Event()
        self._tts_user_interrupt_done = threading.Event()
        self._response_submit_lock = threading.Lock()
        self._shutdown_requested = threading.Event()
        self.is_processing_response = False
        self.mini_mic_mode = False
        self._mini_mic_button: Optional[gtk.ToggleButton] = None
        self._streaming_assistant_label: Optional[gtk.Label] = None
        self._streaming_target_text = ""
        self._streaming_display_text = ""
        self._streaming_done = False
        self._typing_source_id: Optional[int] = None
        self._typing_step_chars = 3
        self._typing_interval_ms = 24
        self._selection_drag_active = False
        self._selection_auto_scroll_source_id: Optional[int] = None
        self._selection_auto_scroll_direction = 0
        self._selection_auto_scroll_speed = 18
        self._wheel_scroll_step = 12.0
        self._wheel_smooth_factor = 12.0
        self._selection_edge_margin = 42
        self._follow_stream_bottom = False
        self._markdown_mode = False
        self._markdown_toggle_button: Optional[gtk.ToggleButton] = None
        self._output_label_meta: dict = {}

        split = gtk.Paned.new(gtk.Orientation.VERTICAL)
        split.set_hexpand(True)
        split.set_vexpand(True)

        self.top_scroll = gtk.ScrolledWindow()
        self.top_scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        self.top_scroll.get_style_context().add_class("halzi-scroll")
        self.top_scroll.set_hexpand(True)
        self.top_scroll.set_vexpand(True)
        self.top_scroll.add_events(Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.top_scroll.connect("button-release-event", self._on_top_scroll_button_release)

        self.top_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        self.top_box.set_margin_top(12)
        self.top_box.set_margin_bottom(12)
        self.top_box.set_margin_start(12)
        self.top_box.set_margin_end(12)
        self.top_box.get_style_context().add_class("halzi-output")

        self.top_scroll.add(self.top_box)
        split.add1(self.top_scroll)

        bottom_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        bottom_box.set_margin_top(10)
        bottom_box.set_margin_bottom(10)
        bottom_box.set_margin_start(10)
        bottom_box.set_margin_end(10)
        bottom_box.get_style_context().add_class("halzi-input-area")

        input_label = gtk.Label(label="User input")
        input_label.set_xalign(0.0)
        input_label.get_style_context().add_class("halzi-input-label")

        # Label row with mini-micro toggle on the same line
        label_row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        label_row.set_hexpand(True)

        # Mini mic button styled like header mic but smaller
        mini_button = gtk.ToggleButton()
        mini_button.set_relief(gtk.ReliefStyle.NORMAL)
        mini_button.set_focus_on_click(False)
        mini_button.get_style_context().add_class("halzi-header-toggle")
        mini_button.get_style_context().add_class("jarvis-mini-mic")
        mini_icon = gtk.Image.new_from_icon_name("audio-input-microphone-symbolic", gtk.IconSize.MENU)
        mini_button.add(mini_icon)
        mini_button.connect("toggled", self._on_mini_mic_toggled)
        mini_button.set_active(False)
        self._mini_mic_button = mini_button

        markdown_button = gtk.ToggleButton(label="Text")
        markdown_button.set_relief(gtk.ReliefStyle.NORMAL)
        markdown_button.set_focus_on_click(False)
        markdown_button.get_style_context().add_class("halzi-header-toggle")
        markdown_button.connect("toggled", self._on_markdown_mode_toggled)
        self._markdown_toggle_button = markdown_button

        controls_box = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)
        controls_box.pack_start(markdown_button, False, False, 0)
        controls_box.pack_start(mini_button, False, False, 0)

        self.input_view = gtk.TextView()
        self.input_view.set_wrap_mode(gtk.WrapMode.WORD_CHAR)
        self.input_view.set_left_margin(20)
        self.input_view.set_right_margin(20)
        self.input_view.get_style_context().add_class("halzi-input-text")

        input_scroll = gtk.ScrolledWindow()
        input_scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        input_scroll.set_hexpand(True)
        input_scroll.set_vexpand(True)
        input_scroll.add(self.input_view)

        label_row.pack_start(input_label, True, True, 0)
        label_row.pack_end(controls_box, False, False, 0)
        bottom_box.pack_start(label_row, False, False, 0)
        bottom_box.pack_start(input_scroll, True, True, 0)

        split.add2(bottom_box)
        split.set_position(500)

        self.pack_start(split, True, True, 0)
        self.clear_conversation_view()
        self.input_view.connect("key-press-event", self.on_input_key_press)

    def scroll_to_bottom(self) -> bool:
        vadj = self.top_scroll.get_vadjustment()
        if vadj is None:
            return False
        vadj.set_value(max(0.0, vadj.get_upper() - vadj.get_page_size()))
        return False

    def _is_near_bottom(self, tolerance: float = 8.0) -> bool:
        vadj = self.top_scroll.get_vadjustment()
        if vadj is None:
            return True

        max_value = max(vadj.get_lower(), vadj.get_upper() - vadj.get_page_size())
        return (max_value - vadj.get_value()) <= tolerance

    def _stream_is_active(self) -> bool:
        return (self._streaming_assistant_label is not None) and (not self._streaming_done)

    def clear_conversation_view(self) -> None:
        for child in self.top_box.get_children():
            self.top_box.remove(child)

        self._output_label_meta.clear()

        self.output_hint = gtk.Label(label="Scrollable area for LLM responses")
        self.output_hint.set_xalign(0.0)
        self.output_hint.set_line_wrap(True)
        self.output_hint.get_style_context().add_class("halzi-output-text")
        self.top_box.pack_start(self.output_hint, False, False, 0)
        self.top_box.show_all()
        GLib.idle_add(self.scroll_to_bottom)

    def _wire_output_widget(self, widget: gtk.Widget) -> None:
        widget.set_can_focus(True)
        widget.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.SCROLL_MASK
            | Gdk.EventMask.SMOOTH_SCROLL_MASK
            | Gdk.EventMask.KEY_PRESS_MASK
        )
        widget.connect("button-press-event", self._on_output_button_press)
        widget.connect("button-release-event", self._on_output_button_release)
        widget.connect("motion-notify-event", self._on_output_motion)
        widget.connect("scroll-event", self._on_output_scroll)
        widget.connect("key-press-event", self._on_output_key_press)

    def _build_output_row(self, text: str, is_user: bool) -> Tuple[gtk.Widget, gtk.Label]:
        row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=0)
        row.set_hexpand(True)

        label = gtk.Label(label=text)
        label.set_line_wrap(True)
        label.set_selectable(True)
        label.set_xalign(1.0 if is_user else 0.0)
        label.set_halign(gtk.Align.END if is_user else gtk.Align.START)
        label.get_style_context().add_class("halzi-output-text")
        self._register_output_label(label, is_user=is_user, raw_text=text)

        self._wire_output_widget(row)
        self._wire_output_widget(label)

        if is_user:
            row.pack_end(label, False, False, 6)
        else:
            row.pack_start(label, False, False, 6)

        return row, label

    def _on_markdown_mode_toggled(self, button: gtk.ToggleButton) -> None:
        self._markdown_mode = bool(button.get_active())
        button.set_label("Markdown" if self._markdown_mode else "Text")
        self._refresh_output_rendering()

    def _register_output_label(self, label: gtk.Label, is_user: bool, raw_text: str) -> None:
        self._output_label_meta[label] = {
            "is_user": is_user,
            "raw_text": raw_text,
        }
        self._render_output_label(label)

    def _set_output_label_text(self, label: gtk.Label, raw_text: str) -> None:
        meta = self._output_label_meta.get(label)
        if meta is None:
            return

        meta["raw_text"] = raw_text
        self._render_output_label(label)

    def _refresh_output_rendering(self) -> None:
        for label in self._iter_output_labels():
            self._render_output_label(label)

    def _render_output_label(self, label: gtk.Label) -> None:
        meta = self._output_label_meta.get(label)
        if meta is None:
            return

        raw_text = str(meta.get("raw_text", ""))
        is_user = bool(meta.get("is_user", False))

        if self._markdown_mode and (not is_user):
            try:
                label.set_use_markup(True)
                label.set_markup(markdown_to_pango(raw_text))
            except Exception as exc:
                logger.warning(f"Markdown render fallback to plain text: {exc}")
                label.set_use_markup(False)
                label.set_text(raw_text)
        else:
            label.set_use_markup(False)
            label.set_text(raw_text)

    def _selection_auto_scroll_stop(self) -> None:
        self._selection_auto_scroll_direction = 0
        if self._selection_auto_scroll_source_id is not None:
            GLib.source_remove(self._selection_auto_scroll_source_id)
            self._selection_auto_scroll_source_id = None

    def _selection_auto_scroll_tick(self) -> bool:
        direction = self._selection_auto_scroll_direction
        if direction == 0 or not self._selection_drag_active:
            self._selection_auto_scroll_stop()
            return False

        vadj = self.top_scroll.get_vadjustment()
        if vadj is None:
            self._selection_auto_scroll_stop()
            return False

        current = vadj.get_value()
        lower = vadj.get_lower()
        upper_limit = max(lower, vadj.get_upper() - vadj.get_page_size())
        next_value = current + (direction * self._selection_auto_scroll_speed)
        next_value = max(lower, min(upper_limit, next_value))
        if next_value == current:
            return True

        vadj.set_value(next_value)
        return True

    def _update_selection_auto_scroll(self, widget: gtk.Widget, event: Gdk.EventMotion) -> bool:
        if not self._selection_drag_active:
            self._selection_auto_scroll_stop()
            return False

        if not (event.state & Gdk.ModifierType.BUTTON1_MASK):
            self._selection_auto_scroll_stop()
            return False

        translated = widget.translate_coordinates(self.top_scroll, int(event.x), int(event.y))
        if translated is None:
            self._selection_auto_scroll_stop()
            return False

        _, y = translated
        allocation = self.top_scroll.get_allocation()
        if allocation.height <= 0:
            self._selection_auto_scroll_stop()
            return False

        direction = 0
        margin = self._selection_edge_margin
        if y <= margin:
            direction = -1
        elif y >= allocation.height - margin:
            direction = 1

        if direction == 0:
            self._selection_auto_scroll_stop()
            return False

        self._selection_auto_scroll_direction = direction
        if self._selection_auto_scroll_source_id is None:
            self._selection_auto_scroll_source_id = GLib.timeout_add(24, self._selection_auto_scroll_tick)

        return False

    def _on_output_button_press(self, widget: gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self._selection_drag_active = True
            self._selection_auto_scroll_direction = 0
            if self._stream_is_active():
                # Do not keep forcing bottom-follow while user is selecting text.
                self._follow_stream_bottom = False
        return False

    def _on_output_button_release(self, _widget: gtk.Widget, event: Gdk.EventButton) -> bool:
        if event.button == 1:
            self._selection_drag_active = False
            self._selection_auto_scroll_stop()
        return False

    def _on_output_motion(self, widget: gtk.Widget, event: Gdk.EventMotion) -> bool:
        return self._update_selection_auto_scroll(widget, event)

    def _iter_output_labels(self) -> List[gtk.Label]:
        labels: List[gtk.Label] = []
        for row in self.top_box.get_children():
            if not isinstance(row, gtk.Box):
                continue
            for child in row.get_children():
                if isinstance(child, gtk.Label):
                    labels.append(child)
        return labels

    def _has_output_selection(self) -> bool:
        for label in self._iter_output_labels():
            try:
                bounds = label.get_selection_bounds()
            except Exception:
                continue

            if not bounds:
                continue

            # Depending on GTK/PyGObject bindings this can be:
            # (start, end) or (has_selection, start, end).
            if len(bounds) == 2:
                start, end = bounds
                if start != end:
                    return True
            elif len(bounds) >= 3 and bool(bounds[0]):
                return True

        return False

    def _select_all_output_text(self) -> bool:
        labels = self._iter_output_labels()
        if not labels:
            return False

        all_text_parts: List[str] = []
        for label in labels:
            text = label.get_text() or ""
            all_text_parts.append(text)
            label.select_region(0, len(text))

        full_text = "\n\n".join(part for part in all_text_parts if part)
        if full_text:
            gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(full_text, -1)
            gtk.Clipboard.get(Gdk.SELECTION_PRIMARY).set_text(full_text, -1)
        return True

    def _on_output_key_press(self, _widget: gtk.Widget, event: Gdk.EventKey) -> bool:
        is_ctrl_a = (
            (event.state & Gdk.ModifierType.CONTROL_MASK)
            and event.keyval in (Gdk.KEY_a, Gdk.KEY_A)
        )
        if not is_ctrl_a:
            return False

        return self._select_all_output_text()

    def _on_output_scroll(self, _widget: gtk.Widget, event: Gdk.EventScroll) -> bool:
        vadj = self.top_scroll.get_vadjustment()
        if vadj is None:
            return False

        step = self._wheel_scroll_step
        page = vadj.get_page_increment() or max(step * 4.0, 48.0)
        delta = 0.0

        if event.direction == Gdk.ScrollDirection.UP:
            delta = -step
        elif event.direction == Gdk.ScrollDirection.DOWN:
            delta = step
        elif event.direction == Gdk.ScrollDirection.LEFT:
            delta = -page
        elif event.direction == Gdk.ScrollDirection.RIGHT:
            delta = page
        elif event.direction == Gdk.ScrollDirection.SMOOTH:
            deltas = event.get_scroll_deltas()
            if len(deltas) == 3:
                _has_delta, _smooth_dx, smooth_dy = deltas
            elif len(deltas) == 2:
                _smooth_dx, smooth_dy = deltas
            else:
                smooth_dy = 0.0
            if smooth_dy != 0.0:
                delta = smooth_dy * self._wheel_smooth_factor

        if delta == 0.0:
            return False

        current = vadj.get_value()
        lower = vadj.get_lower()
        upper_limit = max(lower, vadj.get_upper() - vadj.get_page_size())
        vadj.set_value(max(lower, min(upper_limit, current + delta)))

        if self._stream_is_active():
            self._follow_stream_bottom = self._is_near_bottom()

        return True

    def _on_top_scroll_button_release(self, _widget: gtk.Widget, _event: Gdk.EventButton) -> bool:
        if self._stream_is_active():
            self._follow_stream_bottom = self._is_near_bottom()
        return False

    def append_message(self, text: str, is_user: bool) -> None:
        if self.output_hint.get_parent() is not None:
            self.top_box.remove(self.output_hint)

        row, _label = self._build_output_row(text, is_user)

        self.top_box.pack_start(row, False, False, 0)
        self.top_box.show_all()
        GLib.idle_add(self.scroll_to_bottom)

    def _start_assistant_stream(self) -> bool:
        if self.output_hint.get_parent() is not None:
            self.top_box.remove(self.output_hint)

        row, label = self._build_output_row("", False)
        self.top_box.pack_start(row, False, False, 0)
        self.top_box.show_all()

        self._streaming_assistant_label = label
        self._streaming_target_text = ""
        self._streaming_display_text = ""
        self._streaming_done = False
        self._follow_stream_bottom = False

        # One initial jump to bottom before stream rendering starts.
        GLib.idle_add(self.scroll_to_bottom)

        if self._typing_source_id is None:
            self._typing_source_id = GLib.timeout_add(self._typing_interval_ms, self._typing_effect_tick)

        return False

    def _append_assistant_stream_chunk(self, piece: str) -> bool:
        if self._streaming_assistant_label is None:
            self._start_assistant_stream()

        self._streaming_target_text += piece

        if self._typing_source_id is None:
            self._typing_source_id = GLib.timeout_add(self._typing_interval_ms, self._typing_effect_tick)

        return False

    def _typing_effect_tick(self) -> bool:
        label = self._streaming_assistant_label
        if label is None:
            self._typing_source_id = None
            return False

        # Keep current visual text stable while the user is drag-selecting
        # or while any output text remains selected.
        # New chunks keep accumulating in _streaming_target_text and will be rendered
        # once selection is cleared.
        if self._selection_drag_active or self._has_output_selection():
            return True

        target_len = len(self._streaming_target_text)
        current_len = len(self._streaming_display_text)

        if current_len < target_len:
            next_len = min(target_len, current_len + self._typing_step_chars)
            self._streaming_display_text = self._streaming_target_text[:next_len]
            self._set_output_label_text(label, self._streaming_display_text)
            if self._follow_stream_bottom:
                GLib.idle_add(self.scroll_to_bottom)
            return True

        if self._streaming_done:
            self._typing_source_id = None
            self._streaming_assistant_label = None
            return False

        return True

    def _finalize_assistant_stream(self) -> bool:
        self._streaming_done = True
        self._follow_stream_bottom = False
        if self._typing_source_id is None:
            self._typing_source_id = GLib.timeout_add(self._typing_interval_ms, self._typing_effect_tick)
        return False

    def _split_completed_sentences(self, text: str) -> Tuple[List[str], str]:
        """Return completed sentences and remaining tail from a text buffer."""
        completed: List[str] = []
        last_end = 0
        for match in re.finditer(r"[.!?](?=\s|$)", text):
            end = match.end()
            sentence = text[last_end:end].strip()
            if sentence:
                completed.append(sentence)
            last_end = end
        return completed, text[last_end:]

    def _drain_queue_nowait(self, q: "queue.Queue[Any]") -> None:
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break

    def _tts_pipeline_active(self) -> bool:
        return bool(self.tts_thread is not None and self.tts_thread.is_alive())

    def _set_status_threadsafe(self, text: str) -> None:
        status_state.set_status(text)

    def _notify_ready_for_input(self) -> None:
        if (not self.is_processing_response) and (not self._tts_pipeline_active()):
            self._set_status_threadsafe("🟢 Ready")

    def _request_tts_soft_interrupt(self, wait_timeout: float = 3.0) -> bool:
        """Stop pending TTS after current phrase, then return when workers unwind."""
        if not self._tts_pipeline_active():
            return False

        self._tts_user_interrupt_done.clear()
        self._tts_user_interrupt_requested.set()

        if self.tts_queue is not None:
            self._drain_queue_nowait(self.tts_queue)
            try:
                self.tts_queue.put_nowait(None)
            except Exception:
                pass

        if self.tts_audio_queue is not None:
            self._drain_queue_nowait(self.tts_audio_queue)
            try:
                self.tts_audio_queue.put_nowait(None)
            except Exception:
                pass

        self._tts_user_interrupt_done.wait(timeout=wait_timeout)
        # Never keep this flag set across submissions, otherwise next TTS can be skipped.
        self._tts_user_interrupt_requested.clear()
        self._notify_ready_for_input()
        return True

    def _interrupt_then_submit(self, prompt: str) -> None:
        self._request_tts_soft_interrupt()
        if prompt:
            GLib.idle_add(self._submit_prompt_text, prompt, False)

    def submit_prompt(self) -> None:
        buffer_ = self.input_view.get_buffer()
        start_iter = buffer_.get_start_iter()
        end_iter = buffer_.get_end_iter()
        prompt = buffer_.get_text(start_iter, end_iter, True).strip()

        tts_active = self._tts_pipeline_active()

        if tts_active:
            # Clear now so delayed submit won't wipe user typing done while waiting.
            if prompt:
                buffer_.set_text("")
            threading.Thread(target=self._interrupt_then_submit, args=(prompt,), daemon=True).start()
            return

        if prompt:
            self._submit_prompt_text(prompt, clear_input=True)
        else:
            self._notify_ready_for_input()

    def _submit_prompt_text(self, prompt: str, clear_input: bool) -> None:

        if not prompt:
            return

        # Prevent overlapping LLM/TTS pipelines from manual + voice + interrupt paths.
        if not self._response_submit_lock.acquire(blocking=False):
            self._set_status_threadsafe("Response already in progress.")
            return

        # Safety reset in case a previous interruption timed out before worker teardown.
        self._tts_user_interrupt_requested.clear()
        self._tts_user_interrupt_done.clear()

        self._set_status_threadsafe("Processing...")

        self.append_message(prompt, is_user=True)
        if clear_input:
            buffer_ = self.input_view.get_buffer()
            buffer_.set_text("")

        if process_prompt is None:
            self.append_message("Error: unable to import ollama core.", is_user=False)
            try:
                self._response_submit_lock.release()
            except Exception:
                pass
            return

        process_fn = process_prompt

        # Mark processing state and run the LLM call in a background thread
        self.is_processing_response = True

        def worker():
            streamed_any = {"value": False}
            sentence_buffer = {"text": ""}
            tts_queue: "queue.Queue[Optional[str]]" = queue.Queue()
            tts_audio_queue: "queue.Queue[Optional[Tuple[Any, int]]]" = queue.Queue(maxsize=4)
            tts_thread: Optional[threading.Thread] = None
            self.tts_queue = tts_queue
            self.tts_audio_queue = tts_audio_queue

            speaker_enabled = (
                self.get_speaker_active is not None
                and self.get_speaker_active()
                and text_to_speech is not None
            )

            if speaker_enabled:
                def tts_consumer() -> None:
                    speaker_cancel_event = threading.Event()

                    def speaker_is_active_now() -> bool:
                        if self.get_speaker_active is None:
                            return True
                        try:
                            return bool(self.get_speaker_active())
                        except Exception:
                            return True

                    def clear_queue_nowait(q: "queue.Queue[Any]") -> None:
                        while True:
                            try:
                                q.get_nowait()
                            except queue.Empty:
                                break

                    def cancel_pending_speech() -> None:
                        speaker_cancel_event.set()
                        clear_queue_nowait(tts_queue)
                        clear_queue_nowait(tts_audio_queue)
                        try:
                            tts_queue.put_nowait(None)
                        except Exception:
                            pass
                        try:
                            tts_audio_queue.put_nowait(None)
                        except Exception:
                            pass

                    try:
                        if set_tts_active is not None:
                            set_tts_active(True)
                        if pause_audio_capture is not None:
                            pause_audio_capture()

                        def synth_worker() -> None:
                            try:
                                while True:
                                    sentence = tts_queue.get()
                                    if sentence is None:
                                        break

                                    if self._tts_user_interrupt_requested.is_set():
                                        cancel_pending_speech()
                                        break

                                    if speaker_cancel_event.is_set():
                                        continue

                                    cleaned = sanitize_for_tts(sentence.strip())
                                    if not cleaned:
                                        continue
                                    if self._shutdown_requested.is_set():
                                        continue

                                    if not speaker_is_active_now():
                                        cancel_pending_speech()
                                        continue

                                    try:
                                        if synthesize_text_to_audio is not None:
                                            audio, sample_rate = synthesize_text_to_audio(cleaned)
                                            if (
                                                speaker_cancel_event.is_set()
                                                or self._shutdown_requested.is_set()
                                                or self._tts_user_interrupt_requested.is_set()
                                            ):
                                                continue
                                            if not speaker_is_active_now():
                                                cancel_pending_speech()
                                                continue
                                            tts_audio_queue.put((audio, sample_rate))
                                        elif text_to_speech is not None:
                                            # Compatibility path if RAM synthesis is unavailable.
                                            text_to_speech(cleaned)
                                    except Exception:
                                        # Skip failed sentence synthesis without breaking the full stream.
                                        continue
                            finally:
                                tts_audio_queue.put(None)

                        def play_worker() -> None:
                            while True:
                                item = tts_audio_queue.get()
                                if item is None:
                                    break
                                if speaker_cancel_event.is_set():
                                    continue
                                audio, sample_rate = item
                                if self._shutdown_requested.is_set():
                                    continue
                                if play_audio_buffer is not None:
                                    play_audio_buffer(audio, sample_rate)

                                if self._tts_user_interrupt_requested.is_set():
                                    cancel_pending_speech()
                                    break

                                # Allow current phrase to finish, then stop subsequent ones if speak is off.
                                if not speaker_is_active_now():
                                    cancel_pending_speech()
                                    break

                        synth_thread = threading.Thread(target=synth_worker, daemon=True)
                        play_thread = threading.Thread(target=play_worker, daemon=True)
                        synth_thread.start()
                        play_thread.start()
                        synth_thread.join()
                        play_thread.join()
                    finally:
                        # Mark TTS worker as no longer active before publishing readiness.
                        self.tts_thread = None
                        if resume_audio_capture is not None:
                            resume_audio_capture()
                        if set_tts_active is not None:
                            set_tts_active(False)
                        if self._tts_user_interrupt_requested.is_set():
                            self._tts_user_interrupt_done.set()
                            self._tts_user_interrupt_requested.clear()
                        self._notify_ready_for_input()

                tts_thread = threading.Thread(target=tts_consumer, daemon=True)
                self.tts_thread = tts_thread
                tts_thread.start()

            def on_chunk(piece: str) -> None:
                if self._shutdown_requested.is_set():
                    return
                streamed_any["value"] = True
                GLib.idle_add(self._append_assistant_stream_chunk, piece)

                if not speaker_enabled:
                    return

                sentence_buffer["text"] += piece
                completed, remainder = self._split_completed_sentences(sentence_buffer["text"])
                for sentence in completed:
                    if self._tts_user_interrupt_requested.is_set():
                        break
                    if self.get_speaker_active is not None and not self.get_speaker_active():
                        try:
                            tts_queue.put_nowait(None)
                        except Exception:
                            pass
                        break
                    tts_queue.put(sentence)
                sentence_buffer["text"] = remainder

            try:
                GLib.idle_add(self._start_assistant_stream)
                _, response = process_fn(prompt, display=False, on_chunk=on_chunk)

                # Safety fallback if no callback chunk arrived.
                if (not streamed_any["value"]) and response:
                    GLib.idle_add(self._append_assistant_stream_chunk, response)
                    if speaker_enabled:
                        completed, remainder = self._split_completed_sentences(response)
                        for sentence in completed:
                            tts_queue.put(sentence)
                        sentence_buffer["text"] = remainder

                GLib.idle_add(self._finalize_assistant_stream)

                if speaker_enabled:
                    speaker_active_now = (
                        self.get_speaker_active is not None and self.get_speaker_active()
                    )
                    if (
                        speaker_active_now
                        and (not self._tts_user_interrupt_requested.is_set())
                        and sentence_buffer["text"].strip()
                    ):
                        tts_queue.put(sentence_buffer["text"].strip())
                    tts_queue.put(None)

            except Exception as exc:
                tb = traceback.format_exc()
                GLib.idle_add(self._finalize_assistant_stream)
                GLib.idle_add(self.append_message, f"Error: {exc}\n{tb}", False)
                if speaker_enabled:
                    tts_queue.put(None)
            finally:
                # Clear processing flag on GTK thread
                if self.tts_thread is not None and not self.tts_thread.is_alive():
                    self.tts_thread = None
                if self.tts_queue is not None:
                    self.tts_queue = None
                if self.tts_audio_queue is not None:
                    self.tts_audio_queue = None
                if self.response_thread is not None and not self.response_thread.is_alive():
                    self.response_thread = None
                self.is_processing_response = False
                self._notify_ready_for_input()
                try:
                    self._response_submit_lock.release()
                except Exception:
                    pass

        self.response_thread = threading.Thread(target=worker, daemon=True)
        self.response_thread.start()

    def start_voice_input(self) -> None:
        if self.voice_active:
            return

        self.voice_active = True
        self.voice_stop_event = threading.Event()
        self.voice_thread = threading.Thread(target=self._voice_input_loop, daemon=True)
        self.voice_thread.start()
        self._set_status_threadsafe("Voice mode active.")

    def stop_voice_input(self) -> None:
        if self.voice_stop_event is not None:
            self.voice_stop_event.set()

    def shutdown(self) -> None:
        self._tts_user_interrupt_requested.set()
        self._tts_user_interrupt_done.set()
        self._shutdown_requested.set()
        self._selection_auto_scroll_stop()
        self.stop_voice_input()
        self.header_mic_active = False
        self.mini_mic_mode = False

        if set_tts_active is not None:
            try:
                set_tts_active(False)
            except Exception:
                pass

        if resume_audio_capture is not None:
            try:
                resume_audio_capture()
            except Exception:
                pass

        if stop_all_playback is not None:
            try:
                stop_all_playback()
            except Exception:
                pass

        if self.tts_queue is not None:
            try:
                self.tts_queue.put_nowait(None)
            except Exception:
                pass
        if self.tts_audio_queue is not None:
            try:
                self.tts_audio_queue.put_nowait(None)
            except Exception:
                pass

        if self.voice_thread is not None and self.voice_thread.is_alive():
            try:
                self.voice_thread.join(timeout=1.5)
            except Exception:
                pass

        if self.tts_thread is not None and self.tts_thread.is_alive():
            try:
                self.tts_thread.join(timeout=2.0)
            except Exception:
                pass

        if self.response_thread is not None and self.response_thread.is_alive():
            try:
                self.response_thread.join(timeout=2.0)
            except Exception:
                pass

    def _voice_input_loop(self) -> None:
        try:
            from app.vad.vad import load_vad, iter_voice_prompts
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
                    if not skipped_while_busy_notified:
                        self._set_status_threadsafe("Voice ignored: response in progress.")
                        skipped_while_busy_notified = True
                    continue

                skipped_while_busy_notified = False
                # If mini mic mode is active, only fill the input without auto-submitting
                if getattr(self, "mini_mic_mode", False):
                    GLib.idle_add(self._fill_input_text, prompt)
                else:
                    GLib.idle_add(self._submit_voice_prompt, prompt)
        except Exception as exc:
            GLib.idle_add(self._on_voice_error, f"Voice error: {exc}")
        finally:
            GLib.idle_add(self._finalize_voice_stopped)

    def _submit_voice_prompt(self, prompt: str) -> bool:
        # In big-mic mode, keep current user input untouched.
        # Voice prompts are submitted directly without clearing TextView.
        self._submit_prompt_text(prompt.strip(), clear_input=False)
        return False

    def _fill_input_text(self, prompt: str) -> bool:
        buffer_ = self.input_view.get_buffer()
        start_iter = buffer_.get_start_iter()
        end_iter = buffer_.get_end_iter()
        existing = buffer_.get_text(start_iter, end_iter, True)

        speech = (prompt or "").strip()
        if not speech:
            return False

        # Decide suffix: if speech ends with terminal punctuation, add a space,
        # otherwise add ". " to separate sentences.
        if speech[-1] in (".", "!", "?"):
            suffix = " "
        else:
            suffix = ". "

        # Ensure there's a separator between existing text and new speech
        new_text = existing
        if new_text and not new_text.endswith((" ", "\n")):
            new_text += " "

        new_text += speech + suffix

        buffer_.set_text(new_text)
        # place cursor at end
        end_iter = buffer_.get_end_iter()
        buffer_.place_cursor(end_iter)
        return False

    def _on_mini_mic_toggled(self, button: gtk.ToggleButton) -> None:
        active = button.get_active()
        # Keep a single VAD service running and only switch routing behavior.
        self.mini_mic_mode = active

        if active:
            if self.set_header_mic_active is not None:
                try:
                    # Force header mic off for mutual exclusion.
                    self.set_header_mic_active(False)
                except Exception:
                    pass
            if not self.voice_active:
                self.start_voice_input()
        else:
            # Stop VAD only if header mic is not active.
            if not self.header_mic_active:
                self.stop_voice_input()

    def on_header_mic_toggled(self, active: bool) -> None:
        self.header_mic_active = active

        if active:
            # Header mic owns submission mode; mini must be off.
            self.mini_mic_mode = False
            if self._mini_mic_button is not None and self._mini_mic_button.get_active():
                self._mini_mic_button.set_active(False)
            if not self.voice_active:
                self.start_voice_input()
        else:
            # If header mic goes off, keep VAD only when mini mode is still active.
            if not self.mini_mic_mode:
                self.stop_voice_input()

    def set_mini_mic_active(self, active: bool) -> None:
        # Called by external code (e.g., MainWindow) to force mini mic state
        def _set():
            try:
                if self._mini_mic_button is not None:
                    self._mini_mic_button.set_active(active)
                self.mini_mic_mode = active
            except Exception:
                pass
            return False

        GLib.idle_add(_set)

    def _on_voice_error(self, message: str) -> bool:
        self._set_status_threadsafe(message)
        return False

    def _finalize_voice_stopped(self) -> bool:
        self.voice_active = False
        self.voice_stop_event = None
        self.voice_thread = None
        self._set_status_threadsafe("Voice mode stopped.")
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
    on_voice_stopped: Optional[Callable[[], None]] = None,
    get_speaker_active: Optional[Callable[[], bool]] = None,
    get_header_mic_active: Optional[Callable[[], bool]] = None,
    set_header_mic_active: Optional[Callable[[bool], None]] = None,
) -> gtk.Widget:
    return CenterPanel(
        on_voice_stopped=on_voice_stopped,
        get_speaker_active=get_speaker_active,
        get_header_mic_active=get_header_mic_active,
        set_header_mic_active=set_header_mic_active,
    )
