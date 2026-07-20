from src.mes.digital_twin import build_digital_twin_state
from src.mes.ingestion import CanonicalIngestionRecord
from tests.mes_api_support import client


def test_postgres_schema_contract_exposes_production_backbone_tables() -> None:
    from src.mes.persistence.postgres_schema import (
        POSTGRES_SCHEMA_VERSION,
        postgres_ddl_statements,
        postgres_schema_contract,
    )

    contract = postgres_schema_contract()
    ddl = "\n".join(postgres_ddl_statements())

    assert POSTGRES_SCHEMA_VERSION == "production_data_backbone_v1"
    assert contract["schema_version"] == POSTGRES_SCHEMA_VERSION
    assert contract["migration_files"][0].endswith(
        "001_production_data_backbone_v1.sql"
    )
    for table_name in (
        "raw_source_records",
        "canonical_ingestion_records",
        "source_key_mappings",
        "action_proposals",
        "action_proposal_reviews",
        "legacy_decisions",
        "outcome_records",
        "ingestion_job_runs",
    ):
        assert table_name in contract["tables"]
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in ddl

    canonical_columns = contract["tables"]["canonical_ingestion_records"]["columns"]
    assert canonical_columns["canonical_id"]["nullable"] is False
    assert canonical_columns["event_time"]["type"] == "BIGINT"
    assert "idx_canonical_ingestion_entity" in contract["indexes"]


def test_source_adapter_registry_contract_and_adapter_metadata() -> None:
    from src.mes.ingestion.adapters.registry import (
        adapt_source_row,
        source_adapter_catalog,
    )

    catalog = source_adapter_catalog()
    adapter_ids = {item["adapter_id"] for item in catalog["items"]}

    assert catalog["interface_version"] == "source-adapter-v1"
    assert {
        "legacy_mes_wip_unit",
        "legacy_mes_equipment",
        "legacy_mes_assignment",
        "fdc_quality_event",
        "fdc_equipment_event",
        "rms_recipe",
        "rms_recipe_eligibility",
        "erp_order_lot",
    }.issubset(adapter_ids)
    for item in catalog["items"]:
        assert item["mode"] == "row_to_canonical_ingestion_payload"
        assert item["output_contract"] == {
            "raw_source_record": "raw-source-record-v1",
            "canonical_ingestion_record": "canonical-ingestion-record-v1",
            "source_key_mapping": "source-key-mapping-v1",
        }
        assert item["source_system"]
        assert item["canonical_entity_types"]

    payload = adapt_source_row(
        "legacy_mes_wip_unit",
        {
            "unit_id": "WAFER_900",
            "lot_id": "LOT_900",
            "operation_id": "A",
            "task_uid": 900,
            "event_time": 10,
            "ingest_time": 11,
        },
    )

    assert payload["source_system"] == "LEGACY_MES"
    assert payload["entity_type"] == "UNIT"
    assert payload["canonical"]["event_type"] == "UNIT_WAITING"
    assert payload["canonical"]["attributes"]["task_uid"] == 900


