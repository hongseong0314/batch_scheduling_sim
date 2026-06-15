"""Common contracts for process-specific quality evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol


REQUIRED_QUALITY_EVIDENCE_FIELDS = (
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
)


class QualityEvidenceProvider(Protocol):
    """Generates process-specific evidence using the common envelope."""

    operation_id: str

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        """Generate normalized quality evidence."""


def normalize_quality_evidence(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and detach a JSON-compatible quality evidence payload."""
    if not isinstance(evidence, Mapping):
        raise ValueError("INVALID_QUALITY_EVIDENCE:NOT_A_MAPPING")

    for field in REQUIRED_QUALITY_EVIDENCE_FIELDS:
        if field not in evidence:
            raise ValueError(
                f"INVALID_QUALITY_EVIDENCE:MISSING_FIELD:{field}"
            )

    operation_id = str(evidence["operation_id"]).strip().upper()
    if not operation_id:
        raise ValueError("INVALID_QUALITY_EVIDENCE:EMPTY_OPERATION_ID")

    payload = dict(evidence)
    payload["operation_id"] = operation_id
    try:
        serialized = json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
        )
        return json.loads(serialized)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "INVALID_QUALITY_EVIDENCE:NON_SERIALIZABLE"
        ) from exc
