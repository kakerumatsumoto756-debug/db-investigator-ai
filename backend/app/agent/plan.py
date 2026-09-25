from typing import Any


def inspect_plan_document(document: list[dict[str, Any]] | dict[str, Any]) -> dict[str, Any]:
    envelope = document[0] if isinstance(document, list) else document
    root = envelope.get("Plan", envelope)
    findings: list[dict[str, Any]] = []
    node_count = 0

    def visit(node: dict[str, Any], path: str) -> None:
        nonlocal node_count
        node_count += 1
        node_type = str(node.get("Node Type", "Unknown"))
        relation = node.get("Relation Name")
        actual_rows = node.get("Actual Rows")
        planned_rows = node.get("Plan Rows")

        if node_type == "Seq Scan":
            findings.append(
                {
                    "kind": "sequential_scan",
                    "node": path,
                    "relation": relation,
                    "rows_removed_by_filter": node.get("Rows Removed by Filter", 0),
                }
            )
        if "Sort" in node_type:
            findings.append(
                {
                    "kind": "sort",
                    "node": path,
                    "method": node.get("Sort Method"),
                    "key": node.get("Sort Key", []),
                    "space_kb": node.get("Sort Space Used"),
                }
            )
        if node_type in {"Nested Loop", "Hash Join", "Merge Join"}:
            findings.append(
                {
                    "kind": "join",
                    "node": path,
                    "strategy": node_type,
                    "join_type": node.get("Join Type"),
                    "actual_rows": actual_rows,
                }
            )
        if isinstance(actual_rows, (int, float)) and isinstance(planned_rows, (int, float)):
            denominator = max(min(actual_rows, planned_rows), 1)
            ratio = max(actual_rows, planned_rows) / denominator
            if ratio >= 10:
                findings.append(
                    {
                        "kind": "cardinality_mismatch",
                        "node": path,
                        "planned_rows": planned_rows,
                        "actual_rows": actual_rows,
                        "ratio": round(ratio, 2),
                    }
                )

        for index, child in enumerate(node.get("Plans", [])):
            visit(child, f"{path}.{index}")

    visit(root, "0")
    return {
        "planning_time_ms": envelope.get("Planning Time"),
        "execution_time_ms": envelope.get("Execution Time"),
        "root_node": root.get("Node Type"),
        "node_count": node_count,
        "findings": findings,
    }

