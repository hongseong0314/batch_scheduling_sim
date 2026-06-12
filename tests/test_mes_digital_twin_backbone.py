from src.mes.digital_twin import (
    build_canonical_decision_state,
    build_digital_twin_state,
)
from src.mes.ingestion import CanonicalIngestionRecord
from src.mes.services import MESDecisionService
from tests.mes_api_support import client


def _record(
    record_id: str,
    entity_type: str,
    canonical_id: str,
    event_type: str,
    event_time: int,
    operation_id: str = "A",
    equipment_id: str = "",
    lot_id: str = "",
    unit_id: str = "",
    attributes: dict | None = None,
) -> CanonicalIngestionRecord:
    return CanonicalIngestionRecord(
        record_id=record_id,
        raw_record_id=f"RAW_{record_id}",
        entity_type=entity_type,
        canonical_id=canonical_id,
        operation_id=operation_id,
        equipment_id=equipment_id,
        lot_id=lot_id,
        unit_id=unit_id,
        event_type=event_type,
        event_time=event_time,
        ingest_time=event_time + 1,
        attributes=dict(attributes or {}),
        run_id="RUN_TWIN",
    )


def test_canonical_records_reconstruct_policy_ready_wait_pool() -> None:
    records = [
        _record(
            "EQ_A0",
            "EQUIPMENT",
            "A_0",
            "EQUIPMENT_AVAILABLE",
            1,
            equipment_id="A_0",
            attributes={"batch_size": 2},
        ),
        _record(
            "U101",
            "UNIT",
            "WAFER_101",
            "UNIT_WAITING",
            2,
            lot_id="LOT_ALPHA",
            unit_id="WAFER_101",
            attributes={
                "task_uid": 101,
                "due_date": 30,
                "spec_a": [48, 53],
                "material_type": "plastic",
                "color": "red",
                "customer_id": "ALPHA",
                "margin_value": 0.9,
            },
        ),
        _record(
            "U102",
            "UNIT",
            "WAFER_102",
            "UNIT_WAITING",
            3,
            lot_id="LOT_ALPHA",
            unit_id="WAFER_102",
            attributes={
                "task_uid": 102,
                "due_date": 31,
                "spec_a": [48, 53],
                "material_type": "plastic",
                "color": "red",
                "customer_id": "ALPHA",
                "margin_value": 0.9,
            },
        ),
    ]

    twin_state = build_digital_twin_state(records, at_time=5)
    decision_state = build_canonical_decision_state(twin_state)
    candidates = MESDecisionService(config={"batch_size_A": 2}).l1_candidate_portfolio(
        decision_state,
        stages=["A"],
    )

    assert twin_state["state_source"] == "CANONICAL_TWIN"
    assert twin_state["wip_by_operation"]["A"]["wait"] == 2
    assert twin_state["diagnostics"]["status"] == "OK"
    assert twin_state["diagnostics"]["unit_count"] == 2
    assert decision_state["state_source"] == "CANONICAL_TWIN"
    assert decision_state["A"]["machines"]["A_0"]["status"] == "idle"
    assert decision_state["A"]["machines"]["A_0"]["batch_size"] == 2
    assert decision_state["A"]["wait_pool_uids"] == [101, 102]
    assert decision_state["tasks"][101]["job_id"] == "LOT_ALPHA"
    assert candidates[0]["stage"] == "A"
    assert candidates[0]["equipment_id"] == "A_0"
    assert candidates[0]["task_uids"] == [101, 102]


def test_replay_respects_event_time_cutoff_and_rework_updates() -> None:
    records = [
        _record(
            "EQ_A0",
            "EQUIPMENT",
            "A_0",
            "EQUIPMENT_AVAILABLE",
            1,
            equipment_id="A_0",
            attributes={"batch_size": 1},
        ),
        _record(
            "U201_WAIT",
            "UNIT",
            "WAFER_201",
            "UNIT_WAITING",
            2,
            lot_id="LOT_BETA",
            unit_id="WAFER_201",
            attributes={"task_uid": 201, "due_date": 15},
        ),
        _record(
            "U201_RUN",
            "UNIT",
            "WAFER_201",
            "TRACK_IN",
            4,
            equipment_id="A_0",
            lot_id="LOT_BETA",
            unit_id="WAFER_201",
            attributes={"task_uid": 201, "finish_time": 8},
        ),
        _record(
            "U201_REWORK",
            "UNIT",
            "WAFER_201",
            "REWORK_REQUESTED",
            9,
            lot_id="LOT_BETA",
            unit_id="WAFER_201",
            attributes={"task_uid": 201, "rework_count": 1},
        ),
    ]

    before_track_in = build_canonical_decision_state(
        build_digital_twin_state(records, at_time=3)
    )
    during_run = build_canonical_decision_state(
        build_digital_twin_state(records, at_time=5)
    )
    after_rework = build_canonical_decision_state(
        build_digital_twin_state(records, at_time=10)
    )

    assert before_track_in["A"]["wait_pool_uids"] == [201]
    assert during_run["A"]["wait_pool_uids"] == []
    assert during_run["A"]["machines"]["A_0"]["status"] == "busy"
    assert during_run["A"]["machines"]["A_0"]["current_batch_uids"] == [201]
    assert after_rework["A"]["rework_pool_uids"] == [201]
    assert after_rework["tasks"][201]["rework_count"] == 1


