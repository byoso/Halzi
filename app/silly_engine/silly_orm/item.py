from .accessor import Accessor
from dataclasses import fields
import json


class QItem:
    def __init__(self, table, data: dict):
        self._table = table
        self._db = table.db
        self._model = table.model
        self._data = data
        self._accessor = Accessor(self._model, self._data, self._db)

    @property
    def q(self) -> Accessor:
        return self._accessor

    def __repr__(self) -> str:
        return f"<Q{self._model.__name__} {self._data.get('_id')}>"

    def to_dict(self) -> dict:
        """Convert item to dictionary."""
        return dict(self._data)

    def to_model(self):
        """Convert item to a model instance with properties preserved."""
        model_cls = self._model

        init_values = {}
        for field_info in fields(model_cls):
            if field_info.init and field_info.name in self._data:
                init_values[field_info.name] = self._data[field_info.name]

        model_obj = model_cls(**init_values)

        for key, value in self._data.items():
            if key not in init_values:
                setattr(model_obj, key, value)

        return model_obj

    def to_json(self) -> str:
        """Convert item to JSON string."""
        return json.dumps(self._data, default=str)