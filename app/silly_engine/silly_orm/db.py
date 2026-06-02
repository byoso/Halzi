from dataclasses import asdict, dataclass
import logging
from pathlib import Path
from typing import get_type_hints, Callable
from contextlib import contextmanager

from .connectors.sqlite import SQLiteConnector
from .models import Model
from .relations.mtm import Mtm
from .relations.mto import Mto
from .relations.oto import Oto
from .table import Table
from .tools import SillyDbError

logger = logging.getLogger("SillyDb")

def version_tuple(version_str: str | None) -> tuple[int, ...]:
    """Convert a version string like '1.2.3' to a tuple (1, 2, 3) for comparison."""
    if version_str is None:
        return (0, 0, 0)
    try:
        return tuple(int(part) for part in version_str.split('.'))
    except ValueError:
        raise SillyDbError(f"Invalid version format: '{version_str}'. Expected format is 'X.Y.Z' where X, Y, Z are integers.")


def _is_connector_module(connector, module_suffix: str) -> bool:
    return connector.__class__.__module__.endswith(module_suffix)


def _is_postgres_connector(connector) -> bool:
    return _is_connector_module(connector, ".connectors.postgres")


def _is_mtm_annotation(field_type) -> bool:
    return "Mtm" in str(field_type)


def _is_otm_annotation(field_type) -> bool:
    return "Otm" in str(field_type)

def generate_create_table_sql(name: str, model: type, connector=None) -> str:
    """
    Automatically generates the CREATE TABLE SQL command for SQLite
    from a dataclass. Adds singleton constraint if model Meta.singleton is True.
    Adds _created_at, _updated_at, _expires_at based on Meta config.
    """
    fields = []
    is_postgres = connector is not None and _is_postgres_connector(connector)
    type_map = (
        {
            str: "TEXT",
            int: "BIGINT",
            float: "DOUBLE PRECISION",
            bool: "BOOLEAN",
        }
        if is_postgres
        else {
            str: "TEXT",
            int: "INTEGER",
            float: "REAL",
            bool: "INTEGER",  # SQLite has no native bool
        }
    )

    hints = get_type_hints(model)
    for field_name, field_type in hints.items():
        # MTM relations are persisted in dedicated join tables.
        if _is_mtm_annotation(field_type):
            continue

        # OTM relations are inverse lookups and do not need a local column.
        if _is_otm_annotation(field_type):
            continue

        # if the type is a relation Oto/Otm/Mto/Mtm, store as TEXT (id) or JSON (list)
        if str(field_type).startswith(("Oto", "Mto", "Otm", "Mtm")):
            fields.append(f"{field_name} TEXT")
        else:
            sqlite_type = type_map.get(field_type, "TEXT")
            fields.append(f"{field_name} {sqlite_type}")

    # _id is assumed to always exist and be the PK
    if "_id" not in hints:
        raise SillyDbError(f"Dataclass {model.__name__} must have a _id field")

    # Add Meta-driven auxiliary fields.
    meta = model.get_meta()
    if hasattr(meta, 'ttl') and meta.ttl:
        fields.append("_expires_at BIGINT" if is_postgres else "_expires_at INTEGER")

    # Add singleton constraint if enabled
    constraints = []
    if hasattr(meta, 'singleton') and meta.singleton:
        fields.append("_singleton_lock INTEGER DEFAULT 1")
        constraints.append("UNIQUE(_singleton_lock)")

    # Add unique constraints from Meta.unique
    if hasattr(meta, 'unique') and meta.unique:
        for field_or_fields in meta.unique:
            if isinstance(field_or_fields, (list, tuple)):
                constraints.append(f"UNIQUE({', '.join(field_or_fields)})")
            else:
                constraints.append(f"UNIQUE({field_or_fields})")

    fields_str = ", ".join(fields)
    if constraints:
        fields_str += ", " + ", ".join(constraints)

    sql = f"CREATE TABLE IF NOT EXISTS {name} ({fields_str}, PRIMARY KEY(_id))"
    return sql


