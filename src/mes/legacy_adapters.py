# -*- coding: utf-8 -*-
"""Source-specific V1 adapters for legacy rows into ingestion payloads."""

from __future__ import annotations

from typing import Any, Dict


ADAPTER_IDS = (
    "legacy_mes_wip_unit",
    "legacy_mes_equipment",
    "fdc_quality_event",
    "rms_recipe",
)


def legacy_adapter_catalog() -> Dict[str, Any]:
    return {
        "count": len(ADAPTER_IDS),
        "items": [
            {
                "adapter_id": adapter_id,
                "mode": "row_to_canonical_ingestion_payload",
                "writes": ["raw_source_records", "canonical_ingestion_records", "source_key_mappings"],
            }
            for adapter_id in ADAPTER_IDS
        ],
    }


def legacy_adapter_payload(adapter_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    adapter = str(adapter_id)
    if adapter == "legacy_mes_wip_unit":
        return _legacy_mes_wip_unit(row)
    if adapter == "legacy_mes_equipment":
        return _legacy_mes_equipment(row)
    if adapter == "fdc_quality_event":
        return _fdc_quality_event(row)
    if adapter == "rms_recipe":
        return _rms_recipe(row)
    raise KeyError(f"unknown legacy adapter: {adapter_id}")


def _legacy_mes_wip_unit(row: Dict[str, Any]) -> Dict[str, Any]:
    unit_id = str(row["unit_id"])
    operation_id = str(row.get("operation_id") or "A")
    task_uid = _task_uid(row, unit_id)
    event_type = str(row.get("event_type") or "UNIT_WAITING")
    return {
        "source_system": "LEGACY_MES",
        "source_table": str(row.get("source_table") or "WIP_UNIT"),
        "source_pk": str(row.get("source_pk") or unit_id),
        "entity_type": "UNIT",
        "canonical_id": unit_id,
        "operation_id": operation_id,
        "equipment_id": str(row.get("equipment_id") or ""),
        "lot_id": str(row.get("lot_id") or row.get("job_id") or "UNKNOWN"),
        "unit_id": unit_id,
        "event_time": _optional_int(row.get("event_time")),
        "ingest_time": _optional_int(row.get("ingest_time")),
        "decision_time": _optional_int(row.get("decision_time")),
        "canonical": {
            "event_type": event_type,
            "attributes": {
                "task_uid": task_uid,
                "due_date": int(row.get("due_date", 0) or 0),
                "spec_a": row.get("spec_a", [45.0, 55.0]),
                "spec_b": row.get("spec_b", [20.0, 80.0]),
                "arrival_time": int(row.get("arrival_time", row.get("event_time", 0)) or 0),
                "material_type": str(row.get("material_type") or "plastic"),
                "color": str(row.get("color") or "red"),
                "customer_id": str(row.get("customer_id") or "UNKNOWN"),
                "margin_value": float(row.get("margin_value", 0.5) or 0.0),
                "rework_count": int(row.get("rework_count", 0) or 0),
            },
        },
        "payload": dict(row),
    }


def _legacy_mes_equipment(row: Dict[str, Any]) -> Dict[str, Any]:
    equipment_id = str(row["equipment_id"])
    operation_id = str(row.get("operation_id") or equipment_id.split("_", 1)[0])
    status = str(row.get("status") or "AVAILABLE").upper()
    event_type = "EQUIPMENT_AVAILABLE" if status in {"AVAILABLE", "IDLE"} else "EQUIPMENT_BUSY"
    return {
        "source_system": "LEGACY_MES",
        "source_table": str(row.get("source_table") or "EQP_MASTER"),
        "source_pk": str(row.get("source_pk") or equipment_id),
        "entity_type": "EQUIPMENT",
        "canonical_id": equipment_id,
        "operation_id": operation_id,
        "equipment_id": equipment_id,
        "event_time": _optional_int(row.get("event_time")),
        "ingest_time": _optional_int(row.get("ingest_time")),
        "canonical": {
            "event_type": str(row.get("event_type") or event_type),
            "attributes": {
                "batch_size": int(row.get("batch_size", 1) or 1),
                "status": status,
                "finish_time": int(row.get("finish_time", -1) or -1),
            },
        },
        "payload": dict(row),
    }


def _fdc_quality_event(row: Dict[str, Any]) -> Dict[str, Any]:
    unit_id = str(row["unit_id"])
    event_id = str(row.get("event_id") or row.get("source_pk") or unit_id)
    operation_id = str(row.get("operation_id") or "A")
    qa = row.get("qa", row.get("quality"))
    return {
        "source_system": "FDC",
        "source_table": str(row.get("source_table") or "QUALITY_EVENT"),
        "source_pk": event_id,
        "entity_type": "QUALITY",
        "canonical_id": str(row.get("canonical_id") or event_id),
        "operation_id": operation_id,
        "equipment_id": str(row.get("equipment_id") or ""),
        "lot_id": str(row.get("lot_id") or ""),
        "unit_id": unit_id,
        "event_time": _optional_int(row.get("event_time")),
        "ingest_time": _optional_int(row.get("ingest_time")),
        "canonical": {
            "event_type": str(row.get("event_type") or "QA_MEASURED"),
            "measurements": {"qa": float(qa) if qa is not None else 0.0},
            "quality_result": {"risk": str(row.get("risk") or "UNKNOWN")},
            "attributes": {"task_uid": _task_uid(row, unit_id)},
        },
        "payload": dict(row),
    }


def _rms_recipe(row: Dict[str, Any]) -> Dict[str, Any]:
    recipe_id = str(row["recipe_id"])
    operation_id = str(row.get("operation_id") or "")
    return {
        "source_system": "RMS",
        "source_table": str(row.get("source_table") or "RECIPE_MASTER"),
        "source_pk": str(row.get("source_pk") or recipe_id),
        "entity_type": "RECIPE",
        "canonical_id": recipe_id,
        "operation_id": operation_id,
        "recipe_id": recipe_id,
        "event_time": _optional_int(row.get("event_time")),
        "ingest_time": _optional_int(row.get("ingest_time")),
        "canonical": {
            "event_type": str(row.get("event_type") or "RECIPE_AVAILABLE"),
            "attributes": {
                "recipe_version": str(row.get("recipe_version") or "v1"),
                "approval_status": str(row.get("approval_status") or "APPROVED"),
                "parameter_set": dict(row.get("parameter_set") or {}),
            },
        },
        "payload": dict(row),
    }


def _task_uid(row: Dict[str, Any], unit_id: str) -> int:
    value = row.get("task_uid") or row.get("uid")
    if value is not None and str(value).lstrip("-").isdigit():
        return int(value)
    suffix = str(unit_id).split("_")[-1]
    return int(suffix) if suffix.isdigit() else 0


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
