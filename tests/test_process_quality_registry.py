from __future__ import annotations

import json
from typing import Any

import pytest

from src.environment.process_quality import QUALITY_PROVIDER_REGISTRY
from src.environment.process_quality.contracts import normalize_quality_evidence
from src.environment.process_quality.registry import QualityProviderRegistry


class _FakeProvider:
    def __init__(self, operation_id: str) -> None:
        self.operation_id = operation_id

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        return {"operation_id": self.operation_id, **kwargs}


def _evidence(**overrides: Any) -> dict[str, Any]:
    evidence = {
        "operation_id": "A",
        "quality_kind": "PROCESS_A_SPATIAL_QUALITY",
        "evidence_type": "SIMULATED_SPATIAL_QUALITY",
        "equipment_id": "A_0",
        "task_uid": 7,
        "completion_time": 20,
        "scalar_qa": 49.2,
        "scalar_verdict": "PASS",
        "map_verdict": "RISK",
        "geometry": {
            "shape": "CIRCLE",
            "grid_size": 17,
            "coordinate_system": "NORMALIZED_CARTESIAN",
        },
        "spec": {"low": 45.0, "high": 55.0},
        "cells": [
            {
                "x": 0.0,
                "y": 0.0,
                "row": 8,
                "column": 8,
                "value": 49.2,
                "verdict": "PASS",
                "margin": 4.2,
                "zone": "CENTER",
            }
        ],
        "summary": {
            "mean": 49.2,
            "scalar_passed": True,
            "map_passed": False,
        },
        "components": {"radial_amplitude": 0.4},
        "reason_codes": ["LOCAL_OOS_CLUSTER"],
        "model": {
            "model_id": "PROCESS_A_SPATIAL_FIELD",
            "version": "1.0.0",
            "evidence_type": "SIMULATED_SPATIAL_QUALITY",
        },
    }
    evidence.update(overrides)
    return evidence


def test_registry_resolves_registered_process_quality_providers() -> None:
    registry = QualityProviderRegistry()
    provider_a = _FakeProvider("A")
    provider_b = _FakeProvider("B")

    registry.register("a", provider_a)
    registry.register("B", provider_b)

    assert registry.get("A") is provider_a
    assert registry.get("b") is provider_b
    assert registry.operations() == ["A", "B"]


def test_default_registry_exposes_process_a_and_b_providers() -> None:
    assert QUALITY_PROVIDER_REGISTRY.operations() == ["A", "B"]
    assert QUALITY_PROVIDER_REGISTRY.get("A").operation_id == "A"
    assert QUALITY_PROVIDER_REGISTRY.get("B").operation_id == "B"


def test_registry_rejects_unknown_and_conflicting_providers() -> None:
    registry = QualityProviderRegistry()
    registry.register("A", _FakeProvider("A"))

    with pytest.raises(KeyError, match="UNKNOWN_QUALITY_PROVIDER:C"):
        registry.get("C")
    with pytest.raises(ValueError, match="QUALITY_PROVIDER_ALREADY_REGISTERED:A"):
        registry.register("A", _FakeProvider("A"))
    with pytest.raises(ValueError, match="QUALITY_PROVIDER_OPERATION_MISMATCH:A:B"):
        registry.register("A", _FakeProvider("B"))


def test_normalize_quality_evidence_returns_detached_data_only_contract() -> None:
    source = _evidence()

    normalized = normalize_quality_evidence(source)

    assert normalized == source
    assert normalized is not source
    assert normalized["cells"] is not source["cells"]
    assert json.loads(json.dumps(normalized)) == normalized


@pytest.mark.parametrize(
    "field",
    [
        "operation_id",
        "quality_kind",
        "evidence_type",
        "equipment_id",
        "task_uid",
        "completion_time",
        "scalar_qa",
        "scalar_verdict",
        "map_verdict",
        "geometry",
        "spec",
        "cells",
        "summary",
        "components",
        "reason_codes",
        "model",
    ],
)
def test_normalize_quality_evidence_requires_contract_fields(field: str) -> None:
    evidence = _evidence()
    evidence.pop(field)

    with pytest.raises(
        ValueError,
        match=f"INVALID_QUALITY_EVIDENCE:MISSING_FIELD:{field}",
    ):
        normalize_quality_evidence(evidence)


def test_normalize_quality_evidence_rejects_non_data_values() -> None:
    with pytest.raises(
        ValueError,
        match="INVALID_QUALITY_EVIDENCE:NON_SERIALIZABLE",
    ):
        normalize_quality_evidence(
            _evidence(components={"callback": lambda: None})
        )
