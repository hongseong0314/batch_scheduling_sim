"""Common factory-twin snapshot projection for simulator and canonical state."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from src.mes.factory_twin.contracts import (
    CarrierStateV1,
    EquipmentStateV1,
    FactoryTwinLayoutV1,
    FactoryTwinSnapshotV1,
    QueueStateV1,
    TransferStateV1,
    WarehouseStateV1,
    WorkItemStateV1,
)
from src.mes.operations.registry import OperationRegistry


def build_factory_twin_snapshot(
    *,
    decision_state: Mapping[str, Any],
    registry: OperationRegistry,
    layout: FactoryTwinLayoutV1,
    run_id: str,
    sequence: int,
    rendering_config: Mapping[str, Any] | None = None,
    warehouse_config: Mapping[str, Any] | None = None,
) -> FactoryTwinSnapshotV1:
    state = dict(decision_state)
    now = int(state.get("time", 0) or 0)
    source = str(state.get("state_source", "SIMULATOR")).upper()
    source = "CANONICAL_TWIN" if source == "CANONICAL_TWIN" else "SIMULATOR"
    render_config = dict(rendering_config or {})
    max_visible = max(0, int(render_config.get("max_visible_queue_items", 24) or 0))
    missing_operations = []

    equipment = []
    for definition in layout.equipment:
        operation_id = str(definition.operation_id or "")
        operation_state = dict(state.get(operation_id, {}) or {})
        machines = dict(operation_state.get("machines", {}) or {})
        machine = _machine_state(machines, definition.id)
        if machine is None:
            status = "UNKNOWN"
            task_uids = []
            batch_size = int(definition.metadata.get("batch_size", 1) or 1)
            finish_time = None
            start_time = None
            progress = None
            evidence_source = "MISSING"
        else:
            status = str(machine.get("status", "UNKNOWN")).upper()
            task_uids = _int_list(machine.get("current_batch_uids", []))
            batch_size = max(1, int(machine.get("batch_size", 1) or 1))
            finish_time = _nullable_time(machine.get("finish_time"))
            process_time = registry.get_operation(operation_id).process_time
            start_time = (
                finish_time - process_time
                if status in {"BUSY", "PROCESSING", "RUNNING"} and finish_time is not None
                else None
            )
            progress = _progress(now, start_time, finish_time, status)
            evidence_source = "OBSERVED" if source == "CANONICAL_TWIN" else "SIMULATED"
        equipment.append(
            EquipmentStateV1(
                equipment_id=definition.id,
                operation_id=operation_id,
                status=status,
                batch_size=batch_size,
                task_uids=task_uids,
                start_time=start_time,
                finish_time=finish_time,
                progress=progress,
                recipe_summary=_recipe_summary(machine),
                health_summary=_health_summary(machine),
                evidence_source=evidence_source,
            )
        )

    queues = []
    for definition in layout.queues:
        operation_id = str(definition.operation_id or "")
        operation_state = dict(state.get(operation_id, {}) or {})
        if operation_id not in state and operation_id not in missing_operations:
            missing_operations.append(operation_id)
        state_key = str(definition.metadata.get("state_key", ""))
        task_uids = _int_list(operation_state.get(state_key, []))
        queues.append(
            QueueStateV1(
                queue_id=definition.id,
                operation_id=operation_id,
                queue_type=str(definition.metadata.get("queue_type", "wait")),
                task_uids=task_uids,
                count=len(task_uids),
                visible_task_uids=task_uids[:max_visible],
            )
        )

    transfer_rows = _transfer_rows(state)
    transfers = [TransferStateV1(**row) for row in transfer_rows]
    material_flow = dict(state.get("material_flow", {}) or {})
    carrier_rows = []
    for row in transfer_rows:
        if row["status"] == "IN_TRANSIT":
            carrier_rows.append(row)
            continue
        visual_age = now - int(row["dispatch_time"])
        if (
            material_flow.get("mode") == "immediate"
            and 0 <= visual_age <= 4
        ):
            carrier_rows.append(
                {
                    **row,
                    "status": "INFERRED_VISUAL",
                    "progress": round(min(1.0, visual_age / 4.0), 4),
                }
            )
    carriers = [
        CarrierStateV1(
            carrier_id=row["carrier_id"],
            transfer_id=row["transfer_id"],
            task_uids=row["task_uids"],
            route_id=row["route_id"],
            from_operation_id=row["from_operation_id"],
            to_operation_id=row["to_operation_id"],
            dispatch_time=row["dispatch_time"],
            arrival_time=row["arrival_time"],
            status=row["status"],
            progress=row["progress"],
        )
        for row in carrier_rows
    ]
    transfer_by_task = {
        int(uid): row
        for row in transfer_rows
        if row["status"] == "IN_TRANSIT"
        for uid in row["task_uids"]
    }
    task_locations = _task_locations(state, equipment, queues, transfer_by_task)
    work_items = []
    for raw_uid, task in sorted(
        dict(state.get("tasks", {}) or {}).items(), key=lambda item: int(item[0])
    ):
        uid = int(raw_uid)
        location = task_locations.get(uid) or _canonical_location(task)
        quality = {
            "qa_a": _nullable_quality(task.get("realized_qa_A")),
            "qa_b": _nullable_quality(task.get("realized_qa_B")),
        }
        transfer = transfer_by_task.get(uid)
        work_items.append(
            WorkItemStateV1(
                task_uid=uid,
                lot_id=str(task.get("job_id") or task.get("lot_id") or "UNKNOWN"),
                carrier_id=transfer["carrier_id"] if transfer else None,
                operation_id=location.get("operation_id"),
                location_type=location["location_type"],
                location_id=location["location_id"],
                status=location["status"],
                due_date=_nullable_time(task.get("due_date")),
                customer_id=str(task.get("customer_id") or "UNKNOWN"),
                quality_summary={key: value for key, value in quality.items() if value is not None},
            )
        )

    raw_warehouse = dict(state.get("warehouse", {}) or {})
    completed_count = int(
        raw_warehouse.get("completed_count", state.get("num_completed", 0)) or 0
    )
    recent_completed = _int_list(raw_warehouse.get("recent_task_uids", []))
    warehouse_cfg = dict(warehouse_config or {})
    visible_slots = max(1, int(warehouse_cfg.get("visible_slots", 48) or 48))
    transport_source = (
        "OBSERVED"
        if source == "CANONICAL_TWIN" and transfer_rows
        else "SIMULATED"
        if source == "SIMULATOR" and material_flow.get("mode") == "timed_oht"
        else "INFERRED_VISUAL"
    )
    return FactoryTwinSnapshotV1(
        run_id=str(run_id),
        snapshot_id=f"TWIN_{str(run_id).replace('RUN_', '')}_{sequence:08d}",
        sequence=int(sequence),
        time=now,
        state_source=source,
        spatial_source=layout.spatial_source,
        transport_source=transport_source,
        layout_id=layout.layout_id,
        equipment=equipment,
        queues=queues,
        work_items=work_items,
        carriers=carriers,
        transfers=transfers,
        warehouse=WarehouseStateV1(
            completed_count=completed_count,
            recent_task_uids=recent_completed[-visible_slots:],
            visible_slots=visible_slots,
        ),
        diagnostics={
            "missing_runtime_operations": missing_operations,
            "exact_work_item_count": len(work_items),
            "visible_queue_limit": max_visible,
            "transport_mode": material_flow.get("mode", "inferred"),
        },
    )


def _machine_state(machines: Dict[str, Any], equipment_id: str) -> Optional[Dict[str, Any]]:
    direct = machines.get(equipment_id)
    if isinstance(direct, Mapping):
        return dict(direct)
    suffix = equipment_id.split("_")[-1]
    for key, value in machines.items():
        if str(key).split("_")[-1] == suffix and isinstance(value, Mapping):
            return dict(value)
    return None


def _recipe_summary(machine: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not machine:
        return None
    recipe = machine.get("current_recipe") or machine.get("recipe")
    return {"parameters": list(recipe)} if isinstance(recipe, (list, tuple)) else None


def _health_summary(machine: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not machine:
        return None
    keys = ("u", "m_age", "v", "b_age")
    values = {key: machine[key] for key in keys if key in machine}
    return values or None


def _progress(now: int, start: Optional[int], finish: Optional[int], status: str) -> Optional[float]:
    if status not in {"BUSY", "PROCESSING", "RUNNING"}:
        return 0.0 if status in {"IDLE", "AVAILABLE"} else None
    if start is None or finish is None or finish <= start:
        return None
    return round(max(0.0, min(1.0, (now - start) / (finish - start))), 4)


def _transfer_rows(state: Dict[str, Any]) -> list[Dict[str, Any]]:
    flow = dict(state.get("material_flow", {}) or {})
    rows = [*list(flow.get("active", []) or []), *list(flow.get("recent_completed", []) or [])[-20:]]
    result = []
    seen = set()
    for raw in rows:
        row = dict(raw or {})
        transfer_id = str(row.get("transfer_id", ""))
        if not transfer_id or transfer_id in seen:
            continue
        seen.add(transfer_id)
        result.append(
            {
                "transfer_id": transfer_id,
                "carrier_id": str(row.get("carrier_id") or transfer_id.replace("TRANSFER", "CARRIER")),
                "task_uids": _int_list(row.get("task_uids", [])),
                "from_operation_id": str(row.get("from_operation_id", "")),
                "to_operation_id": str(row.get("to_operation_id", "")),
                "route_id": str(row.get("route_id") or f"ROUTE_{row.get('from_operation_id', '')}_{row.get('to_operation_id', '')}"),
                "dispatch_time": int(row.get("dispatch_time", 0) or 0),
                "arrival_time": int(row.get("arrival_time", 0) or 0),
                "status": str(row.get("status", "IN_TRANSIT")).upper(),
                "progress": float(row.get("progress", 0.0) or 0.0),
            }
        )
    return result


def _task_locations(state, equipment, queues, transfer_by_task):
    locations = {}
    for row in equipment:
        for uid in row.task_uids:
            locations[uid] = {
                "operation_id": row.operation_id,
                "location_type": "EQUIPMENT",
                "location_id": row.equipment_id,
                "status": "RUNNING",
            }
    for row in queues:
        for uid in row.task_uids:
            queue_location = {
                "operation_id": row.operation_id,
                "location_type": "QUEUE",
                "location_id": row.queue_id,
                "status": (
                    "REWORK"
                    if row.queue_type == "rework"
                    else "FINISHED"
                    if row.queue_type == "output"
                    else "WAITING"
                ),
            }
            if row.queue_type == "output":
                locations[uid] = queue_location
            else:
                locations.setdefault(uid, queue_location)
    for uid, transfer in transfer_by_task.items():
        locations[uid] = {
            "operation_id": transfer["to_operation_id"],
            "location_type": "CARRIER",
            "location_id": transfer["carrier_id"],
            "status": "IN_TRANSIT",
        }
    return locations


def _canonical_location(task: Mapping[str, Any]) -> Dict[str, Any]:
    status = str(task.get("status", "UNKNOWN")).upper()
    equipment_id = str(task.get("equipment_id", ""))
    operation_id = str(task.get("operation_id", "")) or None
    if status in {"COMPLETED", "SHIPPED"}:
        return {"operation_id": operation_id, "location_type": "WAREHOUSE", "location_id": "WAREHOUSE_FINISHED", "status": status}
    if equipment_id:
        return {"operation_id": operation_id, "location_type": "EQUIPMENT", "location_id": equipment_id, "status": status}
    return {"operation_id": operation_id, "location_type": "UNKNOWN", "location_id": str(task.get("location", "UNKNOWN")), "status": status}


def _nullable_time(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _nullable_quality(value: Any) -> Optional[float]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _int_list(values: Any) -> list[int]:
    result = []
    for value in values or []:
        try:
            result.append(int(value))
        except (TypeError, ValueError):
            continue
    return result


__all__ = ["build_factory_twin_snapshot"]
