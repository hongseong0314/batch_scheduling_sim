import json

from src.mes.factory_twin.diff import snapshot_delta
from src.mes.factory_twin.layout import build_factory_twin_layout
from src.mes.factory_twin.snapshot import build_factory_twin_snapshot
from src.mes.operations.registry import build_default_operation_registry


def _large_fixture():
    config = {
        "operations": [
            {
                "operation_id": "A",
                "display_name": "Large Process",
                "operation_type": "process_qa",
                "equipment_group_id": "A",
                "batch_size": 3,
                "process_time": 20,
                "queue_keys": {
                    "wait": "wait_pool_uids",
                    "rework": "rework_pool_uids",
                },
            }
        ],
        "equipment": [
            {
                "equipment_id": f"A_{index}",
                "display_name": f"TOOL-{index:03d}",
                "equipment_group_id": "A",
                "capable_operations": ["A"],
                "batch_size": 3,
            }
            for index in range(200)
        ],
    }
    registry = build_default_operation_registry(config)
    layout = build_factory_twin_layout(registry)
    tasks = {
        uid: {
            "uid": uid,
            "job_id": f"LOT_{uid // 25:04d}",
            "location": "QUEUE_A",
            "due_date": 100 + uid,
            "customer_id": "PERF",
            "material_type": "composite",
            "color": "blue",
        }
        for uid in range(2_000)
    }
    machines = {
        f"A_{index}": {
            "status": "idle",
            "batch_size": 3,
            "current_batch_uids": [],
            "finish_time": -1,
        }
        for index in range(200)
    }
    state = {
        "time": 1,
        "state_source": "SIMULATOR",
        "tasks": tasks,
        "A": {
            "wait_pool_uids": list(tasks),
            "rework_pool_uids": [],
            "machines": machines,
        },
    }
    return registry, layout, state


def test_large_snapshot_and_normal_delta_stay_within_v1_payload_budgets():
    registry, layout, state = _large_fixture()
    first = build_factory_twin_snapshot(
        decision_state=state,
        registry=registry,
        layout=layout,
        run_id="RUN_PERF",
        sequence=1,
        rendering_config={"max_visible_queue_items": 24},
    )

    assert len(layout.equipment) == 200
    assert len(first.work_items) == 2_000
    assert len(next(queue for queue in first.queues if queue.queue_id == "QUEUE_A_WAIT").visible_task_uids) == 24
    assert len(first.model_dump_json().encode("utf-8")) < 500 * 1024

    state["time"] = 2
    state["A"]["machines"]["A_0"].update(
        status="busy", current_batch_uids=[0, 1, 2], finish_time=22
    )
    second = build_factory_twin_snapshot(
        decision_state=state,
        registry=registry,
        layout=layout,
        run_id="RUN_PERF",
        sequence=2,
        rendering_config={"max_visible_queue_items": 24},
    )
    delta = snapshot_delta(first, second)

    assert len(json.dumps(delta.model_dump(mode="json")).encode("utf-8")) < 50 * 1024
    assert [row["equipment_id"] for row in delta.upsert["equipment"]] == ["A_0"]
