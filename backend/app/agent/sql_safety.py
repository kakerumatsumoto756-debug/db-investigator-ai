from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError


class UnsafeSQLError(ValueError):
    """Raised when SQL is invalid or outside the read-only diagnostic policy."""


@dataclass(frozen=True)
class ValidatedSQL:
    original: str
    normalized: str


_ALLOWED_ROOTS = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_BLOCKED_NODE_NAMES = {
    "Alter",
    "Analyze",
    "Command",
    "Copy",
    "Create",
    "Delete",
    "Drop",
    "Grant",
    "Insert",
    "LoadData",
    "Lock",
    "Merge",
    "Pragma",
    "Revoke",
    "Set",
    "Transaction",
    "TruncateTable",
    "Update",
    "Use",
}
_BLOCKED_FUNCTIONS = {
    "dblink",
    "dblink_connect",
    "dblink_exec",
    "lo_export",
    "lo_import",
    "nextval",
    "pg_advisory_lock",
    "pg_advisory_xact_lock",
    "pg_cancel_backend",
    "pg_logical_emit_message",
    "pg_read_binary_file",
    "pg_read_file",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "pg_terminate_backend",
    "pg_write_binary_file",
    "set_config",
    "setval",
}


def validate_readonly_sql(statement: str) -> ValidatedSQL:
    source = statement.strip()
    if not source:
        raise UnsafeSQLError("SQL cannot be empty")

    try:
        parsed = [item for item in parse(source, read="postgres") if item is not None]
    except ParseError as exc:
        raise UnsafeSQLError(f"SQL could not be parsed: {exc}") from exc

    if len(parsed) != 1:
        raise UnsafeSQLError("Exactly one SQL statement is allowed")

    expression = parsed[0]
    if not isinstance(expression, _ALLOWED_ROOTS):
        raise UnsafeSQLError("Only SELECT queries are allowed")

    for node in expression.walk():
        if type(node).__name__ in _BLOCKED_NODE_NAMES:
            raise UnsafeSQLError(f"SQL operation {type(node).__name__.upper()} is not allowed")
        if isinstance(node, exp.Into):
            raise UnsafeSQLError("SELECT INTO is not allowed")
        if isinstance(node, exp.Func):
            function_name = (
                node.name.lower() if isinstance(node, exp.Anonymous) else node.sql_name().lower()
            )
            if function_name in _BLOCKED_FUNCTIONS:
                raise UnsafeSQLError(f"SQL function {function_name} is not allowed")

    if expression.args.get("locks"):
        raise UnsafeSQLError("Row-locking clauses are not allowed")

    return ValidatedSQL(original=source, normalized=expression.sql(dialect="postgres"))
