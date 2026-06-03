

class SillyOrmRelation:
    _is_relation = True

    def resolve(self, db, value):
        raise NotImplementedError()