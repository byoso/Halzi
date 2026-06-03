from .base import SillyOrmRelation
from ..tools import SillyDbError


class Mtm(SillyOrmRelation):
    def __init__(self, target: str):
        self.target = target
        self.through: str | None = None
        self.source_field: str | None = None
        self.target_field: str | None = None

    def resolve(self, db, value):
        if value is None:
            return []

        if not (self.through and self.source_field and self.target_field):
            raise SillyDbError(
                "Mtm relation is not configured. Register tables through db.table(...) first."
            )

        db.execute(
            f"SELECT {self.target_field} FROM {self.through} WHERE {self.source_field} = ?",
            (value,),
        )
        ids = [r[0] for r in db.fetchall()]
        table = db.table(self.target)
        return [table.filter_first(_id) for _id in ids]