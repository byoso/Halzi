import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from typing import Callable, Optional

from app import status_state
from app import core
from app.silly_engine.silly_orm.item import QItem

from app.store import store

from .new_theme_dialog import NewThemeDialog
from app.gui.new_session_dialog import NewSessionDialog


class ThemePanel(gtk.Box):
    def __init__(
        self,
        on_theme_changed: Optional[Callable[[], None]] = None,
        on_session_selected: Optional[Callable[[QItem | None], None]] = None,
    ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.themes_list = core.list_themes()
        if self.themes_list:
            self.active_theme = self.themes_list[0]
        else:
            self.active_theme = None
        self.sessions_list: list[QItem] = []
        self.active_session: QItem | None = None

        store.active_theme = self.active_theme
        store.active_session = None
        self.get_style_context().add_class("halzi-panel")
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.on_theme_changed = on_theme_changed
        self.on_session_selected = on_session_selected
        self._syncing = False
        self._syncing_sessions = False
        self._theme_buttons = {}
        self._session_buttons = {}

        scroll = gtk.ScrolledWindow()
        scroll.set_policy(gtk.PolicyType.AUTOMATIC, gtk.PolicyType.AUTOMATIC)
        scroll.get_style_context().add_class("halzi-scroll")
        scroll.set_hexpand(True)
        scroll.set_vexpand(True)

        self.box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=8)
        self.box.set_margin_top(10)
        self.box.set_margin_bottom(10)
        self.box.set_margin_start(10)
        self.box.set_margin_end(10)

        self.theme_expander = gtk.Expander(label="Themes")
        self.theme_expander.get_style_context().add_class("halzi-themes-expander")
        self.theme_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        self.theme_expander.add(self.theme_box)
        self.box.pack_start(self.theme_expander, False, True, 0)

        self.add_button = gtk.Button(label="+ theme")
        self.add_button.get_style_context().add_class("halzi-add-theme-button")
        self.add_button.connect("clicked", self._on_add_theme_clicked)

        self.theme_list_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)

        self.theme_box.pack_start(self.add_button, False, False, 0)
        self.theme_box.pack_start(self.theme_list_box, False, False, 0)

        self.sessions_expander = gtk.Expander(label="Sessions")
        self.sessions_expander.get_style_context().add_class("halzi-sessions-expander")
        self.sessions_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        self.sessions_expander.add(self.sessions_box)
        self.box.pack_start(self.sessions_expander, False, True, 0)

        self.add_session_button = gtk.Button(label="+ session")
        self.add_session_button.get_style_context().add_class("halzi-add-session-button")
        self.add_session_button.connect("clicked", self._on_add_session_clicked)

        self.sessions_list_box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=6)
        self.sessions_box.pack_start(self.add_session_button, False, False, 0)
        self.sessions_box.pack_start(self.sessions_list_box, False, False, 0)

        scroll.add(self.box)
        self.pack_start(scroll, True, True, 0)

        self.refresh()

    def _set_status(self, text: str) -> None:
        status_state.set_status(text)

    def _notify_theme_changed(self) -> None:
        if self.on_theme_changed is not None:
            self.on_theme_changed()

    def _notify_session_selected(self, session: QItem | None) -> None:
        if self.on_session_selected is not None:
            self.on_session_selected(session)

    def _set_theme_button_active_style(self, button: gtk.ToggleButton) -> None:
        context = button.get_style_context()
        if button.get_active():
            context.add_class("halzi-theme-button-on")
        else:
            context.remove_class("halzi-theme-button-on")

    def _sync_buttons_for_active_theme(self, active_theme) -> None:
        self._syncing = True
        for theme, button in self._theme_buttons.items():
            button.set_active(theme == active_theme)
            self._set_theme_button_active_style(button)
        self._syncing = False

    def _set_session_button_active_style(self, button: gtk.ToggleButton) -> None:
        context = button.get_style_context()
        if button.get_active():
            context.add_class("halzi-session-button-on")
        else:
            context.remove_class("halzi-session-button-on")

    def _sync_buttons_for_active_session(self, active_session: QItem | None) -> None:
        self._syncing_sessions = True
        active_session_id = active_session.q._id if active_session is not None else None
        for session, button in self._session_buttons.items():
            button.set_active(session.q._id == active_session_id)
            self._set_session_button_active_style(button)
        self._syncing_sessions = False

    def _on_theme_toggled(self, button: gtk.ToggleButton, theme) -> None:
        if self._syncing:
            return

        if not button.get_active():
            # Keep one theme always active.
            if theme == self.active_theme:
                self._syncing = True
                button.set_active(True)
                self._syncing = False
            self._set_theme_button_active_style(button)
            return

        try:
            self.active_theme = theme
            store.active_theme = theme
            self.active_session = None
            store.active_session = None
            core.clear_active_session()
            self._sync_buttons_for_active_theme(self.active_theme)
            self.refresh_sessions()
            self._notify_theme_changed()
            self._notify_session_selected(None)
            if not self.active_theme:
                self._set_status("No active theme.")
            else:
                self._set_status(f"Active theme: {self.active_theme.q.name}")
        except Exception as exc:
            self._set_status(f"Theme selection failed: {exc}")

    def _on_session_toggled(self, button: gtk.ToggleButton, session: QItem) -> None:
        if self._syncing_sessions:
            return

        if not button.get_active():
            if session == self.active_session:
                self._syncing_sessions = True
                button.set_active(True)
                self._syncing_sessions = False
            self._set_session_button_active_style(button)
            return

        try:
            self.active_session = session
            store.active_session = session
            core.activate_session(session)
            self._sync_buttons_for_active_session(self.active_session)
            self._notify_session_selected(session)
            self._set_status(f"Active session: {session.q.name}")
        except Exception as exc:
            self._set_status(f"Session selection failed: {exc}")

    def _on_delete_theme_clicked(self, _button: gtk.Button, theme) -> None:
        try:
            core.delete_theme(theme)
            store.active_theme = None
            self.active_session = None
            store.active_session = None
            core.clear_active_session()
            self.refresh()
            self._notify_theme_changed()
            self._notify_session_selected(None)
            self._set_status(f"Theme deleted: {theme.q.name}")
        except Exception as exc:
            self._set_status(f"Theme delete failed: {exc}")

    def _on_delete_session_clicked(self, _button: gtk.Button, session: QItem) -> None:
        try:
            was_active = self.active_session is not None and session.q._id == self.active_session.q._id
            core.delete_session(session)
            if was_active:
                self.active_session = None
                store.active_session = None
                core.clear_active_session()
                self._notify_session_selected(None)
            self.refresh_sessions()
            self._set_status(f"Session deleted: {session.q.name}")
        except Exception as exc:
            self._set_status(f"Session delete failed: {exc}")

    def _on_add_session_clicked(self, _button: gtk.Button) -> None:
        parent = self.get_toplevel()
        if not isinstance(parent, gtk.Window):
            self._set_status("Session creation failed: parent window not found.")
            return

        if self.active_theme is None:
            self._set_status("Session creation failed: no active theme.")
            return

        dialog = NewSessionDialog(parent)
        response = dialog.run()
        raw_name = dialog.get_session_name()
        dialog.destroy()

        if response != gtk.ResponseType.OK:
            return

        try:
            created = core.create_session(self.active_theme, raw_name)
            self.active_session = created
            store.active_session = created
            self.refresh_sessions()
            self._notify_session_selected(created)
            self._set_status(f"Session created: {created.q.name}")
        except Exception as exc:
            self._set_status(f"Session creation failed: {exc}")

    def _on_add_theme_clicked(self, _button: gtk.Button) -> None:

        parent = self.get_toplevel()
        if not isinstance(parent, gtk.Window):
            self._set_status("Theme creation failed: parent window not found.")
            return

        dialog = NewThemeDialog(parent)
        response = dialog.run()
        raw_name = dialog.get_theme_name()
        dialog.destroy()

        if response != gtk.ResponseType.OK:
            return

        try:
            created = core.create_theme(raw_name)
            self.themes_list.append(created)
            self.refresh()
            self._notify_theme_changed()
            self._set_status(f"Theme created: {created.q.name}")
        except Exception as exc:
            self._set_status(f"Theme creation failed: {exc}")

    def refresh(self) -> None:
        while self.theme_list_box.get_children():
            child = self.theme_list_box.get_children()[0]
            self.theme_list_box.remove(child)

        self._theme_buttons = {}

        self.themes_list = core.list_themes()

        if self.active_theme not in self.themes_list:
            self.active_theme = self.themes_list[0] if self.themes_list else None
        store.active_theme = self.active_theme

        for theme in self.themes_list:
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)

            theme_button = gtk.ToggleButton(label=theme.q.name)
            theme_button.set_hexpand(True)
            theme_button.set_halign(gtk.Align.FILL)
            theme_button.get_style_context().add_class("halzi-theme-button")
            theme_button.connect("toggled", self._on_theme_toggled, theme)
            row.pack_start(theme_button, True, True, 0)

            delete_button = gtk.Button(label="X")
            delete_button.get_style_context().add_class("halzi-theme-delete-button")
            delete_button.connect("clicked", self._on_delete_theme_clicked, theme)
            row.pack_start(delete_button, False, False, 0)

            self.theme_list_box.pack_start(row, False, False, 0)
            self._theme_buttons[theme] = theme_button

        self._sync_buttons_for_active_theme(self.active_theme)
        self.refresh_sessions()
        self.show_all()

    def refresh_sessions(self) -> None:
        while self.sessions_list_box.get_children():
            child = self.sessions_list_box.get_children()[0]
            self.sessions_list_box.remove(child)

        self._session_buttons = {}

        self.sessions_list = core.list_sessions(self.active_theme)

        active_session_id = self.active_session.q._id if self.active_session is not None else None
        if active_session_id is not None and not any(session.q._id == active_session_id for session in self.sessions_list):
            if self.active_session is not None:
                core.clear_active_session()
                self._notify_session_selected(None)
            self.active_session = None
            store.active_session = None

        for session in self.sessions_list:
            row = gtk.Box(orientation=gtk.Orientation.HORIZONTAL, spacing=6)

            session_button = gtk.ToggleButton(label=session.q.name)
            session_button.set_hexpand(True)
            session_button.set_halign(gtk.Align.FILL)
            session_button.get_style_context().add_class("halzi-session-button")
            session_button.connect("toggled", self._on_session_toggled, session)
            row.pack_start(session_button, True, True, 0)

            delete_button = gtk.Button(label="X")
            delete_button.get_style_context().add_class("halzi-session-delete-button")
            delete_button.connect("clicked", self._on_delete_session_clicked, session)
            row.pack_start(delete_button, False, False, 0)

            self.sessions_list_box.pack_start(row, False, False, 0)
            self._session_buttons[session] = session_button

        self._sync_buttons_for_active_session(self.active_session)
        self.show_all()


def build_left_panel(
    on_theme_changed: Optional[Callable[[], None]] = None,
    on_session_selected: Optional[Callable[[QItem | None], None]] = None,
) -> gtk.Widget:
    return ThemePanel(
        on_theme_changed=on_theme_changed,
        on_session_selected=on_session_selected,
    )
