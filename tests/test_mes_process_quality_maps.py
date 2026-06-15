import pytest

from src.environment.process_a_spatial_quality import (
    generate_process_a_spatial_quality,
)
from src.environment.process_quality.process_b import (
    generate_process_b_quality_evidence,
)
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.process_quality_maps import (
    query_process_a_spatial_quality,
    query_process_quality_evidence,
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


def _context_with_common_evidence() -> MESAPIContext:
    context = _context_with_maps()
    context.env.env_B.event_log = [
        {
            "timestamp": 22,
            "event_type": "task_completed",
            "process": "B",
            "machine_id": "B_0",
            "quality_evidence": [
                generate_process_b_quality_evidence(
                    scalar_qa=52.4,
                    spec=(40.0, 70.0),
                    recipe=[50.0, 50.0, 30.0],
                    v=8,
                    b_age=80,
                    task_uid=22,
                    equipment_id="B_0",
                    completion_time=22,
                )
            ],
        }
    ]
    return context


def test_query_process_quality_evidence_returns_latest_a_or_b_evidence() -> None:
    context = _context_with_common_evidence()

    process_a = query_process_quality_evidence(
        context,
        equipment_id="LITHO-01",
    )
    process_b = query_process_quality_evidence(
        context,
        operation_id="B",
        equipment_id="CLEAN-01",
    )

    assert process_a["found"] is True
    assert process_a["operation_id"] == "A"
    assert process_a["quality_evidence"]["quality_kind"] == (
        "PROCESS_A_SPATIAL_QUALITY"
    )
    assert process_b["found"] is True
    assert process_b["operation_id"] == "B"
    assert process_b["equipment_id"] == "B_0"
    assert process_b["display_name"] == "CLEAN-01"
    assert process_b["task_uid"] == 22
    assert process_b["quality_evidence"]["quality_kind"] == (
        "PROCESS_B_CLEANING_QUALITY"
    )


def test_query_process_quality_evidence_searches_by_task_and_validates_operation() -> None:
    context = _context_with_common_evidence()

    by_task = query_process_quality_evidence(context, task_uid=22)
    assert by_task["operation_id"] == "B"

    with pytest.raises(
        ValueError,
        match="QUALITY_EVIDENCE_OPERATION_MISMATCH:A:B",
    ):
        query_process_quality_evidence(
            context,
            operation_id="A",
            equipment_id="B_0",
        )
    with pytest.raises(
        ValueError,
        match="UNSUPPORTED_QUALITY_EVIDENCE_OPERATION:C",
    ):
        query_process_quality_evidence(
            context,
            operation_id="C",
            task_uid=22,
        )


def test_query_process_quality_evidence_handles_missing_lookup_and_evidence() -> None:
    context = MESAPIContext()
    context.env.env_A.event_log = []
    context.env.env_B.event_log = []

    with pytest.raises(ValueError, match="MISSING_QUALITY_EVIDENCE_LOOKUP"):
        query_process_quality_evidence(context)

    assert query_process_quality_evidence(
        context,
        operation_id="B",
        task_uid=999,
    ) == {
        "found": False,
        "reason": "NO_MATCHING_QUALITY_EVIDENCE",
        "operation_id": "B",
        "equipment_id": None,
        "task_uid": 999,
    }


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
