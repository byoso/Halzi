
class SillyDbError(Exception):
    pass


# =======================================================================
# Migration helpers
# =======================================================================

def raw_sql_migration(db, sql: str):
    db.connector.execute(sql)