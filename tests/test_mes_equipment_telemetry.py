import pytest

from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.equipment_telemetry import (
    equipment_metric_catalog,
    query_equipment_anomalies,
    query_equipment_timeseries,
    resolve_equipment_ids,
)


def _relative_periods(value: int = 15):
    return {"type": "relative", "value": value, "unit": "day"}


def test_resolve_equipment_ids_accepts_canonical_ids_and_display_names() -> None:
    context = MESAPIContext()

    assert resolve_equipment_ids(context, ["A_0", "LITHO-01", "clean-01"]) == [
        "A_0",
        "B_0",
    ]

    with pytest.raises(ValueError, match="UNKNOWN_EQUIPMENT"):
        resolve_equipment_ids(context, ["NOT-A-TOOL"])


def test_equipment_metric_catalog_is_generic_for_all_abc_equipment() -> None:
    context = MESAPIContext()

    payload = equipment_metric_catalog(context, ["A_0", "B_0", "C_0"])

    assert payload["read_only"] is True
    assert payload["equipment_count"] == 3
    assert [item["equipment_id"] for item in payload["equipment"]] == [
        "A_0",
        "B_0",
        "C_0",
    ]
    assert set(payload["metrics"]) == {
        "quality",
        "utilization",
        "throughput",
        "alarm",
        "anomaly",
    }
    assert payload["source"] == "SIMULATOR"
    assert payload["time_basis"] == "SIMULATION_STEP"


def test_query_equipment_timeseries_returns_quality_utilization_and_throughput() -> None:
    context = MESAPIContext()
    context.env.time = 20
    context.env.env_A.event_log = [
        {
            "timestamp": 4,
            "event_type": "task_assigned",
            "machine_id": "A_0",
            "task_uids": [1, 2],
            "start_time": 4,
            "end_time": 10,
        },
        {
            "timestamp": 10,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "task_uids": [1, 2],
            "quality_values": [49.0, 51.0],
            "avg_quality": 50.0,
            "target_specs": [
                {"low": 48.0, "high": 53.0},
                {"low": 48.0, "high": 53.0},
            ],
        },
        {
            "timestamp": 12,
            "event_type": "task_assigned",
            "machine_id": "A_0",
            "task_uids": [3],
            "start_time": 12,
            "end_time": 18,
        },
        {
            "timestamp": 18,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "task_uids": [3],
            "quality_values": [47.0],
            "avg_quality": 47.0,
            "target_specs": [{"low": 48.0, "high": 53.0}],
        },
    ]

    payload = query_equipment_timeseries(
        context,
        equipment_ids=["LITHO-01"],
        metrics=["quality", "utilization", "throughput"],
        time_range=_relative_periods(),
        aggregation="daily",
    )

    assert payload["equipment_ids"] == ["A_0"]
    assert payload["requested_range"] == "15 days"
    assert payload["effective_range"] == "last 15 simulation periods"
    assert payload["window"] == {"start": 5, "end": 20}
    assert payload["source"] == "SIMULATOR"
    assert payload["time_basis"] == "SIMULATION_STEP"
    quality = [point for point in payload["series"] if point["metric"] == "quality"]
    throughput = [point for point in payload["series"] if point["metric"] == "throughput"]
    utilization = [point for point in payload["series"] if point["metric"] == "utilization"]
    assert [point["value"] for point in quality] == [50.0, 47.0]
    assert [point["value"] for point in throughput] == [2.0, 1.0]
    assert utilization == [
        {
            "equipment_id": "A_0",
            "display_name": "LITHO-01",
            "metric": "utilization",
            "time": 20,
            "value": pytest.approx(11 / 15, abs=0.0001),
            "unit": "ratio",
            "sample_count": 2,
        }
    ]
    assert payload["summary"]["A_0"]["quality"]["oos_count"] == 1
    assert payload["summary"]["A_0"]["throughput"]["total"] == 3


