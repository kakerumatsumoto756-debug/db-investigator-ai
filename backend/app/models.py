from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class InvestigationRequest(BaseModel):
    problem: str = Field(default="", max_length=10_000)
    sql: str | None = Field(default=None, max_length=100_000)

    @model_validator(mode="after")
    def require_input(self) -> "InvestigationRequest":
        if not self.problem.strip() and not (self.sql and self.sql.strip()):
            raise ValueError("Provide a problem description, SQL query, or both")
        return self


class ActivityEvent(BaseModel):
    sequence: int
    kind: str
    summary: str
    tool_name: str | None = None
    result_preview: dict[str, Any] | None = None
    created_at: datetime


class InvestigationReport(BaseModel):
    problem: str
    evidence: list[str]
    root_cause_hypothesis: str
    recommended_change: str
    before_after_evidence: list[str]
    risks: list[str]
    confidence: float = Field(ge=0, le=1)
    sql_recommendation: str | None = None


class InvestigationResponse(BaseModel):
    id: UUID
    status: InvestigationStatus
    events: list[ActivityEvent] = Field(default_factory=list)
    report: InvestigationReport | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DatabaseStatus(BaseModel):
    connected: bool
    version: str | None = None
    error: str | None = None

