from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.database import Database
from app.models import (
    ActivityEvent,
    InvestigationReport,
    InvestigationRequest,
    InvestigationResponse,
    InvestigationStatus,
)


class InvestigationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(self, request: InvestigationRequest) -> InvestigationResponse:
        investigation_id = uuid4()
        async with self._database.connection() as connection:
            row = await connection.execute(
                """
                INSERT INTO investigations (id, status, problem, submitted_sql)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (
                    investigation_id,
                    InvestigationStatus.QUEUED.value,
                    request.problem.strip(),
                    request.sql.strip() if request.sql else None,
                ),
            )
            record = await row.fetchone()
            await connection.commit()
        return self._to_response(record)

    async def get(self, investigation_id: UUID) -> InvestigationResponse | None:
        async with self._database.readonly_connection() as connection:
            cursor = await connection.execute(
                "SELECT * FROM investigations WHERE id = %s", (investigation_id,)
            )
            record = await cursor.fetchone()
        return self._to_response(record) if record else None

    async def set_status(self, investigation_id: UUID, status: InvestigationStatus) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                "UPDATE investigations SET status = %s, updated_at = now() WHERE id = %s",
                (status.value, investigation_id),
            )
            await connection.commit()

    async def append_event(
        self,
        investigation_id: UUID,
        kind: str,
        summary: str,
        result: dict[str, Any] | None = None,
    ) -> None:
        async with self._database.connection() as connection:
            cursor = await connection.execute(
                "SELECT jsonb_array_length(events) AS count FROM investigations WHERE id = %s",
                (investigation_id,),
            )
            row = await cursor.fetchone()
            sequence = int(row["count"]) if row else 0
            event = ActivityEvent(
                sequence=sequence,
                kind=kind,
                summary=summary,
                tool_name=result.get("tool") if result else None,
                result_preview=result,
                created_at=datetime.now(UTC),
            )
            await connection.execute(
                """
                UPDATE investigations
                SET events = events || %s::jsonb, updated_at = now()
                WHERE id = %s
                """,
                (Jsonb([event.model_dump(mode="json")]), investigation_id),
            )
            await connection.commit()

    async def complete(self, investigation_id: UUID, report: InvestigationReport) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE investigations
                SET status = 'completed', report = %s, error = NULL, updated_at = now()
                WHERE id = %s
                """,
                (Jsonb(report.model_dump(mode="json")), investigation_id),
            )
            await connection.commit()

    async def fail(self, investigation_id: UUID, message: str) -> None:
        async with self._database.connection() as connection:
            await connection.execute(
                """
                UPDATE investigations
                SET status = 'failed', error = %s, updated_at = now()
                WHERE id = %s
                """,
                (message[:2_000], investigation_id),
            )
            await connection.commit()

    @staticmethod
    def _to_response(record: dict[str, Any]) -> InvestigationResponse:
        report = InvestigationReport.model_validate(record["report"]) if record["report"] else None
        events = [ActivityEvent.model_validate(item) for item in record["events"]]
        return InvestigationResponse(
            id=record["id"],
            status=InvestigationStatus(record["status"]),
            events=events,
            report=report,
            error=record["error"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

