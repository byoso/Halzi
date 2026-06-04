#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
from pathlib import Path

from gi.repository import Gtk as gtk, GLib, GdkPixbuf

import threading

from .constants import SIDEBAR_WIDTH
from .styles import load_css
from .headerbar import build_headerbar
from .left_panel import LeftPanel
from .center_panel import build_center_panel, CenterPanel
from .right_panel import RightPanel
from .stack_switcher import StackSwitcher
from .settings_gui.main_settings import build_settings_page
from .logger import logger

from app.config import APP_NAME
from app import status_state
from app import core


APP_DIR = Path(__file__).resolve().parent.parent

class MainWindow(gtk.Window):
    """Main GUI mockup with 3 columns: 1/4 - 1/2 - 1/4."""
    def __init__(self):
        super().__init__(title=f"{APP_NAME} GUI")
        self.set_default_size(1280, 760)
        self.set_position(gtk.WindowPosition.CENTER)
        self.connect("destroy", self._on_destroy)
        icon = GdkPixbuf.Pixbuf.new_from_file(str(APP_DIR / "icon.png"))
        self.set_icon(icon)

        self.stack_switcher = StackSwitcher(
            on_show_main=self._show_main_page,
            on_show_settings=self._show_settings_page,
        )
        header, self.folder_button, self.mic_button, self.speaker_button = build_headerbar(
            f"{APP_NAME} GUI",
            stack_switcher=self.stack_switcher,
        )
        self.set_titlebar(header)

        load_css()

        root = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("halzi-root")
        self.add(root)

        self.page_stack = gtk.Stack()
        self.page_stack.set_hexpand(True)
        self.page_stack.set_vexpand(True)
        self.page_stack.set_transition_type(gtk.StackTransitionType.CROSSFADE)
        self.page_stack.set_transition_duration(150)

        self.right_panel = RightPanel(on_memory_saved=self._on_memory_saved)
        main_page = self._build_main_page()
        settings_page = build_settings_page()

        self.page_stack.add_named(main_page, "main")
        self.page_stack.add_named(settings_page, "settings")
        self.page_stack.set_visible_child_name("main")

        root.pack_start(self.page_stack, True, True, 0)
        self.stack_switcher.set_active_page("main")

        self.mic_button.connect("toggled", self._on_mic_toggled)

        def _status_listener(text: str) -> None:
            GLib.idle_add(self.status_label.set_text, text)

        self._status_listener = _status_listener
        status_state.subscribe(self._status_listener, emit_current=True)

    def _build_main_page(self) -> gtk.Box:
        page = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)

        content = gtk.Grid()
        content.set_column_homogeneous(False)
        content.set_column_spacing(10)
        content.set_hexpand(True)
        content.set_vexpand(True)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        page.pack_start(content, True, True, 0)

        self.center_panel = build_center_panel(
            on_voice_stopped=self._sync_mic_toggle_off,
            get_speaker_active=lambda: self.speaker_button.get_active(),
            get_header_mic_active=lambda: self.mic_button.get_active(),
            set_header_mic_active=lambda v: self.mic_button.set_active(v),
        )
        self.center_panel.connect("prompt-submitted", self._on_prompt_submitted)
        self.left_panel = LeftPanel(
            on_theme_changed=self._on_theme_changed,
            on_session_selected=self._on_session_selected,
        )

        self.left_panel.set_size_request(SIDEBAR_WIDTH, -1)
        self.left_panel.set_hexpand(False)
        self.left_panel.set_vexpand(True)
        self.center_panel.set_hexpand(True)
        self.center_panel.set_vexpand(True)
        self.right_panel.set_size_request(SIDEBAR_WIDTH , -1)
        self.right_panel.set_hexpand(False)
        self.right_panel.set_vexpand(True)

        # 3 columns: fixed SIDEBAR_WIDTH + flexible center + fixed SIDEBAR_WIDTH
        content.attach(self.left_panel, 0, 0, 1, 1)
        content.attach(self.center_panel, 1, 0, 1, 1)
        content.attach(self.right_panel, 2, 0, 1, 1)

        status_bar = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=0)
        status_bar.set_size_request(-1, 22)
        status_bar.get_style_context().add_class("halzi-status-bar")

        self.status_label = gtk.Label(label=status_state.get_status())
        self.status_label.set_xalign(0.0)
        self.status_label.set_selectable(True)
        self.status_label.set_can_focus(True)
        self.status_label.set_margin_start(8)
        self.status_label.get_style_context().add_class("halzi-status-label")

        status_bar.pack_start(self.status_label, True, True, 0)
        page.pack_start(status_bar, False, True, 0)
        return page

    def _show_main_page(self) -> None:
        self.page_stack.set_visible_child_name("main")
        self.stack_switcher.set_active_page("main")

    def _show_settings_page(self) -> None:
        self.page_stack.set_visible_child_name("settings")
        self.stack_switcher.set_active_page("settings")

    def set_status(self, text: str) -> None:
        status_state.set_status(text)

    def _on_theme_changed(self) -> None:
        if isinstance(self.center_panel, CenterPanel):
            self.center_panel.clear_conversation_view()


    def _on_session_selected(self, session) -> None:
        if not isinstance(self.center_panel, CenterPanel):
            return

        self.center_panel.clear_conversation_view()
        if session is None:
            return

        markdown_content = core.load_session_markdown(session)
        if markdown_content:
            self.center_panel.append_message(markdown_content, is_user=False)

        if isinstance(self.right_panel, RightPanel):
            self.right_panel.files_cherry_picker_lister.file_lister.clear_files()
            self.right_panel.files_cherry_picker_lister.file_cherry_picker.clear_folders()

            folders = [folder.q.path for folder in session.q.folder_ids]
            files = [file.q.path for file in session.q.file_ids]
            for folder in folders:
                self.right_panel.files_cherry_picker_lister.file_cherry_picker.add_folder(None, folder)
            for file in files:
                self.right_panel.files_cherry_picker_lister.file_lister.add_file(file)

    def _on_memory_saved(self, session) -> None:
        if hasattr(self.left_panel, "active_session"):
            self.left_panel.active_session = session
        if hasattr(self.left_panel, "refresh_sessions"):
            self.left_panel.refresh_sessions()
        self._on_session_selected(session)

    def _on_mic_toggled(self, button: gtk.ToggleButton) -> None:
        if not isinstance(self.center_panel, CenterPanel):
            return

        # Delegate mic mode/VAD decisions to CenterPanel.
        self.center_panel.on_header_mic_toggled(button.get_active())

    def _sync_mic_toggle_off(self) -> None:
        if self.mic_button.get_active():
            self.mic_button.set_active(False)

    def get_allowed_files(self) -> list[str]:
        if isinstance(self.right_panel, RightPanel):
            return self.right_panel.get_allowed_files()
        return []

    def _on_destroy(self, *args) -> None:
        try:
            core.save_last_selection()
        except Exception:
            pass

        try:
            if hasattr(self, "_status_listener"):
                status_state.unsubscribe(self._status_listener)
        except Exception:
            pass

        try:
            if hasattr(self, "mic_button") and self.mic_button.get_active():
                self.mic_button.set_active(False)
        except Exception:
            pass

        try:
            if hasattr(self, "speaker_button") and self.speaker_button.get_active():
                self.speaker_button.set_active(False)
        except Exception:
            pass

        try:
            if isinstance(self.center_panel, CenterPanel):
                self.center_panel.shutdown()
        except Exception:
            pass

        gtk.main_quit()

    def _on_prompt_submitted(self, widget, prompt: str) -> None:
        files = self.get_allowed_files()

        if isinstance(self.center_panel, CenterPanel):
            # transmit the prompt and allowed files to the center panel for processing
            self.center_panel._submit_prompt_text(prompt, files=files, clear_input=True)


if __name__ == "__main__":
    window = MainWindow()
    window.show_all()
    gtk.main()