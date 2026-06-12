# -*- coding: utf-8 -*-
"""Event-sourced digital twin reconstruction from canonical ingestion records."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.mes.ingestion import CanonicalIngestionRecord


WAIT_EVENTS = {
    "LOT_WAITING",
    "UNIT_WAITING",
    "WAFER_WAITING",
    "WAITING",
    "QUEUED",
    "QUEUE_ENTERED",
    "MOVE_TO_OPERATION",
    "RELEASE",
    "TRACK_OUT",
}
RUN_EVENTS = {
    "TRACK_IN",
    "ASSIGNMENT_STARTED",
    "PROCESS_STARTED",
    "EQUIPMENT_STARTED",
}
REWORK_EVENTS = {"REWORK_REQUESTED", "REWORK_WAITING", "REWORK"}
HOLD_EVENTS = {"HOLD", "LOT_HOLD", "UNIT_HOLD"}
COMPLETE_EVENTS = {"PACKED", "SHIPPED", "COMPLETED", "UNIT_COMPLETED"}
EQUIPMENT_IDLE_EVENTS = {
    "EQUIPMENT_AVAILABLE",
    "EQUIPMENT_IDLE",
    "IDLE",
    "TOOL_AVAILABLE",
}
EQUIPMENT_BUSY_EVENTS = {
    "EQUIPMENT_BUSY",
    "EQUIPMENT_RUNNING",
    "TOOL_BUSY",
}


def build_digital_twin_state(
    records: Iterable[CanonicalIngestionRecord],
    at_time: Optional[int] = None,
) -> Dict[str, Any]:
    """Replay canonical records into a compact production digital twin state."""
    ordered = _ordered_records(records, at_time=at_time)
    lots: Dict[str, Dict[str, Any]] = {}
    units: Dict[int, Dict[str, Any]] = {}
    equipment: Dict[str, Dict[str, Any]] = {}
    quality_results: List[Dict[str, Any]] = []
    applied_record_ids: List[str] = []
    latest_time = 0

    for record in ordered:
        latest_time = max(latest_time, int(record.event_time or record.ingest_time or 0))
        applied_record_ids.append(record.record_id)
        entity_type = record.entity_type.upper()
        if entity_type == "EQUIPMENT":
            _apply_equipment_record(equipment, record)
        elif entity_type in {"UNIT", "WAFER"}:
            _apply_unit_record(units, equipment, record)
        elif entity_type == "LOT":
            _apply_lot_record(lots, record)
        elif entity_type == "QUALITY":
            quality_results.append(record.to_dict())
            _apply_quality_record(units, record)
        elif entity_type == "ASSIGNMENT":
            _apply_assignment_record(units, equipment, record)

    _ensure_equipment_batches(equipment, units)
    diagnostics = _twin_diagnostics(
        ordered,
        units=units,
        equipment=equipment,
        at_time=at_time,
    )
    return {
        "state_source": "CANONICAL_TWIN",
        "time": int(at_time if at_time is not None else latest_time),
        "latest_event_time": latest_time,
        "event_count": len(applied_record_ids),
        "applied_record_ids": applied_record_ids,
        "lots": lots,
        "units": units,
        "equipment": equipment,
        "quality_results": quality_results,
        "wip_by_operation": _wip_by_operation(units),
        "diagnostics": diagnostics,
    }


def build_canonical_decision_state(
    twin_state: Dict[str, Any],
    operation_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Convert canonical twin state into the existing policy decision-state shape."""
    requested = operation_ids or _operation_ids_from_twin(twin_state)
    stages = [operation for operation in requested if operation in {"A", "B", "C"}]
    for stage in ("A", "B", "C"):
        if stage not in stages:
            stages.append(stage)

    tasks = {
        int(uid): dict(row)
        for uid, row in dict(twin_state.get("units") or {}).items()
        if str(row.get("status", "")).upper() not in {"COMPLETED", "SHIPPED"}
    }
    decision_state: Dict[str, Any] = {
        "state_source": "CANONICAL_TWIN",
        "time": int(twin_state.get("time", 0) or 0),
        "max_steps": 0,
        "num_completed": _completed_count(twin_state),
        "tasks": tasks,
        "operations": {
            operation_id: {
                "operation_id": operation_id,
                "wip": dict(
                    dict(twin_state.get("wip_by_operation") or {}).get(operation_id, {})
                ),
            }
            for operation_id in requested
        },
    }

    for stage in stages:
        stage_state = _stage_decision_state(twin_state, stage)
        if stage == "B":
            stage_state.setdefault("incoming_from_A_uids", [])
        elif stage == "C":
            stage_state.setdefault("incoming_from_B_uids", [])
            stage_state.setdefault("last_pack_time", -1)
            stage_state.setdefault("pack_count", 0)
            stage_state.setdefault("capabilities", {"multi_machine": True})
        decision_state[stage] = stage_state
    return decision_state


