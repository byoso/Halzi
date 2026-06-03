from abc import ABC, abstractmethod
from typing import Any

class BaseConnector(ABC):
    """Interface for any database backend."""

    @abstractmethod
    def connect(self) -> Any:
        pass

    @abstractmethod
    def execute(self, query: str, params=None) -> Any:
        """Execute an SQL query (INSERT, UPDATE, DELETE, etc.)."""
        pass

    @abstractmethod
    def fetchone(self) -> Any:
        """Fetch a single result."""
        pass

    @abstractmethod
    def fetchall(self) -> Any:
        """Fetch all results."""
        pass

    @abstractmethod
    def commit(self) -> Any:
        """Commit pending changes."""
        pass

    @abstractmethod
    def rollback(self) -> Any:
        """Rollback uncommitted changes."""
        pass

    @abstractmethod
    def close(self) -> Any:
        pass