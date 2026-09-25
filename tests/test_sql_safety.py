import pytest

from app.agent.sql_safety import UnsafeSQLError, validate_readonly_sql


@pytest.mark.parametrize(
    "query",
    [
        "SELECT * FROM orders WHERE id = 1",
        "WITH recent AS (SELECT * FROM orders) SELECT * FROM recent",
        "SELECT id FROM users UNION SELECT user_id FROM orders",
    ],
)
def test_accepts_readonly_queries(query: str) -> None:
    assert validate_readonly_sql(query).normalized


@pytest.mark.parametrize(
    "query",
    [
        "DELETE FROM orders",
        "UPDATE users SET email = 'x'",
        "INSERT INTO users (email, full_name, region) VALUES ('x', 'x', 'x')",
        "DROP TABLE users",
        "ALTER TABLE users ADD COLUMN unsafe text",
        "TRUNCATE users",
        "SELECT * INTO copied_users FROM users",
        "SELECT * FROM users; DELETE FROM users",
        "WITH removed AS (DELETE FROM orders RETURNING *) SELECT * FROM removed",
        "SELECT * FROM orders FOR UPDATE",
        "SELECT pg_terminate_backend(123)",
        "SELECT nextval('orders_id_seq')",
        "SELECT set_config('statement_timeout', '0', false)",
    ],
)
def test_rejects_unsafe_queries(query: str) -> None:
    with pytest.raises(UnsafeSQLError):
        validate_readonly_sql(query)