def _ordered_records(
    records: Iterable[CanonicalIngestionRecord],
    at_time: Optional[int],
) -> List[CanonicalIngestionRecord]:
    filtered = []
    for record in records:
        event_time = record.event_time if record.event_time is not None else record.ingest_time
        if at_time is not None and event_time is not None and int(event_time) > int(at_time):
            continue
        filtered.append(record)
    return sorted(
        filtered,
        key=lambda item: (
            int(item.event_time if item.event_time is not None else item.ingest_time or 0),
            str(item.record_id),
        ),
    )


def _apply_equipment_record(
    equipment: Dict[str, Dict[str, Any]],
    record: CanonicalIngestionRecord,
) -> None:
    equipment_id = _equipment_id(record)
    if not equipment_id:
        return
    attributes = dict(record.attributes or {})
    operation_id = _operation_id(record, equipment_id=equipment_id)
    row = equipment.setdefault(
        equipment_id,
        {
            "equipment_id": equipment_id,
            "operation_id": operation_id,
            "status": "idle",
            "batch_size": int(attributes.get("batch_size", 1) or 1),
            "finish_time": int(attributes.get("finish_time", -1) or -1),
            "current_batch_uids": [],
            "attributes": {},
        },
    )
    row["operation_id"] = operation_id or row.get("operation_id", "")
    row["batch_size"] = int(attributes.get("batch_size", row.get("batch_size", 1)) or 1)
    if "finish_time" in attributes:
        row["finish_time"] = int(attributes.get("finish_time") or -1)
    status = str(attributes.get("status") or "").upper()
    event_type = str(record.event_type or "").upper()
    if event_type in EQUIPMENT_BUSY_EVENTS or status in {"BUSY", "RUN", "RUNNING"}:
        row["status"] = "busy"
    elif event_type in EQUIPMENT_IDLE_EVENTS or status in {"IDLE", "AVAILABLE"}:
        row["status"] = "idle"
    row["attributes"].update(attributes)


def _apply_lot_record(
    lots: Dict[str, Dict[str, Any]],
    record: CanonicalIngestionRecord,
) -> None:
    lot_id = _lot_id(record)
    if not lot_id:
        return
    attributes = dict(record.attributes or {})
    row = lots.setdefault(
        lot_id,
        {
            "lot_id": lot_id,
            "operation_id": str(record.operation_id or ""),
            "status": "WAIT",
            "attributes": {},
        },
    )
    row["operation_id"] = str(record.operation_id or row.get("operation_id", ""))
    row["status"] = _status_from_event(record.event_type, default=row.get("status", "WAIT"))
    row["attributes"].update(attributes)


