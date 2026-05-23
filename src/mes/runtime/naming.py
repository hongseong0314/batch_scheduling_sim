# -*- coding: utf-8 -*-
"""Display-name helpers for MES processes and equipment."""

from __future__ import annotations

from typing import Any, Mapping


DEFAULT_STAGE_DISPLAY_NAMES = {
    "A": "Process QA",
    "B": "Clean QA",
    "C": "Packing",
}


def stage_display_name(context: Any, stage: str) -> str:
    """Return the configured display name for a process stage."""

    stage_key = str(stage)
    registry = getattr(context, "operation_registry", None)
    if registry is not None:
        operation = registry.find_operation(stage_key)
        if operation is not None:
            return operation.display_name
    configured = _config_mapping(context, "stage_display_names")
    return str(configured.get(stage_key) or DEFAULT_STAGE_DISPLAY_NAMES.get(stage_key) or stage_key)


def equipment_display_name(context: Any, equipment_id: str) -> str:
    """Return the configured display name for an equipment id."""

    key = str(equipment_id)
    registry = getattr(context, "operation_registry", None)
    if registry is not None:
        equipment = registry.find_equipment(key)
        if equipment is not None:
            return equipment.display_name
    configured = _config_mapping(context, "equipment_display_names")
    return str(configured.get(key) or key)


def _config_mapping(context: Any, key: str) -> Mapping[str, Any]:
    env = getattr(context, "env", None)
    config = getattr(env, "config", {}) or {}
    value = config.get(key, {})
    return value if isinstance(value, Mapping) else {}
