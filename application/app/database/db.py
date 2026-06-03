#!/usr/bin/env python3

from dataclasses import asdict
from pathlib import Path

from app.silly_engine.logger import Logger
from app.config import LOG_LEVEL

from app.database.models.models_settings import SettingsModel
from app.silly_engine.silly_orm.db import SillyDb, SillyDbError
from app.database.logger import logger
from app.database.models.models_llm import ToolModel, SessionModel, MessageModel, MemoryModel, ThemeModel

logger = Logger("app.database", display_level=False)
logger.set_level(LOG_LEVEL)

BASE_DIR = Path("~/.local/share/geninstaller-applications/.data/halzimir").expanduser()
# BASE_DIR = Path(__file__).parent  # path for dev
DATA_FILE = BASE_DIR / "data.sqlite3"

db = SillyDb(DATA_FILE)

# ORM tables
Settings = db.table("settings", SettingsModel)
Tools = db.table("tools", ToolModel)
Sessions = db.table("sessions", SessionModel)
Messages = db.table("messages", MessageModel)
Memories = db.table("memories", MemoryModel)
Themes = db.table("themes", ThemeModel)


def init_db() -> None:
    try:
        settings = Settings.first()
        if settings is None:
            Settings.insert(asdict(SettingsModel()))
    except SillyDbError as e:
        logger.error(f"Database error: {e}")


def get_settings() -> SettingsModel:
    settings = Settings.first()
    if settings is None:
        raise ValueError("Settings not found in database")
    return settings.to_model()

if __name__ == "__main__":
        init_db()
        # Example usage: create settings if not exist, then print them
        settings = get_settings()
        assert settings is not None, "Settings should have been initialized"
        logger.debug(f"Current settings: {settings}")
        logger.debug(f"property test: {settings.voice_gender}")
        logger.debug(f"property test: {settings.piper_voice}")