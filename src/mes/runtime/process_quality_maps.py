"""Read-only MES queries for process-specific quality evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Dict

from src.environment.process_quality import QUALITY_PROVIDER_REGISTRY
from src.environment.process_quality.contracts import (
    normalize_quality_evidence,
)
from src.mes.runtime.equipment_telemetry import resolve_equipment_ids
from src.mes.runtime.naming import equipment_display_name


def query_process_quality_evidence(
    context: Any,
    *,
    operation_id: str | None = None,
    equipment_id: str | None = None,
    task_uid: int | None = None,
) -> Dict[str, Any]:
    """Return the latest matching A/B process quality evidence."""
    if equipment_id is None and task_uid is None:
        raise ValueError("MISSING_QUALITY_EVIDENCE_LOOKUP")

    normalized_operation = _operation_id(operation_id)
    if (
        normalized_operation is not None
        and normalized_operation not in QUALITY_PROVIDER_REGISTRY.operations()
    ):
        raise ValueError(
            "UNSUPPORTED_QUALITY_EVIDENCE_OPERATION:"
            f"{normalized_operation}"
        )

    canonical_equipment = None
    if equipment_id is not None:
        canonical_equipment = resolve_equipment_ids(
            context,
            [equipment_id],
        )[0]
        equipment_operation = canonical_equipment.split("_", 1)[0].upper()
        if (
            normalized_operation is not None
            and normalized_operation != equipment_operation
        ):
            raise ValueError(
                "QUALITY_EVIDENCE_OPERATION_MISMATCH:"
                f"{normalized_operation}:{equipment_operation}"
            )
        normalized_operation = equipment_operation
        if normalized_operation not in QUALITY_PROVIDER_REGISTRY.operations():
            raise ValueError(
                "UNSUPPORTED_QUALITY_EVIDENCE_OPERATION:"
                f"{normalized_operation}"
            )

    normalized_task_uid = _normalize_task_uid(task_uid)
    operations = (
        [normalized_operation]
        if normalized_operation is not None
        else QUALITY_PROVIDER_REGISTRY.operations()
    )
    events = _completion_events(context, operations)

    for operation, event in events:
        event_equipment = str(event.get("machine_id") or "")
        if (
            canonical_equipment is not None
            and event_equipment != canonical_equipment
        ):
            continue
        for raw_evidence in reversed(_event_evidence(operation, event)):
            evidence_equipment = str(
                raw_evidence.get("equipment_id") or event_equipment
            )
            evidence_task_uid = _task_uid(raw_evidence.get("task_uid"))
            if (
                canonical_equipment is not None
                and evidence_equipment != canonical_equipment
            ):
                continue
            if (
                normalized_task_uid is not None
                and evidence_task_uid != normalized_task_uid
            ):
                continue
            evidence = _normalize_event_evidence(
                operation,
                event,
                raw_evidence,
            )
            return {
                "found": True,
                "read_only": True,
                "source": "SIMULATOR",
                "time_basis": "SIMULATION_STEP",
                "operation_id": operation,
                "evidence_type": evidence["evidence_type"],
                "equipment_id": evidence_equipment,
                "display_name": equipment_display_name(
                    context,
                    evidence_equipment,
                ),
                "task_uid": evidence_task_uid,
                "completion_time": int(
                    evidence.get(
                        "completion_time",
                        event.get("timestamp", 0),
                    )
                    or 0
                ),
                "quality_evidence": evidence,
            }

    return {
        "found": False,
        "reason": "NO_MATCHING_QUALITY_EVIDENCE",
        "operation_id": normalized_operation,
        "equipment_id": canonical_equipment,
        "task_uid": normalized_task_uid,
    }


def query_process_a_spatial_quality(
    context: Any,
    *,
    equipment_id: str | None = None,
    task_uid: int | None = None,
) -> Dict[str, Any]:
    """Backward-compatible projection of Process A quality evidence."""
    if equipment_id is None and task_uid is None:
        raise ValueError("MISSING_SPATIAL_QUALITY_LOOKUP")
    if equipment_id is not None:
        canonical_equipment = resolve_equipment_ids(
            context,
            [equipment_id],
        )[0]
        stage = canonical_equipment.split("_", 1)[0]
        if stage != "A":
            raise ValueError(f"UNSUPPORTED_SPATIAL_QUALITY_OPERATION:{stage}")

    try:
        payload = query_process_quality_evidence(
            context,
            operation_id="A",
            equipment_id=equipment_id,
            task_uid=task_uid,
        )
    except ValueError as exc:
        if str(exc) == "INVALID_QUALITY_EVIDENCE_TASK_UID":
            raise ValueError("INVALID_SPATIAL_QUALITY_TASK_UID") from exc
        raise

    if not payload["found"]:
        return {
            "found": False,
            "reason": "NO_MATCHING_SPATIAL_QUALITY",
            "equipment_id": payload["equipment_id"],
            "task_uid": payload["task_uid"],
        }
    return {
        "found": True,
        "read_only": payload["read_only"],
        "source": payload["source"],
        "time_basis": payload["time_basis"],
        "evidence_type": payload["evidence_type"],
        "equipment_id": payload["equipment_id"],
        "display_name": payload["display_name"],
        "task_uid": payload["task_uid"],
        "completion_time": payload["completion_time"],
        "spatial_quality": payload["quality_evidence"],
    }


def _completion_events(
    context: Any,
    operations: list[str],
) -> list[tuple[str, Mapping[str, Any]]]:
    events: list[tuple[str, Mapping[str, Any]]] = []
    for operation in operations:
        process_env = getattr(context.env, f"env_{operation}", None)
        for event in list(getattr(process_env, "event_log", []) or []):
            if not isinstance(event, Mapping):
                continue
            if str(event.get("event_type", "")).lower() != "task_completed":
                continue
            events.append((operation, event))
    return sorted(
        events,
        key=lambda row: int(row[1].get("timestamp", 0) or 0),
        reverse=True,
    )


def _event_evidence(
    operation: str,
    event: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    common = [
        row
        for row in list(event.get("quality_evidence") or [])
        if isinstance(row, Mapping)
    ]
    if common:
        return common
    if operation == "A":
        return [
            row
            for row in list(event.get("spatial_quality_maps") or [])
            if isinstance(row, Mapping)
        ]
    return []


def _normalize_event_evidence(
    operation: str,
    event: Mapping[str, Any],
    raw_evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if "operation_id" in raw_evidence:
        return normalize_quality_evidence(raw_evidence)
    if operation != "A":
        raise ValueError("INVALID_QUALITY_EVIDENCE:LEGACY_OPERATION")

    evidence = dict(raw_evidence)
    summary = dict(evidence.get("summary") or {})
    model = dict(evidence.get("model") or {})
    evidence.update(
        {
            "operation_id": "A",
            "quality_kind": "PROCESS_A_SPATIAL_QUALITY",
            "evidence_type": model.get(
                "evidence_type",
                "SIMULATED_SPATIAL_QUALITY",
            ),
            "equipment_id": str(
                evidence.get("equipment_id")
                or event.get("machine_id")
                or ""
            ),
            "task_uid": _task_uid(evidence.get("task_uid")),
            "completion_time": int(
                evidence.get(
                    "completion_time",
                    event.get("timestamp", 0),
                )
                or 0
            ),
            "scalar_verdict": (
                "PASS" if summary.get("scalar_passed") else "FAIL"
            ),
            "map_verdict": "PASS" if summary.get("map_passed") else "RISK",
        }
    )
    return normalize_quality_evidence(evidence)


def _operation_id(value: Any) -> str | None:
    if value is None:
        return None
    operation = str(value).strip().upper()
    return operation or None


def _normalize_task_uid(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_QUALITY_EVIDENCE_TASK_UID") from exc


def _task_uid(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
