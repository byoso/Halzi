from dataclasses import dataclass, field, fields
from typing import ClassVar
from uuid import uuid4

@dataclass
class Model:
    _id: str = field(default_factory=lambda: str(uuid4()), init=False)
    _relation_fields_cache: ClassVar[dict] = {}

    class Meta:
        """Default metadata. Override in subclass to customize table constraints and behavior."""
        # Singleton constraint
        singleton: bool = False

        # Table naming and defaults
        table_name: str | None = None          # Custom table name instead of model name
        ordering: list[str] | None = None             # Default ordering (e.g., ["age", "-created_at"])
        defaults: dict | None = None                  # Field defaults at insert (e.g., {"status": "active"})

        # Field constraints and indexes
        unique: list[str] | None = None               # Unique constraints (e.g., ["email", "username"])
        indexes: list[str] | None = None              # Columns to index (e.g., ["age", "email"])

        # Auto timestamps
        auto_now_add: list[str] | None = None         # Fields auto-set on create (e.g., ["created_at"])
        auto_now: list[str] | None = None             # Fields auto-updated on each save (e.g., ["updated_at"])

        # TTL: records auto-expire with _expires_at field
        ttl: int | None = None                 # Seconds until record expires (generates _expires_at)

    @classmethod
    def get_meta(cls):
        """Get metadata for this model, with fallback to defaults."""
        if hasattr(cls, 'Meta'):
            return cls.Meta
        return Model.Meta

    @classmethod
    def new_id(cls) -> str:
        return str(uuid4())

    @classmethod
    def get_relations(cls):
        rels = cls._relation_fields_cache.get(cls)
        if rels is not None:
            return rels

        rels = {}

        for f in fields(cls):
            value = getattr(cls, f.name, None)

            if hasattr(value, "_is_relation"):
                value.name = f.name
                rels[f.name] = value

        cls._relation_fields_cache[cls] = rels
        return rels

    @classmethod
    def relation_aliases(cls):

        aliases = {}

        for name, rel in cls.get_relations().items():

            if name.endswith("_id"):
                aliases.setdefault(name[:-3], name)

            elif name.endswith("_ids"):
                aliases.setdefault(name[:-4], name)

        return aliases

    @classmethod
    def validate(cls, payload: dict, operation: str = "insert", record_id: str | None = None):
        """
        Validation hook called before insert/update or whatever action.
        Override in user models and raise an exception to reject a payload.
        """
        if operation == "insert":
            pass
        elif operation == "update":
            pass
        return None
