from typing import Any

from .relations.otm import Otm
from .relations.mtm import Mtm
from .relations.oto import Oto
from .relations.mto import Mto
from .tools import SillyDbError


_MISSING = object()


class _RelationMutator:
    def __init__(self, accessor, relation_name):
        self._accessor = accessor
        self._relation_name = relation_name

    def add(self, value):
        self._accessor._add_relation(self._relation_name, value)
        return self

    def remove(self, value=None):
        self._accessor._remove_relation(self._relation_name, value)
        return self


class Accessor:
    def __init__(self, model_cls, data, db):
        self._model_cls = model_cls
        self._data = data
        self._db = db

    def _resolve_property(self, name: str) -> Any:
        descriptor = getattr(self._model_cls, name, _MISSING)
        if not isinstance(descriptor, property):
            return _MISSING

        # Build a lightweight model instance backed by row data so @property can
        # compute values using the same attributes as regular model instances.
        model_instance = self._model_cls.__new__(self._model_cls)
        for key, value in self._data.items():
            setattr(model_instance, key, value)

        return descriptor.__get__(model_instance, self._model_cls)

    def __getattr__(self, name: str) -> Any:
        """
        For relation fields:
        - Otm, Mtm: always returns a list of QItem (never None)
        - Oto, Mto: returns a QItem or None
        For normal fields: returns the value or None.
        """
        aliases = self._model_cls.relation_aliases()
        relation_fields = self._model_cls.get_relations()
        field_name = aliases.get(name, name)

        if field_name in relation_fields:
            rel_obj = relation_fields[field_name]

            # -------------------------
            # Many-to-Many special case
            # -------------------------
            if isinstance(rel_obj, Mtm):

                source_id = self._data.get("_id")
                if source_id is None:
                    return []

                source_table = self._db.table_name_for_model(self._model_cls)
                if not source_table:
                    raise SillyDbError(f"Unknown source table for model {self._model_cls.__name__}")

                self._db.ensure_mtm_table(source_table, rel_obj)

                cursor = self._db.connector.execute(
                    f"""
                    SELECT {rel_obj.target_field}
                    FROM {rel_obj.through}
                    WHERE {rel_obj.source_field}=?
                    """,
                    (source_id,),
                )

                ids = [row[0] for row in cursor.fetchall()]

                if not ids:
                    return []

                target_table = self._db.table(rel_obj.target)

                return [
                    target_table.filter_first(_id=i)
                    for i in ids
                ]

            # -------------------------
            # Normal relations
            # -------------------------
            if isinstance(rel_obj, Otm):
                source_id = self._data.get("_id")
                if source_id is None:
                    return []
                source_table = self._db.table_name_for_model(self._model_cls)
                if not source_table:
                    raise SillyDbError(f"Unknown source table for model {self._model_cls.__name__}")
                return rel_obj.resolve(self._db, source_id, source_table=source_table)

            value = self._data.get(field_name)

            if value is None:
                if isinstance(rel_obj, (Otm, Mtm)):
                    return []
                return None

            return rel_obj.resolve(self._db, value)

        # fallback to regular field
        if name in self._data:
            return self._data[name]

        property_value = self._resolve_property(name)
        if property_value is not _MISSING:
            return property_value

        raise SillyDbError(f"{self._model_cls.__name__} has no attribute {name}")

    def _source_table(self):
        source_table = self._db.table_name_for_model(self._model_cls)
        if not source_table:
            raise SillyDbError(f"Unknown source table for model {self._model_cls.__name__}")
        return source_table

    def _source_id(self):
        source_id = self._data.get("_id")
        if not source_id:
            raise SillyDbError("Cannot mutate relations for an object without _id")
        return source_id

    def _source_table_obj(self):
        return self._db.table(self._source_table())

    def _refresh_from_db(self):
        source = self._source_table_obj().filter_first(_id=self._source_id())
        if source is None:
            return
        self._data.clear()
        self._data.update(source._data)

    def _coerce_related_id(self, value):
        if value is None:
            return None

        if hasattr(value, "_data") and isinstance(value._data, dict):
            return value._data.get("_id")

        if hasattr(value, "_id"):
            return value._id

        return str(value)

    def _resolve_relation_field(self, relation):
        relation_fields = self._model_cls.get_relations()
        aliases = self._model_cls.relation_aliases()

        if isinstance(relation, str):
            field_name = aliases.get(relation, relation)
            if field_name not in relation_fields:
                available = ", ".join(sorted(relation_fields.keys()))
                raise SillyDbError(f"Unknown relation '{relation}'. Available: {available}")
            return field_name, relation_fields[field_name]

        for field_name, rel in relation_fields.items():
            if rel is relation:
                return field_name, rel

        raise SillyDbError("relation must be a relation name or a declared relation descriptor")

    def relation(self, relation_name):
        return _RelationMutator(self, relation_name)

    def _add_relation(self, relation, value):
        field_name, rel_obj = self._resolve_relation_field(relation)
        source_id = self._source_id()

        if isinstance(rel_obj, Mtm):
            related_id = self._coerce_related_id(value)
            current_items = self.__getattr__(field_name)
            current_ids = [item._data.get("_id") for item in current_items]
            if related_id not in current_ids:
                self._source_table_obj().update(source_id, **{field_name: current_ids + [related_id]})

        elif isinstance(rel_obj, (Oto, Mto)):
            related_id = self._coerce_related_id(value)
            self._source_table_obj().update(source_id, **{field_name: related_id})

        elif isinstance(rel_obj, Otm):
            related_id = self._coerce_related_id(value)
            source_table = self._source_table()
            target_table = self._db.table(rel_obj.target)
            fk_field = rel_obj.resolve_fk_field(self._db, source_table)
            target_table.update(related_id, **{fk_field: source_id})

        else:
            raise SillyDbError(f"Unsupported relation type: {type(rel_obj).__name__}")

        self._refresh_from_db()
        return self

    def _remove_relation(self, relation, value=None):
        field_name, rel_obj = self._resolve_relation_field(relation)
        source_id = self._source_id()

        if isinstance(rel_obj, Mtm):
            related_id = self._coerce_related_id(value)
            current_items = self.__getattr__(field_name)
            current_ids = [item._data.get("_id") for item in current_items]
            next_ids = [rid for rid in current_ids if rid != related_id]
            self._source_table_obj().update(source_id, **{field_name: next_ids})

        elif isinstance(rel_obj, Oto):
            source_table = self._source_table_obj()
            target_id = self._data.get(field_name)

            if value is not None:
                requested_id = self._coerce_related_id(value)
                if target_id != requested_id:
                    self._refresh_from_db()
                    return self

            try:
                if target_id:
                    target_table, reverse_field = source_table._find_reverse_oto(rel_obj)
                    if reverse_field:
                        self._db.connector.execute(
                            f"UPDATE {target_table.name} SET {reverse_field}=NULL WHERE _id=?",
                            (target_id,),
                        )

                self._db.connector.execute(
                    f"UPDATE {source_table.name} SET {field_name}=NULL WHERE _id=?",
                    (source_id,),
                )
                if not self._db._in_transaction:
                    self._db.connector.commit()
            except Exception:
                if not self._db._in_transaction:
                    self._db.connector.rollback()
                raise

        elif isinstance(rel_obj, Mto):
            if value is None:
                self._source_table_obj().update(source_id, **{field_name: None})
            else:
                current_id = self._data.get(field_name)
                related_id = self._coerce_related_id(value)
                if current_id == related_id:
                    self._source_table_obj().update(source_id, **{field_name: None})

        elif isinstance(rel_obj, Otm):
            source_table = self._source_table()
            target_table = self._db.table(rel_obj.target)
            fk_field = rel_obj.resolve_fk_field(self._db, source_table)

            if value is None:
                for child in self.__getattr__(field_name):
                    target_table.update(child._data.get("_id"), **{fk_field: None})
            else:
                related_id = self._coerce_related_id(value)
                target_table.update(related_id, **{fk_field: None})

        else:
            raise SillyDbError(f"Unsupported relation type: {type(rel_obj).__name__}")

        self._refresh_from_db()
        return self