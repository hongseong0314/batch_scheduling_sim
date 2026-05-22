from tests.mes_api_support import client


def test_process_tools_api_runs_a_apc_prediction() -> None:
    response = client.post(
        "/api/v2/process-tools/predict_process_a_apc/run",
        json={
            "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
            "machine_state": {"u": 6, "m_age": 12},
            "recipe": [10.0, 2.0, 1.0],
            "current_time": 120,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["tool_id"] == "predict_process_a_apc"
    assert body["stage"] == "A"
    assert body["read_only"] is True


def test_process_tools_catalog_api_lists_a_apc_tool() -> None:
    response = client.get("/api/v2/process-tools/catalog")

    assert response.status_code == 200
    tool_ids = {item["id"] for item in response.json()["tools"]}
    assert "predict_process_a_apc" in tool_ids
