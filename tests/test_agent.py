from typing import Any

import pytest

from app.agent.agent import InvestigationAgent
from app.agent.tools import ToolResult
from app.llm.provider import MockLLMProvider


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult:
        self.calls.append((tool_name, arguments))
        return ToolResult(
            tool=tool_name,
            data=[{"table_name": "orders"}],
            row_count=1,
            duration_ms=1,
        )


def report_fixture() -> dict[str, Any]:
    return {
        "problem": "Slow query",
        "evidence": ["The orders table was observed."],
        "root_cause_hypothesis": "More evidence would be required outside this unit fixture.",
        "recommended_change": "Inspect the query plan.",
        "before_after_evidence": [],
        "risks": ["This fixture does not contain a query plan."],
        "confidence": 0.2,
        "sql_recommendation": None,
    }


@pytest.mark.asyncio
async def test_agent_uses_a_tool_before_finishing() -> None:
    provider = MockLLMProvider(
        [
            {
                "action": "tool",
                "action_summary": "Inspecting available tables",
                "tool_name": "list_tables",
                "arguments": {},
            },
            {
                "action": "finish",
                "action_summary": "Reporting the evidence-backed finding",
                "report": report_fixture(),
            },
        ]
    )
    tools = FakeTools()

    report = await InvestigationAgent(provider, tools).investigate("Slow query")

    assert report.confidence == 0.2
    assert tools.calls == [("list_tables", {})]


@pytest.mark.asyncio
async def test_agent_rejects_an_immediate_report() -> None:
    provider = MockLLMProvider(
        [
            {"action": "finish", "action_summary": "Too early", "report": report_fixture()},
            {
                "action": "tool",
                "action_summary": "Inspecting tables",
                "tool_name": "list_tables",
                "arguments": {},
            },
            {"action": "finish", "action_summary": "Reporting", "report": report_fixture()},
        ]
    )
    tools = FakeTools()

    await InvestigationAgent(provider, tools).investigate("Slow query")

    assert len(tools.calls) == 1

