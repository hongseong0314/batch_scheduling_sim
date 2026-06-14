"""Read-only MES queries for process-specific spatial quality evidence."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from src.mes.runtime.equipment_telemetry import resolve_equipment_ids
from src.mes.runtime.naming import equipment_display_name


def query_process_a_spatial_quality(
    context: Any,
    *,
    equipment_id: str | None = None,
    task_uid: int | None = None,
) -> Dict[str, Any]:
    """Return one completed Process-A spatial quality map."""
    if equipment_id is None and task_uid is None:
        raise ValueError("MISSING_SPATIAL_QUALITY_LOOKUP")

    canonical_equipment = None
    if equipment_id is not None:
        canonical_equipment = resolve_equipment_ids(
            context,
            [equipment_id],
        )[0]
        stage = canonical_equipment.split("_", 1)[0]
        if stage != "A":
            raise ValueError(f"UNSUPPORTED_SPATIAL_QUALITY_OPERATION:{stage}")

    normalized_task_uid = None
    if task_uid is not None:
        try:
            normalized_task_uid = int(task_uid)
        except (TypeError, ValueError) as exc:
            raise ValueError("INVALID_SPATIAL_QUALITY_TASK_UID") from exc

    event_log = list(getattr(context.env.env_A, "event_log", []) or [])
    for event in reversed(event_log):
        if str(event.get("event_type", "")).lower() != "task_completed":
            continue
        if (
            canonical_equipment is not None
            and str(event.get("machine_id", "")) != canonical_equipment
        ):
            continue
        maps = list(event.get("spatial_quality_maps") or [])
        for raw_map in reversed(maps):
            if not isinstance(raw_map, Mapping):
                continue
            map_equipment = str(
                raw_map.get("equipment_id")
                or event.get("machine_id")
                or ""
            )
            map_task_uid = _task_uid(raw_map.get("task_uid"))
            if canonical_equipment is not None and map_equipment != canonical_equipment:
                continue
            if normalized_task_uid is not None and map_task_uid != normalized_task_uid:
                continue
            spatial_quality = dict(raw_map)
            return {
                "found": True,
                "read_only": True,
                "source": "SIMULATOR",
                "time_basis": "SIMULATION_STEP",
                "evidence_type": "SIMULATED_SPATIAL_QUALITY",
                "equipment_id": map_equipment,
                "display_name": equipment_display_name(context, map_equipment),
                "task_uid": map_task_uid,
                "completion_time": int(
                    raw_map.get(
                        "completion_time",
                        event.get("timestamp", 0),
                    )
                    or 0
                ),
                "spatial_quality": spatial_quality,
            }

    return {
        "found": False,
        "reason": "NO_MATCHING_SPATIAL_QUALITY",
        "equipment_id": canonical_equipment,
        "task_uid": normalized_task_uid,
    }


def _task_uid(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
