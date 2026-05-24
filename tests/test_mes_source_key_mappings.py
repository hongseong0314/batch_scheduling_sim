from src.mes.domain import SourceKeyMapping
from src.mes.sqlite_store import SQLiteMESStore
from src.mes.store import InMemoryMESStore
from tests.mes_api_support import client


def test_source_key_mapping_contract_records_time_boundaries() -> None:
    mapping = SourceKeyMapping(
        mapping_id="SKM_1",
        source_system="LEGACY_MES",
        source_table="WIP_LOT",
        source_pk="LOT123",
        entity_type="LOT",
        canonical_id="LOT_CANON_123",
        ingest_time=100,
        event_time=90,
        decision_time=120,
        source_payload={"LOT_ID": "LOT123"},
    )

    payload = mapping.to_dict()

    assert payload["mapping_id"] == "SKM_1"
    assert payload["source_system"] == "LEGACY_MES"
    assert payload["source_key"] == "LEGACY_MES:WIP_LOT:LOT123"
    assert payload["canonical_id"] == "LOT_CANON_123"
    assert payload["ingest_time"] == 100
    assert payload["event_time"] == 90
    assert payload["decision_time"] == 120
    assert payload["status"] == "ACTIVE"


def test_in_memory_store_resolves_source_key_mapping() -> None:
    store = InMemoryMESStore()
    store.upsert_source_key_mapping(
        SourceKeyMapping(
            mapping_id="SKM_1",
            source_system="LEGACY_MES",
            source_table="EQP_MASTER",
            source_pk="EQP001",
            entity_type="EQUIPMENT",
            canonical_id="A_0",
        )
    )

    resolved = store.resolve_source_key_mapping(
        source_system="LEGACY_MES",
        source_table="EQP_MASTER",
        source_pk="EQP001",
        entity_type="EQUIPMENT",
    )

    assert resolved is not None
    assert resolved.canonical_id == "A_0"
    assert store.source_key_mappings(entity_type="EQUIPMENT")[0].mapping_id == "SKM_1"
    assert store.source_key_mappings(canonical_id="A_0")[0].source_pk == "EQP001"


def test_sqlite_store_reloads_source_key_mappings(tmp_path) -> None:
    db_path = tmp_path / "mes.sqlite3"
    store = SQLiteMESStore(db_path)
    store.start_run("RUN_1", reason="test", time=0)
    store.upsert_source_key_mapping(
        SourceKeyMapping(
            mapping_id="SKM_1",
            source_system="FDC",
            source_table="TRACE_EVENT",
            source_pk="EVT777",
            entity_type="EVENT",
            canonical_id="EVT_CANON_777",
            run_id="RUN_1",
            ingest_time=10,
            event_time=9,
        )
    )

    reloaded = SQLiteMESStore(db_path)
    resolved = reloaded.resolve_source_key_mapping(
        source_system="FDC",
        source_table="TRACE_EVENT",
        source_pk="EVT777",
        entity_type="EVENT",
        run_id="RUN_1",
    )
    index_rows = reloaded.normalized_index_rows("source_key_mapping_index", run_id="RUN_1")

    assert resolved is not None
    assert resolved.canonical_id == "EVT_CANON_777"
    assert index_rows[0]["mapping_id"] == "SKM_1"
    assert index_rows[0]["canonical_id"] == "EVT_CANON_777"


def test_source_key_mapping_api_upserts_lists_and_resolves_mapping() -> None:
    response = client.post(
        "/api/v2/source-key-mappings",
        json={
            "source_system": "LEGACY_MES",
            "source_table": "WIP_LOT",
            "source_pk": "LOT999",
            "entity_type": "LOT",
            "canonical_id": "LOT_CANON_999",
            "ingest_time": 20,
            "event_time": 18,
            "decision_time": 25,
        },
    )
    assert response.status_code == 200
    created = response.json()["item"]
    assert created["mapping_id"].startswith("SKM_")
    assert created["source_key"] == "LEGACY_MES:WIP_LOT:LOT999"

    listed = client.get(
        "/api/v2/source-key-mappings",
        params={"source_system": "LEGACY_MES", "entity_type": "LOT"},
    ).json()
    resolved = client.get(
        "/api/v2/source-key-mappings/resolve",
        params={
            "source_system": "LEGACY_MES",
            "source_table": "WIP_LOT",
            "source_pk": "LOT999",
            "entity_type": "LOT",
        },
    ).json()

    assert listed["count"] >= 1
    assert any(item["canonical_id"] == "LOT_CANON_999" for item in listed["items"])
    assert resolved["found"] is True
    assert resolved["item"]["canonical_id"] == "LOT_CANON_999"
