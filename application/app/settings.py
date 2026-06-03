from dataclasses import fields

from app.database.db import Settings
from app.database.models.models_settings import SettingsModel


ALLOWED_SETTINGS_KEYS = {
    field.name
    for field in fields(SettingsModel)
    if field.name != "_id" and not field.name.startswith("_")
}


def get_settings():
    settings = Settings.first()
    if settings is None:
        raise ValueError("Settings not found in database")
    return settings.to_model()


def update_settings(**kwargs) -> None:
    settings = Settings.first()
    if settings is None:
        raise ValueError("Settings not found in database")

    unknown_keys = sorted(key for key in kwargs if key not in ALLOWED_SETTINGS_KEYS)
    if unknown_keys:
        raise ValueError(f"Unsupported settings keys: {', '.join(unknown_keys)}")

    settings_id = settings.to_dict().get("_id")
    if not settings_id:
        raise ValueError("Settings id not found in database")

    if not kwargs:
        return

    Settings.update(_id=settings_id, **kwargs)