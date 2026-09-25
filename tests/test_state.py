from app.agent.agent import InvestigationAgent
from app.agent.planner import StateUpdate
from app.agent.state import InvestigationState


def test_state_updates_are_deduplicated() -> None:
    state = InvestigationState(original_problem="slow query")
    update = StateUpdate(
        known_facts=["orders exists", "orders exists"],
        hypotheses=["missing index", "missing index"],
        proposed_fixes=["add index", "add index"],
    )

    InvestigationAgent._apply_state_update(state, update)
    InvestigationAgent._apply_state_update(state, update)

    assert state.known_facts == ["orders exists"]
    assert [item.statement for item in state.hypotheses] == ["missing index"]
    assert state.proposed_fixes == ["add index"]

