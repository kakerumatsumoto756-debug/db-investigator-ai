import warnings

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from fastapi.testclient import TestClient

from app.llm.provider import MockLLMProvider
from app.main import app


def test_health_and_database_status() -> None:
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        status = client.get("/api/database/status")
        assert status.status_code == 200
        assert status.json()["connected"] is True


def test_investigation_requires_problem_or_sql() -> None:
    with TestClient(app) as client:
        response = client.post("/api/investigate", json={"problem": "", "sql": ""})
    assert response.status_code == 422


def test_missing_investigation_returns_404() -> None:
    with TestClient(app) as client:
        response = client.get("/api/investigations/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_investigation_runs_and_persists_report_with_mock_provider() -> None:
    report = {
        "problem": "Customer order history is slow",
        "evidence": ["The orders table exists."],
        "root_cause_hypothesis": "A plan is needed before changing the schema.",
        "recommended_change": "Collect and compare an execution plan.",
        "before_after_evidence": [],
        "risks": ["No index change was tested in this API fixture."],
        "confidence": 0.3,
        "sql_recommendation": None,
    }
    provider = MockLLMProvider(
        [
            {
                "action": "tool",
                "action_summary": "Inspecting the schema",
                "tool_name": "list_tables",
                "arguments": {},
            },
            {"action": "finish", "action_summary": "Writing the report", "report": report},
        ]
    )

    with TestClient(app) as client:
        app.state.provider_factory = lambda settings: provider
        created = client.post(
            "/api/investigate",
            json={"problem": "Customer order history is slow", "sql": None},
        )
        investigation_id = created.json()["id"]
        stored = client.get(f"/api/investigations/{investigation_id}")

    assert created.status_code == 202
    assert stored.json()["status"] == "completed"
    assert stored.json()["report"]["confidence"] == 0.3
    assert any(event["tool_name"] == "list_tables" for event in stored.json()["events"])