def test_digital_twin_api_builds_candidate_preview_from_ingested_records() -> None:
    client.post("/api/v2/simulation/reset")
    for payload in [
        {
            "source_system": "LEGACY_MES",
            "source_table": "EQP_MASTER",
            "source_pk": "A_0",
            "entity_type": "EQUIPMENT",
            "canonical_id": "A_0",
            "operation_id": "A",
            "equipment_id": "A_0",
            "event_time": 1,
            "canonical": {
                "event_type": "EQUIPMENT_AVAILABLE",
                "attributes": {"batch_size": 2},
            },
            "payload": {"EQP_ID": "A_0"},
        },
        {
            "source_system": "LEGACY_MES",
            "source_table": "WIP_UNIT",
            "source_pk": "W301",
            "entity_type": "UNIT",
            "canonical_id": "WAFER_301",
            "operation_id": "A",
            "lot_id": "LOT_API_ALPHA",
            "unit_id": "WAFER_301",
            "event_time": 2,
            "canonical": {
                "event_type": "UNIT_WAITING",
                "attributes": {
                    "task_uid": 301,
                    "due_date": 30,
                    "material_type": "plastic",
                    "color": "blue",
                    "customer_id": "ALPHA",
                },
            },
            "payload": {"WAFER_ID": "W301"},
        },
        {
            "source_system": "LEGACY_MES",
            "source_table": "WIP_UNIT",
            "source_pk": "W302",
            "entity_type": "UNIT",
            "canonical_id": "WAFER_302",
            "operation_id": "A",
            "lot_id": "LOT_API_ALPHA",
            "unit_id": "WAFER_302",
            "event_time": 3,
            "canonical": {
                "event_type": "UNIT_WAITING",
                "attributes": {
                    "task_uid": 302,
                    "due_date": 31,
                    "material_type": "plastic",
                    "color": "blue",
                    "customer_id": "ALPHA",
                },
            },
            "payload": {"WAFER_ID": "W302"},
        },
    ]:
        response = client.post("/api/v2/ingestion/source-records", json=payload)
        assert response.status_code == 200

    state_response = client.get("/api/v2/digital-twin/canonical-state")
    decision_response = client.get("/api/v2/digital-twin/canonical-decision-state")
    preview_response = client.get(
        "/api/v2/digital-twin/candidate-preview",
        params={"stage": "A"},
    )

    assert state_response.status_code == 200
    assert decision_response.status_code == 200
    assert preview_response.status_code == 200
    state_body = state_response.json()
    decision_state = decision_response.json()["decision_state"]
    preview = preview_response.json()
    assert state_body["diagnostics"]["twin"]["status"] == "OK"
    assert state_body["diagnostics"]["data_quality"]["status"] == "OK"
    assert decision_state["A"]["wait_pool_uids"] == [301, 302]
    assert preview["state_source"] == "CANONICAL_TWIN"
    assert preview["candidate_count"] == 1
    assert preview["items"][0]["task_uids"] == [301, 302]
    assert preview["diagnostics"]["data_quality"]["counts"]["canonical_records"] == 3


def test_canonical_genealogy_api_links_raw_evidence_and_timeline() -> None:
    client.post("/api/v2/simulation/reset")
    for payload in [
        {
            "source_system": "LEGACY_MES",
            "source_table": "WIP_UNIT",
            "source_pk": "W401",
            "entity_type": "UNIT",
            "canonical_id": "WAFER_401",
            "operation_id": "A",
            "lot_id": "LOT_TRACE_ALPHA",
            "unit_id": "WAFER_401",
            "event_time": 2,
            "canonical": {
                "event_type": "UNIT_WAITING",
                "attributes": {"task_uid": 401, "due_date": 30},
            },
            "payload": {"WAFER_ID": "W401"},
        },
        {
            "source_system": "FDC",
            "source_table": "QUALITY_EVENT",
            "source_pk": "QE401",
            "entity_type": "QUALITY",
            "canonical_id": "QUALITY_401_A",
            "operation_id": "A",
            "lot_id": "LOT_TRACE_ALPHA",
            "unit_id": "WAFER_401",
            "event_time": 5,
            "canonical": {
                "event_type": "QUALITY_MEASURED",
                "measurements": {"qa": 49.4},
                "quality_result": {"risk": "LOW"},
            },
            "payload": {"FDC_EVENT": "QE401"},
        },
    ]:
        response = client.post("/api/v2/ingestion/source-records", json=payload)
        assert response.status_code == 200

    response = client.get("/api/v2/genealogy/canonical/UNIT/WAFER_401")

    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["entity_type"] == "UNIT"
    assert body["canonical_id"] == "WAFER_401"
    assert body["record_count"] == 2
    assert body["raw_evidence_count"] == 2
    assert body["timeline"][0]["event_type"] == "UNIT_WAITING"
    assert body["timeline"][1]["event_type"] == "QUALITY_MEASURED"
    assert body["related_entities"]["lot_ids"] == ["LOT_TRACE_ALPHA"]
    assert body["diagnostics"]["data_quality"]["status"] == "OK"
