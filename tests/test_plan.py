from app.agent.plan import inspect_plan_document


def test_inspect_plan_finds_scan_sort_and_cardinality_mismatch() -> None:
    plan = [
        {
            "Planning Time": 0.2,
            "Execution Time": 8.4,
            "Plan": {
                "Node Type": "Sort",
                "Plan Rows": 10,
                "Actual Rows": 1000,
                "Sort Key": ["created_at DESC"],
                "Plans": [
                    {
                        "Node Type": "Seq Scan",
                        "Relation Name": "orders",
                        "Plan Rows": 10,
                        "Actual Rows": 1000,
                        "Rows Removed by Filter": 9000,
                    }
                ],
            },
        }
    ]

    result = inspect_plan_document(plan)

    assert result["execution_time_ms"] == 8.4
    assert result["node_count"] == 2
    assert {finding["kind"] for finding in result["findings"]} == {
        "sort",
        "sequential_scan",
        "cardinality_mismatch",
    }

