from src.mes.action_proposals import (
    action_proposal_from_command,
    action_proposals_payload,
)
from src.mes.domain import MESCommand
from tests.mes_api_support import client


def test_action_proposal_maps_validated_command_for_legacy_submission() -> None:
    command = MESCommand(
        command_id="CMD_1",
        command_type="RESERVE_AND_TRACK_IN",
        correlation_id="CORR_1",
        validation_status="PASSED",
        validated_command={
            "stage": "A",
            "operation_id": "A",
            "equipment_id": "A_0",
            "task_uids": [1, 2, 3],
            "candidate_id": "CAND_1",
        },
        run_id="RUN_1",
    )

    proposal = action_proposal_from_command(command)

    assert proposal.proposal_type == "LEGACY_MES_ACTION_PROPOSAL"
    assert proposal.operation_id == "A"
    assert proposal.source_command_id == "CMD_1"
    assert proposal.target_equipment_id == "A_0"
    assert proposal.target_unit_ids == ["WAFER_1", "WAFER_2", "WAFER_3"]
    assert proposal.candidate_id == "CAND_1"
    assert proposal.validation_status == "PASSED"
    assert proposal.status == "PROPOSED"
    assert proposal.to_dict()["direct_equipment_control"] is False


def test_action_proposals_payload_derives_proposals_from_commands() -> None:
    client.post("/api/v2/harness/run-cycle", json={"target_stage": "A"})

    response = client.get("/api/v2/action-proposals")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    proposal = body["items"][-1]
    assert proposal["proposal_type"] == "LEGACY_MES_ACTION_PROPOSAL"
    assert proposal["source_command_id"].startswith("CMD_")
    assert proposal["operation_id"] == "A"
    assert proposal["direct_equipment_control"] is False


def test_action_proposals_payload_supports_correlation_filter() -> None:
    run = client.post("/api/v2/harness/run-cycle", json={"target_stage": "A"}).json()
    correlation_id = run["generated"]["plan"]["correlation_id"]

    payload = action_proposals_payload(client.app.state.context, correlation_id=correlation_id)

    assert payload["correlation_id"] == correlation_id
    assert payload["count"] >= 1
    assert all(item["correlation_id"] == correlation_id for item in payload["items"])
