# -*- coding: utf-8 -*-
"""Process A APC prediction tool.

This module exposes the local process-A tuner as a read-only prediction
surface for LLM tool calling. It does not apply recipes or mutate MES state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Sequence

from src.tuners.tuners_a import RuleBasedTuner


DEFAULT_SPEC_A = (47.1, 52.9)


def predict_process_a_apc(
    arguments: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Predict process-A QA for a proposed batch, machine state, and recipe."""
    task_rows = _task_rows(arguments.get("task_rows", []))
    machine_state = dict(arguments.get("machine_state", {}) or {})
    queue_info = dict(arguments.get("queue_info", {}) or {})
    current_time = int(arguments.get("current_time", 0) or 0)

    tuner = RuleBasedTuner(dict(config or {}))
    recipe = _recipe(arguments.get("recipe"))
    if recipe is None:
        recipe = tuner.get_recipe(
            task_rows=task_rows,
            machine_state=machine_state,
            queue_info=queue_info,
            current_time=current_time,
        )

    spec_low, spec_high = _spec_window(task_rows)
    target = (spec_low + spec_high) / 2.0
    replace_consumable = tuner.should_replace_consumable(machine_state)
    current_u = float(machine_state.get("u", 0.0) or 0.0)
    current_age = float(machine_state.get("m_age", 0.0) or 0.0)
    predicted_qa = float(
        tuner._predict_qa(  # The tuner owns the simulator-backed A-process equation.
            recipe=recipe,
            current_u=current_u,
            current_age=current_age,
            replace_consumable=replace_consumable,
        )
    )
    in_spec = spec_low <= predicted_qa <= spec_high
    distance_to_target = abs(predicted_qa - target)
    nearest_limit_distance = (
        min(abs(predicted_qa - spec_low), abs(predicted_qa - spec_high))
        if not in_spec
        else min(predicted_qa - spec_low, spec_high - predicted_qa)
    )

    return {
        "tool_id": "predict_process_a_apc",
        "stage": "A",
        "model_id": "A_RULE_BASED_APC_PREDICTOR",
        "model_version": "0.1.0",
        "read_only": True,
        "recipe_id": _recipe_id(recipe),
        "recipe": [float(value) for value in recipe],
        "parameters": {
            "temp": float(recipe[0]),
            "flow": float(recipe[1]),
            "duration": float(recipe[2]),
        },
        "predicted_qa": round(predicted_qa, 4),
        "target_spec": {
            "low": float(spec_low),
            "high": float(spec_high),
            "target": float(target),
        },
        "quality_risk": "LOW" if in_spec else "HIGH",
        "replace_consumable": bool(replace_consumable),
        "explanation_factors": {
            "u": current_u,
            "m_age": current_age,
            "current_time": current_time,
            "distance_to_target": round(distance_to_target, 4),
            "nearest_spec_margin": round(nearest_limit_distance, 4),
            "wait_pool_size": int(queue_info.get("wait_pool_size", 0) or 0),
        },
        "input_echo": {
            "task_count": len(task_rows),
            "task_uids": [row.get("task_uid") for row in task_rows],
            "machine_state": machine_state,
        },
    }


def _task_rows(raw_rows: Any) -> List[Dict[str, Any]]:
    if raw_rows is None:
        return []
    if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
        raise ValueError("INVALID_TASK_ROWS")
    rows: List[Dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise ValueError("INVALID_TASK_ROW")
        rows.append(dict(raw))
    return rows


def _recipe(raw_recipe: Any) -> List[float] | None:
    if raw_recipe is None:
        return None
    if not isinstance(raw_recipe, Sequence) or isinstance(raw_recipe, (str, bytes)):
        raise ValueError("INVALID_RECIPE")
    if len(raw_recipe) != 3:
        raise ValueError("INVALID_RECIPE_LENGTH")
    return [float(value) for value in raw_recipe]


def _spec_window(task_rows: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    lows = []
    highs = []
    for row in task_rows:
        spec = row.get("spec_a")
        if not isinstance(spec, Sequence) or isinstance(spec, (str, bytes)):
            continue
        if len(spec) != 2:
            continue
        lows.append(float(spec[0]))
        highs.append(float(spec[1]))
    if not lows or not highs:
        return DEFAULT_SPEC_A
    return max(lows), min(highs)


def _recipe_id(recipe: Sequence[float]) -> str:
    key = "_".join(str(round(float(value), 3)).replace(".", "P") for value in recipe)
    return f"SIM_A_APC_{key}"
