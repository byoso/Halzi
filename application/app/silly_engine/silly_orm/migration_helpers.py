from __future__ import annotations

from typing import Iterable

from .tools import SillyDbError


def _is_postgres(db) -> bool:
    return db.connector.__class__.__module__.endswith(".connectors.postgres")


def quote_identifier(name: str) -> str:
    """Return a safely quoted SQL identifier."""
    escaped = name.replace('"', '""')
    return f'"{escaped}"'


def make_index_name(table_name: str, column_names: Iterable[str]) -> str:
    """Build a deterministic index name as idx_<table>_<col1>_<col2>."""
    return f"idx_{table_name}_{'_'.join(column_names)}"


def _sqlite_version_tuple(db) -> tuple[int, int, int]:
    """Return SQLite version as (major, minor, patch)."""
    if _is_postgres(db):
        return (999, 0, 0)
    db.execute("SELECT sqlite_version()")
    raw = db.fetchone()[0]
    parts = raw.split(".")
    while len(parts) < 3:
        parts.append("0")
    return int(parts[0]), int(parts[1]), int(parts[2])


def raw_sql_migration(db, sql: str, params=None):
    """Execute one raw SQL statement in a migration."""
    return db.execute(sql, params)


def introspect_table_exists(db, table_name: str) -> bool:
    """Return True when the table exists."""
    if _is_postgres(db):
        db.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_name = ? LIMIT 1",
            (table_name,),
        )
    else:
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (table_name,),
        )
    return db.fetchone() is not None


def introspect_column_exists(db, table_name: str, column_name: str) -> bool:
    """Return True when the column exists in the table."""
    if _is_postgres(db):
        db.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ? AND column_name = ? LIMIT 1",
            (table_name, column_name),
        )
        return db.fetchone() is not None

    table_q = quote_identifier(table_name)
    db.execute(f"PRAGMA table_info({table_q})")
    return any(row[1] == column_name for row in db.fetchall())


def introspect_index_exists(db, index_name: str) -> bool:
    """Return True when the index exists."""
    if _is_postgres(db):
        db.execute(
            "SELECT 1 FROM pg_indexes "
            "WHERE schemaname = current_schema() AND indexname = ? LIMIT 1",
            (index_name,),
        )
    else:
        db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='index' AND name=? LIMIT 1",
            (index_name,),
        )
    return db.fetchone() is not None


def introspect_table_columns(db, table_name: str) -> list[dict]:
    """Return table columns metadata."""
    if _is_postgres(db):
        db.execute(
            "SELECT ordinal_position, column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = current_schema() AND table_name = ? "
            "ORDER BY ordinal_position",
            (table_name,),
        )
        return [
            {
                "cid": row[0] - 1,
                "name": row[1],
                "type": row[2],
                "notnull": 0 if row[3] == "YES" else 1,
                "default": row[4],
                "pk": 0,
            }
            for row in db.fetchall()
        ]

    table_q = quote_identifier(table_name)
    db.execute(f"PRAGMA table_info({table_q})")
    return [
        {
            "cid": row[0],
            "name": row[1],
            "type": row[2],
            "notnull": row[3],
            "default": row[4],
            "pk": row[5],
        }
        for row in db.fetchall()
    ]


def introspect_table_indexes(db, table_name: str) -> list[dict]:
    """Return table indexes metadata."""
    if _is_postgres(db):
        db.execute(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = current_schema() AND tablename = ?",
            (table_name,),
        )
        rows = db.fetchall()
        return [
            {
                "seq": i,
                "name": row[0],
                "unique": 1 if "UNIQUE INDEX" in row[1].upper() else 0,
                "origin": "c",
                "partial": 1 if " WHERE " in row[1].upper() else 0,
            }
            for i, row in enumerate(rows)
        ]

    table_q = quote_identifier(table_name)
    db.execute(f"PRAGMA index_list({table_q})")
    return [
        {
            "seq": row[0],
            "name": row[1],
            "unique": row[2],
            "origin": row[3],
            "partial": row[4],
        }
        for row in db.fetchall()
    ]


def schema_rename_table(db, old_name: str, new_name: str) -> None:
    """Rename a table."""
    old_q = quote_identifier(old_name)
    new_q = quote_identifier(new_name)
    db.execute(f"ALTER TABLE {old_q} RENAME TO {new_q}")


def schema_add_column(
    db,
    table_name: str,
    column_name: str,
    column_type: str,
    *,
    not_null: bool = False,
    default_sql: str | None = None,
) -> None:
    """Add a column with optional NOT NULL and SQL default."""
    table_q = quote_identifier(table_name)
    col_q = quote_identifier(column_name)

    parts = [f"ALTER TABLE {table_q} ADD COLUMN {col_q} {column_type}"]
    if not_null:
        parts.append("NOT NULL")
    if default_sql is not None:
        parts.append(f"DEFAULT {default_sql}")

    db.execute(" ".join(parts))


