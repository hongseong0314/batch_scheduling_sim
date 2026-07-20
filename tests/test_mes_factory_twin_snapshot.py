from src.environment.manufacturing_env import ManufacturingEnv
from src.mes.factory_twin.layout import build_factory_twin_layout
from src.mes.factory_twin.snapshot import build_factory_twin_snapshot
from src.mes.operations.registry import build_default_operation_registry
from src.mes.runtime.config import default_runtime_config
from src.objects import Task


def test_simulator_snapshot_contains_exact_queue_and_equipment_state():
    config = default_runtime_config()
    env = ManufacturingEnv(config)
    env.reset(seed=11)
    registry = build_default_operation_registry(config)
    layout = build_factory_twin_layout(registry)

    snapshot = build_factory_twin_snapshot(
        decision_state={**env.get_decision_state(), "state_source": "SIMULATOR"},
        registry=registry,
        layout=layout,
        run_id="RUN_TEST",
        sequence=1,
    )

    assert snapshot.schema_version == "factory-twin.v1"
    assert len(snapshot.equipment) == 11
    assert len(snapshot.work_items) == 40
    assert sum(queue.count for queue in snapshot.queues) == 40
    assert snapshot.transport_source == "INFERRED_VISUAL"


def test_missing_runtime_operation_is_unknown_not_idle():
    config = {
        "operations": [{"operation_id": "D", "display_name": "D", "operation_type": "inspection", "equipment_group_id": "D"}],
        "equipment": [{"equipment_id": "D_0", "display_name": "D0", "equipment_group_id": "D", "capable_operations": ["D"]}],
    }
    registry = build_default_operation_registry(config)
    layout = build_factory_twin_layout(registry)
    snapshot = build_factory_twin_snapshot(
        decision_state={"time": 0, "tasks": {}, "state_source": "CANONICAL_TWIN"},
        registry=registry,
        layout=layout,
        run_id="RUN_D",
        sequence=1,
    )

    assert snapshot.equipment[0].status == "UNKNOWN"
    assert snapshot.equipment[0].evidence_source == "MISSING"
    assert snapshot.diagnostics["missing_runtime_operations"] == ["D"]


def test_immediate_transfer_is_exposed_as_short_inferred_visual_carrier():
    config = default_runtime_config()
    env = ManufacturingEnv(config)
    env.reset(seed_initial_tasks=False, initial_tasks=[], seed=1)
    task = env.data_generator.generate_new_jobs(0)[0]
    env.material_flow.dispatch([task], "A", "B", current_time=0)
    registry = build_default_operation_registry(config)
    layout = build_factory_twin_layout(registry)

    snapshot = build_factory_twin_snapshot(
        decision_state={**env.get_decision_state(), "state_source": "SIMULATOR"},
        registry=registry,
        layout=layout,
        run_id="RUN_VISUAL",
        sequence=1,
    )

    assert snapshot.transport_source == "INFERRED_VISUAL"
    assert snapshot.carriers[0].status == "INFERRED_VISUAL"
    assert snapshot.carriers[0].route_id == "ROUTE_A_B"


def test_timed_oht_projects_finishing_work_at_source_finish_before_dispatch():
    config = {
        "num_machines_A": 1,
        "num_machines_B": 1,
        "num_machines_C": 1,
        "batch_size_A": 1,
        "batch_size_B": 1,
        "batch_size_C": 1,
        "process_time_A": 1,
        "process_time_B": 1,
        "process_time_C": 1,
        "deterministic_mode": True,
        "factory_twin": {
            "transport": {
                "mode": "timed_oht",
                "oht_time": {"A>B": 3, "B>C": 2},
            }
        },
    }
    task = Task(uid=10, job_id="J10", due_date=100, spec_a=(48.0, 53.0))
    env = ManufacturingEnv(config)
    env.reset(seed_initial_tasks=False, initial_tasks=[task], seed=3)
    env.step({"A": {"A_0": {"task_uids": [10], "recipe": [10, 2, 1]}}})
    registry = build_default_operation_registry(config)
    layout = build_factory_twin_layout(registry)

    finishing = build_factory_twin_snapshot(
        decision_state={**env.get_decision_state(), "state_source": "SIMULATOR"},
        registry=registry,
        layout=layout,
        run_id="RUN_TIMED_OHT",
        sequence=1,
    )

    queue_by_id = {row.queue_id: row for row in finishing.queues}
    work_item = next(row for row in finishing.work_items if row.task_uid == 10)
    assert queue_by_id["QUEUE_A_OUTPUT"].task_uids == [10]
    assert "QUEUE_B_INCOMING" not in queue_by_id
    assert finishing.carriers == []
    assert work_item.operation_id == "A"
    assert work_item.location_id == "QUEUE_A_OUTPUT"
    assert work_item.status == "FINISHED"

    env.step({})
    in_transit = build_factory_twin_snapshot(
        decision_state={**env.get_decision_state(), "state_source": "SIMULATOR"},
        registry=registry,
        layout=layout,
        run_id="RUN_TIMED_OHT",
        sequence=2,
    )

    assert next(row for row in in_transit.queues if row.queue_id == "QUEUE_A_OUTPUT").count == 0
    assert in_transit.carriers[0].task_uids == [10]
    assert in_transit.carriers[0].arrival_time == 4

    for _ in range(3):
        env.step({})
    arrived = build_factory_twin_snapshot(
        decision_state={**env.get_decision_state(), "state_source": "SIMULATOR"},
        registry=registry,
        layout=layout,
        run_id="RUN_TIMED_OHT",
        sequence=3,
    )

    assert arrived.carriers == []
    assert next(row for row in arrived.queues if row.queue_id == "QUEUE_B_WAIT").task_uids == [10]
    arrived_work_item = next(row for row in arrived.work_items if row.task_uid == 10)
    assert arrived_work_item.location_id == "QUEUE_B_WAIT"
    assert arrived_work_item.status == "WAITING"
