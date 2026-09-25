import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from psycopg import sql
from pydantic import BaseModel, ConfigDict, Field

from app.agent.plan import inspect_plan_document
from app.agent.sql_safety import validate_readonly_sql
from app.database import Database

logger = structlog.get_logger(__name__)


class ToolResult(BaseModel):
    tool: str
    data: Any
    row_count: int | None = None
    truncated: bool = False
    duration_ms: float = Field(ge=0)


class TableArguments(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    table_name: str = Field(min_length=1, max_length=128)
    schema_name: str = Field(default="public", alias="schema", min_length=1, max_length=128)


class QueryArguments(BaseModel):
    query: str = Field(min_length=1, max_length=100_000)


class PlanArguments(BaseModel):
    plan: list[dict[str, Any]] | dict[str, Any]


class DatabaseTools:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def _recorded(
        self, name: str, arguments: dict[str, Any], operation: Callable[[], Awaitable[ToolResult]]
    ) -> ToolResult:
        started = time.perf_counter()
        log = logger.bind(tool=name, arguments=arguments)
        log.info("database_tool_started")
        try:
            result = await operation()
        except Exception as exc:
            log.warning(
                "database_tool_failed",
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                error_type=type(exc).__name__,
            )
            raise
        log.info(
            "database_tool_completed",
            duration_ms=result.duration_ms,
            row_count=result.row_count,
            truncated=result.truncated,
        )
        return result

    async def _query(
        self,
        tool_name: str,
        statement: str | sql.Composed,
        parameters: tuple[Any, ...] = (),
        *,
        max_rows: int | None = None,
    ) -> ToolResult:
        started = time.perf_counter()
        limit = max_rows or self._database.max_rows
        async with self._database.readonly_connection() as connection:
            async with connection.cursor() as cursor:
                await cursor.execute(statement, parameters)
                rows = await cursor.fetchmany(limit + 1)
        truncated = len(rows) > limit
        serializable_rows = [dict(row) for row in rows[:limit]]
        return ToolResult(
            tool=tool_name,
            data=serializable_rows,
            row_count=len(serializable_rows),
            truncated=truncated,
            duration_ms=round((time.perf_counter() - started) * 1000, 2),
        )

    async def list_tables(self) -> ToolResult:
        async def operation() -> ToolResult:
            return await self._query(
                "list_tables",
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """,
            )

        return await self._recorded("list_tables", {}, operation)

    async def describe_table(self, table_name: str, schema: str = "public") -> ToolResult:
        async def operation() -> ToolResult:
            return await self._query(
                "describe_table",
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table_name),
            )

        return await self._recorded(
            "describe_table", {"schema": schema, "table_name": table_name}, operation
        )

    async def list_indexes(self, table_name: str, schema: str = "public") -> ToolResult:
        async def operation() -> ToolResult:
            return await self._query(
                "list_indexes",
                """
                SELECT indexname AS index_name, indexdef AS definition
                FROM pg_indexes
                WHERE schemaname = %s AND tablename = %s
                ORDER BY indexname
                """,
                (schema, table_name),
            )

        return await self._recorded(
            "list_indexes", {"schema": schema, "table_name": table_name}, operation
        )

    async def get_table_statistics(
        self, table_name: str, schema: str = "public"
    ) -> ToolResult:
        async def operation() -> ToolResult:
            return await self._query(
                "get_table_statistics",
                """
                SELECT
                    s.schemaname AS table_schema,
                    s.relname AS table_name,
                    s.n_live_tup AS estimated_live_rows,
                    s.n_dead_tup AS estimated_dead_rows,
                    s.seq_scan,
                    s.idx_scan,
                    s.last_analyze,
                    s.last_autoanalyze,
                    pg_total_relation_size(s.relid) AS total_bytes
                FROM pg_stat_user_tables AS s
                WHERE s.schemaname = %s AND s.relname = %s
                """,
                (schema, table_name),
            )

        return await self._recorded(
            "get_table_statistics", {"schema": schema, "table_name": table_name}, operation
        )

    async def execute_readonly_query(self, query: str) -> ToolResult:
        validated = validate_readonly_sql(query)

        async def operation() -> ToolResult:
            return await self._query("execute_readonly_query", validated.normalized)

        return await self._recorded(
            "execute_readonly_query", {"sql_length": len(query)}, operation
        )

    async def explain_query(self, query: str) -> ToolResult:
        return await self._explain(query, analyze=False)

    async def explain_analyze_query(self, query: str) -> ToolResult:
        return await self._explain(query, analyze=True)

    async def _explain(self, query: str, *, analyze: bool) -> ToolResult:
        validated = validate_readonly_sql(query)
        tool_name = "explain_analyze_query" if analyze else "explain_query"

        async def operation() -> ToolResult:
            started = time.perf_counter()
            options = "ANALYZE, BUFFERS, WAL, FORMAT JSON" if analyze else "FORMAT JSON"
            statement = f"EXPLAIN ({options}) {validated.normalized}"
            async with self._database.readonly_connection() as connection:
                async with connection.cursor() as cursor:
                    await cursor.execute(statement)
                    row = await cursor.fetchone()
            plan = row["QUERY PLAN"] if row else []
            return ToolResult(
                tool=tool_name,
                data=plan,
                row_count=1 if row else 0,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        return await self._recorded(tool_name, {"sql_length": len(query)}, operation)

    async def inspect_query_plan(
        self, plan: list[dict[str, Any]] | dict[str, Any]
    ) -> ToolResult:
        async def operation() -> ToolResult:
            started = time.perf_counter()
            findings = inspect_plan_document(plan)
            return ToolResult(
                tool="inspect_query_plan",
                data=findings,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )

        return await self._recorded("inspect_query_plan", {"plan_supplied": True}, operation)

    async def get_database_version(self) -> ToolResult:
        async def operation() -> ToolResult:
            return await self._query("get_database_version", "SELECT version() AS version")

        return await self._recorded("get_database_version", {}, operation)

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        if tool_name == "list_tables":
            return await self.list_tables()
        if tool_name == "describe_table":
            parsed = TableArguments.model_validate(arguments)
            return await self.describe_table(parsed.table_name, parsed.schema_name)
        if tool_name == "list_indexes":
            parsed = TableArguments.model_validate(arguments)
            return await self.list_indexes(parsed.table_name, parsed.schema_name)
        if tool_name == "get_table_statistics":
            parsed = TableArguments.model_validate(arguments)
            return await self.get_table_statistics(parsed.table_name, parsed.schema_name)
        if tool_name == "execute_readonly_query":
            parsed = QueryArguments.model_validate(arguments)
            return await self.execute_readonly_query(parsed.query)
        if tool_name == "explain_query":
            parsed = QueryArguments.model_validate(arguments)
            return await self.explain_query(parsed.query)
        if tool_name == "explain_analyze_query":
            parsed = QueryArguments.model_validate(arguments)
            return await self.explain_analyze_query(parsed.query)
        if tool_name == "inspect_query_plan":
            parsed = PlanArguments.model_validate(arguments)
            return await self.inspect_query_plan(parsed.plan)
        if tool_name == "get_database_version":
            return await self.get_database_version()
        raise ValueError(f"Unknown database tool: {tool_name}")
