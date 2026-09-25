from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    source: str
    observation: str
    data: dict[str, Any] = Field(default_factory=dict)


class Hypothesis(BaseModel):
    statement: str
    supporting_evidence: list[int] = Field(default_factory=list)
    status: str = "open"


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    result_summary: str
    succeeded: bool


class InvestigationState(BaseModel):
    original_problem: str
    sql: str | None = None
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    proposed_fixes: list[str] = Field(default_factory=list)
    validation_results: list[Evidence] = Field(default_factory=list)
    final_conclusion: str | None = None
    iteration: int = 0

