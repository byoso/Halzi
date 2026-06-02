from .accessor import Accessor
import json


class QItem:
    def __init__(self, table, data: dict):
        self._table = table
        self._db = table.db
        self._model = table.model
        self._data = data
        self._accessor = Accessor(self._model, self._data, self._db)

    @property
    def q(self):
        return self._accessor

    def __repr__(self):
        return f"<Q{self._model.__name__} {self._data.get('_id')}>"

    def dict(self):
        """Convert item to dictionary."""
        return dict(self._data)

    def json(self):
        """Convert item to JSON string."""
        return json.dumps(self._data, default=str)