def schema_rename_column(db, table_name: str, old_name: str, new_name: str) -> None:
    """Rename a column (SQLite 3.25+)."""
    table_q = quote_identifier(table_name)
    old_q = quote_identifier(old_name)
    new_q = quote_identifier(new_name)
    db.execute(f"ALTER TABLE {table_q} RENAME COLUMN {old_q} TO {new_q}")


def schema_drop_column(db, table_name: str, column_name: str) -> None:
    """Drop a column (SQLite 3.35+), otherwise raise SillyDbError."""
    if _sqlite_version_tuple(db) < (3, 35, 0):
        raise SillyDbError("DROP COLUMN requires SQLite >= 3.35.0.")
    table_q = quote_identifier(table_name)
    col_q = quote_identifier(column_name)
    db.execute(f"ALTER TABLE {table_q} DROP COLUMN {col_q}")


def schema_create_index(
    db,
    table_name: str,
    column_names: list[str] | tuple[str, ...],
    *,
    index_name: str | None = None,
    unique: bool = False,
    if_not_exists: bool = True,
) -> str:
    """Create an index and return the final index name."""
    if not column_names:
        raise SillyDbError("schema_create_index requires at least one column.")

    idx_name = index_name or make_index_name(table_name, column_names)
    idx_q = quote_identifier(idx_name)
    table_q = quote_identifier(table_name)
    cols_q = ", ".join(quote_identifier(col) for col in column_names)

    unique_sql = "UNIQUE " if unique else ""
    ine_sql = "IF NOT EXISTS " if if_not_exists else ""
    db.execute(f"CREATE {unique_sql}INDEX {ine_sql}{idx_q} ON {table_q} ({cols_q})")
    return idx_name


def schema_drop_index(db, index_name: str, *, if_exists: bool = True) -> None:
    """Drop an index by name."""
    idx_q = quote_identifier(index_name)
    ie_sql = "IF EXISTS " if if_exists else ""
    db.execute(f"DROP INDEX {ie_sql}{idx_q}")


def safe_rename_table(db, old_name: str, new_name: str) -> bool:
    """Rename table only if old exists and new does not."""
    if not introspect_table_exists(db, old_name):
        return False
    if introspect_table_exists(db, new_name):
        return False
    schema_rename_table(db, old_name, new_name)
    return True


def safe_add_column(
    db,
    table_name: str,
    column_name: str,
    column_type: str,
    *,
    not_null: bool = False,
    default_sql: str | None = None,
) -> bool:
    """Add column only if it does not already exist."""
    if introspect_column_exists(db, table_name, column_name):
        return False
    schema_add_column(
        db,
        table_name,
        column_name,
        column_type,
        not_null=not_null,
        default_sql=default_sql,
    )
    return True


def safe_rename_column(db, table_name: str, old_name: str, new_name: str) -> bool:
    """Rename column only if old exists and new does not."""
    if not introspect_column_exists(db, table_name, old_name):
        return False
    if introspect_column_exists(db, table_name, new_name):
        return False
    schema_rename_column(db, table_name, old_name, new_name)
    return True


def safe_drop_column(db, table_name: str, column_name: str) -> bool:
    """Drop column only if it exists."""
    if not introspect_column_exists(db, table_name, column_name):
        return False
    schema_drop_column(db, table_name, column_name)
    return True


def safe_create_index(
    db,
    table_name: str,
    column_names: list[str] | tuple[str, ...],
    *,
    index_name: str | None = None,
    unique: bool = False,
) -> str | None:
    """Create index only if it does not already exist."""
    candidate = index_name or make_index_name(table_name, column_names)
    if introspect_index_exists(db, candidate):
        return None
    return schema_create_index(
        db,
        table_name,
        column_names,
        index_name=candidate,
        unique=unique,
        if_not_exists=False,
    )


def safe_drop_index(db, index_name: str) -> bool:
    """Drop index only if it exists."""
    if not introspect_index_exists(db, index_name):
        return False
    schema_drop_index(db, index_name, if_exists=False)
    return True


__all__ = [
    "quote_identifier",
    "make_index_name",
    "raw_sql_migration",
    "introspect_table_exists",
    "introspect_column_exists",
    "introspect_index_exists",
    "introspect_table_columns",
    "introspect_table_indexes",
    "schema_rename_table",
    "schema_add_column",
    "schema_rename_column",
    "schema_drop_column",
    "schema_create_index",
    "schema_drop_index",
    "safe_rename_table",
    "safe_add_column",
    "safe_rename_column",
    "safe_drop_column",
    "safe_create_index",
    "safe_drop_index",
]
