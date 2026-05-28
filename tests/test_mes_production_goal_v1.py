from src.mes.action_proposals import action_proposal_feedback_summary
from src.mes.legacy_adapters import legacy_adapter_payload
from src.mes.operations.registry import build_default_operation_registry
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.digital_twin import run_canonical_recommendation_payload
from src.mes.runtime.experiments import capture_canonical_scenario, run_experiment
from tests.mes_api_support import client


def _ingest_minimal_canonical_a_batch() -> None:
    client.post("/api/v2/simulation/reset")
    rows = [
        (
            "legacy_mes_equipment",
            {
                "equipment_id": "A_0",
                "operation_id": "A",
                "batch_size": 2,
                "event_time": 1,
                "status": "AVAILABLE",
            },
        ),
        (
            "legacy_mes_wip_unit",
            {
                "unit_id": "WAFER_501",
                "lot_id": "LOT_PROD_ALPHA",
                "operation_id": "A",
                "task_uid": 501,
                "due_date": 40,
                "material_type": "plastic",
                "color": "green",
                "customer_id": "ALPHA",
                "event_time": 2,
            },
        ),
        (
            "legacy_mes_wip_unit",
            {
                "unit_id": "WAFER_502",
                "lot_id": "LOT_PROD_ALPHA",
                "operation_id": "A",
                "task_uid": 502,
                "due_date": 41,
                "material_type": "plastic",
                "color": "green",
                "customer_id": "ALPHA",
                "event_time": 3,
            },
        ),
    ]
    for adapter_id, row in rows:
        response = client.post(
            f"/api/v2/legacy-adapters/{adapter_id}/ingest",
            json=row,
        )
        assert response.status_code == 200


def test_source_specific_legacy_adapters_map_rows_to_ingestion_payloads() -> None:
    wip = legacy_adapter_payload(
        "legacy_mes_wip_unit",
        {
            "unit_id": "WAFER_10",
            "lot_id": "LOT_10",
            "operation_id": "A",
            "task_uid": 10,
            "due_date": 50,
            "event_time": 4,
        },
    )
    equipment = legacy_adapter_payload(
        "legacy_mes_equipment",
        {
            "equipment_id": "A_0",
            "operation_id": "A",
            "batch_size": 2,
            "event_time": 1,
        },
    )
    quality = legacy_adapter_payload(
        "fdc_quality_event",
        {
            "unit_id": "WAFER_10",
            "operation_id": "A",
            "qa": 49.5,
            "risk": "LOW",
            "event_id": "FDC_10",
            "event_time": 6,
        },
    )

    assert wip["source_system"] == "LEGACY_MES"
    assert wip["entity_type"] == "UNIT"
    assert wip["canonical"]["event_type"] == "UNIT_WAITING"
    assert wip["canonical"]["attributes"]["task_uid"] == 10
    assert equipment["entity_type"] == "EQUIPMENT"
    assert equipment["canonical"]["event_type"] == "EQUIPMENT_AVAILABLE"
    assert quality["source_system"] == "FDC"
    assert quality["entity_type"] == "QUALITY"
    assert quality["canonical"]["measurements"]["qa"] == 49.5


def test_canonical_twin_recommendation_runner_creates_action_proposal() -> None:
    _ingest_minimal_canonical_a_batch()
    before = client.get("/api/v2/fab/live").json()["time"]

    response = client.post(
        "/api/v2/digital-twin/recommendation-run",
        json={"stage": "A"},
    )

    assert response.status_code == 200
    body = response.json()
    after = client.get("/api/v2/fab/live").json()["time"]
    assert body["state_source"] == "CANONICAL_TWIN"
    assert body["result"]["passed"] is True
    assert body["command"]["validated_command"]["task_uids"] == [501, 502]
    assert body["action_proposal"]["proposal_type"] == "LEGACY_MES_ACTION_PROPOSAL"
    assert body["action_proposal"]["direct_equipment_control"] is False
    assert body["action_proposal"]["payload"]["state_source"] == "CANONICAL_TWIN"
    assert after == before


