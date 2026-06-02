import sqlite3
from pathlib import Path
from .base import BaseConnector
from ..tools import SillyDbError

class SQLiteConnector(BaseConnector):
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.conn: sqlite3.Connection
        self.cursor: sqlite3.Cursor

    def connect(self):
        try:
            # Ensure the target directory exists for file-based SQLite databases.
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(self.db_path))
            self.cursor = self.conn.cursor()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite connect failed for '{self.db_path}': {e}") from e

    def execute(self, query: str, params=None) -> sqlite3.Cursor:
        if params is None:
            params = ()
        try:
            return self.cursor.execute(query, params)
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite execute failed: {e}. Query: {query}") from e

    def fetchone(self):
        try:
            return self.cursor.fetchone()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite fetchone failed: {e}") from e

    def fetchall(self):
        try:
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite fetchall failed: {e}") from e

    def commit(self):
        try:
            self.conn.commit()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite commit failed: {e}") from e

    def rollback(self):
        try:
            self.conn.rollback()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite rollback failed: {e}") from e

    def close(self):
        try:
            self.conn.close()
        except sqlite3.Error as e:
            raise SillyDbError(f"SQLite close failed: {e}") from e