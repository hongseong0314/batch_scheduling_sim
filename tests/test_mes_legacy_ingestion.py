from src.mes.ingestion import (
    CanonicalIngestionRecord,
    RawSourceRecord,
    canonical_ingestion_record_from_payload,
    raw_source_record_from_payload,
)
from src.mes.sqlite_store import SQLiteMESStore
from src.mes.store import InMemoryMESStore
from tests.mes_api_support import client


def test_raw_source_record_contract_keeps_three_time_boundaries() -> None:
    record = RawSourceRecord(
        record_id="RAW_1",
        source_system="LEGACY_MES",
        source_table="WIP_LOT",
        source_pk="LOT123",
        entity_type="LOT",
        lot_id="LOT_CANON_123",
        ingest_time=100,
        event_time=90,
        decision_time=120,
        payload={"LOT_ID": "LOT123", "OPER": "A"},
    )

    payload = record.to_dict()

    assert payload["record_id"] == "RAW_1"
    assert payload["source_key"] == "LEGACY_MES:WIP_LOT:LOT123"
    assert payload["entity_type"] == "LOT"
    assert payload["lot_id"] == "LOT_CANON_123"
    assert payload["ingest_time"] == 100
    assert payload["event_time"] == 90
    assert payload["decision_time"] == 120
    assert payload["status"] == "RECEIVED"


def test_ingestion_payload_builders_create_raw_and_canonical_records() -> None:
    raw = raw_source_record_from_payload(
        {
            "source_system": "fdc",
            "source_table": "TRACE_EVENT",
            "source_pk": "EVT777",
            "entity_type": "QUALITY",
            "operation_id": "A",
            "equipment_id": "LITHO-01",
            "event_time": 9,
            "payload": {"qa": 48.5},
        },
        default_run_id="RUN_1",
    )
    canonical = canonical_ingestion_record_from_payload(
        {
            "canonical_id": "QA_EVT_777",
            "entity_type": "QUALITY",
            "event_type": "QA_PREDICTED",
            "measurements": {"qa": 48.5},
            "quality_result": {"risk": "LOW"},
        },
        raw_record=raw,
        default_run_id="RUN_1",
    )

    assert raw.record_id.startswith("RAW_")
    assert raw.source_system == "FDC"
    assert raw.run_id == "RUN_1"
    assert canonical.record_id.startswith("CANON_")
    assert canonical.raw_record_id == raw.record_id
    assert canonical.canonical_id == "QA_EVT_777"
    assert canonical.operation_id == "A"
    assert canonical.equipment_id == "LITHO-01"
    assert canonical.event_time == 9


def test_in_memory_store_indexes_legacy_ingestion_records() -> None:
    store = InMemoryMESStore()
    store.start_run("RUN_1", reason="test")
    raw = RawSourceRecord(
        record_id="RAW_1",
        source_system="LEGACY_MES",
        source_table="WIP_LOT",
        source_pk="LOT123",
        entity_type="LOT",
        lot_id="LOT_CANON_123",
        run_id="RUN_1",
    )
    canonical = CanonicalIngestionRecord(
        record_id="CANON_1",
        raw_record_id="RAW_1",
        entity_type="LOT",
        canonical_id="LOT_CANON_123",
        lot_id="LOT_CANON_123",
        run_id="RUN_1",
    )

    store.add_raw_source_record(raw)
    store.add_canonical_ingestion_record(canonical)

    assert store.raw_source_records(source_system="LEGACY_MES")[0].record_id == "RAW_1"
    assert store.canonical_ingestion_records(canonical_id="LOT_CANON_123")[0].record_id == "CANON_1"
    assert store.normalized_index_counts("RUN_1")["raw_source_record_index"] == 1
    assert store.normalized_index_counts("RUN_1")["canonical_ingestion_index"] == 1
    assert store.normalized_index_rows("raw_source_record_index", run_id="RUN_1")[0]["source_key"] == "LEGACY_MES:WIP_LOT:LOT123"


def test_sqlite_store_reloads_legacy_ingestion_records(tmp_path) -> None:
    db_path = tmp_path / "mes.sqlite3"
    store = SQLiteMESStore(db_path)
    store.start_run("RUN_1", reason="test")
    store.add_raw_source_record(
        RawSourceRecord(
            record_id="RAW_1",
            source_system="ERP",
            source_table="ORDER_LINE",
            source_pk="ORD1",
            entity_type="LOT",
            lot_id="LOT_CANON_1",
            run_id="RUN_1",
            ingest_time=20,
            event_time=18,
        )
    )
    store.add_canonical_ingestion_record(
        CanonicalIngestionRecord(
            record_id="CANON_1",
            raw_record_id="RAW_1",
            entity_type="LOT",
            canonical_id="LOT_CANON_1",
            lot_id="LOT_CANON_1",
            run_id="RUN_1",
        )
    )

    reloaded = SQLiteMESStore(db_path)
    raw_rows = reloaded.raw_source_records(run_id="RUN_1")
    canonical_rows = reloaded.canonical_ingestion_records(
        canonical_id="LOT_CANON_1",
        run_id="RUN_1",
    )
    raw_index = reloaded.normalized_index_rows("raw_source_record_index", run_id="RUN_1")
    canonical_index = reloaded.normalized_index_rows("canonical_ingestion_index", run_id="RUN_1")

    assert raw_rows[0].source_key == "ERP:ORDER_LINE:ORD1"
    assert canonical_rows[0].raw_record_id == "RAW_1"
    assert raw_index[0]["source_pk"] == "ORD1"
    assert canonical_index[0]["canonical_id"] == "LOT_CANON_1"


def test_legacy_ingestion_api_records_canonical_projection_and_source_mapping() -> None:
    response = client.post(
        "/api/v2/ingestion/source-records",
        json={
            "source_system": "LEGACY_MES",
            "source_table": "WIP_LOT",
            "source_pk": "LOT_API_1",
            "entity_type": "LOT",
            "canonical_id": "LOT_CANON_API_1",
            "lot_id": "LOT_CANON_API_1",
            "operation_id": "A",
            "ingest_time": 30,
            "event_time": 29,
            "canonical": {
                "event_type": "LOT_WAITING",
                "attributes": {"priority": "HOT"},
            },
            "payload": {"LOT_ID": "LOT_API_1", "OPER": "A"},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INGESTED"
    assert body["raw_record"]["source_key"] == "LEGACY_MES:WIP_LOT:LOT_API_1"
    assert body["canonical_record"]["canonical_id"] == "LOT_CANON_API_1"
    assert body["source_key_mapping"]["canonical_id"] == "LOT_CANON_API_1"

    raw_list = client.get(
        "/api/v2/ingestion/source-records",
        params={"source_system": "LEGACY_MES", "entity_type": "LOT"},
    ).json()
    canonical_list = client.get(
        "/api/v2/ingestion/canonical-records",
        params={"canonical_id": "LOT_CANON_API_1"},
    ).json()
    resolved = client.get(
        "/api/v2/source-key-mappings/resolve",
        params={
            "source_system": "LEGACY_MES",
            "source_table": "WIP_LOT",
            "source_pk": "LOT_API_1",
            "entity_type": "LOT",
        },
    ).json()

    assert any(item["source_pk"] == "LOT_API_1" for item in raw_list["items"])
    assert canonical_list["count"] >= 1
    assert canonical_list["items"][-1]["canonical_id"] == "LOT_CANON_API_1"
    assert resolved["found"] is True
    assert resolved["item"]["canonical_id"] == "LOT_CANON_API_1"
