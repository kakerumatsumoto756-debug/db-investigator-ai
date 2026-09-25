import pytest

from app.agent.sql_safety import UnsafeSQLError
from app.agent.tools import DatabaseTools
from app.config import get_settings
from app.database import Database


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_tools_against_postgresql() -> None:
    database = Database(get_settings())
    await database.open()
    try:
        tools = DatabaseTools(database)
        tables = await tools.execute("list_tables", {})
        assert "orders" in {row["table_name"] for row in tables.data}

        description = await tools.execute("describe_table", {"table_name": "orders"})
        assert {row["column_name"] for row in description.data} >= {
            "id",
            "user_id",
            "status",
            "total_cents",
            "created_at",
        }

        indexes = await tools.execute("list_indexes", {"table_name": "orders"})
        assert "orders_pkey" in {row["index_name"] for row in indexes.data}

        statistics = await tools.execute("get_table_statistics", {"table_name": "orders"})
        assert statistics.data[0]["estimated_live_rows"] > 0

        result = await tools.execute(
            "execute_readonly_query", {"query": "SELECT n FROM generate_series(1, 205) AS n"}
        )
        assert result.row_count == 200
        assert result.truncated is True

        estimate = await tools.execute(
            "explain_query",
            {"query": "SELECT id FROM orders WHERE user_id = 1544 ORDER BY created_at DESC"},
        )
        assert estimate.row_count == 1

        plan = await tools.execute(
            "explain_analyze_query",
            {
                "query": (
                    "SELECT id FROM orders WHERE user_id = 1544 "
                    "ORDER BY created_at DESC LIMIT 25"
                )
            },
        )
        inspection = await tools.execute("inspect_query_plan", {"plan": plan.data})
        assert inspection.data["execution_time_ms"] >= 0

        version = await tools.execute("get_database_version", {})
        assert version.data[0]["version"].startswith("PostgreSQL 16")

        with pytest.raises(UnsafeSQLError):
            await tools.execute("execute_readonly_query", {"query": "DELETE FROM orders"})

        with pytest.raises(ValueError, match="Unknown database tool"):
            await tools.execute("not_a_tool", {})
    finally:
        await database.close()
