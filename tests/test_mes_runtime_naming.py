from src.mes.runtime.live_state import stage_summary
from src.mes.runtime.gantt import flow_summary, gantt_rows
from src.mes.runtime.naming import equipment_display_name, stage_display_name


class StageEnv:
    stats = {}


class Env:
    config = {
        "stage_display_names": {"A": "Lithography QA"},
        "equipment_display_names": {"A_0": "Lithography Tool 01"},
    }
    env_A = StageEnv()
    env_B = StageEnv()
    env_C = StageEnv()


class HarnessService:
    def dispatch_candidates(self, decision_state, stage):
        return []


class Harness:
    service = HarnessService()


class Context:
    env = Env()
    harness = Harness()


def test_process_and_equipment_display_names_use_config_with_defaults() -> None:
    context = Context()

    assert stage_display_name(context, "A") == "Lithography QA"
    assert stage_display_name(context, "B") == "Clean QA"
    assert equipment_display_name(context, "A_0") == "Lithography Tool 01"
    assert equipment_display_name(context, "B_0") == "B_0"


def test_stage_summary_includes_configured_process_and_equipment_display_names() -> None:
    context = Context()
    decision_state = {
        "A": {
            "machines": {
                "A_0": {
                    "status": "IDLE",
                    "current_batch_uids": [],
                    "finish_time": None,
                    "batch_size": 3,
                }
            },
            "wait_pool_uids": [],
            "rework_pool_uids": [],
        }
    }

    summary = stage_summary(context, "A", decision_state)

    assert summary["label"] == "Lithography QA"
    assert summary["machines"][0]["display_name"] == "Lithography Tool 01"


def test_gantt_payload_uses_configured_display_names() -> None:
    context = Context()
    decision_state = {
        "A": {
            "machines": {
                "A_0": {
                    "status": "IDLE",
                    "current_batch_uids": [],
                    "finish_time": None,
                    "batch_size": 3,
                }
            },
            "wait_pool_uids": [],
            "rework_pool_uids": [],
        },
        "B": {"machines": {}, "wait_pool_uids": [], "rework_pool_uids": []},
        "C": {"machines": {}, "wait_pool_uids": [], "rework_pool_uids": []},
    }

    rows = gantt_rows(context, decision_state)
    fallback_rows = gantt_rows(decision_state)
    flow = flow_summary(context, decision_state)

    assert rows[0]["label"] == "Lithography Tool 01"
    assert rows[0]["display_stage"] == "Lithography QA"
    assert fallback_rows[0]["label"] == "A_0"
    assert flow[0]["label"] == "Lithography QA"
