from src.mes.operations.registry import build_default_operation_registry
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.naming import equipment_display_name, stage_display_name
from tests.mes_api_support import client


def test_default_operation_registry_exposes_simulator_operations() -> None:
    registry = build_default_operation_registry(
        {
            "num_machines_A": 5,
            "num_machines_B": 3,
            "num_machines_C": 3,
            "batch_size_A": 3,
            "batch_size_B": 2,
            "batch_size_C": 4,
            "process_time_A": 20,
            "process_time_B": 8,
            "process_time_C": 2,
            "stage_display_names": {"A": "Process QA"},
        }
    )

    assert registry.operation_ids() == ["A", "B", "C"]
    assert registry.get_operation("A").display_name == "Process QA"
    assert registry.get_operation("B").upstream_operation_ids == ["A"]
    assert registry.get_operation("C").operation_type == "packing"
    assert registry.get_operation("A").execution_boundary == "SIMULATOR_STAGE"
    assert len(registry.equipment_for_operation("A")) == 5
    assert registry.equipment_for_operation("A")[0].equipment_id == "A_0"


def test_operation_registry_accepts_inserted_production_operation() -> None:
    registry = build_default_operation_registry(
        {
            "operations": [
                {
                    "operation_id": "PHOTO_EXPOSE",
                    "display_name": "Photo Exposure",
                    "operation_type": "lithography",
                    "equipment_group_id": "LITHO",
                    "execution_boundary": "LEGACY_MES_REVIEW",
                    "upstream_operation_ids": ["PHOTO_COAT"],
                    "downstream_operation_ids": ["PHOTO_DEVELOP"],
                    "l1_policy_key": "dispatch_fifo",
                    "l2_policy_key": "photo_apc_rule",
                }
            ],
            "equipment": [
                {
                    "equipment_id": "LITHO_01",
                    "display_name": "Lithography Tool 01",
                    "equipment_group_id": "LITHO",
                    "capable_operations": ["PHOTO_EXPOSE"],
                    "batch_size": 1,
                }
            ],
        }
    )

    operation = registry.get_operation("PHOTO_EXPOSE")
    equipment = registry.equipment_for_operation("PHOTO_EXPOSE")

    assert registry.operation_ids() == ["PHOTO_EXPOSE"]
    assert operation.display_name == "Photo Exposure"
    assert operation.execution_boundary == "LEGACY_MES_REVIEW"
    assert operation.l2_policy_key == "photo_apc_rule"
    assert equipment[0].display_name == "Lithography Tool 01"


def test_mes_context_exposes_operation_registry_for_display_names() -> None:
    context = MESAPIContext()
    context.env.config["stage_display_names"]["A"] = "Lithography QA"
    context.operation_registry = build_default_operation_registry(context.env.config)

    assert stage_display_name(context, "A") == "Lithography QA"
    assert equipment_display_name(context, "A_0") == "A_0"
    assert context.operation_registry.get_operation("A").display_name == "Lithography QA"


def test_operations_api_returns_default_registry() -> None:
    response = client.get("/api/v2/operations")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert [item["operation_id"] for item in body["items"]] == ["A", "B", "C"]
    assert body["items"][0]["execution_boundary"] == "SIMULATOR_STAGE"
    assert body["equipment_count"] == 11