def test_route_graph_generalizes_beyond_abc_operations() -> None:
    registry = build_default_operation_registry(
        {
            "operations": [
                {
                    "operation_id": "PHOTO_COAT",
                    "display_name": "Photo Coat",
                    "operation_type": "lithography",
                    "equipment_group_id": "COATER",
                    "downstream_operation_ids": ["PHOTO_EXPOSE"],
                },
                {
                    "operation_id": "PHOTO_EXPOSE",
                    "display_name": "Photo Exposure",
                    "operation_type": "lithography",
                    "equipment_group_id": "LITHO",
                    "upstream_operation_ids": ["PHOTO_COAT"],
                },
            ],
            "equipment": [
                {
                    "equipment_id": "LITHO_01",
                    "display_name": "Lithography Tool 01",
                    "equipment_group_id": "LITHO",
                    "capable_operations": ["PHOTO_EXPOSE"],
                }
            ],
        }
    )
    graph = registry.route_graph_payload()

    assert graph["operation_count"] == 2
    assert graph["nodes"][0]["operation_id"] == "PHOTO_COAT"
    assert graph["edges"] == [
        {"from_operation_id": "PHOTO_COAT", "to_operation_id": "PHOTO_EXPOSE"}
    ]
    assert graph["equipment_by_operation"]["PHOTO_EXPOSE"][0]["equipment_id"] == "LITHO_01"


def test_feedback_summary_links_legacy_decision_outcome_and_learning_signal() -> None:
    _ingest_minimal_canonical_a_batch()
    run = client.post(
        "/api/v2/digital-twin/recommendation-run",
        json={"stage": "A"},
    ).json()
    proposal_id = run["action_proposal"]["proposal_id"]
    client.post(
        f"/api/v2/action-proposals/{proposal_id}/legacy-decisions",
        json={
            "legacy_status": "MODIFIED",
            "actual_equipment_id": "A_0",
            "actual_unit_ids": ["WAFER_501", "WAFER_502"],
            "reason": "legacy dispatch kept same batch",
        },
    )
    client.post(
        f"/api/v2/action-proposals/{proposal_id}/outcomes",
        json={
            "outcome_status": "EXECUTED",
            "actual_equipment_id": "A_0",
            "actual_unit_ids": ["WAFER_501", "WAFER_502"],
            "quality_result": {"risk": "LOW"},
            "cycle_time": 20,
        },
    )

    feedback = client.get(f"/api/v2/action-proposals/{proposal_id}/feedback-summary").json()

    assert feedback["proposal_id"] == proposal_id
    assert feedback["summary"]["latest_legacy_status"] == "MODIFIED"
    assert feedback["summary"]["latest_outcome_status"] == "EXECUTED"
    assert feedback["actual_vs_proposed"]["equipment_changed"] is False
    assert feedback["learning_signal"]["usable_for_policy_evaluation"] is True


def test_policy_evaluation_v2_runs_against_canonical_twin_scenario() -> None:
    _ingest_minimal_canonical_a_batch()
    context = client.app.state.context
    scenario = capture_canonical_scenario(context)

    result = run_experiment(
        context,
        {
            "scenario_id": scenario["scenario_id"],
            "variant_ids": ["baseline_fifo_rule", "l3_throughput_aggressive"],
        },
    )

    assert scenario["state_source"] == "CANONICAL_TWIN"
    assert result["scenario"]["state_source"] == "CANONICAL_TWIN"
    assert result["count"] == 2
    assert all(row["command_valid"] for row in result["results"])
    assert result["comparison"]["best_variant_id"] in {
        "baseline_fifo_rule",
        "l3_throughput_aggressive",
    }


def test_production_readiness_api_reports_storage_boundaries_and_health() -> None:
    response = client.get("/api/v2/production-readiness")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "READY_FOR_V1_INTEGRATION"
    assert body["storage"]["backend"] == "sqlite"
    assert body["boundaries"]["direct_equipment_control"] is False
    assert "canonical_ingestion_records" in body["storage"]["tables"]
    assert "llm_write_tools_default" in body["security"]