def _apply_unit_record(
    units: Dict[int, Dict[str, Any]],
    equipment: Dict[str, Dict[str, Any]],
    record: CanonicalIngestionRecord,
) -> None:
    uid = _task_uid(record)
    if uid is None:
        return
    attributes = dict(record.attributes or {})
    operation_id = _operation_id(record)
    equipment_id = _equipment_id(record)
    current = units.get(uid, {})
    status = _status_from_event(record.event_type, default=current.get("status", "WAIT"))
    rework_count = int(
        attributes.get("rework_count", current.get("rework_count", 0)) or 0
    )
    if status == "REWORK" and rework_count == 0:
        rework_count = 1
    row = {
        "uid": uid,
        "job_id": str(
            record.lot_id
            or attributes.get("job_id")
            or attributes.get("lot_id")
            or current.get("job_id", "UNKNOWN")
        ),
        "due_date": int(attributes.get("due_date", current.get("due_date", 0)) or 0),
        "spec_a": _pair(attributes.get("spec_a", current.get("spec_a", (45.0, 55.0)))),
        "spec_b": _pair(attributes.get("spec_b", current.get("spec_b", (20.0, 80.0)))),
        "location": _location_for(status, operation_id, equipment_id),
        "rework_count": rework_count,
        "arrival_time": int(
            attributes.get(
                "arrival_time",
                current.get("arrival_time", record.event_time or record.ingest_time or 0),
            )
            or 0
        ),
        "material_type": str(
            attributes.get("material_type", current.get("material_type", "plastic"))
        ),
        "color": str(attributes.get("color", current.get("color", "red"))),
        "customer_id": str(
            attributes.get("customer_id", current.get("customer_id", "UNKNOWN"))
        ),
        "margin_value": float(
            attributes.get("margin_value", current.get("margin_value", 0.5)) or 0.0
        ),
        "realized_qa_A": float(
            attributes.get("realized_qa_A", current.get("realized_qa_A", -1.0))
            or -1.0
        ),
        "realized_qa_B": float(
            attributes.get("realized_qa_B", current.get("realized_qa_B", -1.0))
            or -1.0
        ),
        "operation_id": operation_id,
        "equipment_id": equipment_id,
        "status": status,
        "canonical_id": record.canonical_id,
        "unit_id": str(record.unit_id or record.canonical_id),
        "last_event_type": str(record.event_type or ""),
    }
    units[uid] = row
    if status == "RUNNING" and equipment_id:
        machine = equipment.setdefault(
            equipment_id,
            {
                "equipment_id": equipment_id,
                "operation_id": operation_id,
                "status": "busy",
                "batch_size": int(attributes.get("batch_size", 1) or 1),
                "finish_time": int(attributes.get("finish_time", -1) or -1),
                "current_batch_uids": [],
                "attributes": {},
            },
        )
        machine["status"] = "busy"
        machine["operation_id"] = operation_id or machine.get("operation_id", "")
        machine["finish_time"] = int(
            attributes.get("finish_time", machine.get("finish_time", -1)) or -1
        )
        batch = [int(value) for value in machine.get("current_batch_uids", [])]
        if uid not in batch:
            batch.append(uid)
        machine["current_batch_uids"] = sorted(batch)


def _apply_quality_record(
    units: Dict[int, Dict[str, Any]],
    record: CanonicalIngestionRecord,
) -> None:
    uid = _task_uid(record)
    if uid is None or uid not in units:
        return
    measurements = dict(record.measurements or {})
    quality = dict(record.quality_result or {})
    qa_value = measurements.get("qa") or measurements.get("quality")
    if qa_value is None:
        qa_value = quality.get("qa") or quality.get("quality")
    if qa_value is None:
        return
    operation_id = _operation_id(record)
    if operation_id == "A":
        units[uid]["realized_qa_A"] = float(qa_value)
    elif operation_id == "B":
        units[uid]["realized_qa_B"] = float(qa_value)


def _apply_assignment_record(
    units: Dict[int, Dict[str, Any]],
    equipment: Dict[str, Dict[str, Any]],
    record: CanonicalIngestionRecord,
) -> None:
    attributes = dict(record.attributes or {})
    equipment_id = _equipment_id(record)
    operation_id = _operation_id(record, equipment_id=equipment_id)
    task_uids = [
        int(value)
        for value in attributes.get("task_uids", [])
        if str(value).isdigit()
    ]
    if not task_uids:
        uid = _task_uid(record)
        task_uids = [uid] if uid is not None else []
    if not equipment_id or not task_uids:
        return
    machine = equipment.setdefault(
        equipment_id,
        {
            "equipment_id": equipment_id,
            "operation_id": operation_id,
            "status": "idle",
            "batch_size": int(attributes.get("batch_size", len(task_uids)) or 1),
            "finish_time": int(attributes.get("finish_time", -1) or -1),
            "current_batch_uids": [],
            "attributes": {},
        },
    )
    if str(record.event_type or "").upper() in RUN_EVENTS:
        machine["status"] = "busy"
        machine["finish_time"] = int(attributes.get("finish_time", -1) or -1)
        machine["current_batch_uids"] = sorted(task_uids)
        for uid in task_uids:
            if uid in units:
                units[uid]["status"] = "RUNNING"
                units[uid]["operation_id"] = operation_id
                units[uid]["equipment_id"] = equipment_id
                units[uid]["location"] = _location_for("RUNNING", operation_id, equipment_id)


