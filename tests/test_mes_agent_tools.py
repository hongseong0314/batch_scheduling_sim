from src.mes.agent_runtime.mes_tools import MESAgentToolService
from src.mes.runtime.context import MESAPIContext


def test_mes_agent_tool_catalog_exposes_read_only_runtime_tools() -> None:
    service = MESAgentToolService(MESAPIContext())

    catalog = service.catalog()
    by_name = {tool["name"]: tool for tool in catalog["tools"]}

    assert "predict_process_a_apc" in by_name
    assert "get_fab_snapshot" in by_name
    assert "get_policy_stack" in by_name
    assert "get_candidate_portfolio_latest" in by_name
    assert "get_assignment_trace" in by_name
    assert all(tool["read_only"] is True for tool in catalog["tools"])


def test_mes_agent_tool_service_returns_compact_fab_snapshot() -> None:
    service = MESAgentToolService(MESAPIContext())

    result = service.run_tool("get_fab_snapshot", {})

    assert {"run_id", "time", "kpis", "stages", "active_correlation_id"} <= set(result)
    assert {"A", "B", "C"} <= set(result["stages"])
    assert {"wait", "running", "idle", "total_wip"} <= set(result["stages"]["A"])


def test_mes_agent_tool_service_delegates_process_a_apc_prediction() -> None:
    service = MESAgentToolService(MESAPIContext())

    result = service.run_tool(
        "predict_process_a_apc",
        {
            "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
            "machine_state": {"u": 6, "m_age": 12},
            "recipe": [10.0, 2.0, 1.0],
        },
    )

    assert result["stage"] == "A"
    assert result["predicted_qa"]
    assert result["quality_risk"] in {"LOW", "MEDIUM", "HIGH"}
