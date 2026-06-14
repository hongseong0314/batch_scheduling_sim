import pytest

from src.environment.process_a_spatial_quality import (
    generate_process_a_spatial_quality,
)
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.process_quality_maps import (
    query_process_a_spatial_quality,
)


def _spatial(task_uid: int, equipment_id: str, completion_time: int):
    return {
        "task_uid": task_uid,
        "equipment_id": equipment_id,
        "completion_time": completion_time,
        "recipe": [10.0, 2.0, 1.0],
        "machine_state": {"u": 8, "m_age": 80},
        **generate_process_a_spatial_quality(
            scalar_qa=49.2,
            spec=(45.0, 55.0),
            recipe=[10.0, 2.0, 1.0],
            u=8,
            m_age=80,
            task_uid=task_uid,
            equipment_id=equipment_id,
            completion_time=completion_time,
        ),
    }


def _context_with_maps() -> MESAPIContext:
    context = MESAPIContext()
    context.env.env_A.event_log = [
        {
            "timestamp": 10,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "spatial_quality_maps": [_spatial(10, "A_0", 10)],
        },
        {
            "timestamp": 20,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "spatial_quality_maps": [_spatial(20, "A_0", 20)],
        },
        {
            "timestamp": 21,
            "event_type": "task_completed",
            "machine_id": "A_1",
            "spatial_quality_maps": [_spatial(21, "A_1", 21)],
        },
    ]
    return context


def test_query_process_a_spatial_quality_returns_latest_map_by_display_name() -> None:
    payload = query_process_a_spatial_quality(
        _context_with_maps(),
        equipment_id="LITHO-01",
    )

    assert payload["found"] is True
    assert payload["equipment_id"] == "A_0"
    assert payload["display_name"] == "LITHO-01"
    assert payload["task_uid"] == 20
    assert payload["source"] == "SIMULATOR"
    assert payload["evidence_type"] == "SIMULATED_SPATIAL_QUALITY"
    assert payload["spatial_quality"]["summary"]["mean"] == pytest.approx(49.2)


def test_query_process_a_spatial_quality_resolves_exact_task_and_match() -> None:
    payload = query_process_a_spatial_quality(
        _context_with_maps(),
        equipment_id="A_0",
        task_uid=10,
    )

    assert payload["found"] is True
    assert payload["task_uid"] == 10
    assert payload["completion_time"] == 10

    mismatch = query_process_a_spatial_quality(
        _context_with_maps(),
        equipment_id="A_1",
        task_uid=10,
    )
    assert mismatch == {
        "found": False,
        "reason": "NO_MATCHING_SPATIAL_QUALITY",
        "equipment_id": "A_1",
        "task_uid": 10,
    }


def test_query_process_a_spatial_quality_rejects_non_a_equipment() -> None:
    with pytest.raises(
        ValueError,
        match="UNSUPPORTED_SPATIAL_QUALITY_OPERATION:B",
    ):
        query_process_a_spatial_quality(
            _context_with_maps(),
            equipment_id="CLEAN-01",
        )


def test_query_process_a_spatial_quality_requires_lookup_and_handles_empty_log() -> None:
    context = MESAPIContext()
    context.env.env_A.event_log = []

    with pytest.raises(ValueError, match="MISSING_SPATIAL_QUALITY_LOOKUP"):
        query_process_a_spatial_quality(context)

    assert query_process_a_spatial_quality(
        context,
        task_uid=999,
    ) == {
        "found": False,
        "reason": "NO_MATCHING_SPATIAL_QUALITY",
        "equipment_id": None,
        "task_uid": 999,
    }
