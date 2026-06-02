import psycopg2

from .base import BaseConnector
from ..tools import SillyDbError


class PostgresConnector(BaseConnector):
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.conn = None
        self.cursor = None

    def connect(self):
        try:
            self.conn = psycopg2.connect(self.dsn)
            self.cursor = self.conn.cursor()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres connect failed: {e}") from e

    def execute(self, query: str, params=None):
        if params is None:
            params = ()
        try:
            # psycopg2 uses %s placeholders.
            query = query.replace("?", "%s")
            return self.cursor.execute(query, params)
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres execute failed: {e}. Query: {query}") from e

    def fetchone(self):
        try:
            return self.cursor.fetchone()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres fetchone failed: {e}") from e

    def fetchall(self):
        try:
            return self.cursor.fetchall()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres fetchall failed: {e}") from e

    def commit(self):
        try:
            self.conn.commit()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres commit failed: {e}") from e

    def rollback(self):
        try:
            self.conn.rollback()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres rollback failed: {e}") from e

    def close(self):
        try:
            self.conn.close()
        except psycopg2.Error as e:
            raise SillyDbError(f"Postgres close failed: {e}") from e