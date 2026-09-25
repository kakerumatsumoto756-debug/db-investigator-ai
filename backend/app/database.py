from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from psycopg import AsyncConnection, sql
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool = AsyncConnectionPool(
            conninfo=settings.database_url.get_secret_value(),
            min_size=1,
            max_size=5,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        await self._pool.open(wait=True)

    async def close(self) -> None:
        await self._pool.close()

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        async with self._pool.connection() as connection:
            yield connection

    @asynccontextmanager
    async def readonly_connection(self) -> AsyncIterator[AsyncConnection[dict[str, Any]]]:
        async with self._pool.connection() as connection:
            async with connection.transaction():
                await connection.execute("SET TRANSACTION READ ONLY")
                await connection.execute(
                    sql.SQL("SET LOCAL statement_timeout = {}").format(
                        sql.Literal(self._settings.db_statement_timeout_ms)
                    )
                )
                yield connection

    @property
    def max_rows(self) -> int:
        return self._settings.db_max_rows
