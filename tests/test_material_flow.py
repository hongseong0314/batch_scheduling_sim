from src.environment.material_flow import MaterialFlowController
from src.environment.manufacturing_env import ManufacturingEnv
from src.mes.services import MESDecisionService
from src.objects import Task


def _task(uid: int) -> Task:
    return Task(uid=uid, job_id=f"J{uid}", due_date=100, spec_a=(48.0, 53.0))


def test_immediate_transfer_preserves_same_step_arrival():
    controller = MaterialFlowController({"mode": "immediate", "default_travel_time": 3})
    task = _task(1)

    arrived = controller.dispatch([task], "A", "B", current_time=10)

    assert arrived == [task]
    assert controller.active_jobs(10) == []
    assert controller.recent_jobs(10)[0]["status"] == "ARRIVED"


def test_timed_oht_releases_only_at_arrival_and_resets():
    controller = MaterialFlowController(
        {"mode": "timed_oht", "oht_time": {"A>B": 3, "B>C": 2}}
    )
    task = _task(2)

    assert controller.dispatch([task], "A", "B", current_time=4) == []
    assert controller.release_arrivals(6) == {}
    assert controller.active_jobs(6)[0]["progress"] == 0.6667
    assert controller.release_arrivals(7) == {"B": [task]}

    controller.reset()
    assert controller.state(7)["active_count"] == 0
    assert controller.state(7)["completed_count"] == 0


def test_oht_time_scalar_applies_to_every_route():
    controller = MaterialFlowController({"mode": "timed_oht", "oht_time": 4})

    controller.dispatch([_task(20)], "A", "B", current_time=2)
    controller.dispatch([_task(21)], "B", "C", current_time=3)

    jobs = controller.active_jobs(3)
    assert jobs[0]["arrival_time"] == 6
    assert jobs[1]["arrival_time"] == 7


def test_transfer_rejects_duplicate_task_ownership():
    controller = MaterialFlowController({"mode": "timed_oht", "default_travel_time": 2})
    task = _task(3)
    controller.dispatch([task], "A", "B", current_time=0)

    try:
        controller.dispatch([task], "A", "B", current_time=1)
    except ValueError as exc:
        assert "already in transit" in str(exc)
    else:
        raise AssertionError("duplicate transfer ownership must be rejected")


def test_manufacturing_env_timed_oht_blocks_b_until_authoritative_arrival():
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
    task = _task(10)
    env = ManufacturingEnv(config)
    env.reset(seed_initial_tasks=False, initial_tasks=[task], seed=3)

    env.step({"A": {"A_0": {"task_uids": [10], "recipe": [10, 2, 1]}}})
    env.step({})

    assert task not in env.env_B.wait_pool
    assert env.get_decision_state()["material_flow"]["active_count"] == 1
    env.step({})
    env.step({})
    assert task not in env.env_B.wait_pool
    env.step({})
    assert task in env.env_B.wait_pool
    assert env.get_decision_state()["material_flow"]["active_count"] == 0

    env.step(
        {"B": {"B_0": {"task_uids": [10], "recipe": [50.0, 50.0, 30.0]}}}
    )
    env.step({})

    b_to_c = env.get_decision_state()["material_flow"]["active"][0]
    assert b_to_c["from_operation_id"] == "B"
    assert b_to_c["to_operation_id"] == "C"
    assert task not in env.env_C.wait_pool
    assert task in list(env.material_flow.in_transit_tasks())

    env.step({})
    assert task not in env.env_C.wait_pool
    env.step({})
    assert task in env.env_C.wait_pool
    assert task not in list(env.material_flow.in_transit_tasks())


def test_timed_oht_candidates_exclude_tasks_that_have_not_arrived():
    service = MESDecisionService(
        config={
            "batch_size_A": 1,
            "batch_size_B": 2,
            "batch_size_C": 4,
            "scheduler_A": "fifo",
            "scheduler_B": "fifo",
            "packing_C": "fifo",
        }
    )
    tasks = {
        uid: {
            "uid": uid,
            "job_id": f"J{uid}",
            "due_date": 100,
            "spec_a": [48.0, 53.0],
            "spec_b": [20.0, 80.0],
            "arrival_time": 0,
        }
        for uid in range(1, 7)
    }
    state = {
        "time": 10,
        "tasks": tasks,
        "material_flow": {"mode": "timed_oht"},
        "B": {
            "wait_pool_uids": [1],
            "incoming_from_A_uids": [2],
            "rework_pool_uids": [],
            "machines": {"B_0": {"status": "idle", "batch_size": 2}},
        },
        "C": {
            "wait_pool_uids": [3, 4],
            "incoming_from_B_uids": [5, 6],
            "rework_pool_uids": [],
            "machines": {"C_0": {"status": "idle", "batch_size": 4}},
        },
    }

    b_candidates = service.dispatch_candidates(state, stage="B")
    c_candidates = service.dispatch_candidates(state, stage="C")

    assert b_candidates[0]["task_uids"] == [1]
    assert c_candidates == []

    state["material_flow"]["mode"] = "immediate"
    immediate_c = service.dispatch_candidates(state, stage="C")
    assert immediate_c[0]["task_uids"] == [3, 4, 5, 6]
