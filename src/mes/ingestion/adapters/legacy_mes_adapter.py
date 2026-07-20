# -*- coding: utf-8 -*-
"""Legacy MES source adapters for WIP, equipment, and assignments."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.ingestion.adapters.base import (
    BaseSourceAdapter,
    list_of_strings,
    optional_int,
    task_uid,
)


class LegacyMESWIPAdapter(BaseSourceAdapter):
    adapter_id = "legacy_mes_wip_unit"
    source_system = "LEGACY_MES"
    source_tables = ("WIP_UNIT", "WIP_WAFER", "WIP_LOT")
    canonical_entity_types = ("UNIT", "WAFER", "LOT")
    description = "Maps legacy WIP unit/wafer rows into canonical queued unit events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        unit_id = str(row["unit_id"])
        operation_id = str(row.get("operation_id") or "A")
        uid = task_uid(row, unit_id)
        event_type = str(row.get("event_type") or "UNIT_WAITING")
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "WIP_UNIT"),
            "source_pk": str(row.get("source_pk") or unit_id),
            "entity_type": str(row.get("entity_type") or "UNIT").upper(),
            "canonical_id": str(row.get("canonical_id") or unit_id),
            "operation_id": operation_id,
            "equipment_id": str(row.get("equipment_id") or ""),
            "lot_id": str(row.get("lot_id") or row.get("job_id") or "UNKNOWN"),
            "unit_id": unit_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": event_type,
                "attributes": {
                    "task_uid": uid,
                    "due_date": int(row.get("due_date", 0) or 0),
                    "spec_a": row.get("spec_a", [45.0, 55.0]),
                    "spec_b": row.get("spec_b", [20.0, 80.0]),
                    "arrival_time": int(
                        row.get("arrival_time", row.get("event_time", 0)) or 0
                    ),
                    "material_type": str(row.get("material_type") or "plastic"),
                    "color": str(row.get("color") or "red"),
                    "customer_id": str(row.get("customer_id") or "UNKNOWN"),
                    "margin_value": float(row.get("margin_value", 0.5) or 0.0),
                    "rework_count": int(row.get("rework_count", 0) or 0),
                    "source_state": str(row.get("source_state") or row.get("state") or ""),
                },
            },
            "payload": dict(row),
        }


class LegacyMESEquipmentAdapter(BaseSourceAdapter):
    adapter_id = "legacy_mes_equipment"
    source_system = "LEGACY_MES"
    source_tables = ("EQP_MASTER", "EQP_STATUS", "EQUIPMENT")
    canonical_entity_types = ("EQUIPMENT",)
    description = "Maps legacy MES equipment status rows into canonical tool events."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        equipment_id = str(row["equipment_id"])
        operation_id = str(row.get("operation_id") or equipment_id.split("_", 1)[0])
        status = str(row.get("status") or "AVAILABLE").upper()
        event_type = (
            "EQUIPMENT_AVAILABLE"
            if status in {"AVAILABLE", "IDLE"}
            else "EQUIPMENT_BUSY"
        )
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "EQP_MASTER"),
            "source_pk": str(row.get("source_pk") or equipment_id),
            "entity_type": "EQUIPMENT",
            "canonical_id": str(row.get("canonical_id") or equipment_id),
            "operation_id": operation_id,
            "equipment_id": equipment_id,
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or event_type),
                "attributes": {
                    "equipment_group_id": str(row.get("equipment_group_id") or operation_id),
                    "batch_size": int(row.get("batch_size", 1) or 1),
                    "status": status,
                    "finish_time": int(row.get("finish_time", -1) or -1),
                    "capable_operations": list_of_strings(
                        row.get("capable_operations") or [operation_id]
                    ),
                },
            },
            "payload": dict(row),
        }


class LegacyMESAssignmentAdapter(BaseSourceAdapter):
    adapter_id = "legacy_mes_assignment"
    source_system = "LEGACY_MES"
    source_tables = ("DISPATCH_ASSIGNMENT", "TRACK_IN", "RESERVATION")
    canonical_entity_types = ("ASSIGNMENT",)
    description = "Maps legacy MES dispatch/track-in rows into canonical assignments."

    def adapt(self, row: Dict[str, Any]) -> Dict[str, Any]:
        assignment_id = str(row.get("assignment_id") or row.get("source_pk") or "")
        if not assignment_id:
            assignment_id = f"ASN_{row.get('equipment_id', 'UNKNOWN')}_{row.get('event_time', '')}"
        equipment_id = str(row.get("equipment_id") or "")
        operation_id = str(row.get("operation_id") or equipment_id.split("_", 1)[0])
        unit_ids = list_of_strings(row.get("unit_ids") or row.get("unit_id"))
        return {
            "source_system": self.source_system,
            "source_table": str(row.get("source_table") or "DISPATCH_ASSIGNMENT"),
            "source_pk": str(row.get("source_pk") or assignment_id),
            "entity_type": "ASSIGNMENT",
            "canonical_id": str(row.get("canonical_id") or assignment_id),
            "operation_id": operation_id,
            "equipment_id": equipment_id,
            "unit_id": unit_ids[0] if unit_ids else "",
            "lot_id": str(row.get("lot_id") or ""),
            "event_time": optional_int(row.get("event_time")),
            "ingest_time": optional_int(row.get("ingest_time")),
            "decision_time": optional_int(row.get("decision_time")),
            "canonical": {
                "event_type": str(row.get("event_type") or "ASSIGNMENT_STARTED"),
                "attributes": {
                    "assignment_id": assignment_id,
                    "unit_ids": unit_ids,
                    "task_uids": [
                        task_uid({"unit_id": unit_id}, unit_id) for unit_id in unit_ids
                    ],
                    "candidate_id": str(row.get("candidate_id") or ""),
                    "command_id": str(row.get("command_id") or ""),
                    "legacy_dispatch_rule": str(row.get("legacy_dispatch_rule") or ""),
                },
            },
            "payload": dict(row),
        }
