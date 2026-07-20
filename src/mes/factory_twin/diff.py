"""Ordered entity-level diffs for factory twin snapshots."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from src.mes.factory_twin.contracts import FactoryTwinDeltaV1, FactoryTwinSnapshotV1


COLLECTION_KEYS = {
    "equipment": "equipment_id",
    "queues": "queue_id",
    "work_items": "task_uid",
    "carriers": "carrier_id",
    "transfers": "transfer_id",
}


def snapshot_delta(
    previous: FactoryTwinSnapshotV1,
    current: FactoryTwinSnapshotV1,
) -> FactoryTwinDeltaV1:
    if previous.run_id != current.run_id or previous.state_source != current.state_source:
        raise ValueError("snapshots from different channels cannot be diffed")
    upsert: Dict[str, list[Dict[str, Any]]] = {}
    remove: Dict[str, list[str]] = {}
    before = previous.model_dump(mode="json")
    after = current.model_dump(mode="json")
    for collection, id_key in COLLECTION_KEYS.items():
        old_rows = _indexed(before.get(collection, []), id_key)
        new_rows = _indexed(after.get(collection, []), id_key)
        changed = [row for key, row in new_rows.items() if old_rows.get(key) != row]
        removed = [key for key in old_rows if key not in new_rows]
        if changed:
            upsert[collection] = changed
        if removed:
            remove[collection] = removed
    if before.get("warehouse") != after.get("warehouse"):
        upsert["warehouse"] = [after["warehouse"]]
    return FactoryTwinDeltaV1(
        run_id=current.run_id,
        base_sequence=previous.sequence,
        sequence=current.sequence,
        time=current.time,
        state_source=current.state_source,
        upsert=upsert,
        remove=remove,
    )


def _indexed(rows: Iterable[Dict[str, Any]], id_key: str) -> Dict[str, Dict[str, Any]]:
    return {str(row[id_key]): row for row in rows}


__all__ = ["snapshot_delta"]
