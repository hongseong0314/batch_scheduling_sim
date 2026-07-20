"""Factory twin facade with layout, snapshot, sequence, and replay ownership."""

from __future__ import annotations

import hashlib
import json
import threading
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Optional, Tuple

from src.mes.factory_twin.contracts import (
    FactoryTwinDeltaV1,
    FactoryTwinLayoutV1,
    FactoryTwinSnapshotV1,
)
from src.mes.factory_twin.diff import snapshot_delta
from src.mes.factory_twin.layout import build_factory_twin_layout
from src.mes.factory_twin.snapshot import build_factory_twin_snapshot
from src.mes.factory_twin.sources import canonical_source_state, simulator_source_state


class FactoryTwinService:
    """Project authoritative state into stable spatial twin channels."""

    def __init__(self, context: Any, lock: threading.RLock | None = None) -> None:
        self.context = context
        self.lock = lock or threading.RLock()
        self._sequence: Dict[Tuple[str, str], int] = defaultdict(int)
        self._latest: Dict[Tuple[str, str], FactoryTwinSnapshotV1] = {}
        self._latest_delta: Dict[Tuple[str, str], FactoryTwinDeltaV1] = {}
        self._fingerprints: Dict[Tuple[str, str], str] = {}
        self._history: Dict[Tuple[str, str], Deque[FactoryTwinSnapshotV1]] = defaultdict(
            lambda: deque(maxlen=128)
        )
        self._rebuild_layout()

    def reset(self) -> None:
        with self.lock:
            self._sequence.clear()
            self._latest.clear()
            self._latest_delta.clear()
            self._fingerprints.clear()
            self._history.clear()
            self._rebuild_layout()
            self.commit("SIMULATOR", force=True)

    def layout(self) -> FactoryTwinLayoutV1:
        return self._layout

    def commit(
        self,
        source: str = "SIMULATOR",
        *,
        run_id: Optional[str] = None,
        at_time: Optional[int] = None,
        force: bool = False,
    ) -> FactoryTwinSnapshotV1:
        source = self._normalize_source(source)
        with self.lock:
            resolved_run_id = str(run_id or self.context.run_id)
            channel = (source, resolved_run_id)
            state = self._source_state(source, resolved_run_id, at_time)
            fingerprint = self._fingerprint(state)
            current = self._latest.get(channel)
            if (
                not force
                and at_time is None
                and current is not None
                and self._fingerprints.get(channel) == fingerprint
            ):
                return current
            self._sequence[channel] += 1
            snapshot = build_factory_twin_snapshot(
                decision_state=state,
                registry=self.context.operation_registry,
                layout=self._layout,
                run_id=resolved_run_id,
                sequence=self._sequence[channel],
                rendering_config=self._twin_config.get("rendering", {}),
                warehouse_config=self._twin_config.get("warehouse", {}),
            )
            if current is not None:
                self._latest_delta[channel] = snapshot_delta(current, snapshot)
            self._latest[channel] = snapshot
            self._fingerprints[channel] = fingerprint
            self._history[channel].append(snapshot)
            return snapshot

    def latest_delta(
        self, source: str, run_id: str
    ) -> FactoryTwinDeltaV1 | None:
        return self._latest_delta.get((self._normalize_source(source), str(run_id)))

    def snapshot_after(
        self, source: str, run_id: str, sequence: int
    ) -> tuple[str, FactoryTwinSnapshotV1 | FactoryTwinDeltaV1]:
        channel = (self._normalize_source(source), str(run_id))
        current = self._latest.get(channel)
        if current is None:
            current = self.commit(source, run_id=run_id)
        if current.sequence == int(sequence):
            return "snapshot", current
        delta = self._latest_delta.get(channel)
        if delta is not None and delta.base_sequence == int(sequence):
            return "delta", delta
        return "resync_required", current

    def entity(
        self,
        entity_type: str,
        entity_id: str,
        source: str = "SIMULATOR",
        run_id: Optional[str] = None,
        at_time: Optional[int] = None,
    ) -> Dict[str, Any] | None:
        snapshot = self.commit(source, run_id=run_id, at_time=at_time)
        entity_type = str(entity_type).lower()
        entity_id = str(entity_id)
        layout_collections = {
            "operation": self._layout.operations,
            "equipment": self._layout.equipment,
            "queue": self._layout.queues,
            "route": self._layout.routes,
            "warehouse": [self._layout.warehouse],
        }
        layout_entity = next(
            (
                item.model_dump(mode="json")
                for item in layout_collections.get(entity_type, [])
                if str(getattr(item, "id", "")) == entity_id
            ),
            None,
        )
        state_collections = {
            "equipment": (snapshot.equipment, "equipment_id"),
            "queue": (snapshot.queues, "queue_id"),
            "task": (snapshot.work_items, "task_uid"),
            "carrier": (snapshot.carriers, "carrier_id"),
            "transfer": (snapshot.transfers, "transfer_id"),
            "warehouse": ([snapshot.warehouse], "warehouse_id"),
        }
        rows, key = state_collections.get(entity_type, ([], ""))
        state_entity = next(
            (
                item.model_dump(mode="json")
                for item in rows
                if str(getattr(item, key, "")) == entity_id
            ),
            None,
        )
        if layout_entity is None and state_entity is None:
            return None
        return {
            "found": True,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "layout": layout_entity,
            "state": state_entity,
            "snapshot": {
                "run_id": snapshot.run_id,
                "sequence": snapshot.sequence,
                "time": snapshot.time,
                "state_source": snapshot.state_source,
            },
        }

    def replay_range(self, run_id: Optional[str] = None) -> Dict[str, Any]:
        resolved_run_id = str(run_id or self.context.run_id)
        records = self.context.harness.store.canonical_ingestion_records(
            run_id=resolved_run_id
        )
        times = sorted(
            {
                int(record.event_time if record.event_time is not None else record.ingest_time or 0)
                for record in records
            }
        )
        return {
            "run_id": resolved_run_id,
            "state_source": "CANONICAL_TWIN",
            "available": bool(times),
            "min_time": times[0] if times else None,
            "max_time": times[-1] if times else None,
            "event_times": times,
            "record_count": len(records),
        }

    def _source_state(
        self, source: str, run_id: str, at_time: Optional[int]
    ) -> Dict[str, Any]:
        if source == "SIMULATOR":
            return simulator_source_state(self.context.env)
        records = self.context.harness.store.canonical_ingestion_records(run_id=run_id)
        return canonical_source_state(records, at_time=at_time)

    def _rebuild_layout(self) -> None:
        self._twin_config = dict(self.context.env.config.get("factory_twin", {}) or {})
        layout_config = dict(self._twin_config.get("layout", {}) or {})
        transport_config = dict(self._twin_config.get("transport", {}) or {})
        layout_config["route_travel_time"] = transport_config.get(
            "route_travel_time", {}
        )
        self._layout = build_factory_twin_layout(
            self.context.operation_registry, layout_config
        )

    @staticmethod
    def _normalize_source(source: str) -> str:
        normalized = str(source or "SIMULATOR").upper()
        if normalized not in {"SIMULATOR", "CANONICAL_TWIN"}:
            raise ValueError(f"unsupported factory twin source: {source}")
        return normalized

    @staticmethod
    def _fingerprint(state: Dict[str, Any]) -> str:
        return hashlib.sha256(
            json.dumps(state, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()


__all__ = ["FactoryTwinService"]
