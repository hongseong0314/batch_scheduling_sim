"""Process A quality evidence provider."""

from __future__ import annotations

from typing import Any, Sequence

from src.environment.process_a_spatial_quality import (
    generate_process_a_spatial_quality,
)
from src.environment.process_quality.contracts import (
    normalize_quality_evidence,
)


QUALITY_KIND = "PROCESS_A_SPATIAL_QUALITY"


def generate_process_a_quality_evidence(
    *,
    scalar_qa: float,
    spec: tuple[float, float],
    recipe: Sequence[float],
    u: float,
    m_age: float,
    task_uid: int,
    equipment_id: str,
    completion_time: int,
    grid_size: int = 17,
) -> dict[str, Any]:
    """Wrap the existing A spatial model in the common evidence envelope."""
    spatial_quality = generate_process_a_spatial_quality(
        scalar_qa=scalar_qa,
        spec=spec,
        recipe=recipe,
        u=u,
        m_age=m_age,
        task_uid=task_uid,
        equipment_id=equipment_id,
        completion_time=completion_time,
        grid_size=grid_size,
    )
    low = float(spatial_quality["spec"]["low"])
    high = float(spatial_quality["spec"]["high"])
    scalar_value = float(spatial_quality["scalar_qa"])
    return normalize_quality_evidence(
        {
            "operation_id": "A",
            "quality_kind": QUALITY_KIND,
            "evidence_type": spatial_quality["model"]["evidence_type"],
            "equipment_id": str(equipment_id),
            "task_uid": int(task_uid),
            "completion_time": int(completion_time),
            "scalar_verdict": (
                "PASS" if low <= scalar_value <= high else "FAIL"
            ),
            "map_verdict": (
                "PASS"
                if spatial_quality["summary"]["map_passed"]
                else "RISK"
            ),
            "recipe": [float(value) for value in recipe],
            "machine_state": {
                "u": float(u),
                "m_age": float(m_age),
            },
            **spatial_quality,
        }
    )


class ProcessAQualityEvidenceProvider:
    operation_id = "A"

    def generate(self, **kwargs: Any) -> dict[str, Any]:
        return generate_process_a_quality_evidence(**kwargs)


PROCESS_A_QUALITY_PROVIDER = ProcessAQualityEvidenceProvider()
