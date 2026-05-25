# -*- coding: utf-8 -*-
"""Runtime payload builders for canonical digital twin reconstruction."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.digital_twin import (
    build_canonical_decision_state,
    build_digital_twin_state,
)
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
