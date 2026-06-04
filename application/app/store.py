from dataclasses import dataclass
from typing import Any

from app.silly_engine.silly_orm.item import QItem

# store: dict[str, Any] = {
#     "active_theme": None,
# }


@dataclass
class Store:
    active_theme: QItem | None = None
    active_session: QItem | None = None


store = Store()