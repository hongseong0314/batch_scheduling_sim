import pytest

from src.mes.process_tools.service import ProcessToolService


def test_process_a_apc_predicts_quality_for_explicit_recipe() -> None:
    service = ProcessToolService()

    result = service.run_tool(
        "predict_process_a_apc",
        {
            "task_rows": [{"task_uid": "T0", "spec_a": [48.0, 53.0]}],
            "machine_state": {"u": 6, "m_age": 12},
            "recipe": [10.0, 2.0, 1.0],
            "queue_info": {"wait_pool_size": 12},
            "current_time": 120,
        },
    )

    assert result["stage"] == "A"
    assert result["tool_id"] == "predict_process_a_apc"
    assert result["model_id"] == "A_RULE_BASED_APC_PREDICTOR"
    assert result["recipe"] == [10.0, 2.0, 1.0]
    assert isinstance(result["predicted_qa"], float)
    assert result["target_spec"] == {"low": 48.0, "high": 53.0, "target": 50.5}
    assert result["replace_consumable"] is True
    assert result["quality_risk"] in {"LOW", "HIGH"}
    assert result["explanation_factors"]["u"] == 6.0
    assert result["explanation_factors"]["m_age"] == 12.0


def test_process_tool_catalog_exposes_continue_ready_schema() -> None:
    service = ProcessToolService()

    catalog = service.catalog()

    tool = next(item for item in catalog["tools"] if item["id"] == "predict_process_a_apc")
    assert tool["name"] == "predict_process_a_apc"
    assert tool["read_only"] is True
    assert tool["layer"] == "L2"
    assert tool["operation_id"] == "A"
    assert tool["policy_id"] == "A_RULE_BASED_APC_PREDICTOR"
    assert tool["input_schema"]["type"] == "object"
    assert "task_rows" in tool["input_schema"]["properties"]
    assert "machine_state" in tool["input_schema"]["properties"]


def test_unknown_process_tool_is_rejected() -> None:
    service = ProcessToolService()

    with pytest.raises(ValueError, match="UNKNOWN_PROCESS_TOOL"):
        service.run_tool("apply_recipe_to_mes", {})
