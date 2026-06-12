# -*- coding: utf-8 -*-
"""Runtime payload builders for canonical digital twin reconstruction."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.mes.action_proposals import action_proposal_from_command
from src.mes.digital_twin import (
    build_canonical_decision_state,
    build_digital_twin_state,
)
from src.mes.production_data import (
    canonical_record_matches_entity,
    data_quality_diagnostics,
)
from src.mes.recommendations import make_id
from src.mes.runtime.common import normalize_target_stage


def canonical_twin_state_payload(
    context: Any,
    at_time: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_run_id = _resolved_run_id(context, run_id)
    records = context.harness.store.canonical_ingestion_records(run_id=resolved_run_id)
    state = build_digital_twin_state(records, at_time=at_time)
    diagnostics = _canonical_diagnostics(
        context,
        resolved_run_id,
        state,
        at_time=at_time,
    )
    return {
        "source": "canonical_ingestion",
        "state_source": "CANONICAL_TWIN",
        "run_id": resolved_run_id,
        "at_time": at_time,
        "record_count": len(records),
        "diagnostics": diagnostics,
        "state": state,
    }


def canonical_decision_state_payload(
    context: Any,
    at_time: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    twin_payload = canonical_twin_state_payload(context, at_time=at_time, run_id=run_id)
    decision_state = build_canonical_decision_state(twin_payload["state"])
    return {
        "source": "canonical_ingestion",
        "state_source": "CANONICAL_TWIN",
        "run_id": twin_payload["run_id"],
        "at_time": at_time,
        "record_count": twin_payload["record_count"],
        "diagnostics": twin_payload["diagnostics"],
        "decision_state": decision_state,
    }


def canonical_candidate_preview_payload(
    context: Any,
    stage: str = "AUTO",
    at_time: Optional[int] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    decision_payload = canonical_decision_state_payload(
        context,
        at_time=at_time,
        run_id=run_id,
    )
    decision_state = decision_payload["decision_state"]
    target_stage = normalize_target_stage(stage, default="AUTO")
    stages = None if target_stage == "AUTO" else [target_stage]
    raw_candidates = context.harness.service.l1_candidate_portfolio(
        decision_state,
        stages=stages,
    )
    candidates = context.harness.service.annotate_candidate_portfolio(
        decision_state,
        raw_candidates,
    )
    return {
        "source": "canonical_ingestion",
        "state_source": "CANONICAL_TWIN",
        "run_id": decision_payload["run_id"],
        "at_time": at_time,
        "stage": target_stage,
        "candidate_count": len(candidates),
        "items": candidates,
        "diagnostics": decision_payload["diagnostics"],
        "decision_state_summary": _decision_state_summary(decision_state),
    }


def run_canonical_recommendation_payload(
    context: Any,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    target_stage = normalize_target_stage(payload.get("stage"), default="AUTO")
    at_time = payload.get("at_time")
    run_id = payload.get("run_id")
    decision_payload = canonical_decision_state_payload(
        context,
        at_time=int(at_time) if at_time is not None else None,
        run_id=str(run_id) if run_id else None,
    )
    decision_state = dict(decision_payload["decision_state"])
    correlation_id = str(payload.get("correlation_id") or make_id("CORR_CANON"))
    result = context.harness.run(
        decision_state,
        target_stage=None if target_stage == "AUTO" else target_stage,
        correlation_id=correlation_id,
    )
    command = result.command
    if command is not None:
        command.validated_command.setdefault("state_source", "CANONICAL_TWIN")
        command.validated_command.setdefault(
            "production_recommendation_mode",
            "CANONICAL_TWIN_PREVIEW",
        )
        context.harness.store.add_command(command)
        proposal = action_proposal_from_command(
            command,
            legacy_submission_mode="LEGACY_MES_REVIEW",
        ).to_dict()
    else:
        proposal = None
    context.last_correlation_id = correlation_id
    return {
        "source": "canonical_ingestion",
        "state_source": "CANONICAL_TWIN",
        "run_id": decision_payload["run_id"],
        "correlation_id": correlation_id,
        "target_stage": target_stage,
        "record_count": decision_payload["record_count"],
        "diagnostics": decision_payload["diagnostics"],
        "result": {
            "passed": result.passed,
            "status": result.evaluation.status,
            "issues": list(result.evaluation.issues),
            "validation_status": result.generated.validation.validation_status,
            "validation_reasons": list(result.generated.validation.reasons),
        },
        "command": command.to_dict() if command is not None else None,
        "action_proposal": proposal,
        "recommendation_count": len(result.generated.recommendations),
        "feature_snapshot_count": len(result.generated.feature_snapshots),
    }


def canonical_genealogy_payload(
    context: Any,
    entity_type: str,
    canonical_id: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_run_id = _resolved_run_id(context, run_id)
    target_type = str(entity_type).upper()
    target_id = str(canonical_id)
    records = [
        record
        for record in context.harness.store.canonical_ingestion_records(
            run_id=resolved_run_id
        )
        if canonical_record_matches_entity(record, target_type, target_id)
    ]
    records = sorted(
        records,
        key=lambda item: (
            int(
                item.event_time
                if item.event_time is not None
                else item.ingest_time or 0
            ),
            str(item.record_id),
        ),
    )
    raw_by_id = {
        record.record_id: record
        for record in context.harness.store.raw_source_records(run_id=resolved_run_id)
    }
    raw_evidence = []
    seen_raw_ids = set()
    for record in records:
        raw_record = raw_by_id.get(record.raw_record_id)
        if raw_record is None or raw_record.record_id in seen_raw_ids:
            continue
        seen_raw_ids.add(raw_record.record_id)
        raw_evidence.append(raw_record.to_dict())
    diagnostics = _canonical_diagnostics(
        context,
        resolved_run_id,
        {
            "diagnostics": {
                "status": "EMPTY" if not records else "OK",
                "issue_count": 0,
                "issues": [],
            }
        },
    )
    if not records:
        diagnostics = {
            **diagnostics,
            "genealogy": {
                "status": "NOT_FOUND",
                "issues": [
                    {
                        "severity": "WARN",
                        "code": "CANONICAL_ENTITY_NOT_FOUND",
                        "message": "No canonical ingestion records matched the requested entity.",
                    }
                ],
            },
        }
    return {
        "found": bool(records),
        "state_source": "CANONICAL_TWIN",
        "run_id": resolved_run_id,
        "entity_type": target_type,
        "canonical_id": target_id,
        "record_count": len(records),
        "raw_evidence_count": len(raw_evidence),
        "timeline": [
            _genealogy_timeline_row(record, raw_by_id.get(record.raw_record_id))
            for record in records
        ],
        "raw_evidence": raw_evidence,
        "related_entities": _related_entities(records),
        "diagnostics": diagnostics,
    }


def _resolved_run_id(context: Any, run_id: Optional[str]) -> str:
    return str(
        run_id
        or getattr(context, "run_id", "")
        or context.harness.store.current_run_id
    )


def _decision_state_summary(decision_state: Dict[str, Any]) -> Dict[str, Any]:
    stages = {}
    for stage in ("A", "B", "C"):
        stage_state = dict(decision_state.get(stage) or {})
        stages[stage] = {
            "wait": len(stage_state.get("wait_pool_uids", []) or []),
            "rework": len(stage_state.get("rework_pool_uids", []) or []),
            "hold": len(stage_state.get("held_uids", []) or []),
            "machines": len(stage_state.get("machines", {}) or {}),
        }
    return {
        "time": decision_state.get("time", 0),
        "state_source": decision_state.get("state_source", ""),
        "task_count": len(decision_state.get("tasks", {}) or {}),
        "stages": stages,
    }


def _canonical_diagnostics(
    context: Any,
    run_id: str,
    state: Dict[str, Any],
    at_time: Optional[int] = None,
) -> Dict[str, Any]:
    registry = getattr(context, "operation_registry", None)
    operation_ids = registry.operation_ids() if registry is not None else []
    return {
        "twin": dict(state.get("diagnostics") or {}),
        "data_quality": data_quality_diagnostics(
            context.harness.store.raw_source_records(run_id=run_id),
            context.harness.store.canonical_ingestion_records(run_id=run_id),
            context.harness.store.source_key_mappings(run_id=run_id),
            operation_ids=operation_ids,
            at_time=at_time,
        ),
    }


def _genealogy_timeline_row(record: Any, raw_record: Any) -> Dict[str, Any]:
    return {
        "record_id": record.record_id,
        "raw_record_id": record.raw_record_id,
        "raw_source_key": raw_record.source_key if raw_record is not None else "",
        "entity_type": record.entity_type,
        "canonical_id": record.canonical_id,
        "event_type": record.event_type,
        "operation_id": record.operation_id,
        "equipment_id": record.equipment_id,
        "lot_id": record.lot_id,
        "unit_id": record.unit_id,
        "recipe_id": record.recipe_id,
        "event_time": record.event_time,
        "ingest_time": record.ingest_time,
        "decision_time": record.decision_time,
        "attributes": dict(record.attributes or {}),
        "measurements": dict(record.measurements or {}),
        "quality_result": dict(record.quality_result or {}),
    }


def _related_entities(records: List[Any]) -> Dict[str, List[str]]:
    related = {
        "lot_ids": set(),
        "unit_ids": set(),
        "equipment_ids": set(),
        "recipe_ids": set(),
        "operation_ids": set(),
    }
    for record in records:
        if record.lot_id:
            related["lot_ids"].add(str(record.lot_id))
        if record.unit_id:
            related["unit_ids"].add(str(record.unit_id))
        if record.equipment_id:
            related["equipment_ids"].add(str(record.equipment_id))
        if record.recipe_id:
            related["recipe_ids"].add(str(record.recipe_id))
        if record.operation_id:
            related["operation_ids"].add(str(record.operation_id))
    return {key: sorted(values) for key, values in related.items()}
