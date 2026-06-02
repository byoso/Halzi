"""
silly_orm is a simple ORM based on SillyDb that provides
 querying, and performing schema migrations. It includes:
- A Model class that can be subclassed to define data models with fields and relationships.
- A SillyDb class that extends the base SillyDb with ORM features like model validation,
  automatic table creation, and a migration system.
- Migration helper functions for safely modifying the database schema while preserving data.
- Custom exceptions for better error handling in the ORM context.

1.1.0: Added support for many-to-many relationships and improved relation accessors.
1.0.0: Initial release with basic Model and SillyDb classes, support for defining models,
 and simple migrations.
"""


from .tools import SillyDbError
from .db import SillyDb
from .models import Model
from .relations import Mtm, Otm, Mto, Oto
from .typing_helpers import cast_accessor

__all__ = [
    "SillyDbError",
    "SillyDb",
    "Model",
    "Mtm",
    "Mto",
    "Otm",
    "Oto",
    "cast_accessor",
    ]

VERSION = "1.1.0"