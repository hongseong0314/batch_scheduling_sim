# -*- coding: utf-8 -*-
"""Runtime payload builders for canonical digital twin reconstruction."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.action_proposals import action_proposal_from_command
from src.mes.digital_twin import (
    build_canonical_decision_state,
    build_digital_twin_state,
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
    return {
        "source": "canonical_ingestion",
        "state_source": "CANONICAL_TWIN",
        "run_id": resolved_run_id,
        "at_time": at_time,
        "record_count": len(records),
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
        command.validated_command.setdefault("production_recommendation_mode", "CANONICAL_TWIN_PREVIEW")
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


def _resolved_run_id(context: Any, run_id: Optional[str]) -> str:
    return str(run_id or getattr(context, "run_id", "") or context.harness.store.current_run_id)


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
