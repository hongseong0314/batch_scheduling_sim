# -*- coding: utf-8 -*-
"""FDC/inspection adapters for quality and equipment events."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.ingestion.adapters.base import BaseSourceAdapter, optional_float, optional_int, task_uid


class FDCQualityEventAdapter(BaseSourceAdapter):
    adapter_id = "fdc_quality_event"
    source_system = "FDC"
    source_tables = ("QUALITY_EVENT", "INSPECTION_RESULT", "APC_PREDICTION")
    canonical_entity_types = ("QUALITY",)
    description = "Maps FDC or inspection quality rows into canonical quality events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        unit_id = str(row["unit_id"])
        event_id = str(row.get("event_id") or row.get("source_pk") or unit_id)
        operation_id = str(row.get("operation_id") or "A")
        qa = row.get("qa", row.get("quality"))
        predicted_qa = row.get("predicted_qa", qa)
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "QUALITY_EVENT"),
            "source_pk": event_id,
            "entity_type": "QUALITY",
            "canonical_id": str(row.get("canonical_id") or event_id),
            "operation_id": operation_id,
            "equipment_id": str(row.get("equipment_id") or ""),
            "lot_id": str(row.get("lot_id") or ""),
            "unit_id": unit_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or "QA_MEASURED"),
                "measurements": {
                    "qa": float(qa) if qa is not None else 0.0,
                    "predicted_qa": optional_float(predicted_qa),
                    "target_low": optional_float(row.get("target_low")),
                    "target_high": optional_float(row.get("target_high")),
                },
                "quality_result": {
                    "risk": str(row.get("risk") or row.get("quality_risk") or "UNKNOWN"),
                    "passed": row.get("passed"),
                    "reason": str(row.get("reason") or ""),
                },
                "attributes": {
                    "task_uid": task_uid(row, unit_id),
                    "sample_count": int(row.get("sample_count", 1) or 1),
                    "recipe_id": str(row.get("recipe_id") or ""),
                    "metrology_tool_id": str(row.get("metrology_tool_id") or ""),
                },
            },
            "payload": dict(row),
        }


class FDCEquipmentEventAdapter(BaseSourceAdapter):
    adapter_id = "fdc_equipment_event"
    source_system = "FDC"
    source_tables = ("EQUIPMENT_EVENT", "ALARM_EVENT", "TRACE_EVENT")
    canonical_entity_types = ("EVENT", "EQUIPMENT")
    description = "Maps FDC tool telemetry/alarm rows into canonical equipment events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        event_id = str(row.get("event_id") or row.get("source_pk") or "")
        equipment_id = str(row["equipment_id"])
        if not event_id:
            event_id = f"FDC_{equipment_id}_{row.get('event_time', '')}"
        operation_id = str(row.get("operation_id") or equipment_id.split("_", 1)[0])
        event_type = str(row.get("event_type") or "EQUIPMENT_EVENT").upper()
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "EQUIPMENT_EVENT"),
            "source_pk": event_id,
            "entity_type": "EVENT",
            "canonical_id": str(row.get("canonical_id") or event_id),
            "operation_id": operation_id,
            "equipment_id": equipment_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": event_type,
                "measurements": dict(row.get("measurements") or {}),
                "attributes": {
                    "alarm_code": str(row.get("alarm_code") or ""),
                    "severity": str(row.get("severity") or row.get("alarm_severity") or ""),
                    "status": str(row.get("status") or ""),
                    "message": str(row.get("message") or row.get("alarm_text") or ""),
                },
            },
            "payload": dict(row),
        }
