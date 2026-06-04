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

    def update(self, **data):
        """Update item with new data and save to database."""
        source_id = self._data.get("_id")
        if source_id is None:
            raise ValueError("Cannot update item without _id")

        updated_data = {**data}
        updated_data.pop("_id", None)
        self._table.update(source_id, **updated_data)

        refreshed_item = self._table.get_by_id(source_id)
        if refreshed_item is None:
            raise ValueError("Cannot refresh item after update")

        self._data.clear()
        self._data.update(refreshed_item._data)
        return self