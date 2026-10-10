from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite


class Database:
    def __init__(self, path: Path, migrations_path: Path) -> None:
        self.path = path.resolve()
        self.migrations_path = migrations_path.resolve()

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        async with self.connection() as connection:
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                )
                """
            )
            cursor = await connection.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in await cursor.fetchall()}

            for migration in sorted(self.migrations_path.glob("*.sql")):
                version = migration.stem.split("_", 1)[0]
                if version in applied:
                    continue
                await connection.executescript(migration.read_text(encoding="utf-8"))
                await connection.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES (?, ?)",
                    (version, migration.name),
                )
            await connection.commit()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[aiosqlite.Connection]:
        connection = await aiosqlite.connect(self.path, timeout=10)
        connection.row_factory = aiosqlite.Row
        await connection.execute("PRAGMA foreign_keys = ON")
        await connection.execute("PRAGMA journal_mode = WAL")
        await connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            await connection.close()

    async def fetch_one(self, query: str, parameters: Sequence[Any] = ()) -> dict[str, Any] | None:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def fetch_all(self, query: str, parameters: Sequence[Any] = ()) -> list[dict[str, Any]]:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            return [dict(row) for row in await cursor.fetchall()]

    async def execute(self, query: str, parameters: Sequence[Any] = ()) -> int:
        async with self.connection() as connection:
            cursor = await connection.execute(query, parameters)
            await connection.commit()
            return cursor.lastrowid or 0

    async def executemany(self, query: str, values: Iterable[Sequence[Any]]) -> None:
        async with self.connection() as connection:
            await connection.executemany(query, values)
            await connection.commit()
