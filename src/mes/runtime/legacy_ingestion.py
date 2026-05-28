# -*- coding: utf-8 -*-
"""Runtime helpers for legacy ingestion API payloads."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.ingestion import (
    CanonicalIngestionRecord,
    RawSourceRecord,
    canonical_ingestion_record_from_payload,
    raw_source_record_from_payload,
)
from src.mes.runtime.source_key_mappings import source_key_mapping_from_payload


def ingest_source_record_payload(context: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    raw = raw_source_record_from_payload(
        payload,
        default_run_id=getattr(context, "run_id", ""),
    )
    context.harness.store.add_raw_source_record(raw)

    canonical_record = _canonical_record_from_ingest_payload(
        raw,
        payload,
        default_run_id=getattr(context, "run_id", ""),
    )
    mapping = None
    if canonical_record is not None:
        context.harness.store.add_canonical_ingestion_record(canonical_record)
        mapping = source_key_mapping_from_payload(
            {
                "source_system": raw.source_system,
                "source_table": raw.source_table,
                "source_pk": raw.source_pk,
                "entity_type": raw.entity_type,
                "canonical_id": canonical_record.canonical_id,
                "canonical_namespace": canonical_record.canonical_namespace,
                "run_id": raw.run_id,
                "ingest_time": raw.ingest_time,
                "event_time": raw.event_time,
                "decision_time": raw.decision_time,
                "source_payload": raw.payload,
                "metadata": {
                    "raw_record_id": raw.record_id,
                    "canonical_record_id": canonical_record.record_id,
                },
            },
            default_run_id=getattr(context, "run_id", ""),
        )
        context.harness.store.upsert_source_key_mapping(mapping)

    return {
        "status": "INGESTED",
        "raw_record": raw.to_dict(),
        "canonical_record": (
            canonical_record.to_dict() if canonical_record is not None else None
        ),
        "source_key_mapping": mapping.to_dict() if mapping is not None else None,
    }


def raw_source_records_payload(
    context: Any,
    source_system: Optional[str] = None,
    entity_type: Optional[str] = None,
    record_id: Optional[str] = None,
    source_table: Optional[str] = None,
    source_pk: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    records = context.harness.store.raw_source_records(
        source_system=source_system.upper() if source_system else None,
        entity_type=entity_type.upper() if entity_type else None,
        record_id=record_id,
        source_table=source_table,
        source_pk=source_pk,
        run_id=run_id,
    )
    return {
        "count": len(records),
        "source_system": source_system,
        "entity_type": entity_type,
        "record_id": record_id,
        "source_table": source_table,
        "source_pk": source_pk,
        "run_id": run_id,
        "items": [record.to_dict() for record in records],
    }


def canonical_ingestion_records_payload(
    context: Any,
    entity_type: Optional[str] = None,
    canonical_id: Optional[str] = None,
    raw_record_id: Optional[str] = None,
    record_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    records = context.harness.store.canonical_ingestion_records(
        entity_type=entity_type.upper() if entity_type else None,
        canonical_id=canonical_id,
        raw_record_id=raw_record_id,
        record_id=record_id,
        run_id=run_id,
    )
    return {
        "count": len(records),
        "entity_type": entity_type,
        "canonical_id": canonical_id,
        "raw_record_id": raw_record_id,
        "record_id": record_id,
        "run_id": run_id,
        "items": [record.to_dict() for record in records],
    }


def _canonical_record_from_ingest_payload(
    raw: RawSourceRecord,
    payload: Dict[str, Any],
    default_run_id: str,
) -> Optional[CanonicalIngestionRecord]:
    canonical_payload = dict(payload.get("canonical_record") or {})
    canonical_payload.update(dict(payload.get("canonical") or {}))
    canonical_id = (
        canonical_payload.get("canonical_id")
        or payload.get("canonical_id")
        or payload.get("canonical_entity_id")
    )
    if not canonical_id:
        return None

    inherited = {
        "canonical_id": canonical_id,
        "canonical_namespace": payload.get("canonical_namespace"),
        "entity_type": payload.get("entity_type"),
        "operation_id": payload.get("operation_id"),
        "equipment_id": payload.get("equipment_id"),
        "lot_id": payload.get("lot_id"),
        "unit_id": payload.get("unit_id"),
        "recipe_id": payload.get("recipe_id"),
        "event_time": payload.get("event_time"),
        "ingest_time": payload.get("ingest_time"),
        "decision_time": payload.get("decision_time"),
        "run_id": payload.get("run_id"),
    }
    merged = {key: value for key, value in inherited.items() if value is not None}
    merged.update(canonical_payload)
    return canonical_ingestion_record_from_payload(
        merged,
        raw_record=raw,
        default_run_id=default_run_id,
    )
