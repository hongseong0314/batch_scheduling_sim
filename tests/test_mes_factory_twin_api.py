from fastapi.testclient import TestClient

from src.mes.api import app
from src.mes.ingestion import CanonicalIngestionRecord


client = TestClient(app)


def test_factory_twin_layout_snapshot_entity_and_replay_range():
    layout = client.get("/api/v2/factory-twin/layout")
    assert layout.status_code == 200
    assert layout.json()["schema_version"] == "factory-twin.v1"
    assert len(layout.json()["equipment"]) == 11

    snapshot = client.get("/api/v2/factory-twin/snapshot?source=SIMULATOR")
    assert snapshot.status_code == 200
    assert snapshot.json()["layout_id"] == layout.json()["layout_id"]

    entity = client.get("/api/v2/factory-twin/entity/equipment/A_0")
    assert entity.status_code == 200
    assert entity.json()["state"]["equipment_id"] == "A_0"

    replay = client.get("/api/v2/factory-twin/replay-range")
    assert replay.status_code == 200
    assert replay.json()["state_source"] == "CANONICAL_TWIN"


def test_factory_twin_rejects_unknown_source():
    response = client.get("/api/v2/factory-twin/snapshot?source=UNKNOWN")
    assert response.status_code == 422


def test_factory_twin_websocket_negotiates_and_sends_snapshot():
    with client.websocket_connect(
        "/api/v2/factory-twin/stream?source=SIMULATOR&schema=factory-twin.v1"
    ) as websocket:
        hello = websocket.receive_json()
        snapshot = websocket.receive_json()

    assert hello["type"] == "hello"
    assert snapshot["type"] == "snapshot"
    assert snapshot["payload"]["schema_version"] == "factory-twin.v1"


def test_factory_twin_delta_advances_after_simulator_mutation():
    initial = client.get("/api/v2/factory-twin/snapshot").json()
    client.post("/api/v2/tasks/generate", json={})
    current = client.get("/api/v2/factory-twin/snapshot").json()
    service = app.state.context.factory_twin
    kind, payload = service.snapshot_after(
        "SIMULATOR", current["run_id"], initial["sequence"]
    )

    assert current["sequence"] > initial["sequence"]
    assert kind == "delta"
    assert payload.base_sequence == initial["sequence"]


def test_canonical_replay_uses_the_same_spatial_contract_at_each_event_time():
    client.post("/api/v2/simulation/reset")
    context = app.state.context
    run_id = context.run_id
    records = [
        CanonicalIngestionRecord(
            record_id="CANON_TWIN_EQ_A0",
            raw_record_id="RAW_TWIN_EQ_A0",
            entity_type="EQUIPMENT",
            canonical_id="A_0",
            operation_id="A",
            equipment_id="A_0",
            event_type="EQUIPMENT_AVAILABLE",
            event_time=1,
            attributes={"batch_size": 3},
            run_id=run_id,
        ),
        CanonicalIngestionRecord(
            record_id="CANON_TWIN_UNIT_WAIT",
            raw_record_id="RAW_TWIN_UNIT_WAIT",
            entity_type="UNIT",
            canonical_id="WAFER_501",
            operation_id="A",
            lot_id="LOT_TWIN",
            unit_id="WAFER_501",
            event_type="UNIT_WAITING",
            event_time=2,
            attributes={"task_uid": 501, "due_date": 40},
            run_id=run_id,
        ),
        CanonicalIngestionRecord(
            record_id="CANON_TWIN_UNIT_RUN",
            raw_record_id="RAW_TWIN_UNIT_RUN",
            entity_type="UNIT",
            canonical_id="WAFER_501",
            operation_id="A",
            equipment_id="A_0",
            lot_id="LOT_TWIN",
            unit_id="WAFER_501",
            event_type="TRACK_IN",
            event_time=4,
            attributes={"task_uid": 501, "finish_time": 12},
            run_id=run_id,
        ),
    ]
    for record in records:
        context.harness.store.add_canonical_ingestion_record(record)

    waiting = context.factory_twin.commit(
        "CANONICAL_TWIN", run_id=run_id, at_time=3, force=True
    )
    running = context.factory_twin.commit(
        "CANONICAL_TWIN", run_id=run_id, at_time=5, force=True
    )
    replay = context.factory_twin.replay_range(run_id)

    assert waiting.schema_version == running.schema_version == "factory-twin.v1"
    assert waiting.layout_id == running.layout_id
    assert waiting.state_source == running.state_source == "CANONICAL_TWIN"
    assert next(queue for queue in waiting.queues if queue.queue_id == "QUEUE_A_WAIT").count == 1
    assert next(item for item in running.equipment if item.equipment_id == "A_0").status == "BUSY"
    assert replay["available"] is True
    assert replay["event_times"] == [1, 2, 4]
