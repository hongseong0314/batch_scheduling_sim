# -*- coding: utf-8 -*-
"""Runtime payload builders for legacy source-key mapping contracts."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from src.mes.domain import SourceKeyMapping


def source_key_mapping_id(
    source_system: str,
    source_table: str,
    source_pk: str,
    entity_type: str,
    run_id: str = "",
) -> str:
    raw = "|".join(
        [
            str(source_system).upper(),
            str(source_table),
            str(source_pk),
            str(entity_type).upper(),
            str(run_id),
        ]
    )
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12].upper()
    return f"SKM_{digest}"


def source_key_mapping_from_payload(
    payload: Dict[str, Any],
    default_run_id: str = "",
) -> SourceKeyMapping:
    source_system = str(payload["source_system"]).upper()
    source_table = str(payload["source_table"])
    source_pk = str(payload["source_pk"])
    entity_type = str(payload["entity_type"]).upper()
    run_id = str(payload.get("run_id") or default_run_id or "")
    mapping_id = str(
        payload.get("mapping_id")
        or source_key_mapping_id(
            source_system,
            source_table,
            source_pk,
            entity_type,
            run_id=run_id,
        )
    )
    return SourceKeyMapping(
        mapping_id=mapping_id,
        source_system=source_system,
        source_table=source_table,
        source_pk=source_pk,
        entity_type=entity_type,
        canonical_id=str(payload["canonical_id"]),
        canonical_namespace=str(payload.get("canonical_namespace") or "AI_MES"),
        run_id=run_id,
        ingest_time=_optional_int(payload.get("ingest_time")),
        event_time=_optional_int(payload.get("event_time")),
        decision_time=_optional_int(payload.get("decision_time")),
        status=str(payload.get("status") or "ACTIVE").upper(),
        confidence=float(payload.get("confidence", 1.0) or 0.0),
        source_payload=dict(payload.get("source_payload", {}) or {}),
        metadata=dict(payload.get("metadata", {}) or {}),
    )


def upsert_source_key_mapping_payload(
    context: Any,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    mapping = source_key_mapping_from_payload(
        payload,
        default_run_id=getattr(context, "run_id", ""),
    )
    context.harness.store.upsert_source_key_mapping(mapping)
    return {"status": "UPSERTED", "item": mapping.to_dict()}


def source_key_mappings_payload(
    context: Any,
    source_system: Optional[str] = None,
    entity_type: Optional[str] = None,
    canonical_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    items = context.harness.store.source_key_mappings(
        source_system=source_system.upper() if source_system else None,
        entity_type=entity_type.upper() if entity_type else None,
        canonical_id=canonical_id,
        run_id=run_id,
    )
    return {
        "count": len(items),
        "source_system": source_system,
        "entity_type": entity_type,
        "canonical_id": canonical_id,
        "run_id": run_id,
        "items": [item.to_dict() for item in items],
    }


def resolve_source_key_mapping_payload(
    context: Any,
    source_system: str,
    source_table: str,
    source_pk: str,
    entity_type: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    mapping = context.harness.store.resolve_source_key_mapping(
        source_system=source_system.upper(),
        source_table=source_table,
        source_pk=source_pk,
        entity_type=entity_type.upper() if entity_type else None,
        run_id=run_id,
    )
    return {
        "found": mapping is not None,
        "source_system": source_system,
        "source_table": source_table,
        "source_pk": source_pk,
        "entity_type": entity_type,
        "run_id": run_id,
        "item": mapping.to_dict() if mapping is not None else None,
    }


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)

