import pytest

from src.mes.agent_runtime.visual_artifacts import (
    build_anomaly_artifact,
    build_process_a_spatial_quality_artifact,
    build_timeseries_artifact,
    validate_visual_artifact,
)
from src.environment.process_a_spatial_quality import (
    generate_process_a_spatial_quality,
)


def _timeseries_payload():
    return {
        "source": "SIMULATOR",
        "time_basis": "SIMULATION_STEP",
        "equipment_ids": ["A_0", "A_1"],
        "metrics": ["quality"],
        "aggregation": "daily",
        "requested_range": "15 days",
        "effective_range": "last 15 simulation periods",
        "window": {"start": 5, "end": 20},
        "series": [
            {
                "equipment_id": "A_0",
                "display_name": "LITHO-01",
                "metric": "quality",
                "time": 10,
                "value": 50.0,
                "unit": "quality",
                "sample_count": 2,
                "target_window": [48.0, 53.0],
            },
            {
                "equipment_id": "A_1",
                "display_name": "LITHO-02",
                "metric": "quality",
                "time": 10,
                "value": 51.0,
                "unit": "quality",
                "sample_count": 2,
                "target_window": [48.0, 53.0],
            },
        ],
        "summary": {
            "A_0": {"quality": {"average": 50.0, "oos_count": 0}},
            "A_1": {"quality": {"average": 51.0, "oos_count": 0}},
        },
    }


def test_timeseries_artifact_is_deterministic_and_preserves_provenance() -> None:
    payload = _timeseries_payload()

    first = build_timeseries_artifact(payload, query_tool="query_equipment_timeseries")
    second = build_timeseries_artifact(payload, query_tool="query_equipment_timeseries")

    assert first == second
    assert first["artifact_id"].startswith("VIZ_")
    assert first["artifact_type"] == "equipment_timeseries"
    assert first["title"] == "LITHO-01 + 1 · Quality"
    assert first["visualization"] == {
        "chart_type": "line",
        "x_field": "time",
        "y_field": "value",
        "series_field": "equipment_id",
        "metric_field": "metric",
        "target_bands": [[48.0, 53.0]],
    }
    assert first["provenance"] == {
        "source": "SIMULATOR",
        "time_basis": "SIMULATION_STEP",
        "query_tool": "query_equipment_timeseries",
        "requested_range": "15 days",
        "effective_range": "last 15 simulation periods",
    }


def test_anomaly_artifact_uses_event_timeline_and_evidence_counts() -> None:
    artifact = build_anomaly_artifact(
        {
            "source": "SIMULATOR",
            "time_basis": "SIMULATION_STEP",
            "equipment_ids": ["A_0"],
            "requested_range": "15 days",
            "effective_range": "last 15 simulation periods",
            "window": {"start": 5, "end": 20},
            "events": [
                {
                    "event_id": "ALARM-1",
                    "equipment_id": "A_0",
                    "display_name": "LITHO-01",
                    "time": 14,
                    "evidence_class": "OBSERVED_ALARM",
                    "code": "TEMP_HIGH",
                    "severity": "critical",
                    "message": "Temperature exceeded limit",
                },
                {
                    "event_id": "ANOMALY-1",
                    "equipment_id": "A_0",
                    "display_name": "LITHO-01",
                    "time": 18,
                    "evidence_class": "DERIVED_ANOMALY",
                    "code": "QUALITY_OOS",
                    "severity": "warning",
                    "message": "Quality outside target",
                },
            ],
            "observed_alarm_count": 1,
            "derived_anomaly_count": 1,
        },
        query_tool="query_equipment_anomalies",
    )

    assert artifact["artifact_type"] == "equipment_anomalies"
    assert artifact["visualization"]["chart_type"] == "event_timeline"
    assert artifact["summary"] == {
        "observed_alarm_count": 1,
        "derived_anomaly_count": 1,
        "event_count": 2,
    }


@pytest.mark.parametrize("chart_type", ["line", "bar", "event_timeline"])
def test_visual_artifact_accepts_only_known_chart_types(chart_type: str) -> None:
    artifact = build_timeseries_artifact(_timeseries_payload())
    artifact["visualization"]["chart_type"] = chart_type

    assert validate_visual_artifact(artifact)["visualization"]["chart_type"] == chart_type


def test_visual_artifact_rejects_executable_or_unknown_visualization_fields() -> None:
    artifact = build_timeseries_artifact(_timeseries_payload())
    artifact["visualization"]["script"] = "alert(1)"

    with pytest.raises(ValueError, match="UNKNOWN_VISUALIZATION_FIELD"):
        validate_visual_artifact(artifact)

    artifact = build_timeseries_artifact(_timeseries_payload())
    artifact["visualization"]["chart_type"] = "raw_html"
    with pytest.raises(ValueError, match="UNKNOWN_CHART_TYPE"):
        validate_visual_artifact(artifact)


def test_visual_artifact_rejects_non_data_payload_values() -> None:
    artifact = build_timeseries_artifact(_timeseries_payload())
    artifact["series"][0]["label"] = "<script>alert(1)</script>"

    with pytest.raises(ValueError, match="UNSAFE_ARTIFACT_TEXT"):
        validate_visual_artifact(artifact)


def test_process_a_spatial_artifact_preserves_map_and_simulator_provenance() -> None:
    spatial = {
        "task_uid": 184,
        "equipment_id": "A_0",
        "completion_time": 20,
        "recipe": [10.0, 2.0, 1.0],
        "machine_state": {"u": 8, "m_age": 80},
        **generate_process_a_spatial_quality(
            scalar_qa=49.2,
            spec=(45.0, 55.0),
            recipe=[10.0, 2.0, 1.0],
            u=8,
            m_age=80,
            task_uid=184,
            equipment_id="A_0",
            completion_time=20,
        ),
    }
    artifact = build_process_a_spatial_quality_artifact(
        {
            "found": True,
            "source": "SIMULATOR",
            "time_basis": "SIMULATION_STEP",
            "evidence_type": "SIMULATED_SPATIAL_QUALITY",
            "equipment_id": "A_0",
            "display_name": "LITHO-01",
            "task_uid": 184,
            "completion_time": 20,
            "spatial_quality": spatial,
        }
    )

    assert artifact["artifact_type"] == "process_a_spatial_quality"
    assert artifact["title"] == "LITHO-01 · Task 184 · Spatial Quality"
    assert artifact["visualization"] == {
        "chart_type": "spatial_quality_map",
        "grid_field": "spatial_quality.cells",
        "value_field": "value",
        "verdict_field": "verdict",
        "coordinate_fields": ["x", "y"],
        "target_bands": [[45.0, 55.0]],
    }
    assert artifact["spatial_quality"]["summary"]["mean"] == pytest.approx(49.2)
    assert artifact["provenance"]["evidence_type"] == "SIMULATED_SPATIAL_QUALITY"
    assert artifact["provenance"]["model_id"] == "PROCESS_A_SPATIAL_FIELD"
    assert artifact["provenance"]["model_version"] == "1.0.0"