def test_mes_fdc_and_rms_adapters_emit_expected_canonical_payloads() -> None:
    from src.mes.ingestion.adapters.erp_adapter import ERPOrderLotAdapter
    from src.mes.ingestion.adapters.fdc_adapter import (
        FDCEquipmentEventAdapter,
        FDCQualityEventAdapter,
    )
    from src.mes.ingestion.adapters.legacy_mes_adapter import (
        LegacyMESAssignmentAdapter,
        LegacyMESEquipmentAdapter,
        LegacyMESWIPAdapter,
    )
    from src.mes.ingestion.adapters.rms_adapter import (
        RMSRecipeAdapter,
        RMSRecipeEligibilityAdapter,
    )

    wip = LegacyMESWIPAdapter().adapt(
        {
            "unit_id": "WAFER_1",
            "lot_id": "LOT_1",
            "operation_id": "A",
            "task_uid": 1,
            "event_time": 1,
        }
    )
    equipment = LegacyMESEquipmentAdapter().adapt(
        {"equipment_id": "A_0", "operation_id": "A", "status": "AVAILABLE"}
    )
    assignment = LegacyMESAssignmentAdapter().adapt(
        {
            "assignment_id": "ASN_1",
            "equipment_id": "A_0",
            "operation_id": "A",
            "unit_ids": ["WAFER_1", "WAFER_2"],
            "event_time": 2,
        }
    )
    quality = FDCQualityEventAdapter().adapt(
        {
            "event_id": "FDC_QA_1",
            "unit_id": "WAFER_1",
            "operation_id": "A",
            "equipment_id": "A_0",
            "qa": 49.5,
            "risk": "LOW",
            "event_time": 3,
        }
    )
    equipment_event = FDCEquipmentEventAdapter().adapt(
        {
            "event_id": "FDC_TOOL_1",
            "equipment_id": "A_0",
            "operation_id": "A",
            "event_type": "TOOL_ALARM",
            "alarm_code": "TEMP_DRIFT",
        }
    )
    recipe = RMSRecipeAdapter().adapt(
        {
            "recipe_id": "RCP_A_1",
            "operation_id": "A",
            "parameter_set": {"dose": 12.0},
        }
    )
    eligibility = RMSRecipeEligibilityAdapter().adapt(
        {
            "eligibility_id": "ELIG_A_1",
            "recipe_id": "RCP_A_1",
            "operation_id": "A",
            "equipment_id": "A_0",
            "eligible": True,
        }
    )
    order = ERPOrderLotAdapter().adapt(
        {
            "order_id": "ORD_1",
            "lot_id": "LOT_ERP_1",
            "product_id": "PROD_ALPHA",
            "customer_id": "ALPHA",
            "due_date": 120,
            "route_id": "A_B_C",
        }
    )

    assert wip["entity_type"] == "UNIT"
    assert equipment["entity_type"] == "EQUIPMENT"
    assert assignment["entity_type"] == "ASSIGNMENT"
    assert assignment["canonical"]["attributes"]["unit_ids"] == ["WAFER_1", "WAFER_2"]
    assert quality["source_system"] == "FDC"
    assert quality["canonical"]["quality_result"]["risk"] == "LOW"
    assert equipment_event["entity_type"] == "EVENT"
    assert equipment_event["canonical"]["attributes"]["alarm_code"] == "TEMP_DRIFT"
    assert recipe["entity_type"] == "RECIPE"
    assert recipe["canonical"]["attributes"]["parameter_set"] == {"dose": 12.0}
    assert eligibility["entity_type"] == "RECIPE"
    assert eligibility["canonical"]["attributes"]["eligible"] is True
    assert order["source_system"] == "ERP"
    assert order["entity_type"] == "LOT"
    assert order["canonical"]["attributes"]["customer_id"] == "ALPHA"


def test_ingestion_job_run_batch_and_backfill_ingest_records() -> None:
    from src.mes.jobs.ingestion_jobs import backfill_ingestion, run_ingestion_batch

    client.post("/api/v2/simulation/reset")
    context = client.app.state.context

    batch = run_ingestion_batch(
        context,
        adapter_id="legacy_mes_wip_unit",
        rows=[
            {
                "unit_id": "WAFER_JOB_1",
                "lot_id": "LOT_JOB",
                "operation_id": "A",
                "task_uid": 901,
                "event_time": 10,
                "ingest_time": 11,
            }
        ],
        job_id="JOB_WIP_DELTA",
    )
    backfill = backfill_ingestion(
        context,
        adapter_id="fdc_quality_event",
        rows=[
            {
                "event_id": "FDC_BACKFILL_1",
                "unit_id": "WAFER_JOB_1",
                "operation_id": "A",
                "qa": 50.1,
                "risk": "LOW",
                "event_time": 12,
                "ingest_time": 40,
            }
        ],
        job_id="JOB_FDC_BACKFILL",
        window_start=0,
        window_end=50,
    )

    assert batch["status"] == "COMPLETED"
    assert batch["raw_count"] == 1
    assert batch["canonical_count"] == 1
    assert batch["job_id"] == "JOB_WIP_DELTA"
    assert backfill["mode"] == "BACKFILL"
    assert backfill["window"] == {"start": 0, "end": 50}
    assert backfill["canonical_count"] == 1

    job_catalog = client.get("/api/v2/ingestion/jobs").json()
    assert "legacy_mes_wip_unit" in {
        item["adapter_id"] for item in job_catalog["available_adapters"]
    }


