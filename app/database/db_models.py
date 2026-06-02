#!/usr/bin/env python3

from dataclasses import asdict
from pathlib import Path


from app.database.models.settings import SettingsModel
from app.silly_engine.silly_orm.db import SillyDb, SillyDbError
from app.database.logger import logger

BASE_DIR = Path("~/.local/share/geninstaller-applications/.data/halzimir").expanduser()
# BASE_DIR = Path(__file__).parent  # path for dev
DATA_FILE = BASE_DIR / "data.sqlite3"

db = SillyDb(DATA_FILE)

# ORM tables
Settings = db.table("settings", SettingsModel)



def init_db() -> None:
    try:
        settings = Settings.first()
        if settings is None:
            Settings.insert(asdict(SettingsModel()))
    except SillyDbError as e:
        logger.error(f"Database error: {e}")


if __name__ == "__main__":
        init_db()
        # Example usage: create settings if not exist, then print them
        settings = Settings.first()
        assert settings is not None, "Settings should have been initialized"
        logger.debug(f"Current settings: {settings}")
        logger.debug(f"property test: {settings.q.voice_gender}")
        logger.debug(f"property test: {settings.q.piper_voice}")