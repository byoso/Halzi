from .connection import db
from .models import Knight


Knights = db.table("knights", Knight)
