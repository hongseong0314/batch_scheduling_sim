import pytest

from src.environment.process_a_env import ProcessA_Env
from src.environment.process_a_spatial_quality import (
    generate_process_a_spatial_quality,
)
from src.objects import Task


def _generate(**overrides):
    inputs = {
        "scalar_qa": 49.2,
        "spec": (45.0, 55.0),
        "recipe": [10.0, 2.0, 1.0],
        "u": 8.0,
        "m_age": 80.0,
        "task_uid": 184,
        "equipment_id": "A_0",
        "completion_time": 20,
    }
    inputs.update(overrides)
    return generate_process_a_spatial_quality(**inputs)


def test_spatial_map_is_deterministic_and_preserves_scalar_mean() -> None:
    first = _generate()
    second = _generate()

    assert first == second
    assert first["summary"]["mean"] == pytest.approx(49.2, abs=1e-6)
    assert first["model"] == {
        "model_id": "PROCESS_A_SPATIAL_FIELD",
        "version": "1.0.0",
        "evidence_type": "SIMULATED_SPATIAL_QUALITY",
        "seed": first["model"]["seed"],
    }


def test_spatial_map_uses_circular_canonical_grid_and_position_verdicts() -> None:
    result = _generate()

    assert result["geometry"] == {
        "shape": "CIRCLE",
        "grid_size": 17,
        "coordinate_system": "NORMALIZED_CARTESIAN",
    }
    assert 180 < len(result["cells"]) < 289
    assert all(-1.0 <= cell["x"] <= 1.0 for cell in result["cells"])
    assert all(-1.0 <= cell["y"] <= 1.0 for cell in result["cells"])
    assert {
        "x",
        "y",
        "row",
        "column",
        "value",
        "verdict",
        "margin",
        "zone",
    } <= set(result["cells"][0])
    assert {cell["verdict"] for cell in result["cells"]} <= {
        "PASS",
        "MARGIN",
        "OOS_LOW",
        "OOS_HIGH",
    }
    assert {cell["zone"] for cell in result["cells"]} <= {"CENTER", "EDGE"}


def test_spatial_summary_exposes_local_risk_separately_from_scalar_verdict() -> None:
    result = _generate(
        scalar_qa=45.3,
        spec=(45.0, 55.0),
        u=20.0,
        m_age=200.0,
    )
    summary = result["summary"]

    assert summary["scalar_passed"] is True
    assert summary["map_passed"] is False
    assert summary["oos_ratio"] > 0
    assert summary["largest_oos_cluster"] > 0
    assert summary["minimum"] < 45.0
    assert "LOCAL_OOS_CLUSTER" in result["reason_codes"]
    assert result["components"]["hotspot_amplitude"] > 0
    assert result["components"]["radial_amplitude"] > 0


def test_spatial_map_rejects_invalid_spec_recipe_and_grid_size() -> None:
    with pytest.raises(ValueError, match="INVALID_SPATIAL_SPEC"):
        _generate(spec=(55.0, 45.0))
    with pytest.raises(ValueError, match="INVALID_SPATIAL_RECIPE"):
        _generate(recipe=[10.0, 2.0])
    with pytest.raises(ValueError, match="INVALID_SPATIAL_GRID_SIZE"):
        _generate(grid_size=8)


def test_process_a_completion_event_contains_spatial_map_without_changing_scalar_verdict() -> None:
    env = ProcessA_Env(
        {
            "num_machines_A": 1,
            "process_time_A": 1,
            "batch_size_A": 1,
            "deterministic_mode": True,
        }
    )
    task = Task(uid=7, job_id="JOB", due_date=20, spec_a=(45.0, 55.0))
    env.add_tasks([task])

    env.step(
        current_time=0,
        actions={
            "A_0": {
                "task_uids": [7],
                "recipe": [10.0, 2.0, 1.0],
            }
        },
    )
    result = env.step(current_time=1)

    assert result["succeeded"] == [task]
    assert task.realized_qa_A == pytest.approx(49.958865, abs=1e-5)
    completion = next(
        event for event in env.event_log if event["event_type"] == "task_completed"
    )
    assert len(completion["spatial_quality_maps"]) == 1
    spatial = completion["spatial_quality_maps"][0]
    assert spatial["task_uid"] == 7
    assert spatial["equipment_id"] == "A_0"
    assert spatial["summary"]["mean"] == pytest.approx(task.realized_qa_A, abs=1e-6)
    quality_history = next(
        row for row in task.history if row.get("process") == "A" and "qa" in row
    )
    assert quality_history["spatial_quality_summary"] == spatial["summary"]
    assert quality_history["spatial_quality_model"] == spatial["model"]
