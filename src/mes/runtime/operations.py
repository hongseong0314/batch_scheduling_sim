# -*- coding: utf-8 -*-
"""Runtime payload builders for operation registry APIs."""

from __future__ import annotations

from typing import Any, Dict

from src.mes.operations.registry import build_default_operation_registry


def operations_payload(context: Any) -> Dict[str, Any]:
    registry = getattr(context, "operation_registry", None)
    if registry is None:
        registry = build_default_operation_registry(getattr(context.env, "config", {}))
    payload = registry.to_payload()
    payload["source"] = "operation_registry"
    payload["canonical_id_policy"] = "operation_id_and_equipment_id_are_stable_contract_keys"
    return payload
