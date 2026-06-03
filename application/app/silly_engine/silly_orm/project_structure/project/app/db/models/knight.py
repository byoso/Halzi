from dataclasses import dataclass

from silly_orm.models import Model
from silly_orm.relations.oto import Oto
from silly_orm.relations.otm import Otm
from silly_orm.relations.mtm import Mtm


@dataclass
class Knight(Model):
    name: str
    age: int
    sword: Oto = Oto("swords")
    dragons_killed: Otm = Otm("dead_dragons")
    courted_princesses: Mtm = Mtm("courted_princesses")
