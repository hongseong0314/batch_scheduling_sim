# -*- coding: utf-8 -*-
"""Decision and policy evaluation payloads for production-transition review."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Optional

from src.mes.action_proposals import (
    action_proposal_workflow_payload,
    action_proposals_payload,
)
from src.mes.runtime.ai_dev import policy_stack_payload
from src.mes.runtime.candidate_portfolio import candidate_portfolio


def decision_dataset_payload(
    context: Any,
    limit: int = 200,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_run_id = _resolve_run_id(context, run_id)
    rows = []
    snapshots = [
        snapshot
        for snapshot in context.harness.store.feature_snapshots(run_id=resolved_run_id)
        if snapshot.layer_id == "PORTFOLIO"
    ]
    for snapshot in reversed(snapshots):
        if len(rows) >= limit:
            break
        rows.append(_decision_dataset_row(context, snapshot))
    rows = list(reversed(rows))
    return {
        "run_id": resolved_run_id,
        "count": len(rows),
        "items": rows,
    }


def policy_evaluation_summary_payload(
    context: Any,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_run_id = _resolve_run_id(context, run_id)
    dataset = decision_dataset_payload(context, limit=1000, run_id=resolved_run_id)
    rows = dataset["items"]
    validation_counts = Counter(row.get("validation_status", "PENDING") for row in rows)
    workflow_counts = Counter(
        row.get("workflow", {}).get("current_status", "UNKNOWN")
        for row in rows
        if row.get("action_proposal")
    )
    selected_stage_counts = Counter(
        row.get("selected_stage") or "-"
        for row in rows
    )
    proposal_rows = [row for row in rows if row.get("action_proposal")]
    learning_ready = [
        row for row in rows
        if row.get("learning_label", {}).get("usable_for_policy_evaluation")
    ]
    experiments = list(getattr(context, "experiment_results", {}).values())
    return {
        "run_id": resolved_run_id,
        "decision_count": len(rows),
        "proposal_count": len(proposal_rows),
        "learning_ready_count": len(learning_ready),
        "policy_stack": policy_stack_payload(context),
        "validation_status_counts": dict(validation_counts),
        "workflow_status_counts": dict(workflow_counts),
        "selected_stage_counts": dict(selected_stage_counts),
        "experiment_count": len(experiments),
        "latest_experiment_id": experiments[-1]["experiment_id"] if experiments else None,
    }


def _decision_dataset_row(context: Any, snapshot: Any) -> Dict[str, Any]:
    correlation_id = snapshot.correlation_id
    run_id = snapshot.run_id
    portfolio = candidate_portfolio(context, correlation_id, run_id=run_id)
    summary = dict(portfolio.get("summary") or {})
    selected_candidate = next(
        (item for item in portfolio.get("items", []) if item.get("selected")),
        None,
    )
    proposal = _proposal_for_correlation(context, correlation_id, run_id=run_id)
    workflow = (
        action_proposal_workflow_payload(
            context,
            proposal["proposal_id"],
            run_id=proposal.get("run_id"),
        )
        if proposal
        else {
            "workflow": {
                "current_status": "NO_ACTION_PROPOSAL",
                "safe_to_submit_to_legacy": False,
            },
            "summary": {},
        }
    )
    validations = context.harness.store.validations(correlation_id, run_id=run_id)
    commands = context.harness.store.commands(correlation_id, run_id=run_id)
    validation_status = validations[-1].validation_status if validations else "PENDING"
    command = commands[-1].to_dict() if commands else None
    workflow_summary = dict(workflow.get("summary") or {})
    return {
        "correlation_id": correlation_id,
        "run_id": run_id,
        "time": snapshot.decision_state.get("time"),
        "state_source": snapshot.decision_state.get("state_source", "SIMULATOR"),
        "objective_id": summary.get("objective_id"),
        "selected_stage": (selected_candidate or {}).get("stage"),
        "selected_candidate_id": summary.get("selected_candidate_id"),
        "selected_candidate": selected_candidate,
        "candidate_count": portfolio.get("count", 0),
        "portfolio_summary": summary,
        "policy_stack": {
            "l1_policy_id": summary.get("l1_policy_id") or "L1_FIFO_BASELINE",
            "l2_policy_id": "L2_RULE_BASED_APC",
            "l3_policy_id": summary.get("l3_policy_id"),
            "l4_policy_id": summary.get("l4_policy_id"),
        },
        "validation_status": validation_status,
        "command_id": (command or {}).get("command_id"),
        "command_status": (command or {}).get("status", "NONE"),
        "action_proposal": proposal,
        "workflow": workflow.get("workflow", {}),
        "learning_label": {
            "has_legacy_decision": workflow_summary.get("legacy_decision_count", 0) > 0,
            "has_outcome": workflow_summary.get("outcome_count", 0) > 0,
            "usable_for_policy_evaluation": (
                workflow_summary.get("legacy_decision_count", 0) > 0
                and workflow_summary.get("outcome_count", 0) > 0
            ),
            "latest_review_status": workflow_summary.get("latest_review_status", ""),
            "latest_legacy_status": workflow_summary.get("latest_legacy_status", ""),
            "latest_outcome_status": workflow_summary.get("latest_outcome_status", ""),
        },
    }


def _proposal_for_correlation(
    context: Any,
    correlation_id: str,
    run_id: Optional[str],
) -> Dict[str, Any]:
    payload = action_proposals_payload(
        context,
        correlation_id=correlation_id,
        run_id=run_id,
    )
    items = payload.get("items", []) or []
    return dict(items[-1]) if items else {}


def _resolve_run_id(context: Any, run_id: Optional[str]) -> str:
    return str(
        run_id
        or getattr(context, "run_id", "")
        or context.harness.store.current_run_id
    )
