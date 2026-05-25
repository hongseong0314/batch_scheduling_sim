# -*- coding: utf-8 -*-
"""Runtime configuration loading for the simulator-backed MES app."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping

from src.mes.agent_runtime.config import _parse_yaml_subset


DEFAULT_RUNTIME_CONFIG_PATH = Path("config/mes-runtime.yaml")
STAGES = ("A", "B", "C")


def default_runtime_config() -> Dict[str, Any]:
    """Return the built-in simulator config used when no runtime file exists."""

    return {
        "num_machines_A": 5,
        "num_machines_B": 3,
        "num_machines_C": 3,
        "batch_size_A": 3,
        "batch_size_B": 2,
        "batch_size_C": 4,
        "max_packs_per_step": 3,
        "process_time_A": 20,
        "process_time_B": 8,
        "process_time_C": 2,
        "deterministic_mode": True,
        "stage_display_names": {
            "A": "Lithography QA",
            "B": "Wet Clean QA",
            "C": "Final Packing",
        },
        "equipment_display_names": {
            "A_0": "LITHO-01",
            "A_1": "LITHO-02",
            "A_2": "LITHO-03",
            "A_3": "LITHO-04",
            "A_4": "LITHO-05",
            "B_0": "CLEAN-01",
            "B_1": "CLEAN-02",
            "B_2": "CLEAN-03",
            "C_0": "PACK-01",
            "C_1": "PACK-02",
            "C_2": "PACK-03",
        },
    }


def runtime_config_path() -> Path:
    return Path(os.environ.get("MES_RUNTIME_CONFIG", str(DEFAULT_RUNTIME_CONFIG_PATH)))


def load_runtime_config(path: str | Path | None = None) -> Dict[str, Any]:
    """Load runtime config from YAML/JSON and normalize it for ManufacturingEnv."""

    config_path = Path(path) if path is not None else runtime_config_path()
    base = default_runtime_config()
    if not config_path.exists():
        return base
    data = _read_config(config_path)
    return normalize_runtime_config(data, base=base)


def normalize_runtime_config(
    data: Mapping[str, Any],
    base: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Normalize friendly nested runtime config into the existing flat env keys."""

    config = dict(base or default_runtime_config())
    simulator = _mapping(data.get("simulator"))
    display = _mapping(data.get("display"))

    for stage in STAGES:
        stage_values = {
            "num_machines": simulator.get("num_machines"),
            "batch_size": simulator.get("batch_size"),
            "process_time": simulator.get("process_time"),
        }
        for prefix, values in stage_values.items():
            value = _mapping(values).get(stage)
            if value is not None:
                config[f"{prefix}_{stage}"] = int(value)

    for key in ("max_packs_per_step", "deterministic_mode"):
        if key in simulator:
            config[key] = simulator[key]
        if key in data:
            config[key] = data[key]

    stage_names = _mapping(display.get("stages"))
    equipment_names = _mapping(display.get("equipment"))
    if stage_names:
        config["stage_display_names"] = {
            str(key): str(value) for key, value in stage_names.items()
        }
    if equipment_names:
        config["equipment_display_names"] = {
            str(key): str(value) for key, value in equipment_names.items()
        }

    for key in (
        "stage_display_names",
        "equipment_display_names",
        "operations",
        "equipment",
    ):
        if key in data:
            config[key] = data[key]

    for stage in STAGES:
        for prefix in ("num_machines", "batch_size", "process_time"):
            key = f"{prefix}_{stage}"
            if key in data:
                config[key] = int(data[key])
    return config


def _read_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        payload = json.loads(text)
    else:
        payload = _parse_yaml_subset(text)
    if not isinstance(payload, Mapping):
        raise ValueError(f"runtime config must be a mapping: {path}")
    return dict(payload)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}
