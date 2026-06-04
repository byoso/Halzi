from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from .item import QItem


class QList(Sequence[Any]):
    """List-like view over an OTM/MTM relation with mutation helpers."""

    def __init__(self, accessor: Any, relation_name: str, relation_obj: Any) -> None:
        self._accessor = accessor
        self._relation_name = relation_name
        self._relation_obj = relation_obj

    def _items(self) -> list[Any]:
        """Resolve and return the current related items."""
        return self._accessor._read_relation_value(self._relation_name, self._relation_obj)

    def add(self, value: Any) -> QList:
        """Add a relation link using an ID, model instance, or QItem."""
        self._accessor._add_relation(self._relation_name, value)
        return self

    def remove(self, value: Any = None) -> QList:
        """Remove a relation link by value, or clear all depending on relation type."""
        self._accessor._remove_relation(self._relation_name, value)
        return self

    def first(self) -> Any | None:
        """Return the first related item, or None if the relation is empty."""
        items = self._items()
        if not items:
            return None
        return items[0]

    def to_list(self) -> list[Any]:
        """Return a concrete list snapshot of the related items."""
        return list(self._items())

    def __iter__(self) -> Iterator[Any]:
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    @overload
    def __getitem__(self, index: int) -> Any:
        ...

    @overload
    def __getitem__(self, index: slice) -> list[Any]:
        ...

    def __getitem__(self, index: int | slice) -> Any | list[Any]:
        return self._items()[index]

    def __contains__(self, value: object) -> bool:
        return value in self._items()

    def __repr__(self) -> str:
        return repr(self._items())


class QRef:
    """Reference-like view over an OTO/MTO relation with mutation helpers."""

    def __init__(self, accessor: Any, relation_name: str, relation_obj: Any) -> None:
        self._accessor = accessor
        self._relation_name = relation_name
        self._relation_obj = relation_obj

    @property
    def value(self) -> Any | None:
        """Return the related item, or None when the relation is not set."""
        return self.get()

    def get(self) -> QItem | None:
        """Resolve and return the related item, or None if missing."""
        return self._accessor._read_relation_value(self._relation_name, self._relation_obj)

    def set(self, value: Any) -> QRef:
        """Set the relation target using an ID, model instance, or QItem."""
        self._accessor._add_relation(self._relation_name, value)
        return self

    def add(self, value: Any) -> QRef:
        """Alias for set(), kept for API symmetry with QList.add()."""
        # Alias for symmetry with QList API.
        return self.set(value)

    def remove(self, value: Any = None) -> QRef:
        """Remove or clear the relation target."""
        self._accessor._remove_relation(self._relation_name, value)
        return self

    def __bool__(self) -> bool:
        """Return True when a related item exists."""
        return self.get() is not None

    def __getattr__(self, name: str) -> Any:
        """Proxy attribute access to the resolved related item."""
        item = self.get()
        if item is None:
            raise AttributeError(f"Relation '{self._relation_name}' is not set")
        return getattr(item, name)

    def __repr__(self) -> str:
        return repr(self.get())
