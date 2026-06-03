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
class PersonnalityModel(Model):
    """personnalities"""
    name: str
    description: str
    file: str  # path to the Markdown file of this personnality


@dataclass
class SessionModel(Model):
    """sessions"""
    _created_at: int
    _updated_at: int
    message_ids: Otm = Otm("messages")
    theme_id: Mto = Mto("themes")

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
class MessageModel(Model):
    """messages"""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float
    session_id: Mto = Mto("sessions")


@dataclass
class MemoryModel(Model):
    """memories"""
    content: str
    importance: int = 0
    _created_at: int = 0

    class Meta(Model.Meta):
        auto_now_add = ["_created_at"]

    @property
    def created_at(self) -> datetime:
        return datetime.fromtimestamp(self._created_at, tz=timezone.utc)

@dataclass
class ThemeModel(Model):
    """themes"""
    name: str
    description: str
    session_ids: Otm = Otm("sessions")
