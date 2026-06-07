from __future__ import annotations

import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

COMMON_SCHEMA = [
    "CREATE INDEX IF NOT EXISTS idx_devices_online ON devices(online)",
    "CREATE INDEX IF NOT EXISTS idx_presence_events_happened_at ON presence_events(happened_at)",
]

SQLITE_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS devices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mac TEXT NOT NULL UNIQUE,
        ip TEXT,
        hostname TEXT,
        vendor TEXT,
        label TEXT,
        first_seen TEXT NOT NULL,
        last_seen TEXT NOT NULL,
        online INTEGER NOT NULL DEFAULT 0,
        missed_scans INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS presence_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL CHECK (event_type IN ('online', 'offline')),
        happened_at TEXT NOT NULL
    )
    """,
    *COMMON_SCHEMA,
]

POSTGRESQL_SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS devices (
        id BIGSERIAL PRIMARY KEY,
        mac TEXT NOT NULL UNIQUE,
        ip TEXT,
        hostname TEXT,
        vendor TEXT,
        label TEXT,
        first_seen TIMESTAMPTZ NOT NULL,
        last_seen TIMESTAMPTZ NOT NULL,
        online BOOLEAN NOT NULL DEFAULT FALSE,
        missed_scans INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS presence_events (
        id BIGSERIAL PRIMARY KEY,
        device_id BIGINT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
        event_type TEXT NOT NULL CHECK (event_type IN ('online', 'offline')),
        happened_at TIMESTAMPTZ NOT NULL
    )
    """,
    *COMMON_SCHEMA,
]


class Database(ABC):
    schema: list[str]

    @contextmanager
    def connect(self) -> Iterator[Any]:
        connection = self.open_connection()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @abstractmethod
    def open_connection(self):
        pass

    @abstractmethod
    def execute(self, connection, sql: str, params: tuple[Any, ...] = ()):
        pass

    @abstractmethod
    def insert(self, connection, sql: str, params: tuple[Any, ...]) -> int:
        pass

    def migrate(self) -> None:
        with self.connect() as connection:
            for statement in self.schema:
                self.execute(connection, statement)


class SQLiteDatabase(Database):
    schema = SQLITE_SCHEMA

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    def open_connection(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def execute(self, connection, sql: str, params: tuple[Any, ...] = ()):
        serialized = tuple(value.isoformat() if isinstance(value, datetime) else value for value in params)
        return connection.execute(sql, serialized)

    def insert(self, connection, sql: str, params: tuple[Any, ...]) -> int:
        return self.execute(connection, sql, params).lastrowid


class PostgreSQLDatabase(Database):
    schema = POSTGRESQL_SCHEMA

    def __init__(self, url: str):
        self.url = url

    def open_connection(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires psycopg; install project requirements") from exc
        return psycopg.connect(self.url, row_factory=dict_row)

    def execute(self, connection, sql: str, params: tuple[Any, ...] = ()):
        return connection.execute(sql.replace("?", "%s"), params)

    def insert(self, connection, sql: str, params: tuple[Any, ...]) -> int:
        cursor = self.execute(connection, f"{sql} RETURNING id", params)
        return cursor.fetchone()["id"]


def create_database(database: Path | str) -> Database:
    if isinstance(database, Path):
        return SQLiteDatabase(str(database))

    database_value = str(database)
    parsed = urlparse(database_value)
    if parsed.scheme in {"postgres", "postgresql"}:
        return PostgreSQLDatabase(database_value)
    if parsed.scheme and parsed.scheme != "sqlite":
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")
    if not parsed.scheme:
        return SQLiteDatabase(database_value)
    return SQLiteDatabase(_sqlite_path(parsed))


def _sqlite_path(parsed) -> str:
    if parsed.netloc:
        raise ValueError("SQLite connection strings must not include a host")
    if parsed.params or parsed.query or parsed.fragment:
        raise ValueError("SQLite connection string parameters are not supported")
    if parsed.path == "/:memory:":
        raise ValueError("In-memory SQLite databases are not supported")
    if not parsed.path:
        raise ValueError("SQLite connection string must include a database path")
    if parsed.path.startswith("//"):
        return parsed.path[1:]
    return parsed.path.lstrip("/")