def test_data_quality_dashboard_api_flags_late_events_and_ui_mount_exists() -> None:
    client.post("/api/v2/simulation/reset")
    response = client.post(
        "/api/v2/legacy-adapters/fdc_quality_event/ingest",
        json={
            "event_id": "FDC_LATE_1",
            "unit_id": "WAFER_LATE_1",
            "operation_id": "A",
            "qa": 47.2,
            "risk": "HIGH",
            "event_time": 1,
            "ingest_time": 40,
        },
    )
    assert response.status_code == 200

    body = client.get(
        "/api/v2/production/data-quality",
        params={"late_threshold": 10},
    ).json()

    assert body["dashboard"]["readiness_status"] == body["status"]
    assert body["dashboard"]["late_event_count"] >= 1
    assert body["issue_groups"]["LATE_ARRIVING_CANONICAL_EVENT"]["count"] >= 1
    assert any(
        issue["code"] == "LATE_ARRIVING_CANONICAL_EVENT"
        for issue in body["issues"]
    )

    html = client.get("/mes").text
    assert 'href="#data-quality"' in html
    assert 'id="data-quality-page"' in html
    assert 'id="data-quality-issues-body"' in html


def test_canonical_replay_stress_orders_events_and_survives_late_duplicates() -> None:
    records = [
        CanonicalIngestionRecord(
            record_id="CANON_UNIT_RUN",
            raw_record_id="RAW_RUN",
            entity_type="UNIT",
            canonical_id="WAFER_42",
            operation_id="A",
            unit_id="WAFER_42",
            event_type="TRACK_IN",
            event_time=20,
            ingest_time=22,
            attributes={"task_uid": 42},
        ),
        CanonicalIngestionRecord(
            record_id="CANON_EQP_IDLE",
            raw_record_id="RAW_EQP",
            entity_type="EQUIPMENT",
            canonical_id="A_0",
            operation_id="A",
            equipment_id="A_0",
            event_type="EQUIPMENT_AVAILABLE",
            event_time=1,
            ingest_time=100,
            attributes={"batch_size": 3, "status": "IDLE"},
        ),
        CanonicalIngestionRecord(
            record_id="CANON_UNIT_WAIT",
            raw_record_id="RAW_WAIT",
            entity_type="UNIT",
            canonical_id="WAFER_42",
            operation_id="A",
            unit_id="WAFER_42",
            event_type="UNIT_WAITING",
            event_time=5,
            ingest_time=6,
            attributes={"task_uid": 42, "due_date": 80},
        ),
        CanonicalIngestionRecord(
            record_id="CANON_UNIT_COMPLETE",
            raw_record_id="RAW_DONE",
            entity_type="UNIT",
            canonical_id="WAFER_42",
            operation_id="B",
            unit_id="WAFER_42",
            event_type="UNIT_COMPLETED",
            event_time=30,
            ingest_time=31,
            attributes={"task_uid": 42},
        ),
    ]

    twin_at_wait = build_digital_twin_state(records, at_time=10)
    twin_final = build_digital_twin_state(records)

    assert twin_at_wait["units"][42]["status"] == "WAIT"
    assert twin_at_wait["units"][42]["location"] == "QUEUE_A"
    assert twin_final["units"][42]["status"] == "COMPLETED"
    assert twin_final["applied_record_ids"] == [
        "CANON_EQP_IDLE",
        "CANON_UNIT_WAIT",
        "CANON_UNIT_RUN",
        "CANON_UNIT_COMPLETE",
    ]
