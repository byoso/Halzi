import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk as gtk
from typing import Callable, Optional

import os

from app import status_state
from app.database.db import SessionFolders, SessionFiles
from app import core
from app.silly_engine.silly_orm.item import QItem
from app.store import store
from app.gui.components.big.files_cherry_picker_lister import FilesCherryPickerLister
from app.gui.logger import logger



class RightPanel(gtk.Box):
    def __init__(
            self,
            on_memory_saved: Optional[Callable[[QItem], None]] = None,
        ):
        super().__init__(orientation=gtk.Orientation.VERTICAL, spacing=0)
        self.get_style_context().add_class("halzi-panel")
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.on_memory_saved = on_memory_saved

        box = gtk.Box(orientation=gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(10)
        box.set_margin_end(10)


        memorize_button = gtk.Button(label="memorize session")
        memorize_button.get_style_context().add_class("halzi-memorize-button")
        memorize_button.connect("clicked", self.on_memorize_clicked)
        box.pack_start(memorize_button, False, False, 0)

        source_session = store.active_session
        if source_session is not None:
            folders = [folder.q.path for folder in source_session.q.folder_ids]
            files = [file.q.path for file in source_session.q.file_ids]
            self.files_cherry_picker_lister = FilesCherryPickerLister(folders=folders, files=files, short_path_length=35)

        else:
            self.files_cherry_picker_lister = FilesCherryPickerLister(short_path_length=35)

        box.pack_start(self.files_cherry_picker_lister, True, True, 0)

        self.pack_start(box, True, True, 0)

    def set_status(self, text: str) -> None:
        status_state.set_status(text)

    def on_memorize_clicked(self, _button: gtk.Button) -> None:
        history_snapshot = list(core.session_memory)
        source_session = store.active_session

        if source_session is None:
            self.set_status("No active session selected. Create or select a session first.")
            return

        try:
            assert store.active_theme is not None
            saved_session = core.save_memory(
                history_snapshot,
                theme=store.active_theme,
                topic=str(source_session.q.name),
                source_session=source_session,
            )
            if saved_session is not None and self.on_memory_saved is not None:
                self.on_memory_saved(saved_session)
            self.set_status(f"Conversation memorized in theme: {store.active_theme.q.name} -> session: {source_session.q.name}")
        except Exception as exc:
            self.set_status(f"Memorize failed: {exc}")


        # remove all session_files and session_folders linked to the session
        SessionFiles.delete().filter(session_id=source_session.q._id).execute()
        SessionFolders.delete().filter(session_id=source_session.q._id).execute()

        current_files = self.files_cherry_picker_lister.get_files_list()
        current_folders = self.files_cherry_picker_lister.get_folders_list()

        # Save files to the database and link them to the session
        for file_path in current_files:
            file_record = SessionFiles.insert(
                {
                    "path": file_path,
                    "is_dir": os.path.isdir(file_path),
                    "session_id": source_session.q._id,

                })
            logger.debug(f"Saved file: {file_record.q.path} linked to session ID: {file_record.q.session_id}")

        # Save folders to the database and link them to the session
        for folder_path in current_folders:
            folder_record = SessionFolders.insert(
                {
                    "path": folder_path,
                    "session_id": source_session.q._id
                })
            logger.debug(f"Saved folder: {folder_record.q.path} linked to session ID: {folder_record.q.session_id}")


    def get_allowed_files(self) -> list[str]:
        return self.files_cherry_picker_lister.get_allowed_files()