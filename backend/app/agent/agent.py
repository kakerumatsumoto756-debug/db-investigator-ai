import json
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import ValidationError

from app.agent.planner import AgentDecision, StateUpdate
from app.agent.prompts import SYSTEM_PROMPT, TOOL_CATALOG
from app.agent.report import validate_report_evidence
from app.agent.state import Evidence, Hypothesis, InvestigationState, ToolCallRecord
from app.agent.tools import ToolResult
from app.llm.provider import LLMProvider, Message
from app.models import InvestigationReport


class ToolExecutor(Protocol):
    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolResult: ...


ActivityCallback = Callable[[str, str, ToolResult | None], Awaitable[None]]


class InvestigationAgent:
    def __init__(
        self,
        provider: LLMProvider,
        tools: ToolExecutor,
        *,
        max_iterations: int = 12,
        on_activity: ActivityCallback | None = None,
    ) -> None:
        self._provider = provider
        self._tools = tools
        self._max_iterations = max_iterations
        self._on_activity = on_activity

    async def investigate(self, problem: str, query: str | None = None) -> InvestigationReport:
        state = InvestigationState(original_problem=problem, sql=query)
        messages = [
            Message(role="system", content=f"{SYSTEM_PROMPT}\n\n{TOOL_CATALOG}"),
            Message(
                role="user",
                content=json.dumps({"problem": problem, "sql": query}, ensure_ascii=False),
            ),
        ]

        await self._activity("understanding", "Understanding the submitted database problem")
        for iteration in range(1, self._max_iterations + 1):
            state.iteration = iteration
            decision = await self._provider.generate_structured(messages, AgentDecision)
            self._apply_state_update(state, decision.state_update)

            if decision.action == "finish":
                if not state.tool_calls:
                    messages.append(
                        Message(
                            role="system",
                            content="A report cannot be completed before using diagnostic tools.",
                        )
                    )
                    continue
                report = validate_report_evidence(decision.report, state)  # type: ignore[arg-type]
                state.final_conclusion = report.root_cause_hypothesis
                await self._activity("completed", "Investigation report completed")
                return report

            await self._activity("tool", decision.action_summary)
            try:
                result = await self._tools.execute(decision.tool_name, decision.arguments)  # type: ignore[arg-type]
            except (ValueError, ValidationError) as exc:
                state.tool_calls.append(
                    ToolCallRecord(
                        tool_name=str(decision.tool_name),
                        arguments=decision.arguments,
                        result_summary=str(exc),
                        succeeded=False,
                    )
                )
                messages.append(
                    Message(
                        role="user",
                        content=json.dumps(
                            {
                                "message_type": "tool_error",
                                "tool": decision.tool_name,
                                "error": str(exc),
                                "instruction": "Choose a safe corrected action.",
                            }
                        ),
                    )
                )
                continue

            state.tool_calls.append(
                ToolCallRecord(
                    tool_name=result.tool,
                    arguments=decision.arguments,
                    result_summary=f"Returned {result.row_count} rows"
                    if result.row_count is not None
                    else "Completed",
                    succeeded=True,
                )
            )
            state.evidence.append(
                Evidence(
                    source=result.tool,
                    observation=decision.action_summary,
                    data={
                        "result": result.data,
                        "row_count": result.row_count,
                        "truncated": result.truncated,
                        "duration_ms": result.duration_ms,
                    },
                )
            )
            await self._activity("observation", f"Observed result from {result.tool}", result)
            messages.append(
                Message(
                    role="user",
                    content=json.dumps(
                        {
                            "message_type": "tool_result",
                            "evidence_id": len(state.evidence) - 1,
                            **result.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    ),
                )
            )

        raise RuntimeError(
            f"Investigation did not reach an evidence-backed conclusion in {self._max_iterations} steps"
        )

    async def _activity(
        self, kind: str, summary: str, result: ToolResult | None = None
    ) -> None:
        if self._on_activity is not None:
            await self._on_activity(kind, summary, result)

    @staticmethod
    def _apply_state_update(state: InvestigationState, update: StateUpdate) -> None:
        state.known_facts = list(dict.fromkeys([*state.known_facts, *update.known_facts]))
        state.unknowns = list(dict.fromkeys(update.unknowns))
        statements = list(
            dict.fromkeys([*(item.statement for item in state.hypotheses), *update.hypotheses])
        )
        state.hypotheses = [Hypothesis(statement=item) for item in statements]
        state.rejected_hypotheses = list(
            dict.fromkeys([*state.rejected_hypotheses, *update.rejected_hypotheses])
        )
        state.proposed_fixes = list(
            dict.fromkeys([*state.proposed_fixes, *update.proposed_fixes])
        )
