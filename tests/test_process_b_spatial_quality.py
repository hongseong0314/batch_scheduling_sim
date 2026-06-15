from __future__ import annotations

import pytest

from src.environment.process_b_env import ProcessB_Env
from src.environment.process_quality.process_b import (
    generate_process_b_quality_evidence,
)
from src.objects import Task


def _generate(**overrides):
    inputs = {
        "scalar_qa": 52.4,
        "spec": (40.0, 70.0),
        "recipe": [50.0, 50.0, 30.0],
        "v": 8.0,
        "b_age": 80.0,
        "task_uid": 284,
        "equipment_id": "B_0",
        "completion_time": 24,
    }
    inputs.update(overrides)
    return generate_process_b_quality_evidence(**inputs)


def test_process_b_quality_field_is_deterministic_and_preserves_scalar_mean() -> None:
    first = _generate()
    second = _generate()

    assert first == second
    assert first["operation_id"] == "B"
    assert first["quality_kind"] == "PROCESS_B_CLEANING_QUALITY"
    assert first["evidence_type"] == "SIMULATED_CLEANING_QUALITY"
    assert first["summary"]["mean"] == pytest.approx(52.4, abs=1e-6)
    assert first["model"] == {
        "model_id": "PROCESS_B_CLEANING_FIELD",
        "version": "1.0.0",
        "evidence_type": "SIMULATED_CLEANING_QUALITY",
        "seed": first["model"]["seed"],
    }


def test_process_b_quality_field_uses_common_circular_grid_contract() -> None:
    result = _generate()

    assert result["geometry"] == {
        "shape": "CIRCLE",
        "grid_size": 17,
        "coordinate_system": "NORMALIZED_CARTESIAN",
    }
    assert 180 < len(result["cells"]) < 289
    assert {cell["zone"] for cell in result["cells"]} <= {"CENTER", "EDGE"}
    assert {cell["verdict"] for cell in result["cells"]} <= {
        "PASS",
        "MARGIN",
        "OOS_LOW",
        "OOS_HIGH",
    }
    assert {
        "edge_residue_amplitude",
        "flow_direction_bias_amplitude",
        "solution_hotspot_amplitude",
        "local_noise_amplitude",
        "solution_hotspot_center",
    } <= set(result["components"])


def test_process_b_uses_strict_scalar_verdict_and_exposes_local_cleaning_risk() -> None:
    strict_boundary = _generate(
        scalar_qa=40.0,
        spec=(40.0, 70.0),
    )
    local_risk = _generate(
        scalar_qa=40.8,
        spec=(40.0, 70.0),
        v=30.0,
        b_age=500.0,
    )

    assert strict_boundary["scalar_verdict"] == "FAIL"
    assert strict_boundary["summary"]["scalar_passed"] is False
    assert local_risk["scalar_verdict"] == "PASS"
    assert local_risk["map_verdict"] == "RISK"
    assert local_risk["summary"]["map_passed"] is False
    assert local_risk["summary"]["minimum"] < 40.0
    assert local_risk["summary"]["largest_oos_cluster"] > 0
    assert "RESIDUAL_CONTAMINATION_CLUSTER" in local_risk["reason_codes"]
    assert "EDGE_CLEANING_NON_UNIFORMITY" in local_risk["reason_codes"]
    assert "SOLUTION_DEGRADATION_HOTSPOT" in local_risk["reason_codes"]


def test_process_b_quality_field_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="INVALID_CLEANING_QUALITY_SPEC"):
        _generate(spec=(70.0, 40.0))
    with pytest.raises(ValueError, match="INVALID_CLEANING_QUALITY_RECIPE"):
        _generate(recipe=[50.0, 50.0])
    with pytest.raises(ValueError, match="INVALID_CLEANING_QUALITY_GRID_SIZE"):
        _generate(grid_size=8)


def test_process_b_completion_records_common_quality_evidence_without_changing_scalar_result() -> None:
    env = ProcessB_Env(
        {
            "num_machines_B": 1,
            "process_time_B": 1,
            "batch_size_B": 1,
            "deterministic_mode": True,
        }
    )
    task = Task(
        uid=9,
        job_id="JOB",
        due_date=20,
        spec_a=(45.0, 55.0),
        spec_b=(40.0, 70.0),
    )
    env.add_tasks([task])

    env.step(
        current_time=0,
        actions={
            "B_0": {
                "task_uids": [9],
                "recipe": [50.0, 50.0, 30.0],
            }
        },
    )
    result = env.step(current_time=1)

    assert result["succeeded"] == [task]
    completion = next(
        event for event in env.event_log if event["event_type"] == "task_completed"
    )
    assert len(completion["quality_evidence"]) == 1
    evidence = completion["quality_evidence"][0]
    assert evidence["operation_id"] == "B"
    assert evidence["quality_kind"] == "PROCESS_B_CLEANING_QUALITY"
    assert evidence["equipment_id"] == "B_0"
    assert evidence["task_uid"] == 9
    assert evidence["scalar_qa"] == pytest.approx(task.realized_qa_B)
    assert evidence["scalar_verdict"] == "PASS"
    quality_history = next(
        row for row in task.history if row.get("process") == "B"
    )
    assert quality_history["quality_evidence_summary"] == evidence["summary"]
    assert quality_history["quality_evidence_model"] == evidence["model"]
