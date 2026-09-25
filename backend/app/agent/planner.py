from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models import InvestigationReport

ToolName = Literal[
    "list_tables",
    "describe_table",
    "list_indexes",
    "get_table_statistics",
    "execute_readonly_query",
    "explain_query",
    "explain_analyze_query",
    "inspect_query_plan",
    "get_database_version",
]


class StateUpdate(BaseModel):
    known_facts: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    rejected_hypotheses: list[str] = Field(default_factory=list)
    proposed_fixes: list[str] = Field(default_factory=list)


class AgentDecision(BaseModel):
    action: Literal["tool", "finish"]
    action_summary: str = Field(min_length=1, max_length=500)
    tool_name: ToolName | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    state_update: StateUpdate = Field(default_factory=StateUpdate)
    report: InvestigationReport | None = None

    @model_validator(mode="after")
    def validate_action(self) -> "AgentDecision":
        if self.action == "tool" and self.tool_name is None:
            raise ValueError("A tool action requires tool_name")
        if self.action == "finish" and self.report is None:
            raise ValueError("A finish action requires report")
        return self

