from mcp.server.fastmcp import FastMCP

from src.mes.mcp.process_apc_server import (
    build_mcp_server,
    get_process_tool_catalog,
    predict_process_a_apc,
)


def test_process_apc_mcp_tool_runs_a_prediction() -> None:
    result = predict_process_a_apc(
        task_rows=[{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
        machine_state={"u": 6, "m_age": 12},
        recipe=[10.0, 2.0, 1.0],
        current_time=120,
    )

    assert result["tool_id"] == "predict_process_a_apc"
    assert result["stage"] == "A"
    assert result["predicted_qa"]
    assert result["read_only"] is True


def test_process_apc_mcp_server_is_buildable() -> None:
    server = build_mcp_server()

    assert isinstance(server, FastMCP)
    assert get_process_tool_catalog()["count"] >= 1
