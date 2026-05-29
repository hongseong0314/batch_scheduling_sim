# -*- coding: utf-8 -*-
"""Layered A/B/C process tools for MES Agent Mode.

These tools expose the current L1/L2 decision surfaces to an LLM without
mutating simulator or MES state.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


LAYERED_PROCESS_TOOL_IDS = {
    "generate_process_a_l1_candidates": ("A", "L1"),
    "generate_process_b_l1_candidates": ("B", "L1"),
    "generate_process_c_l1_candidates": ("C", "L1"),
    "annotate_process_a_l2_apc": ("A", "L2"),
    "annotate_process_b_l2_apc": ("B", "L2"),
    "annotate_process_c_l2_pack_quality": ("C", "L2"),
}


def layered_process_tool_catalog(context: Any) -> list[Dict[str, Any]]:
    """Return LLM-callable metadata for A/B/C L1 and L2 process tools."""
    stack = context.harness.service.policy_stack
    l1_policy_id = str(stack.l1_policy_id)
    l2_policy_id = str(stack.l2_policy_id)
    return [
        _tool(
            "generate_process_a_l1_candidates",
            stage="A",
            layer="L1",
            policy_id=l1_policy_id,
            description=(
                "Generate read-only Process A L1 dispatch candidates from the current "
                "MES decision state. Returns candidate batches, equipment ids, local "
                "scores, and rule precheck information."
            ),
            schema=_l1_schema(),
        ),
        _tool(
            "generate_process_b_l1_candidates",
            stage="B",
            layer="L1",
            policy_id=l1_policy_id,
            description=(
                "Generate read-only Process B L1 cleaning candidates from the current "
                "MES decision state. Returns cleaner assignments, batch candidates, "
                "local scores, and rule precheck information."
            ),
            schema=_l1_schema(),
        ),
        _tool(
            "generate_process_c_l1_candidates",
            stage="C",
            layer="L1",
            policy_id=l1_policy_id,
            description=(
                "Generate read-only Process C L1 packing candidates from the current "
                "MES decision state. Returns pack batches, material/color grouping "
                "features, compatibility, and local scores."
            ),
            schema=_l1_schema(),
        ),
        _tool(
            "annotate_process_a_l2_apc",
            stage="A",
            layer="L2",
            policy_id=l2_policy_id,
            description=(
                "Annotate current Process A L1 candidates with read-only L2 APC "
                "recipe, predicted QA, target spec, consumable replacement, and "
                "quality risk."
            ),
            schema=_l2_schema(),
        ),
        _tool(
            "annotate_process_b_l2_apc",
            stage="B",
            layer="L2",
            policy_id=l2_policy_id,
            description=(
                "Annotate current Process B L1 candidates with read-only L2 cleaning "
                "recipe, process parameters, solution replacement flag, and quality risk."
            ),
            schema=_l2_schema(),
        ),
        _tool(
            "annotate_process_c_l2_pack_quality",
            stage="C",
            layer="L2",
            policy_id=l2_policy_id,
            description=(
                "Annotate current Process C L1 packing candidates with read-only L2 "
                "material/color compatibility, pack quality prediction, grouping "
                "risk, and quality risk."
            ),
            schema=_l2_schema(),
        ),
    ]


def run_layered_process_tool(
    context: Any,
    tool_id: str,
    arguments: Mapping[str, Any],
) -> Dict[str, Any]:
    """Execute one A/B/C layered process tool against current runtime state."""
    if tool_id not in LAYERED_PROCESS_TOOL_IDS:
        raise ValueError(f"UNKNOWN_LAYERED_PROCESS_TOOL:{tool_id}")
    stage, layer = LAYERED_PROCESS_TOOL_IDS[tool_id]
    if layer == "L1":
        return _generate_l1_candidates(context, tool_id, stage, arguments)
    return _annotate_l2_candidates(context, tool_id, stage, arguments)


def _generate_l1_candidates(
    context: Any,
    tool_id: str,
    stage: str,
    arguments: Mapping[str, Any],
) -> Dict[str, Any]:
    decision_state = context.env.get_decision_state()
    service = context.harness.service
    candidates = service.l1_candidate_portfolio(decision_state, stages=[stage])
    limited = _limit(candidates, arguments)
    return {
        "tool_id": tool_id,
        "layer": "L1",
        "operation_id": stage,
        "decision_time": int(decision_state.get("time", 0) or 0),
        "policy_id": str(service.policy_stack.l1_policy_id),
        "policy_source": _l1_policy_source(service, stage),
        "read_only": True,
        "candidate_count": len(candidates),
        "returned_count": len(limited),
        "diagnostics": _stage_diagnostics(decision_state, stage),
        "candidates": [_candidate_summary(candidate) for candidate in limited],
    }


def _annotate_l2_candidates(
    context: Any,
    tool_id: str,
    stage: str,
    arguments: Mapping[str, Any],
) -> Dict[str, Any]:
    decision_state = context.env.get_decision_state()
    service = context.harness.service
    candidates = service.l1_candidate_portfolio(decision_state, stages=[stage])
    candidate_id = str(arguments.get("candidate_id", "") or "").strip()
    if candidate_id:
        candidates = [
            candidate for candidate in candidates if str(candidate.get("candidate_id")) == candidate_id
        ]
    annotated = service.annotate_candidate_portfolio(decision_state, candidates)
    limited = _limit(annotated, arguments)
    return {
        "tool_id": tool_id,
        "layer": "L2",
        "operation_id": stage,
        "decision_time": int(decision_state.get("time", 0) or 0),
        "policy_id": str(service.policy_stack.l2_policy_id),
        "policy_source": _l2_policy_source(service, stage),
        "read_only": True,
        "candidate_count": len(candidates),
        "returned_count": len(limited),
        "diagnostics": _stage_diagnostics(decision_state, stage),
        "annotations": [_annotation_summary(candidate) for candidate in limited],
    }


def _tool(
    tool_id: str,
    stage: str,
    layer: str,
    policy_id: str,
    description: str,
    schema: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": tool_id,
        "name": tool_id,
        "stage": stage,
        "operation_id": stage,
        "layer": layer,
        "policy_id": policy_id,
        "read_only": True,
        "description": description,
        "input_schema": schema,
        "output_contract": {
            "operation_id": stage,
            "layer": layer,
            "read_only": True,
            "fields": _l1_fields() if layer == "L1" else _l2_fields(stage),
        },
    }


def _l1_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "max_candidates": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "Maximum number of candidates to return. Default is 8.",
            }
        },
    }


def _l2_schema() -> Dict[str, Any]:
    schema = _l1_schema()
    schema["properties"]["candidate_id"] = {
        "type": "string",
        "description": "Optional candidate id from the corresponding L1 tool output.",
    }
    return schema


def _l1_fields() -> list[str]:
    return [
        "candidate_id",
        "operation_id",
        "equipment_id",
        "task_uids",
        "group_key",
        "local_score",
        "local_rank",
        "features",
        "rule_precheck_status",
    ]


def _l2_fields(stage: str) -> list[str]:
    common = [
        "candidate_id",
        "operation_id",
        "equipment_id",
        "task_uids",
        "quality_risk",
        "policy_source",
    ]
    if stage == "A":
        return common + ["recipe_id", "recipe", "predicted_qa", "target_spec"]
    if stage == "B":
        return common + ["recipe_id", "recipe", "replace_solution", "predicted_risk"]
    return common + ["pack_quality_prediction", "compatibility", "pack_mode"]


def _limit(items: Iterable[Dict[str, Any]], arguments: Mapping[str, Any]) -> list[Dict[str, Any]]:
    limit = int(arguments.get("max_candidates", 8) or 8)
    limit = max(1, min(20, limit))
    return list(items)[:limit]


def _candidate_summary(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "candidate_id": candidate.get("candidate_id"),
        "operation_id": candidate.get("operation_id") or candidate.get("stage"),
        "stage": candidate.get("stage"),
        "candidate_type": candidate.get("candidate_type"),
        "equipment_id": candidate.get("equipment_id"),
        "task_uids": list(candidate.get("task_uids") or []),
        "group_key": dict(candidate.get("group_key") or {}),
        "local_score": candidate.get("local_score"),
        "local_rank": candidate.get("local_rank"),
        "features": dict(candidate.get("features") or {}),
        "reasons": list(candidate.get("reasons") or []),
        "rule_precheck_status": candidate.get("rule_precheck_status"),
        "policy_source": dict(candidate.get("policy_source") or {}),
    }


def _annotation_summary(candidate: Mapping[str, Any]) -> Dict[str, Any]:
    annotation = dict(candidate.get("l2_annotation") or {})
    return {
        **_candidate_summary(candidate),
        "l2_annotation": annotation,
        "quality_risk": annotation.get("quality_risk"),
        "recipe_id": annotation.get("recipe_id"),
        "recipe": annotation.get("recipe", []),
        "parameters": dict(annotation.get("parameters") or {}),
        "predicted_qa": annotation.get("predicted_qa"),
        "target_spec": annotation.get("target_spec"),
        "pack_quality_prediction": annotation.get("pack_quality_prediction"),
        "compatibility": annotation.get("compatibility"),
        "replace_consumable": annotation.get("replace_consumable"),
        "replace_solution": annotation.get("replace_solution"),
        "selection_reason": annotation.get("selection_reason"),
    }


def _stage_diagnostics(decision_state: Mapping[str, Any], stage: str) -> Dict[str, Any]:
    stage_state = dict(decision_state.get(stage, {}) or {})
    machines = dict(stage_state.get("machines") or {})
    wait = list(stage_state.get("wait_pool_uids") or [])
    rework = list(stage_state.get("rework_pool_uids") or [])
    incoming_key = "incoming_from_A_uids" if stage == "B" else "incoming_from_B_uids"
    incoming = list(stage_state.get(incoming_key) or []) if stage != "A" else []
    idle = [
        equipment_id
        for equipment_id, machine in machines.items()
        if str(dict(machine).get("status", "")).lower() == "idle"
    ]
    busy = [
        equipment_id
        for equipment_id, machine in machines.items()
        if str(dict(machine).get("status", "")).lower() == "busy"
    ]
    batch_sizes = {
        str(equipment_id): int(dict(machine).get("batch_size", 1) or 1)
        for equipment_id, machine in machines.items()
    }
    return {
        "queue_size": len(wait) + len(rework) + len(incoming),
        "wait_pool_size": len(wait),
        "rework_pool_size": len(rework),
        "incoming_size": len(incoming),
        "idle_equipment_ids": [str(item) for item in sorted(idle)],
        "busy_equipment_ids": [str(item) for item in sorted(busy)],
        "batch_sizes": batch_sizes,
    }


def _l1_policy_source(service: Any, stage: str) -> Dict[str, Any]:
    config = service.policy_stack.config
    key = {"A": "scheduler_A", "B": "scheduler_B", "C": "packing_C"}[stage]
    return {
        "factory": service.policy_stack.factory_name,
        "layer": "L1",
        "policy_id": str(service.policy_stack.l1_policy_id),
        "operation_policy_key": key,
        "operation_policy": str(config.get(key, "fifo")),
    }


def _l2_policy_source(service: Any, stage: str) -> Dict[str, Any]:
    config = service.policy_stack.config
    key = {"A": "tuner_A", "B": "tuner_B", "C": "packing_quality_rule"}[stage]
    return {
        "factory": service.policy_stack.factory_name,
        "layer": "L2",
        "policy_id": str(service.policy_stack.l2_policy_id),
        "operation_policy_key": key,
        "operation_policy": str(config.get(key, "rule-based")),
    }
