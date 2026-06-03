
from .base import SillyOrmRelation
from .mto import Mto
from .oto import Oto
from ..tools import SillyDbError

class Otm(SillyOrmRelation):
    def __init__(self, target: str):
        self.target = target
        self.fk_field = None

    def resolve_fk_field(self, db, source_table: str) -> str:
        target_table = db.table(self.target)
        candidates = []

        for field_name, rel in target_table.model.get_relations().items():
            if isinstance(rel, (Oto, Mto)) and rel.target == source_table:
                candidates.append(field_name)

        if len(candidates) == 1:
            self.fk_field = candidates[0]
            return self.fk_field

        if not candidates:
            raise SillyDbError(
                f"Cannot infer Otm fk_field for target '{self.target}' and source '{source_table}'."
            )

        raise SillyDbError(
            f"Ambiguous Otm fk_field inference for target '{self.target}' and source '{source_table}': {candidates}."
        )

    def resolve(self, db, value, source_table: str | None = None):
        if value is None:
            return []

        if source_table is None:
            raise SillyDbError("source_table is required for Otm resolution")

        fk_field = self.resolve_fk_field(db, source_table)

        table = db.table(self.target)
        return table.filter(**{fk_field: value}).all()