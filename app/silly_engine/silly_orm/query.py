from .models import Model
from .item import QItem
from .relations.oto import Oto
from .relations.otm import Otm
from .relations.mto import Mto
from .relations.mtm import Mtm
from .tools import SillyDbError
import json
from dataclasses import dataclass
from typing import List, Any
import time


@dataclass
class Pagination:
    """Pagination result object."""
    data: List[Any]
    page: int
    page_size: int
    total: int

    def dict(self):
        """Convert pagination to dictionary."""
        return {
            "data": [item.dict() if hasattr(item, "dict") else item for item in self.data],
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
        }

    def json(self):
        """Convert pagination to JSON string."""
        return json.dumps(self.dict(), default=str)


class Query:
    SQL_OPS = {
        "eq": "=",
        "gt": ">",
        "lt": "<",
        "gte": ">=",
        "lte": "<=",
        "in": "IN",
        "contains": "LIKE",
    }

    def __init__(self, table):
        self.table = table
        self._filters = []
        self._joins = {}
        self._order = None
        self._limit = None

        # Apply default ordering from Meta if not overridden
        meta = self.table.model.get_meta()
        if hasattr(meta, 'ordering') and meta.ordering:
            # Join multiple ordering fields with comma
            self._order = ", ".join(meta.ordering)

    def filter(self, **kwargs):
        """
        Add filters. Supports relational filters using __ notation
        e.g., sword__name="Excalibur", dragons_killed__age__gt=100
        """
        for key, value in kwargs.items():
            parts = key.split("__")
            self._filters.append((parts, value))
        return self

    def _build_sql(self):
        """
        Build SQL query with JOINs for Oto, Otm, Mto, Mtm relationships.
        """
        sql = f"SELECT DISTINCT {self.table.name}.* FROM {self.table.name}"
        params = []
        join_count = 0
        joins = []
        where_clauses = []

        for path, value in self._filters:

            # ---------- simple field ----------
            if len(path) == 1:
                field = path[0]
                where_clauses.append(f"{self.table.name}.{field} = ?")
                params.append(value)
                continue

            # ---------- detect operator ----------
            if path[-1] in self.SQL_OPS:
                operator = path[-1]
                field = path[-2]
                rel_path = path[:-2]
            else:
                operator = "eq"
                field = path[-1]
                rel_path = path[:-1]

            sql_op = self.SQL_OPS.get(operator, "=")

            # ---------- resolve relations ----------
            current_table = self.table
            prev_alias = current_table.name

            for attr in rel_path:

                attr_name = current_table.model.relation_aliases().get(attr, attr)
                rel_field = getattr(current_table.model, attr_name, None)

                if isinstance(rel_field, (Oto, Mto)):
                    alias = f"t{join_count}"
                    join_count += 1

                    joins.append(
                        f"JOIN {rel_field.target} AS {alias} "
                        f"ON {prev_alias}.{attr_name} = {alias}._id"
                    )

                    prev_alias = alias
                    current_table = current_table.db.table(rel_field.target)

                elif isinstance(rel_field, Otm):
                    alias = f"t{join_count}"
                    join_count += 1
                    fk_field = rel_field.resolve_fk_field(current_table.db, current_table.name)

                    joins.append(
                        f"JOIN {rel_field.target} AS {alias} "
                        f"ON {alias}.{fk_field} = {prev_alias}._id"
                    )

                    prev_alias = alias
                    current_table = current_table.db.table(rel_field.target)

                elif isinstance(rel_field, Mtm):
                    current_table.db.ensure_mtm_table(current_table.name, rel_field)

                    alias1 = f"t{join_count}"
                    join_count += 1
                    alias2 = f"t{join_count}"
                    join_count += 1

                    joins.append(
                        f"JOIN {rel_field.through} AS {alias1} "
                        f"ON {prev_alias}._id = {alias1}.{rel_field.source_field}"
                    )

                    joins.append(
                        f"JOIN {rel_field.target} AS {alias2} "
                        f"ON {alias1}.{rel_field.target_field} = {alias2}._id"
                    )

                    prev_alias = alias2
                    current_table = current_table.db.table(rel_field.target)

                else:
                    raise SillyDbError(f"Unknown relation {attr}")

            # ---------- final WHERE ----------
            where_clauses.append(f"{prev_alias}.{field} {sql_op} ?")
            params.append(value)

        # ---------- add TTL filter if defined ----------
        meta = self.table.model.get_meta()
        if hasattr(meta, 'ttl') and meta.ttl:
            where_clauses.append(f"{self.table.name}._expires_at > ?")
            params.append(int(time.time()))

        # ---------- assemble SQL ----------
        if joins:
            sql += " " + " ".join(joins)

        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        if self._order:
            sql += f" ORDER BY {self._order}"

        if self._limit:
            sql += f" LIMIT {self._limit}"

        return sql, params

    def all(self) -> list[QItem]:
        sql, params = self._build_sql()
        self.table.db.connector.execute(sql, params)
        rows = self.table.db.connector.fetchall()
        colnames = [c[0] for c in self.table.db.connector.cursor.description]
        return [self.table._make_item(dict(zip(colnames, r))) for r in rows]

    def first(self):
        self._limit = 1
        results = self.all()
        return results[0] if results else None

    def order_by(self, field):
        self._order = field
        return self

    def limit(self, n):
        self._limit = n
        return self

    def __iter__(self):
        return iter(self.all())

    def _build_count_sql(self):
        """Build SQL for counting total matching rows."""
        sql = f"SELECT COUNT(DISTINCT {self.table.name}._id) FROM {self.table.name}"
        params = []
        join_count = 0
        joins = []
        where_clauses = []

        for path, value in self._filters:
            if len(path) == 1:
                field = path[0]
                where_clauses.append(f"{self.table.name}.{field} = ?")
                params.append(value)
                continue

            if path[-1] in self.SQL_OPS:
                operator = path[-1]
                field = path[-2]
                rel_path = path[:-2]
            else:
                operator = "eq"
                field = path[-1]
                rel_path = path[:-1]

            sql_op = self.SQL_OPS.get(operator, "=")
            current_table = self.table
            prev_alias = current_table.name

            for attr in rel_path:
                attr_name = current_table.model.relation_aliases().get(attr, attr)
                rel_field = getattr(current_table.model, attr_name, None)

                if isinstance(rel_field, (Oto, Mto)):
                    alias = f"t{join_count}"
                    join_count += 1
                    joins.append(
                        f"JOIN {rel_field.target} AS {alias} "
                        f"ON {prev_alias}.{attr_name} = {alias}._id"
                    )
                    prev_alias = alias
                    current_table = current_table.db.table(rel_field.target)

                elif isinstance(rel_field, Otm):
                    alias = f"t{join_count}"
                    join_count += 1
                    fk_field = rel_field.resolve_fk_field(current_table.db, current_table.name)
                    joins.append(
                        f"JOIN {rel_field.target} AS {alias} "
                        f"ON {alias}.{fk_field} = {prev_alias}._id"
                    )
                    prev_alias = alias
                    current_table = current_table.db.table(rel_field.target)

                elif isinstance(rel_field, Mtm):
                    current_table.db.ensure_mtm_table(current_table.name, rel_field)
                    alias1 = f"t{join_count}"
                    join_count += 1
                    alias2 = f"t{join_count}"
                    join_count += 1
                    joins.append(
                        f"JOIN {rel_field.through} AS {alias1} "
                        f"ON {prev_alias}._id = {alias1}.{rel_field.source_field}"
                    )
                    joins.append(
                        f"JOIN {rel_field.target} AS {alias2} "
                        f"ON {alias1}.{rel_field.target_field} = {alias2}._id"
                    )
                    prev_alias = alias2
                    current_table = current_table.db.table(rel_field.target)
                else:
                    raise SillyDbError(f"Unknown relation {attr}")

            where_clauses.append(f"{prev_alias}.{field} {sql_op} ?")
            params.append(value)

        # ---------- add TTL filter if defined ----------
        meta = self.table.model.get_meta()
        if hasattr(meta, 'ttl') and meta.ttl:
            where_clauses.append(f"{self.table.name}._expires_at > ?")
            params.append(int(time.time()))

        if joins:
            sql += " " + " ".join(joins)
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)

        return sql, params

    def paginate(self, page_size: int, page: int = 1):
        """Paginate results. Returns a Pagination object.

        Args:
            page_size: number of items per page
            page: page number (1-indexed)
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        # Get total count
        count_sql, count_params = self._build_count_sql()
        self.table.db.connector.execute(count_sql, count_params)
        total = self.table.db.connector.fetchone()[0]

        # Calculate offset
        offset = (page - 1) * page_size

        # Build main query with LIMIT and OFFSET
        sql, params = self._build_sql()
        sql += f" LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        self.table.db.connector.execute(sql, params)
        rows = self.table.db.connector.fetchall()
        colnames = [c[0] for c in self.table.db.connector.cursor.description]
        items = [self.table._make_item(dict(zip(colnames, r))) for r in rows]

        return Pagination(data=items, page=page, page_size=page_size, total=total)

    def dict(self):
        """Return results as list of dicts instead of QItems."""
        return [item.dict() if hasattr(item, "dict") else item for item in self.all()]

    def json(self):
        """Return results as JSON string."""
        return json.dumps(self.dict(), default=str)

    def count(self):
        """Count matching records without fetching them."""
        count_sql, count_params = self._build_count_sql()
        self.table.db.connector.execute(count_sql, count_params)
        return self.table.db.connector.fetchone()[0]


class MutationQuery:
    """Chainable bulk mutation helper based on Query filtering."""

    def __init__(self, table, operation: str, payload: dict | None = None):
        self.table = table
        self.operation = operation
        self.payload = payload or {}
        self.query = Query(table)

    def filter(self, **kwargs):
        self.query.filter(**kwargs)
        return self

    def order_by(self, field):
        self.query.order_by(field)
        return self

    def limit(self, n):
        self.query.limit(n)
        return self

    def execute(self) -> int:
        """Execute mutation over current filtered selection and return affected count."""
        ids = [item._data.get("_id") for item in self.query.all()]

        if self.operation == "update" and not self.payload:
            raise SillyDbError("bulk update requires at least one field to update")

        with self.table.db.transaction():
            if self.operation == "delete":
                for _id in ids:
                    self.table.delete_by_id(_id)
            elif self.operation == "update":
                for _id in ids:
                    self.table.update(_id, **self.payload)
            else:
                raise SillyDbError(f"Unknown mutation operation: {self.operation}")

        return len(ids)

    def apply(self) -> int:
        """Alias for execute() to keep mutation chains concise."""
        return self.execute()