from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_migration_module(file_path: Path):
    spec = spec_from_file_location(file_path.stem, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load migration module: {file_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_migrations():
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.py"))

    migrations = []
    for file_path in migration_files:
        module = _load_migration_module(file_path)
        version = getattr(module, "MIGRATION_VERSION", None)
        upgrade = getattr(module, "upgrade", None)

        if version is None or upgrade is None:
            continue

        migrations.append((version, upgrade))

    return migrations


def run_migrations(db):
    db.migrate(load_migrations())
