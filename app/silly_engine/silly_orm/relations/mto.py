from .base import SillyOrmRelation

class Mto(SillyOrmRelation):
    def __init__(self, target: str):
        self.target = target

    def resolve(self, db, value):
        table = db.table(self.target)
        return table.filter_first(_id=value)