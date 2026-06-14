"""Deterministic synthetic spatial quality field for Process A."""

from __future__ import annotations

import hashlib
import math
from collections import deque
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np


MODEL_ID = "PROCESS_A_SPATIAL_FIELD"
MODEL_VERSION = "1.0.0"
EVIDENCE_TYPE = "SIMULATED_SPATIAL_QUALITY"


def generate_process_a_spatial_quality(
    *,
    scalar_qa: float,
    spec: Tuple[float, float],
    recipe: Sequence[float],
    u: float,
    m_age: float,
    task_uid: int,
    equipment_id: str,
    completion_time: int,
    grid_size: int = 17,
) -> Dict[str, Any]:
    """Expand scalar Process-A QA into a reproducible circular spatial field."""
    low, high = _validate_inputs(spec, recipe, grid_size)
    recipe_values = [float(value) for value in recipe]
    scalar_value = float(scalar_qa)
    usage = max(0.0, float(u))
    machine_age = max(0.0, float(m_age))
    seed = _stable_seed(task_uid, equipment_id, completion_time)
    rng = np.random.default_rng(seed)

    radial_amplitude = min(2.5, 0.0045 * machine_age)
    directional_amplitude = min(
        2.0,
        abs(recipe_values[0] - 10.0) * 0.05
        + abs(recipe_values[1] - 2.0) * 0.08
        + abs(recipe_values[2] - 1.0) * 0.12,
    )
    hotspot_amplitude = min(3.0, 0.08 * usage)
    noise_amplitude = min(0.8, 0.04 + 0.018 * usage)
    recipe_angle = math.atan2(
        recipe_values[2] - 1.0,
        (recipe_values[0] - 10.0) + (recipe_values[1] - 2.0) * 0.5,
    )
    if directional_amplitude == 0:
        recipe_angle = rng.uniform(-math.pi, math.pi)
    hotspot_x = float(rng.uniform(-0.45, 0.45))
    hotspot_y = float(rng.uniform(-0.45, 0.45))
    hotspot_sigma = float(rng.uniform(0.16, 0.28))

    raw_cells: List[Dict[str, Any]] = []
    midpoint = (grid_size - 1) / 2.0
    for row in range(grid_size):
        for column in range(grid_size):
            x = (column - midpoint) / midpoint
            y = (midpoint - row) / midpoint
            radius = math.sqrt(x * x + y * y)
            if radius > 1.0:
                continue
            radial = -radial_amplitude * radius * radius
            directional = directional_amplitude * (
                x * math.cos(recipe_angle) + y * math.sin(recipe_angle)
            )
            hotspot_distance = (x - hotspot_x) ** 2 + (y - hotspot_y) ** 2
            hotspot = -hotspot_amplitude * math.exp(
                -hotspot_distance / (2.0 * hotspot_sigma**2)
            )
            local_noise = float(rng.normal(0.0, noise_amplitude))
            raw_cells.append(
                {
                    "x": x,
                    "y": y,
                    "row": row,
                    "column": column,
                    "radius": radius,
                    "variation": radial + directional + hotspot + local_noise,
                }
            )

    mean_variation = sum(cell["variation"] for cell in raw_cells) / len(raw_cells)
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
        directional_amplitude=directional_amplitude,
        hotspot_amplitude=hotspot_amplitude,
    )
    return {
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
        "scalar_qa": scalar_value,
        "cells": cells,
        "summary": summary,
        "components": {
            "radial_amplitude": round(radial_amplitude, 6),
            "directional_amplitude": round(directional_amplitude, 6),
            "hotspot_amplitude": round(hotspot_amplitude, 6),
            "noise_amplitude": round(noise_amplitude, 6),
            "hotspot_center": {
                "x": round(hotspot_x, 6),
                "y": round(hotspot_y, 6),
            },
        },
        "reason_codes": reason_codes,
        "model": {
            "model_id": MODEL_ID,
            "version": MODEL_VERSION,
            "evidence_type": EVIDENCE_TYPE,
            "seed": seed,
        },
    }


def _validate_inputs(
    spec: Tuple[float, float],
    recipe: Sequence[float],
    grid_size: int,
) -> tuple[float, float]:
    try:
        low, high = float(spec[0]), float(spec[1])
    except (IndexError, TypeError, ValueError) as exc:
        raise ValueError("INVALID_SPATIAL_SPEC") from exc
    if low >= high:
        raise ValueError("INVALID_SPATIAL_SPEC")
    if len(recipe) != 3:
        raise ValueError("INVALID_SPATIAL_RECIPE")
    try:
        [float(value) for value in recipe]
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_SPATIAL_RECIPE") from exc
    if grid_size < 9 or grid_size > 65 or grid_size % 2 == 0:
        raise ValueError("INVALID_SPATIAL_GRID_SIZE")
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
    cell: Dict[str, Any],
    value: float,
    low: float,
    high: float,
    margin_threshold: float,
) -> Dict[str, Any]:
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
    cells: Sequence[Dict[str, Any]],
    scalar_qa: float,
    low: float,
    high: float,
) -> Dict[str, Any]:
    values = [float(cell["value"]) for cell in cells]
    oos_cells = [
        cell for cell in cells if str(cell["verdict"]).startswith("OOS_")
    ]
    margin_cells = [cell for cell in cells if cell["verdict"] == "MARGIN"]
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
        "scalar_passed": low <= scalar_qa <= high,
        "map_passed": not oos_cells,
    }


def _largest_oos_cluster(cells: Sequence[Dict[str, Any]]) -> int:
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
    summary: Dict[str, Any],
    *,
    directional_amplitude: float,
    hotspot_amplitude: float,
) -> List[str]:
    reasons: List[str] = []
    if summary["largest_oos_cluster"] > 0:
        reasons.append("LOCAL_OOS_CLUSTER")
    if abs(float(summary["edge_center_delta"])) >= 0.35:
        reasons.append("EDGE_NON_UNIFORMITY")
    if directional_amplitude >= 0.2:
        reasons.append("DIRECTIONAL_BIAS")
    if hotspot_amplitude >= 0.5:
        reasons.append("CONSUMABLE_HOTSPOT")
    return reasons
