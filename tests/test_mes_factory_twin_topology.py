from src.mes.factory_twin.layout import build_factory_twin_layout
from src.mes.operations.registry import build_default_operation_registry
from src.mes.runtime.config import default_runtime_config


def test_default_factory_layout_is_deterministic_and_non_overlapping():
    registry = build_default_operation_registry(default_runtime_config())
    first = build_factory_twin_layout(registry)
    second = build_factory_twin_layout(registry)

    assert first.layout_id == second.layout_id
    assert len(first.operations) == 3
    assert len(first.equipment) == 11
    assert len({tuple(item.position) for item in first.equipment}) == 11
    assert {route.id for route in first.routes} == {"ROUTE_A_B", "ROUTE_B_C"}


def test_configured_future_operation_uses_generic_fallback():
    config = {
        "operations": [
            {
                "operation_id": "D",
                "display_name": "Inspection",
                "operation_type": "inspection",
                "equipment_group_id": "D",
                "batch_size": 1,
                "process_time": 4,
            }
        ],
        "equipment": [
            {
                "equipment_id": "D_0",
                "display_name": "AOI-01",
                "equipment_group_id": "D",
                "capable_operations": ["D"],
            }
        ],
    }
    layout = build_factory_twin_layout(build_default_operation_registry(config))

    assert layout.operations[0].archetype == "generic_process_cell"
    assert layout.equipment[0].display_name == "AOI-01"
