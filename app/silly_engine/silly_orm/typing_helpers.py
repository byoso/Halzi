from __future__ import annotations

from typing import TypeVar, cast

from .accessor import Accessor

TAccessor = TypeVar("TAccessor")


def cast_accessor(accessor: Accessor, accessor_type: type[TAccessor]) -> TAccessor:
    """
    Cast a dynamic Accessor to a user-defined Protocol for editor type hints.

    This helper is intended for static typing and IDE autocompletion only.
    It does not perform runtime validation.

    Example:
        class KnightAccessor(Protocol):
            sword: QRef
            courted_princesses: QList
            name: str

        q = cast_accessor(arthur.q, KnightAccessor)
        q.courted_princesses.add("p1")
    """
    _ = accessor_type
    return cast(TAccessor, accessor)
