from dataclasses import dataclass
from datetime import datetime, timezone
from app.silly_engine.silly_orm import Model, Mto, Otm, Mto


@dataclass
class ToolModel(Model):
    """tools"""
    name: str
    description: str
    enabled: bool = True
    permission_level: int = 0  # 0: all, 1: admin only, etc.

@dataclass
class PersonalityModel(Model):
    """personalities"""
    name: str = "Chloe"
    description: str = "A friendly and helpful assistant."
    file: str = ""  # path to the Markdown file of this personnality
    theme_ids: Otm = Otm("themes")

@dataclass
class ThemeModel(Model):
    """themes"""
    name: str
    description: str
    session_ids: Otm = Otm("sessions")
    personnality_ids: Mto = Mto("personalities")

@dataclass
class SessionModel(Model):
    """sessions"""
    name: str
    _created_at: int
    _updated_at: int
    message_ids: Otm = Otm("messages")
    theme_id: Mto = Mto("themes")
    memory_file_ids: Otm = Otm("session_memory")
    folder_ids: Otm = Otm("session_folders")
    file_ids: Otm = Otm("session_files")

    class Meta(Model.Meta):
        auto_now_add = ["_created_at"]
        auto_now = ["_updated_at"]

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self._created_at, tz=timezone.utc)

    @property
    def updated_at(self) -> datetime:
        return datetime.fromtimestamp(self._updated_at, tz=timezone.utc)

@dataclass
class SessionMemoryModel(Model):
    """session_memory"""
    path: str = ""
    session_id: Mto = Mto("sessions")

@dataclass
class SessionFileModel(Model):
    """session_files"""
    path: str = ""
    is_dir: bool = False
    selected: bool = False
    session_id: Mto = Mto("sessions")

@dataclass
class SessionFolderModel(Model):
    """session_folders"""
    path: str = ""
    session_id: Mto = Mto("sessions")

@dataclass
class MessageModel(Model):
    """messages"""
    role: str  # "user", "assistant", "system"
    content: str
    session_id: Mto = Mto("sessions")
    _created_at: int = 0

    class Meta(Model.Meta):
        auto_now_add = ["_created_at"]

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self._created_at, tz=timezone.utc)
