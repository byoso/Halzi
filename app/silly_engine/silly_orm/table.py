from typing import Type
import json
import time

from .item import QItem
from .query import Query, MutationQuery
from .relations.mtm import Mtm
from .relations.mto import Mto
from .relations.otm import Otm
from .relations.oto import Oto
from .tools import SillyDbError

class Table:
    def __init__(self, db, name: str, model: Type):
        self.db = db
        self.name = name
        self.model = model

    def _deserialize_row(self, row: dict) -> dict:
        decoded = {}

        for key, value in row.items():
            if isinstance(value, str) and value and value[0] in "[{":
                try:
                    decoded[key] = json.loads(value)
                    continue
                except json.JSONDecodeError as e:
                    raise SillyDbError(
                        f"Invalid JSON payload in column '{key}' for table '{self.name}'"
                    ) from e

            decoded[key] = value

        return decoded

    def _serialize_value(self, value):
        if isinstance(value, (list, dict)):
            return json.dumps(value)

        # Relation descriptors are class-level defaults and cannot be bound by sqlite.
        if hasattr(value, "_is_relation"):
            return None

        return value

    def _normalize_single_fk_value(self, value):
        if value == "":
            return None
        return value

    def _normalize_mtm_values(self, value):
        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        if isinstance(value, (list, tuple, set)):
            return [str(v) for v in value if v is not None and str(v) != ""]

        raise SillyDbError(f"Unsupported MTM value type: {type(value).__name__}")

    def _get_mtm_fields(self):
        return {
            name: rel
            for name, rel in self.model.get_relations().items()
            if isinstance(rel, Mtm)
        }

    def _get_otm_fields(self):
        return {
            name: rel
            for name, rel in self.model.get_relations().items()
            if isinstance(rel, Otm)
        }

    def _get_oto_fields(self):
        return {
            name: rel
            for name, rel in self.model.get_relations().items()
            if isinstance(rel, Oto)
        }

    def _get_mto_fields(self):
        return {
            name: rel
            for name, rel in self.model.get_relations().items()
            if isinstance(rel, Mto)
        }

    def _normalize_fk_payload(self, payload: dict):
        relation_fields = {
            **self._get_oto_fields(),
            **self._get_mto_fields(),
        }

        for field_name in relation_fields:
            if field_name in payload:
                payload[field_name] = self._normalize_single_fk_value(payload[field_name])

    def _fetch_row_data(self, **kwargs):
        filters = " AND ".join(f"{k}=?" for k in kwargs.keys())
        sql = f"SELECT * FROM {self.name} WHERE {filters} LIMIT 1"
        self.db.connector.execute(sql, tuple(kwargs.values()))
        row = self.db.connector.fetchone()
        if row is None:
            return None
        return dict(zip([c[0] for c in self.db.connector.cursor.description], row))

    def _find_reverse_oto(self, rel: Oto):
        target_table = self.db.table(rel.target)

        for field_name, target_rel in target_table.model.get_relations().items():
            if isinstance(target_rel, Oto) and target_rel.target == self.name:
                return target_table, field_name

        return target_table, None

    def _sync_oto_field(self, source_id: str, field_name: str):
        rel = self._get_oto_fields()[field_name]
        current_row = self._fetch_row_data(_id=source_id)
        if current_row is None:
            return

        target_id = self._normalize_single_fk_value(current_row.get(field_name))
        target_table, reverse_field = self._find_reverse_oto(rel)

        if reverse_field and not target_id:
            reverse_row = target_table.filter_first(**{reverse_field: source_id})
            if reverse_row is not None:
                target_id = reverse_row._data.get("_id")
                self.db.connector.execute(
                    f"UPDATE {self.name} SET {field_name}=? WHERE _id=?",
                    (target_id, source_id),
                )

        if target_id:
            self.db.connector.execute(
                f"UPDATE {self.name} SET {field_name}=NULL WHERE {field_name}=? AND _id != ?",
                (target_id, source_id),
            )

        if reverse_field:
            if target_id:
                self.db.connector.execute(
                    f"UPDATE {target_table.name} SET {reverse_field}=NULL WHERE {reverse_field}=? AND _id != ?",
                    (source_id, target_id),
                )
                self.db.connector.execute(
                    f"UPDATE {target_table.name} SET {reverse_field}=? WHERE _id=?",
                    (source_id, target_id),
                )
            else:
                self.db.connector.execute(
                    f"UPDATE {target_table.name} SET {reverse_field}=NULL WHERE {reverse_field}=?",
                    (source_id,),
                )

    def _sync_all_oto_fields(self, source_id: str):
        for field_name in self._get_oto_fields():
            self._sync_oto_field(source_id, field_name)

    def _cleanup_relations_for_delete(self, source_id: str):
        for table in self.db._tables.values():
            for field_name, rel in table.model.get_relations().items():
                if isinstance(rel, (Oto, Mto)) and rel.target == self.name:
                    self.db.connector.execute(
                        f"UPDATE {table.name} SET {field_name}=NULL WHERE {field_name}=?",
                        (source_id,),
                    )
                elif isinstance(rel, Mtm):
                    table.db.ensure_mtm_table(table.name, rel)

                    if table.name == self.name:
                        self.db.connector.execute(
                            f"DELETE FROM {rel.through} WHERE {rel.source_field}=?",
                            (source_id,),
                        )

                    if rel.target == self.name:
                        self.db.connector.execute(
                            f"DELETE FROM {rel.through} WHERE {rel.target_field}=?",
                            (source_id,),
                        )

    def _extract_mtm_payload(self, payload: dict):
        mtm_fields = self._get_mtm_fields()
        otm_fields = self._get_otm_fields()
        mtm_payload = {}

        aliases = self.model.relation_aliases()

        # Support logical relation keys (e.g. courted_princesses) and concrete keys (..._ids).
        for logical_name, concrete_name in aliases.items():
            if concrete_name in mtm_fields and logical_name in payload:
                payload[concrete_name] = payload.pop(logical_name)
            elif concrete_name in otm_fields and logical_name in payload:
                payload.pop(logical_name)

        for field_name in list(payload.keys()):
            if field_name in mtm_fields:
                mtm_payload[field_name] = self._normalize_mtm_values(payload.pop(field_name))
            elif field_name in otm_fields:
                payload.pop(field_name)

        return mtm_payload

    def _sync_mtm_links(self, source_id: str, field_name: str, new_ids, old_ids=None):
        rel = self._get_mtm_fields()[field_name]
        self.db.ensure_mtm_table(self.name, rel)

        current = set(self._normalize_mtm_values(old_ids if old_ids is not None else []))
        wanted = set(self._normalize_mtm_values(new_ids))

        to_insert = wanted - current
        to_delete = current - wanted

        for target_id in to_insert:
            if self.db.connector.__class__.__module__.endswith(".connectors.postgres"):
                insert_sql = (
                    f"INSERT INTO {rel.through} ({rel.source_field}, {rel.target_field}) "
                    "VALUES (?, ?) ON CONFLICT DO NOTHING"
                )
            else:
                insert_sql = (
                    f"INSERT OR IGNORE INTO {rel.through} ({rel.source_field}, {rel.target_field}) "
                    "VALUES (?, ?)"
                )
            self.db.connector.execute(
                insert_sql,
                (source_id, target_id),
            )

        for target_id in to_delete:
            self.db.connector.execute(
                f"DELETE FROM {rel.through} WHERE {rel.source_field}=? AND {rel.target_field}=?",
                (source_id, target_id),
            )

    def _fetch_current_mtm_ids(self, source_id: str, field_name: str):
        rel = self._get_mtm_fields()[field_name]
        self.db.ensure_mtm_table(self.name, rel)

        cursor = self.db.connector.execute(
            f"SELECT {rel.target_field} FROM {rel.through} WHERE {rel.source_field}=?",
            (source_id,),
        )
        return [row[0] for row in cursor.fetchall()]

    def _make_item(self, row: dict):
        return QItem(self, self._deserialize_row(row))

    def _apply_meta_fields(self, payload: dict, is_insert: bool = True):
        """Apply Meta-defined defaults and timestamps to payload."""
        meta = self.model.get_meta()
        now_ts = int(time.time())

        # Apply defaults on insert
        if is_insert and hasattr(meta, 'defaults') and meta.defaults:
            for key, value in meta.defaults.items():
                if key not in payload:
                    payload[key] = value

        # Apply auto_now_add fields on insert.
        if is_insert and hasattr(meta, 'auto_now_add') and meta.auto_now_add:
            for field_name in meta.auto_now_add:
                if field_name not in payload:
                    payload[field_name] = now_ts

        # Apply auto_now fields on insert and update.
        if hasattr(meta, 'auto_now') and meta.auto_now:
            for field_name in meta.auto_now:
                payload[field_name] = now_ts

        # Apply ttl
        if hasattr(meta, 'ttl') and meta.ttl:
            if '_expires_at' not in payload:
                payload['_expires_at'] = now_ts + meta.ttl

    def _run_model_validation(self, payload: dict, operation: str, record_id: str | None = None):
        """Run optional model validation hook before writing to DB."""
        self.model.validate(dict(payload), operation=operation, record_id=record_id)

    def insert(self, data: dict):
        try:
            payload = dict(data)
            mtm_payload = self._extract_mtm_payload(payload)
            self._normalize_fk_payload(payload)

            # If caller inserts a dict without _id, let the model provide one.
            if not payload.get("_id"):
                if hasattr(self.model, "new_id"):
                    payload["_id"] = self.model.new_id()

            source_id = str(payload["_id"])

            # Apply Meta fields (defaults, timestamps, ttl)
            self._apply_meta_fields(payload, is_insert=True)

            validation_payload = {**payload, **mtm_payload}
            self._run_model_validation(validation_payload, operation="insert")

            if not payload:
                raise SillyDbError("insert payload cannot be empty")

            fields = ", ".join(payload.keys())
            placeholders = ", ".join(["?"] * len(payload))
            sql = f"INSERT INTO {self.name} ({fields}) VALUES ({placeholders})"
            values = tuple(self._serialize_value(v) for v in payload.values())
            self.db.connector.execute(sql, values)

            self._sync_all_oto_fields(source_id)

            for field_name, target_ids in mtm_payload.items():
                self._sync_mtm_links(source_id, field_name, target_ids, old_ids=[])

            if not self.db._in_transaction:
                self.db.connector.commit()
        except Exception:
            if not self.db._in_transaction:
                self.db.connector.rollback()
            raise

    def update(self, _id: str | None = None, **data):
        if _id is None:
            return MutationQuery(self, "update", payload=data)

        if not data:
            return

        try:
            payload = dict(data)
            mtm_payload = self._extract_mtm_payload(payload)
            self._normalize_fk_payload(payload)

            # Apply Meta fields (timestamps, ttl)
            self._apply_meta_fields(payload, is_insert=False)

            validation_payload = {**payload, **mtm_payload}
            self._run_model_validation(validation_payload, operation="update", record_id=_id)

            if payload:
                assignments = ", ".join(f"{k}=?" for k in payload.keys())
                sql = f"UPDATE {self.name} SET {assignments} WHERE _id=?"
                values = tuple(self._serialize_value(v) for v in payload.values()) + (_id,)
                self.db.connector.execute(sql, values)

            self._sync_all_oto_fields(_id)

            for field_name, new_ids in mtm_payload.items():
                old_ids = self._fetch_current_mtm_ids(_id, field_name)
                self._sync_mtm_links(_id, field_name, new_ids, old_ids=old_ids)

            if not self.db._in_transaction:
                self.db.connector.commit()
        except Exception:
            if not self.db._in_transaction:
                self.db.connector.rollback()
            raise

    def delete_by_id(self, _id: str):
        try:
            self._cleanup_relations_for_delete(_id)
            self.db.connector.execute(f"DELETE FROM {self.name} WHERE _id=?", (_id,))
            if not self.db._in_transaction:
                self.db.connector.commit()
        except Exception:
            if not self.db._in_transaction:
                self.db.connector.rollback()
            raise

    def delete(self, item_or_id=None):
        if item_or_id is None:
            return MutationQuery(self, "delete")

        if hasattr(item_or_id, "_data"):
            _id = item_or_id._data.get("_id")
        else:
            _id = item_or_id

        self.delete_by_id(_id)

    def get_by_id(self, _id: str):
        row = self._fetch_row_data(_id=_id)
        if row is None:
            return None
        return self._make_item(row)

    def filter_first(self, **kwargs):
        """Returns a single QItem matching the filters, or None if not found.
        This is equivalent to a filter(...).first() shortcut.
        """
        filters = " AND ".join(f"{k}=?" for k in kwargs.keys())
        sql = f"SELECT * FROM {self.name} WHERE {filters} LIMIT 1"
        self.db.connector.execute(sql, tuple(kwargs.values()))
        row = self.db.connector.fetchone()
        if row is None:
            return None
        return self._make_item(dict(zip([c[0] for c in self.db.connector.cursor.description], row)))

    def filter(self, **kwargs):
        return Query(self).filter(**kwargs)

    def first(self):
        return Query(self).first()

    def count(self, **kwargs):
        return Query(self).filter(**kwargs).count()