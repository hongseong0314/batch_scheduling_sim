# -*- coding: utf-8 -*-
"""Production-facing action proposal contract.

An ActionProposal is the AI layer's proposed manufacturing action. In a real
deployment this is submitted to a legacy MES for review/execution, not sent
directly to equipment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.mes.adapters import wafer_id_from_task_uid
from src.mes.domain import MESCommand
from src.mes.recommendations import make_id


@dataclass
class ActionProposal:
    proposal_id: str
    proposal_type: str
    correlation_id: str
    operation_id: str
    source_command_id: str
    source_command_type: str
    validation_status: str
    status: str = "PROPOSED"
    candidate_id: str = ""
    target_equipment_id: str = ""
    target_equipment_group_id: str = ""
    target_unit_ids: List[str] = field(default_factory=list)
    target_lot_ids: List[str] = field(default_factory=list)
    policy_refs: Dict[str, Any] = field(default_factory=dict)
    legacy_submission_mode: str = "SIMULATOR_ONLY"
    direct_equipment_control: bool = False
    payload: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LegacyDecision:
    proposal_id: str
    legacy_status: str
    decision_id: str = ""
    correlation_id: str = ""
    legacy_assignment_id: str = ""
    actual_equipment_id: str = ""
    actual_unit_ids: List[str] = field(default_factory=list)
    reason: str = ""
    decision_time: Optional[int] = None
    decided_by: str = "LEGACY_MES"
    payload: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OutcomeRecord:
    proposal_id: str
    outcome_status: str
    outcome_id: str = ""
    correlation_id: str = ""
    actual_equipment_id: str = ""
    actual_unit_ids: List[str] = field(default_factory=list)
    event_time: Optional[int] = None
    quality_result: Dict[str, Any] = field(default_factory=dict)
    cycle_time: Optional[float] = None
    rework_count: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    run_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def action_proposal_from_command(
    command: MESCommand,
    legacy_submission_mode: Optional[str] = None,
) -> ActionProposal:
    validated = dict(command.validated_command or {})
    operation_id = str(
        validated.get("operation_id")
        or validated.get("stage")
        or _operation_from_command(command)
    )
    task_uids = [
        int(uid)
        for uid in validated.get("task_uids", [])
        if str(uid).lstrip("-").isdigit()
    ]
    return ActionProposal(
        proposal_id=f"PROP_{command.command_id}",
        proposal_type="LEGACY_MES_ACTION_PROPOSAL",
        correlation_id=command.correlation_id,
        operation_id=operation_id,
        source_command_id=command.command_id,
        source_command_type=command.command_type,
        validation_status=command.validation_status,
        candidate_id=str(validated.get("candidate_id") or ""),
        target_equipment_id=str(validated.get("equipment_id") or ""),
        target_equipment_group_id=str(validated.get("equipment_group_id") or operation_id),
        target_unit_ids=[wafer_id_from_task_uid(uid) for uid in task_uids],
        target_lot_ids=[str(value) for value in validated.get("lot_ids", [])],
        policy_refs={
            "dispatch_recommendation_id": validated.get("dispatch_recommendation_id"),
            "recipe_recommendation_id": validated.get("recipe_recommendation_id"),
        },
        legacy_submission_mode=str(legacy_submission_mode or "SIMULATOR_ONLY"),
        direct_equipment_control=False,
        payload=validated,
        run_id=command.run_id,
    )


def action_proposals_payload(
    context: Any,
    correlation_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    commands = context.harness.store.commands(correlation_id=correlation_id, run_id=run_id)
    proposals = []
    for command in commands:
        if command.validation_status != "PASSED":
            continue
        proposal = _proposal_with_registry_mode(context, command)
        item = proposal.to_dict()
        item["lifecycle"] = action_proposal_lifecycle_summary(
            context.harness.store,
            proposal.proposal_id,
            run_id=proposal.run_id,
        )
        proposals.append(item)
    return {
        "count": len(proposals),
        "correlation_id": correlation_id,
        "run_id": run_id,
        "items": proposals,
    }


def legacy_decision_from_payload(
    proposal_id: str,
    payload: Dict[str, Any],
    default_run_id: str = "",
) -> LegacyDecision:
    return LegacyDecision(
        proposal_id=str(proposal_id),
        legacy_status=str(payload.get("legacy_status") or "SUBMITTED"),
        decision_id=str(payload.get("decision_id") or make_id("LDEC")),
        correlation_id=str(payload.get("correlation_id") or ""),
        legacy_assignment_id=str(payload.get("legacy_assignment_id") or ""),
        actual_equipment_id=str(payload.get("actual_equipment_id") or ""),
        actual_unit_ids=_string_list(payload.get("actual_unit_ids")),
        reason=str(payload.get("reason") or ""),
        decision_time=_optional_int(payload.get("decision_time")),
        decided_by=str(payload.get("decided_by") or "LEGACY_MES"),
        payload=dict(payload.get("payload") or {}),
        run_id=str(payload.get("run_id") or default_run_id or ""),
    )


def outcome_record_from_payload(
    proposal_id: str,
    payload: Dict[str, Any],
    default_run_id: str = "",
) -> OutcomeRecord:
    return OutcomeRecord(
        proposal_id=str(proposal_id),
        outcome_status=str(payload.get("outcome_status") or "OBSERVED"),
        outcome_id=str(payload.get("outcome_id") or make_id("OUT")),
        correlation_id=str(payload.get("correlation_id") or ""),
        actual_equipment_id=str(payload.get("actual_equipment_id") or ""),
        actual_unit_ids=_string_list(payload.get("actual_unit_ids")),
        event_time=_optional_int(payload.get("event_time")),
        quality_result=dict(payload.get("quality_result") or {}),
        cycle_time=_optional_float(payload.get("cycle_time")),
        rework_count=int(payload.get("rework_count") or 0),
        payload=dict(payload.get("payload") or {}),
        run_id=str(payload.get("run_id") or default_run_id or ""),
    )


def action_proposal_lifecycle_summary(
    store: Any,
    proposal_id: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    decisions = _store_records(store, "legacy_decisions", proposal_id, run_id=run_id)
    outcomes = _store_records(store, "outcome_records", proposal_id, run_id=run_id)
    latest_decision = decisions[-1] if decisions else None
    latest_outcome = outcomes[-1] if outcomes else None
    return {
        "legacy_decision_count": len(decisions),
        "outcome_count": len(outcomes),
        "latest_legacy_status": getattr(latest_decision, "legacy_status", ""),
        "latest_outcome_status": getattr(latest_outcome, "outcome_status", ""),
        "latest_legacy_decision_id": getattr(latest_decision, "decision_id", ""),
        "latest_outcome_id": getattr(latest_outcome, "outcome_id", ""),
    }


def action_proposal_lifecycle_payload(
    context: Any,
    proposal_id: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    store = context.harness.store
    decisions = _store_records(store, "legacy_decisions", proposal_id, run_id=run_id)
    outcomes = _store_records(store, "outcome_records", proposal_id, run_id=run_id)
    return {
        "proposal_id": proposal_id,
        "run_id": run_id,
        "summary": action_proposal_lifecycle_summary(
            store,
            proposal_id,
            run_id=run_id,
        ),
        "legacy_decisions": [decision.to_dict() for decision in decisions],
        "outcomes": [outcome.to_dict() for outcome in outcomes],
    }


def _proposal_with_registry_mode(context: Any, command: MESCommand) -> ActionProposal:
    mode = "SIMULATOR_ONLY"
    registry = getattr(context, "operation_registry", None)
    validated = dict(command.validated_command or {})
    operation_id = str(
        validated.get("operation_id")
        or validated.get("stage")
        or _operation_from_command(command)
    )
    if registry is not None:
        operation = registry.find_operation(operation_id)
        if operation is not None:
            mode = operation.legacy_submission_mode
    return action_proposal_from_command(command, legacy_submission_mode=mode)


def _operation_from_command(command: MESCommand) -> str:
    equipment_id = str((command.validated_command or {}).get("equipment_id") or "")
    return equipment_id.split("_", 1)[0].upper() if equipment_id else ""


def _store_records(
    store: Any,
    method_name: str,
    proposal_id: str,
    run_id: Optional[str] = None,
) -> List[Any]:
    method = getattr(store, method_name, None)
    if method is None:
        return []
    return method(proposal_id, run_id=run_id)


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _optional_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _optional_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    return float(value)
