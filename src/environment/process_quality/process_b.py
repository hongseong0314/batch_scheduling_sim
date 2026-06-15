"""Deterministic residual-contamination evidence for Process B."""

from __future__ import annotations

import hashlib
import math
from collections import deque
from typing import Any, Sequence

import numpy as np

from src.environment.process_quality.contracts import (
    normalize_quality_evidence,
)


MODEL_ID = "PROCESS_B_CLEANING_FIELD"
MODEL_VERSION = "1.0.0"
EVIDENCE_TYPE = "SIMULATED_CLEANING_QUALITY"
QUALITY_KIND = "PROCESS_B_CLEANING_QUALITY"


def generate_process_b_quality_evidence(
    *,
    scalar_qa: float,
    spec: tuple[float, float],
    recipe: Sequence[float],
    v: float,
    b_age: float,
    task_uid: int,
    equipment_id: str,
    completion_time: int,
    grid_size: int = 17,
) -> dict[str, Any]:
    """Expand B scalar QA into residual-contamination/uniformity evidence."""
    low, high = _validate_inputs(spec, recipe, grid_size)
    recipe_values = [float(value) for value in recipe]
    scalar_value = float(scalar_qa)
    solution_usage = max(0.0, float(v))
    machine_age = max(0.0, float(b_age))
    seed = _stable_seed(task_uid, equipment_id, completion_time)
    rng = np.random.default_rng(seed)

    edge_residue_amplitude = min(
        3.0,
        0.004 * machine_age + 0.025 * solution_usage,
    )
    flow_direction_bias_amplitude = min(
        2.0,
        abs(recipe_values[0] - recipe_values[1]) * 0.04
        + abs((recipe_values[0] + recipe_values[1]) / 2.0 - recipe_values[2])
        * 0.015,
    )
    solution_hotspot_amplitude = min(3.5, 0.075 * solution_usage)
    local_noise_amplitude = min(0.8, 0.04 + 0.012 * solution_usage)
    flow_angle = math.atan2(
        recipe_values[1] - recipe_values[0],
        recipe_values[2] - 30.0,
    )
    if flow_direction_bias_amplitude == 0:
        flow_angle = float(rng.uniform(-math.pi, math.pi))
    hotspot_x = float(rng.uniform(-0.5, 0.5))
    hotspot_y = float(rng.uniform(-0.5, 0.5))
    hotspot_sigma = float(rng.uniform(0.18, 0.3))

    raw_cells: list[dict[str, Any]] = []
    midpoint = (grid_size - 1) / 2.0
    for row in range(grid_size):
        for column in range(grid_size):
            x = (column - midpoint) / midpoint
            y = (midpoint - row) / midpoint
            radius = math.sqrt(x * x + y * y)
            if radius > 1.0:
                continue
            edge_residue = -edge_residue_amplitude * radius**2
            flow_bias = flow_direction_bias_amplitude * (
                x * math.cos(flow_angle) + y * math.sin(flow_angle)
            )
            hotspot_distance = (x - hotspot_x) ** 2 + (y - hotspot_y) ** 2
            solution_hotspot = -solution_hotspot_amplitude * math.exp(
                -hotspot_distance / (2.0 * hotspot_sigma**2)
            )
            local_noise = float(rng.normal(0.0, local_noise_amplitude))
            raw_cells.append(
                {
                    "x": x,
                    "y": y,
                    "row": row,
                    "column": column,
                    "radius": radius,
                    "variation": (
                        edge_residue
                        + flow_bias
                        + solution_hotspot
                        + local_noise
                    ),
                }
            )

    mean_variation = sum(cell["variation"] for cell in raw_cells) / len(
        raw_cells
    )
    values = [
        round(scalar_value + cell["variation"] - mean_variation, 6)
        for cell in raw_cells
    ]
    values[0] = round(
        values[0] + scalar_value * len(values) - sum(values),
        6,
    )
    margin_threshold = max(0.1, (high - low) * 0.1)
    cells = [
        _finalize_cell(cell, value, low, high, margin_threshold)
        for cell, value in zip(raw_cells, values)
    ]
    summary = _summarize(cells, scalar_value, low, high)
    reason_codes = _reason_codes(
        summary,
        flow_direction_bias_amplitude=flow_direction_bias_amplitude,
        solution_hotspot_amplitude=solution_hotspot_amplitude,
    )
    scalar_passed = low < scalar_value < high
    return normalize_quality_evidence(
        {
            "operation_id": "B",
            "quality_kind": QUALITY_KIND,
            "evidence_type": EVIDENCE_TYPE,
            "equipment_id": str(equipment_id),
            "task_uid": int(task_uid),
            "completion_time": int(completion_time),
            "scalar_qa": scalar_value,
            "scalar_verdict": "PASS" if scalar_passed else "FAIL",
            "map_verdict": "PASS" if summary["map_passed"] else "RISK",
            "geometry": {
                "shape": "CIRCLE",
                "grid_size": grid_size,
                "coordinate_system": "NORMALIZED_CARTESIAN",
            },
            "spec": {
                "low": low,
                "high": high,
                "margin_threshold": round(margin_threshold, 6),
            },
            "cells": cells,
            "summary": summary,
            "components": {
                "edge_residue_amplitude": round(
                    edge_residue_amplitude,
                    6,
                ),
                "flow_direction_bias_amplitude": round(
                    flow_direction_bias_amplitude,
                    6,
                ),
                "solution_hotspot_amplitude": round(
                    solution_hotspot_amplitude,
                    6,
                ),
                "local_noise_amplitude": round(
                    local_noise_amplitude,
                    6,
                ),
                "solution_hotspot_center": {
                    "x": round(hotspot_x, 6),
                    "y": round(hotspot_y, 6),
                },
            },
            "reason_codes": reason_codes,
            "recipe": recipe_values,
            "machine_state": {
                "v": solution_usage,
                "b_age": machine_age,
            },
            "model": {
                "model_id": MODEL_ID,
                "version": MODEL_VERSION,
                "evidence_type": EVIDENCE_TYPE,
                "seed": seed,
            },
        }
    )