def test_query_equipment_timeseries_supports_b_and_c_quality() -> None:
    context = MESAPIContext()
    context.env.time = 10
    context.env.env_B.event_log = [
        {
            "timestamp": 8,
            "event_type": "task_completed",
            "machine_id": "B_0",
            "task_uids": [11, 12],
            "quality_values": [55.0, 57.0],
            "avg_quality": 56.0,
            "target_specs": [
                {"low": 20.0, "high": 80.0},
                {"low": 20.0, "high": 80.0},
            ],
        }
    ]
    context.env.env_C.event_log = [
        {
            "timestamp": 9,
            "event_type": "pack_completed",
            "machine_id": "C_0",
            "task_uids": [21, 22, 23, 24],
            "pack_quality": 87.5,
            "avg_compat": 0.875,
        }
    ]

    payload = query_equipment_timeseries(
        context,
        equipment_ids=["B_0", "PACK-01"],
        metrics=["quality", "throughput"],
        time_range=_relative_periods(),
        aggregation="daily",
    )

    values = {
        (point["equipment_id"], point["metric"]): point["value"]
        for point in payload["series"]
    }
    assert values[("B_0", "quality")] == 56.0
    assert values[("B_0", "throughput")] == 2.0
    assert values[("C_0", "quality")] == 87.5
    assert values[("C_0", "throughput")] == 4.0


def test_alarm_and_derived_anomaly_evidence_are_not_conflated() -> None:
    context = MESAPIContext()
    context.env.time = 20
    context.env.env_A.event_log = [
        {
            "timestamp": 14,
            "event_type": "equipment_alarm",
            "machine_id": "A_0",
            "alarm_code": "TEMP_HIGH",
            "severity": "critical",
            "message": "Temperature exceeded limit",
        },
        {
            "timestamp": 18,
            "event_type": "task_completed",
            "machine_id": "A_0",
            "task_uids": [3],
            "quality_values": [47.0],
            "avg_quality": 47.0,
            "target_specs": [{"low": 48.0, "high": 53.0}],
        },
    ]

    payload = query_equipment_anomalies(
        context,
        equipment_ids=["A_0"],
        time_range=_relative_periods(),
        severity=["warning", "critical"],
    )

    assert payload["observed_alarm_count"] == 1
    assert payload["derived_anomaly_count"] == 1
    assert {event["evidence_class"] for event in payload["events"]} == {
        "OBSERVED_ALARM",
        "DERIVED_ANOMALY",
    }
    observed = next(
        event for event in payload["events"] if event["evidence_class"] == "OBSERVED_ALARM"
    )
    derived = next(
        event for event in payload["events"] if event["evidence_class"] == "DERIVED_ANOMALY"
    )
    assert observed["code"] == "TEMP_HIGH"
    assert derived["code"] == "QUALITY_OOS"


def test_equipment_query_limits_are_enforced() -> None:
    context = MESAPIContext()

    with pytest.raises(ValueError, match="TOO_MANY_EQUIPMENT"):
        resolve_equipment_ids(context, [f"A_{index}" for index in range(9)])
    with pytest.raises(ValueError, match="TIME_RANGE_TOO_LARGE"):
        query_equipment_timeseries(
            context,
            equipment_ids=["A_0"],
            metrics=["quality"],
            time_range=_relative_periods(366),
            aggregation="daily",
        )
    with pytest.raises(ValueError, match="UNKNOWN_METRIC"):
        query_equipment_timeseries(
            context,
            equipment_ids=["A_0"],
            metrics=["secret_metric"],
            time_range=_relative_periods(),
            aggregation="daily",
        )


def test_time_range_accepts_safe_llm_relative_aliases() -> None:
    context = MESAPIContext()
    context.env.time = 20

    payload = query_equipment_timeseries(
        context,
        equipment_ids=["A_0"],
        metrics=["utilization"],
        time_range={"type": "days", "value": 15, "unit": "days"},
        aggregation="daily",
    )

    assert payload["requested_range"] == "15 days"
    assert payload["effective_range"] == "last 15 simulation periods"