@dataclass
class Settings(Model):
    version: str = "0.0.0"
    description: str = "SillyORM - a simple ORM for Python"

    class Meta(Model.Meta):
        singleton = True


class SillyDb:
    def __init__(self, db_path: str | Path | None = None, connector=None, logger=logger):
        """
        Initialize the DB.
        - If a connector is provided, use it.
        - Otherwise, if db_path is provided, use SQLite by default.
        - Otherwise, raise an exception.
        """

        self._tables = {}
        self._model_to_table = {}
        self._in_transaction = False
        self._transaction_depth = 0
        self.logger = logger
        if connector is None and db_path is not None:
            self.connector = SQLiteConnector(db_path)
        elif connector is not None:
            self.connector = connector
        else:
            raise SillyDbError("Either db_path or connector must be provided")

        self.connector.connect()
        self._initialize_internal_tables()

    def _table_exists(self, table_name: str) -> bool:
        if _is_postgres_connector(self.connector):
            self.connector.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = ? LIMIT 1",
                (table_name,),
            )
        else:
            self.connector.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (table_name,),
            )
        return self.connector.fetchone() is not None

    def _initialize_internal_tables(self) -> None:
        settings_table = "_settings"
        settings_table_obj = Table(self, settings_table, Settings)

        with self.transaction():
            if not self._table_exists(settings_table):
                sql = generate_create_table_sql(settings_table, Settings, connector=self.connector)
                self.connector.execute(sql)

            # Seed default singleton row once so dataclass defaults are persisted.
            self.connector.execute(f"SELECT COUNT(1) FROM {settings_table}")
            row_count = self.connector.fetchone()[0]
            if row_count == 0:
                settings_table_obj.insert(asdict(Settings()))

        # Register internal table in ORM cache only after successful initialization.
        self._tables[settings_table] = settings_table_obj
        self._model_to_table[Settings] = settings_table

    def table_name_for_model(self, model_cls):
        return self._model_to_table.get(model_cls)

    def ensure_mtm_table(self, source_table: str, rel: Mtm):
        # Configure MTM relation with canonical table ordering
        left, right = sorted((source_table, rel.target))
        rel.through = f"_mtm_{left}__{right}"
        rel.source_field = f"{left}_id" if source_table == left else f"{right}_id"
        rel.target_field = f"{right}_id" if source_table == left else f"{left}_id"

        sql = f"""
        CREATE TABLE IF NOT EXISTS {rel.through} (
            {rel.source_field} TEXT,
            {rel.target_field} TEXT,
            UNIQUE({rel.source_field}, {rel.target_field})
        )
        """
        self.connector.execute(sql)

        idx1 = f"idx_{rel.through}_{rel.source_field}"
        idx2 = f"idx_{rel.through}_{rel.target_field}"

        self.connector.execute(
            f"CREATE INDEX IF NOT EXISTS {idx1} ON {rel.through} ({rel.source_field})"
        )
        self.connector.execute(
            f"CREATE INDEX IF NOT EXISTS {idx2} ON {rel.through} ({rel.target_field})"
        )

    def _initialize_mtm_relations(self, table_name: str, model: type):
        relations = model.get_relations()

        for rel in relations.values():
            if isinstance(rel, Mtm):
                self.ensure_mtm_table(table_name, rel)

    def _initialize_fk_indexes(self, table_name: str, model: type):
        relations = model.get_relations()

        for field_name, rel in relations.items():
            if isinstance(rel, (Oto, Mto)):
                idx = f"idx_{table_name}_{field_name}"
                self.connector.execute(
                    f"CREATE INDEX IF NOT EXISTS {idx} ON {table_name} ({field_name})"
                )

    def _initialize_meta_indexes(self, table_name: str, model: type):
        meta = model.get_meta()
        if not hasattr(meta, 'indexes') or not meta.indexes:
            return
        for field_name in meta.indexes:
            idx = f"idx_{table_name}_{field_name}"
            self.connector.execute(
                f"CREATE INDEX IF NOT EXISTS {idx} ON {table_name} ({field_name})"
            )

    def migrate(self, migrations: dict[str, Callable[["SillyDb"], None]], target_version: str | None = None):
        """
        Apply migrations in order, using version comparison logic similar to JsonDb.
        - migrations: dict mapping version string to migration function
        - target_version: if set, only migrate up to this version (inclusive)
        """
        if not isinstance(migrations, dict):
            raise SillyDbError("Migrations must be a dict {version: function}")

        db_settings = self._tables["_settings"].first()
        if db_settings is None:
            raise SillyDbError("Missing _settings row in database")
        current_version = db_settings.q.version

        # If no explicit target_version, use the highest migration version
        migration_versions = sorted(migrations.keys(), key=version_tuple)
        if target_version is None and migration_versions:
            target_version = migration_versions[-1]

        for migration_version in migration_versions:
            if version_tuple(current_version) < version_tuple(migration_version) <= version_tuple(target_version):
                self.logger.info(f"Migration to v{migration_version}...")
                try:
                    with self.transaction():
                        migrations[migration_version](self)
                        db_settings = self._tables["_settings"].first()
                        if db_settings is None:
                            raise SillyDbError("Missing _settings row while updating migration version")
                        self._tables["_settings"].update(db_settings.q._id, version=migration_version)
                    self.logger.info(f"Successfully upgraded SillyDb to v{migration_version}")
                    current_version = migration_version
                except Exception as e:
                    self.logger.error(f"Migration {migration_version} failed: {str(e)}")
                    if _is_connector_module(self.connector, ".connectors.sqlite"):
                        self.logger.warning("SQLite DDL rollback may be partial; verify schema changes manually.")
                    raise SillyDbError(f"Migration {migration_version} failed: {str(e)}") from e

        # Final version update if needed
        if current_version != target_version:
            db_settings = self._tables["_settings"].first()
            if db_settings is None:
                raise SillyDbError("Missing _settings row while updating final migration version")
            self._tables["_settings"].update(db_settings.q._id, version=target_version)
            self.logger.info(f"Database version set to {target_version}")

    def table(self, name_or_model, model=None) -> "Table":
        """
        Return a Table object for the given table name and model.
        Returns:
            Table: The table object for further operations (insert, filter, etc).
        """
        # If name_or_model is a class, extract table name from Meta.table_name or class name
        if isinstance(name_or_model, type):
            model = name_or_model
            meta = model.get_meta()
            name = (meta.table_name if hasattr(meta, 'table_name') and meta.table_name
                    else model.__name__.lower())
        else:
            name = name_or_model

        if name not in self._tables:
            if model is None:
                raise SillyDbError("model required for first declaration")

            table_obj = Table(self, name, model)

            with self.transaction():
                # --- automatic table creation ---
                sql = generate_create_table_sql(name, model, connector=self.connector)
                self.connector.execute(sql)

                # --- automatic MTM join table creation ---
                self._initialize_mtm_relations(name, model)

                # --- automatic index creation for FK relation columns ---
                self._initialize_fk_indexes(name, model)

                # --- automatic index creation from Meta.indexes ---
                self._initialize_meta_indexes(name, model)

            self._tables[name] = table_obj
            self._model_to_table[model] = name

        return self._tables[name]

    def execute(self, query: str, params=None):
        return self.connector.execute(query, params)

    def fetchone(self):
        return self.connector.fetchone()

    def fetchall(self):
        return self.connector.fetchall()

    def commit(self):
        self.connector.commit()

    def rollback(self):
        """Rollback uncommitted changes."""
        self.connector.rollback()

    @contextmanager
    def transaction(self):
        """Context manager for automatic transaction handling.
        Commits on success, rolls back on exception.

        Usage:
            with db.transaction():
                db.table('users').insert({'name': 'Alice'})
                # auto-commits on exit if no exception
        """
        is_outer_transaction = self._transaction_depth == 0
        self._transaction_depth += 1
        self._in_transaction = True
        try:
            yield
            if is_outer_transaction:
                self.commit()
        except Exception:
            if is_outer_transaction:
                self.rollback()
            raise
        finally:
            self._transaction_depth -= 1
            self._in_transaction = self._transaction_depth > 0

    def close(self):
        self.connector.close()