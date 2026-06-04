from dataclasses import dataclass
from typing import Any

from silly_engine.silly_orm.item import QItem

# store: dict[str, Any] = {
#     "active_theme": None,
# }


@dataclass
class Store:
    active_theme: QItem | None = None


store = Store()