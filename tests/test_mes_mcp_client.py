from pathlib import Path

from src.mes.agent_runtime.mcp_client import MCPProcessToolClient


def test_mcp_process_tool_client_lists_and_calls_stdio_server() -> None:
    project_root = Path(__file__).resolve().parents[1]
    client = MCPProcessToolClient(
        command=".venv/bin/python",
        args=["-m", "src.mes.mcp.process_apc_server"],
        cwd=str(project_root),
    )

    catalog = client.catalog()
    result = client.run_tool(
        "predict_process_a_apc",
        {
            "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
            "machine_state": {"u": 6, "m_age": 12},
            "recipe": [10.0, 2.0, 1.0],
            "current_time": 120,
        },
    )

    assert "predict_process_a_apc" in {item["name"] for item in catalog["tools"]}
    assert result["stage"] == "A"
    assert result["predicted_qa"]
