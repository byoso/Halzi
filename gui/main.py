#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk

from constants import SIDEBAR_WIDTH
from styles import load_css
from headerbar import build_headerbar
from left_panel import build_left_panel
from center_panel import build_center_panel, CenterPanel
from right_panel import build_right_panel

class MainWindow(gtk.Window):
    """Main GUI mockup with 3 columns: 1/4 - 1/2 - 1/4."""
    def __init__(self):
        super().__init__(title="Jarvis GUI")
        self.set_default_size(1280, 760)
        self.set_position(gtk.WindowPosition.CENTER)
        self.connect("destroy", gtk.main_quit)

        header, self.folder_button, self.mic_button, self.speaker_button = build_headerbar("Jarvis GUI")
        self.set_titlebar(header)

        load_css()

        root = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=0)
        root.get_style_context().add_class("jarvis-root")
        self.add(root)

        content = gtk.Grid()
        content.set_column_homogeneous(False)
        content.set_column_spacing(10)
        content.set_hexpand(True)
        content.set_vexpand(True)
        content.set_margin_top(10)
        content.set_margin_bottom(10)
        content.set_margin_start(10)
        content.set_margin_end(10)
        root.pack_start(content, True, True, 0)

        self.center_panel = build_center_panel(
            on_status=self.set_status,
            on_voice_stopped=self._sync_mic_toggle_off,
        )
        left_panel = build_left_panel(
            on_status=self.set_status,
            on_theme_changed=lambda _theme: self._on_theme_changed(self.center_panel),
        )
        right_panel = build_right_panel(on_status=self.set_status)

        left_panel.set_size_request(SIDEBAR_WIDTH, -1)
        left_panel.set_hexpand(False)
        left_panel.set_vexpand(True)
        self.center_panel.set_hexpand(True)
        self.center_panel.set_vexpand(True)
        right_panel.set_size_request(SIDEBAR_WIDTH , -1)
        right_panel.set_hexpand(False)
        right_panel.set_vexpand(True)

        # 3 columns: fixed SIDEBAR_WIDTH + flexible center + fixed SIDEBAR_WIDTH
        content.attach(left_panel, 0, 0, 1, 1)
        content.attach(self.center_panel, 1, 0, 1, 1)
        content.attach(right_panel, 2, 0, 1, 1)

        self.mic_button.connect("toggled", self._on_mic_toggled)

        status_bar = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=0)
        status_bar.set_size_request(-1, 22)
        status_bar.get_style_context().add_class("jarvis-status-bar")

        self.status_label = gtk.Label(label="Ready")
        self.status_label.set_xalign(0.0)
        self.status_label.set_selectable(True)
        self.status_label.set_can_focus(True)
        self.status_label.set_margin_start(8)
        self.status_label.get_style_context().add_class("jarvis-status-label")

        status_bar.pack_start(self.status_label, True, True, 0)
        root.pack_start(status_bar, False, True, 0)

    def set_status(self, text: str) -> None:
        self.status_label.set_text(text)

    def _on_theme_changed(self, center_panel: gtk.Widget) -> None:
        if isinstance(center_panel, CenterPanel):
            center_panel.clear_conversation_view()

    def _on_mic_toggled(self, button: gtk.ToggleButton) -> None:
        if not isinstance(self.center_panel, CenterPanel):
            return

        if button.get_active():
            self.center_panel.start_voice_input()
        else:
            self.center_panel.stop_voice_input()

    def _sync_mic_toggle_off(self) -> None:
        if self.mic_button.get_active():
            self.mic_button.set_active(False)


if __name__ == "__main__":
    window = MainWindow()
    window.show_all()
    gtk.main()