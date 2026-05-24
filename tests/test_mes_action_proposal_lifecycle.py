from types import SimpleNamespace

from src.mes.action_proposals import (
    LegacyDecision,
    OutcomeRecord,
    action_proposals_payload,
)
from src.mes.domain import MESCommand
from src.mes.sqlite_store import SQLiteMESStore
from src.mes.store import InMemoryMESStore
from tests.mes_api_support import client


def test_action_proposal_lifecycle_contract_records_decision_and_outcome() -> None:
    decision = LegacyDecision(
        proposal_id="PROP_CMD_1",
        legacy_status="ACCEPTED",
        decision_id="LDEC_1",
        correlation_id="CORR_1",
        legacy_assignment_id="LEGACY_ASSIGN_1",
        actual_equipment_id="A_0",
        actual_unit_ids=["WAFER_1"],
        reason="legacy mes accepted recommended assignment",
        decision_time=12,
        decided_by="LEGACY_MES",
        run_id="RUN_1",
    )
    outcome = OutcomeRecord(
        proposal_id="PROP_CMD_1",
        outcome_status="EXECUTED",
        outcome_id="OUT_1",
        correlation_id="CORR_1",
        actual_equipment_id="A_0",
        actual_unit_ids=["WAFER_1"],
        event_time=32,
        quality_result={"qa": 50.1, "status": "PASS"},
        cycle_time=20.0,
        rework_count=0,
        run_id="RUN_1",
    )

    assert decision.to_dict()["legacy_status"] == "ACCEPTED"
    assert decision.to_dict()["decision_time"] == 12
    assert decision.to_dict()["decided_by"] == "LEGACY_MES"
    assert outcome.to_dict()["outcome_status"] == "EXECUTED"
    assert outcome.to_dict()["event_time"] == 32
    assert outcome.to_dict()["quality_result"]["status"] == "PASS"


def test_in_memory_store_links_lifecycle_summary_to_action_proposal() -> None:
    store = InMemoryMESStore()
    store.start_run("RUN_1", reason="test")
    store.add_command(
        MESCommand(
            command_id="CMD_1",
            command_type="RESERVE_AND_TRACK_IN",
            correlation_id="CORR_1",
            validation_status="PASSED",
            validated_command={
                "stage": "A",
                "operation_id": "A",
                "equipment_id": "A_0",
                "task_uids": [1, 2, 3],
            },
            run_id="RUN_1",
        )
    )
    store.add_legacy_decision(
        LegacyDecision(
            proposal_id="PROP_CMD_1",
            legacy_status="MODIFIED",
            decision_id="LDEC_1",
            correlation_id="CORR_1",
            actual_equipment_id="A_1",
            reason="legacy tool reservation changed the equipment",
            run_id="RUN_1",
        )
    )
    store.add_outcome_record(
        OutcomeRecord(
            proposal_id="PROP_CMD_1",
            outcome_status="EXECUTED",
            outcome_id="OUT_1",
            correlation_id="CORR_1",
            actual_equipment_id="A_1",
            run_id="RUN_1",
        )
    )
    context = SimpleNamespace(harness=SimpleNamespace(store=store), operation_registry=None)

    payload = action_proposals_payload(context, run_id="RUN_1")
    item = payload["items"][0]

    assert store.legacy_decisions("PROP_CMD_1")[0].legacy_status == "MODIFIED"
    assert store.outcome_records("PROP_CMD_1")[0].outcome_status == "EXECUTED"
    assert item["lifecycle"]["legacy_decision_count"] == 1
    assert item["lifecycle"]["outcome_count"] == 1
    assert item["lifecycle"]["latest_legacy_status"] == "MODIFIED"
    assert item["lifecycle"]["latest_outcome_status"] == "EXECUTED"


def test_sqlite_store_reloads_action_proposal_lifecycle_records(tmp_path) -> None:
    db_path = tmp_path / "mes.sqlite3"
    store = SQLiteMESStore(db_path)
    store.start_run("RUN_1", reason="test")
    store.add_legacy_decision(
        LegacyDecision(
            proposal_id="PROP_CMD_1",
            legacy_status="ACCEPTED",
            decision_id="LDEC_1",
            correlation_id="CORR_1",
            legacy_assignment_id="LEGACY_ASSIGN_1",
            run_id="RUN_1",
        )
    )
    store.add_outcome_record(
        OutcomeRecord(
            proposal_id="PROP_CMD_1",
            outcome_status="EXECUTED",
            outcome_id="OUT_1",
            correlation_id="CORR_1",
            cycle_time=20.0,
            run_id="RUN_1",
        )
    )

    reloaded = SQLiteMESStore(db_path)
    decisions = reloaded.legacy_decisions("PROP_CMD_1", run_id="RUN_1")
    outcomes = reloaded.outcome_records("PROP_CMD_1", run_id="RUN_1")
    index_rows = reloaded.normalized_index_rows("proposal_lifecycle_index", run_id="RUN_1")

    assert decisions[0].legacy_assignment_id == "LEGACY_ASSIGN_1"
    assert outcomes[0].cycle_time == 20.0
    assert {row["record_type"] for row in index_rows} == {
        "LEGACY_DECISION",
        "OUTCOME",
    }
    assert all(row["proposal_id"] == "PROP_CMD_1" for row in index_rows)


def test_action_proposal_lifecycle_api_records_and_reads_legacy_feedback() -> None:
    run = client.post("/api/v2/harness/run-cycle", json={"target_stage": "A"}).json()
    correlation_id = run["generated"]["plan"]["correlation_id"]
    proposals = client.get(
        "/api/v2/action-proposals",
        params={"correlation_id": correlation_id},
    ).json()
    proposal = proposals["items"][0]
    proposal_id = proposal["proposal_id"]

    decision_response = client.post(
        f"/api/v2/action-proposals/{proposal_id}/legacy-decisions",
        json={
            "legacy_status": "ACCEPTED",
            "correlation_id": correlation_id,
            "legacy_assignment_id": "LEGACY_ASSIGN_1",
            "actual_equipment_id": proposal["target_equipment_id"],
            "actual_unit_ids": proposal["target_unit_ids"],
            "reason": "legacy mes accepted recommendation",
            "decision_time": 1,
        },
    )
    outcome_response = client.post(
        f"/api/v2/action-proposals/{proposal_id}/outcomes",
        json={
            "outcome_status": "EXECUTED",
            "correlation_id": correlation_id,
            "actual_equipment_id": proposal["target_equipment_id"],
            "actual_unit_ids": proposal["target_unit_ids"],
            "event_time": 21,
            "cycle_time": 20.0,
            "quality_result": {"status": "PASS"},
        },
    )
    lifecycle = client.get(f"/api/v2/action-proposals/{proposal_id}/lifecycle").json()
    listed = client.get(
        "/api/v2/action-proposals",
        params={"correlation_id": correlation_id},
    ).json()

    assert decision_response.status_code == 200
    assert outcome_response.status_code == 200
    assert lifecycle["proposal_id"] == proposal_id
    assert lifecycle["summary"]["latest_legacy_status"] == "ACCEPTED"
    assert lifecycle["summary"]["latest_outcome_status"] == "EXECUTED"
    assert lifecycle["legacy_decisions"][0]["decision_id"].startswith("LDEC_")
    assert lifecycle["outcomes"][0]["outcome_id"].startswith("OUT_")
    assert listed["items"][0]["lifecycle"]["legacy_decision_count"] == 1