class ProcessBQualityEvidenceProvider:
    operation_id = "B"

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        return generate_process_b_quality_evidence(**kwargs)


PROCESS_B_QUALITY_PROVIDER = ProcessBQualityEvidenceProvider()


def _validate_inputs(
    spec: tuple[float, float],
    recipe: Sequence[float],
    grid_size: int,
) -> tuple[float, float]:
    try:
        low, high = float(spec[0]), float(spec[1])
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_CLEANING_QUALITY_SPEC") from exc
    if low >= high:
        raise ValueError("INVALID_CLEANING_QUALITY_SPEC")
    if len(recipe) != 3:
        raise ValueError("INVALID_CLEANING_QUALITY_RECIPE")
    try:
        [float(value) for value in recipe]
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_CLEANING_QUALITY_RECIPE") from exc
    if grid_size < 9 or grid_size > 65 or grid_size % 2 == 0:
        raise ValueError("INVALID_CLEANING_QUALITY_GRID_SIZE")
    return low, high


def _stable_seed(
    task_uid: int,
    equipment_id: str,
    completion_time: int,
) -> int:
    identity = (
        f"{MODEL_ID}:{MODEL_VERSION}:{int(task_uid)}:"
        f"{str(equipment_id)}:{int(completion_time)}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(identity).digest()[:8], "big")


def _finalize_cell(
    cell: dict[str, Any],
    value: float,
    low: float,
    high: float,
    margin_threshold: float,
) -> dict[str, Any]:
    distance_to_spec = min(value - low, high - value)
    if value < low:
        verdict = "OOS_LOW"
        margin = value - low
    elif value > high:
        verdict = "OOS_HIGH"
        margin = high - value
    elif distance_to_spec <= margin_threshold:
        verdict = "MARGIN"
        margin = distance_to_spec
    else:
        verdict = "PASS"
        margin = distance_to_spec
    return {
        "x": round(float(cell["x"]), 6),
        "y": round(float(cell["y"]), 6),
        "row": int(cell["row"]),
        "column": int(cell["column"]),
        "value": round(float(value), 6),
        "verdict": verdict,
        "margin": round(float(margin), 6),
        "zone": "EDGE" if float(cell["radius"]) >= 0.72 else "CENTER",
    }


def _summarize(
    cells: Sequence[dict[str, Any]],
    scalar_qa: float,
    low: float,
    high: float,
) -> dict[str, Any]:
    values = [float(cell["value"]) for cell in cells]
    oos_cells = [
        cell for cell in cells if str(cell["verdict"]).startswith("OOS_")
    ]
    margin_cells = [
        cell for cell in cells if cell["verdict"] == "MARGIN"
    ]
    edge_values = [
        float(cell["value"]) for cell in cells if cell["zone"] == "EDGE"
    ]
    center_values = [
        float(cell["value"]) for cell in cells if cell["zone"] == "CENTER"
    ]
    edge_mean = sum(edge_values) / len(edge_values)
    center_mean = sum(center_values) / len(center_values)
    return {
        "mean": round(sum(values) / len(values), 6),
        "std": round(float(np.std(values)), 6),
        "minimum": round(min(values), 6),
        "maximum": round(max(values), 6),
        "oos_ratio": round(len(oos_cells) / len(cells), 6),
        "margin_ratio": round(len(margin_cells) / len(cells), 6),
        "edge_mean": round(edge_mean, 6),
        "center_mean": round(center_mean, 6),
        "edge_center_delta": round(edge_mean - center_mean, 6),
        "largest_oos_cluster": _largest_oos_cluster(cells),
        "scalar_passed": low < scalar_qa < high,
        "map_passed": not oos_cells,
    }


def _largest_oos_cluster(cells: Sequence[dict[str, Any]]) -> int:
    oos_positions = {
        (int(cell["row"]), int(cell["column"]))
        for cell in cells
        if str(cell["verdict"]).startswith("OOS_")
    }
    largest = 0
    while oos_positions:
        start = oos_positions.pop()
        queue = deque([start])
        size = 0
        while queue:
            row, column = queue.popleft()
            size += 1
            for neighbor in (
                (row - 1, column),
                (row + 1, column),
                (row, column - 1),
                (row, column + 1),
            ):
                if neighbor in oos_positions:
                    oos_positions.remove(neighbor)
                    queue.append(neighbor)
        largest = max(largest, size)
    return largest


def _reason_codes(
    summary: dict[str, Any],
    *,
    flow_direction_bias_amplitude: float,
    solution_hotspot_amplitude: float,
) -> list[str]:
    reasons: list[str] = []
    if summary["largest_oos_cluster"] > 0:
        reasons.append("RESIDUAL_CONTAMINATION_CLUSTER")
    if abs(float(summary["edge_center_delta"])) >= 0.35:
        reasons.append("EDGE_CLEANING_NON_UNIFORMITY")
    if flow_direction_bias_amplitude >= 0.2:
        reasons.append("FLOW_DIRECTION_BIAS")
    if solution_hotspot_amplitude >= 0.5:
        reasons.append("SOLUTION_DEGRADATION_HOTSPOT")
    return reasons
