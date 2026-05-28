# -*- coding: utf-8 -*-
"""Legacy ingestion DTOs for raw records and canonical projections."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from src.mes.recommendations import make_id


@dataclass
class RawSourceRecord:
    record_id: str
    source_system: str
    source_table: str
    source_pk: str
    entity_type: str
    operation_id: str = ""
    equipment_id: str = ""
    lot_id: str = ""
    unit_id: str = ""
    recipe_id: str = ""
    event_time: Optional[int] = None
    ingest_time: Optional[int] = None
    decision_time: Optional[int] = None
    schema_version: str = "raw-source-record-v1"
    status: str = "RECEIVED"
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    @property
    def source_key(self) -> str:
        return f"{self.source_system}:{self.source_table}:{self.source_pk}"

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["source_key"] = self.source_key
        return payload


@dataclass
class CanonicalIngestionRecord:
    record_id: str
    raw_record_id: str
    entity_type: str
    canonical_id: str
    canonical_namespace: str = "AI_MES"
    operation_id: str = ""
    equipment_id: str = ""
    lot_id: str = ""
    unit_id: str = ""
    recipe_id: str = ""
    event_type: str = ""
    event_time: Optional[int] = None
    ingest_time: Optional[int] = None
    decision_time: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    measurements: Dict[str, Any] = field(default_factory=dict)
    quality_result: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""
    schema_version: str = "canonical-ingestion-record-v1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def raw_source_record_from_payload(
    payload: Dict[str, Any],
    default_run_id: str = "",
) -> RawSourceRecord:
    source_system = str(payload["source_system"]).upper()
    source_table = str(payload["source_table"])
    source_pk = str(payload["source_pk"])
    entity_type = str(payload["entity_type"]).upper()
    run_id = str(payload.get("run_id") or default_run_id or "")
    record_id = str(
        payload.get("record_id")
        or _stable_id(
            "RAW",
            source_system,
            source_table,
            source_pk,
            entity_type,
            run_id,
        )
    )
    return RawSourceRecord(
        record_id=record_id,
        source_system=source_system,
        source_table=source_table,
        source_pk=source_pk,
        entity_type=entity_type,
        operation_id=str(payload.get("operation_id") or ""),
        equipment_id=str(payload.get("equipment_id") or ""),
        lot_id=str(payload.get("lot_id") or ""),
        unit_id=str(payload.get("unit_id") or ""),
        recipe_id=str(payload.get("recipe_id") or ""),
        event_time=_optional_int(payload.get("event_time")),
        ingest_time=_optional_int(payload.get("ingest_time")),
        decision_time=_optional_int(payload.get("decision_time")),
        schema_version=str(payload.get("schema_version") or "raw-source-record-v1"),
        status=str(payload.get("status") or "RECEIVED").upper(),
        payload=dict(payload.get("payload", {}) or {}),
        metadata=dict(payload.get("metadata", {}) or {}),
        run_id=run_id,
    )


def canonical_ingestion_record_from_payload(
    payload: Dict[str, Any],
    raw_record: Optional[RawSourceRecord] = None,
    default_run_id: str = "",
) -> CanonicalIngestionRecord:
    raw = raw_record
    entity_type = str(
        payload.get("entity_type")
        or (raw.entity_type if raw is not None else "")
        or "UNKNOWN"
    ).upper()
    canonical_id = str(
        payload.get("canonical_id")
        or _stable_id(
            entity_type or "CANON",
            raw.source_system if raw is not None else "",
            raw.source_table if raw is not None else "",
            raw.source_pk if raw is not None else "",
            default_run_id,
        )
    )
    run_id = str(
        payload.get("run_id")
        or (raw.run_id if raw is not None else "")
        or default_run_id
        or ""
    )
    raw_record_id = str(payload.get("raw_record_id") or (raw.record_id if raw else ""))
    record_id = str(
        payload.get("record_id")
        or _stable_id("CANON", raw_record_id, entity_type, canonical_id, run_id)
        or make_id("CANON")
    )
    return CanonicalIngestionRecord(
        record_id=record_id,
        raw_record_id=raw_record_id,
        entity_type=entity_type,
        canonical_id=canonical_id,
        canonical_namespace=str(payload.get("canonical_namespace") or "AI_MES"),
        operation_id=str(
            payload.get("operation_id")
            or (raw.operation_id if raw is not None else "")
            or ""
        ),
        equipment_id=str(
            payload.get("equipment_id")
            or (raw.equipment_id if raw is not None else "")
            or ""
        ),
        lot_id=str(payload.get("lot_id") or (raw.lot_id if raw is not None else "") or ""),
        unit_id=str(payload.get("unit_id") or (raw.unit_id if raw is not None else "") or ""),
        recipe_id=str(
            payload.get("recipe_id")
            or (raw.recipe_id if raw is not None else "")
            or ""
        ),
        event_type=str(payload.get("event_type") or ""),
        event_time=_optional_int(
            payload.get("event_time")
            if payload.get("event_time") is not None
            else (raw.event_time if raw is not None else None)
        ),
        ingest_time=_optional_int(
            payload.get("ingest_time")
            if payload.get("ingest_time") is not None
            else (raw.ingest_time if raw is not None else None)
        ),
        decision_time=_optional_int(
            payload.get("decision_time")
            if payload.get("decision_time") is not None
            else (raw.decision_time if raw is not None else None)
        ),
        attributes=dict(payload.get("attributes", {}) or {}),
        measurements=dict(payload.get("measurements", {}) or {}),
        quality_result=dict(payload.get("quality_result", {}) or {}),
        payload=dict(payload.get("payload", {}) or {}),
        run_id=run_id,
        schema_version=str(
            payload.get("schema_version") or "canonical-ingestion-record-v1"
        ),
    )


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}_{digest}"


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)