def _ensure_equipment_batches(
    equipment: Dict[str, Dict[str, Any]],
    units: Dict[int, Dict[str, Any]],
) -> None:
    for machine in equipment.values():
        if machine.get("status") != "busy":
            machine["current_batch_uids"] = []
            continue
        batch = [
            uid
            for uid, unit in units.items()
            if unit.get("equipment_id") == machine.get("equipment_id")
            and unit.get("status") == "RUNNING"
        ]
        if batch:
            machine["current_batch_uids"] = sorted(batch)


def _stage_decision_state(
    twin_state: Dict[str, Any],
    stage: str,
) -> Dict[str, Any]:
    units = dict(twin_state.get("units") or {})
    equipment = dict(twin_state.get("equipment") or {})
    wait = sorted(
        int(uid)
        for uid, row in units.items()
        if row.get("operation_id") == stage and row.get("status") == "WAIT"
    )
    rework = sorted(
        int(uid)
        for uid, row in units.items()
        if row.get("operation_id") == stage and row.get("status") == "REWORK"
    )
    held = sorted(
        int(uid)
        for uid, row in units.items()
        if row.get("operation_id") == stage and row.get("status") == "HOLD"
    )
    machines = {
        str(equipment_id): {
            "status": str(machine.get("status", "idle")),
            "finish_time": int(machine.get("finish_time", -1) or -1),
            "batch_size": int(machine.get("batch_size", 1) or 1),
            "current_batch_uids": [
                int(uid) for uid in machine.get("current_batch_uids", [])
            ],
        }
        for equipment_id, machine in sorted(equipment.items())
        if machine.get("operation_id") == stage
    }
    return {
        "machines": machines,
        "wait_pool_uids": wait,
        "rework_pool_uids": rework,
        "held_uids": held,
        "finishing_now_uids": [],
        "queue_stats": {
            "wait_pool_size": len(wait),
            "rework_pool_size": len(rework),
            "hold_pool_size": len(held),
        },
    }


def _wip_by_operation(units: Dict[int, Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    result: Dict[str, Dict[str, int]] = {}
    for row in units.values():
        operation_id = str(row.get("operation_id") or "UNKNOWN")
        status = str(row.get("status") or "WAIT")
        group = result.setdefault(
            operation_id,
            {"wait": 0, "rework": 0, "running": 0, "hold": 0, "completed": 0, "total": 0},
        )
        if status == "WAIT":
            group["wait"] += 1
        elif status == "REWORK":
            group["rework"] += 1
        elif status == "RUNNING":
            group["running"] += 1
        elif status == "HOLD":
            group["hold"] += 1
        elif status in {"COMPLETED", "SHIPPED"}:
            group["completed"] += 1
        group["total"] += 1
    return result


def _operation_ids_from_twin(twin_state: Dict[str, Any]) -> List[str]:
    operations = set(dict(twin_state.get("wip_by_operation") or {}).keys())
    for machine in dict(twin_state.get("equipment") or {}).values():
        if machine.get("operation_id"):
            operations.add(str(machine["operation_id"]))
    return sorted(operations)


def _twin_diagnostics(
    records: List[CanonicalIngestionRecord],
    units: Dict[int, Dict[str, Any]],
    equipment: Dict[str, Dict[str, Any]],
    at_time: Optional[int],
) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    supported = {
        "LOT",
        "UNIT",
        "WAFER",
        "EQUIPMENT",
        "RECIPE",
        "EVENT",
        "ASSIGNMENT",
        "QUALITY",
    }
    for record in records:
        entity_type = str(record.entity_type or "").upper()
        if entity_type not in supported:
            issues.append(
                {
                    "severity": "WARN",
                    "code": "UNSUPPORTED_ENTITY_SKIPPED",
                    "record_id": record.record_id,
                    "entity_type": record.entity_type,
                    "message": "Digital twin replay skipped an unsupported entity type.",
                }
            )
        if (
            entity_type in {"UNIT", "WAFER", "ASSIGNMENT", "QUALITY"}
            and not record.operation_id
        ):
            issues.append(
                {
                    "severity": "WARN",
                    "code": "MISSING_OPERATION_ID",
                    "record_id": record.record_id,
                    "entity_type": entity_type,
                    "message": "Record can be replayed, but policy routing may be incomplete.",
                }
            )
    for uid, row in sorted(units.items()):
        if row.get("status") == "RUNNING" and not row.get("equipment_id"):
            issues.append(
                {
                    "severity": "WARN",
                    "code": "RUNNING_UNIT_WITHOUT_EQUIPMENT",
                    "unit_uid": uid,
                    "message": "Running unit has no equipment_id in canonical state.",
                }
            )
    for equipment_id, machine in sorted(equipment.items()):
        if machine.get("status") == "busy" and not machine.get("current_batch_uids"):
            issues.append(
                {
                    "severity": "WARN",
                    "code": "BUSY_EQUIPMENT_WITHOUT_BATCH",
                    "equipment_id": equipment_id,
                    "message": "Busy equipment has no current_batch_uids after replay.",
                }
            )
    severities = {issue["severity"] for issue in issues}
    status = "WARN" if "WARN" in severities else "OK"
    if not records:
        status = "EMPTY"
    return {
        "status": status,
        "at_time": at_time,
        "record_count": len(records),
        "unit_count": len(units),
        "equipment_count": len(equipment),
        "operation_ids": _operation_ids_from_twin(
            {
                "units": units,
                "equipment": equipment,
                "wip_by_operation": _wip_by_operation(units),
            }
        ),
        "issue_count": len(issues),
        "issues": issues,
    }


def _completed_count(twin_state: Dict[str, Any]) -> int:
    return sum(
        1
        for row in dict(twin_state.get("units") or {}).values()
        if str(row.get("status", "")).upper() in {"COMPLETED", "SHIPPED"}
    )


def _status_from_event(event_type: Any, default: str = "WAIT") -> str:
    event = str(event_type or "").upper()
    if event in WAIT_EVENTS:
        return "WAIT"
    if event in RUN_EVENTS:
        return "RUNNING"
    if event in REWORK_EVENTS:
        return "REWORK"
    if event in HOLD_EVENTS:
        return "HOLD"
    if event in COMPLETE_EVENTS:
        return "COMPLETED"
    return str(default or "WAIT").upper()


def _location_for(status: str, operation_id: str, equipment_id: str = "") -> str:
    if status == "RUNNING":
        return f"PROC_{equipment_id}" if equipment_id else f"PROC_{operation_id}"
    if status == "REWORK":
        return f"REWORK_{operation_id}"
    if status == "HOLD":
        return f"HOLD_{operation_id}"
    if status == "COMPLETED":
        return "COMPLETED"
    return f"QUEUE_{operation_id}"


def _task_uid(record: CanonicalIngestionRecord) -> Optional[int]:
    attributes = dict(record.attributes or {})
    for value in (
        attributes.get("task_uid"),
        attributes.get("uid"),
        record.unit_id,
        record.canonical_id,
    ):
        if value is None:
            continue
        suffix = str(value).split("_")[-1]
        if suffix.isdigit():
            return int(suffix)
    return None


def _operation_id(
    record: CanonicalIngestionRecord,
    equipment_id: str = "",
) -> str:
    if record.operation_id:
        return str(record.operation_id)
    equipment_key = equipment_id or record.equipment_id
    if equipment_key:
        first = str(equipment_key)[0].upper()
        if first in {"A", "B", "C"}:
            return first
    return "UNKNOWN"


def _equipment_id(record: CanonicalIngestionRecord) -> str:
    if record.entity_type.upper() == "EQUIPMENT":
        return str(record.equipment_id or record.canonical_id or "")
    return str(record.equipment_id or "")


def _lot_id(record: CanonicalIngestionRecord) -> str:
    attributes = dict(record.attributes or {})
    return str(record.lot_id or attributes.get("lot_id") or record.canonical_id or "")


def _pair(value: Any) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return (45.0, 55.0)
