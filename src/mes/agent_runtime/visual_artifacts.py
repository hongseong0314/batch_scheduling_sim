"""Typed, non-executable visual artifacts for MES Process Chat."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping


ARTIFACT_TYPES = {
    "equipment_timeseries",
    "equipment_anomalies",
    "process_a_spatial_quality",
}
CHART_TYPES = {"line", "bar", "event_timeline", "spatial_quality_map"}
VISUALIZATION_FIELDS = {
    "chart_type",
    "x_field",
    "y_field",
    "series_field",
    "metric_field",
    "target_bands",
    "time_field",
    "severity_field",
    "label_field",
    "grid_field",
    "value_field",
    "verdict_field",
    "coordinate_fields",
}
UNSAFE_TEXT_MARKERS = ("<script", "</script", "javascript:", "data:text/html")


def build_timeseries_artifact(
    payload: Mapping[str, Any],
    *,
    query_tool: str = "query_equipment_timeseries",
) -> Dict[str, Any]:
    equipment_ids = [str(value) for value in payload.get("equipment_ids", [])]
    metrics = [str(value) for value in payload.get("metrics", [])]
    series = [dict(point) for point in payload.get("series", [])]
    title = _timeseries_title(equipment_ids, metrics, series)
    artifact = {
        "artifact_type": "equipment_timeseries",
        "title": title,
        "equipment_ids": equipment_ids,
        "metrics": metrics,
        "window": dict(payload.get("window") or {}),
        "series": series,
        "events": [],
        "summary": deepcopy(dict(payload.get("summary") or {})),
        "visualization": {
            "chart_type": "line",
            "x_field": "time",
            "y_field": "value",
            "series_field": "equipment_id",
            "metric_field": "metric",
            "target_bands": _target_bands(series),
        },
        "provenance": _provenance(payload, query_tool),
    }
    artifact["artifact_id"] = _artifact_id(artifact)
    return validate_visual_artifact(artifact)


def build_anomaly_artifact(
    payload: Mapping[str, Any],
    *,
    query_tool: str = "query_equipment_anomalies",
) -> Dict[str, Any]:
    equipment_ids = [str(value) for value in payload.get("equipment_ids", [])]
    events = [dict(event) for event in payload.get("events", [])]
    artifact = {
        "artifact_type": "equipment_anomalies",
        "title": _anomaly_title(equipment_ids, events),
        "equipment_ids": equipment_ids,
        "metrics": ["alarm", "anomaly"],
        "window": dict(payload.get("window") or {}),
        "series": [],
        "events": events,
        "summary": {
            "observed_alarm_count": int(payload.get("observed_alarm_count", 0) or 0),
            "derived_anomaly_count": int(payload.get("derived_anomaly_count", 0) or 0),
            "event_count": len(events),
        },
        "visualization": {
            "chart_type": "event_timeline",
            "time_field": "time",
            "series_field": "equipment_id",
            "severity_field": "severity",
            "label_field": "code",
            "target_bands": [],
        },
        "provenance": _provenance(payload, query_tool),
    }
    artifact["artifact_id"] = _artifact_id(artifact)
    return validate_visual_artifact(artifact)


def build_process_a_spatial_quality_artifact(
    payload: Mapping[str, Any],
    *,
    query_tool: str = "query_process_a_spatial_quality",
) -> Dict[str, Any]:
    spatial_quality = deepcopy(dict(payload.get("spatial_quality") or {}))
    display_name = str(
        payload.get("display_name")
        or payload.get("equipment_id")
        or "Process A"
    )
    task_uid = payload.get("task_uid")
    spec = dict(spatial_quality.get("spec") or {})
    low = spec.get("low")
    high = spec.get("high")
    target_bands = (
        [[float(low), float(high)]]
        if low is not None and high is not None
        else []
    )
    reason_codes = [
        str(value) for value in spatial_quality.get("reason_codes", [])
    ]
    artifact = {
        "artifact_type": "process_a_spatial_quality",
        "title": f"{display_name} · Task {task_uid} · Spatial Quality",
        "equipment_ids": [str(payload.get("equipment_id") or "")],
        "metrics": ["spatial_quality"],
        "window": {
            "start": int(payload.get("completion_time", 0) or 0),
            "end": int(payload.get("completion_time", 0) or 0),
        },
        "series": [],
        "events": [
            {
                "event_id": f"SPATIAL-{task_uid}-{index}",
                "equipment_id": str(payload.get("equipment_id") or ""),
                "display_name": display_name,
                "time": int(payload.get("completion_time", 0) or 0),
                "evidence_class": "DERIVED_SPATIAL_QUALITY",
                "code": code,
                "severity": (
                    "critical" if code == "LOCAL_OOS_CLUSTER" else "warning"
                ),
                "message": _spatial_reason_message(code),
            }
            for index, code in enumerate(reason_codes)
        ],
        "summary": deepcopy(dict(spatial_quality.get("summary") or {})),
        "spatial_quality": spatial_quality,
        "visualization": {
            "chart_type": "spatial_quality_map",
            "grid_field": "spatial_quality.cells",
            "value_field": "value",
            "verdict_field": "verdict",
            "coordinate_fields": ["x", "y"],
            "target_bands": target_bands,
        },
        "provenance": _provenance(payload, query_tool),
    }
    artifact["artifact_id"] = _artifact_id(artifact)
    return validate_visual_artifact(artifact)


def validate_visual_artifact(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(dict(artifact))
    artifact_type = str(payload.get("artifact_type", ""))
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError(f"UNKNOWN_ARTIFACT_TYPE:{artifact_type}")
    visualization = payload.get("visualization")
    if not isinstance(visualization, Mapping):
        raise ValueError("MISSING_VISUALIZATION")
    unknown_fields = set(visualization) - VISUALIZATION_FIELDS
    if unknown_fields:
        raise ValueError(
            f"UNKNOWN_VISUALIZATION_FIELD:{sorted(unknown_fields)[0]}"
        )
    chart_type = str(visualization.get("chart_type", ""))
    if chart_type not in CHART_TYPES:
        raise ValueError(f"UNKNOWN_CHART_TYPE:{chart_type}")
    _validate_data_only(payload)
    return payload


def _provenance(payload: Mapping[str, Any], query_tool: str) -> Dict[str, Any]:
    provenance = {
        "source": str(payload.get("source") or "UNKNOWN"),
        "time_basis": str(payload.get("time_basis") or "UNKNOWN"),
        "query_tool": str(query_tool),
        "requested_range": str(payload.get("requested_range") or ""),
        "effective_range": str(payload.get("effective_range") or ""),
    }
    evidence_type = payload.get("evidence_type")
    if evidence_type:
        provenance["evidence_type"] = str(evidence_type)
    spatial_quality = payload.get("spatial_quality")
    if isinstance(spatial_quality, Mapping):
        model = spatial_quality.get("model")
        if isinstance(model, Mapping):
            provenance["model_id"] = str(model.get("model_id") or "")
            provenance["model_version"] = str(model.get("version") or "")
            provenance["seed"] = int(model.get("seed", 0) or 0)
    return provenance


def _spatial_reason_message(code: str) -> str:
    messages = {
        "LOCAL_OOS_CLUSTER": "One or more connected spatial cells are outside specification.",
        "EDGE_NON_UNIFORMITY": "Edge and center quality means differ beyond the model threshold.",
        "DIRECTIONAL_BIAS": "Recipe-dependent directional variation is present.",
        "CONSUMABLE_HOTSPOT": "Consumable usage contributes a localized quality hotspot.",
    }
    return messages.get(code, "Derived spatial quality condition.")


def _timeseries_title(
    equipment_ids: list[str],
    metrics: list[str],
    series: Iterable[Mapping[str, Any]],
) -> str:
    display_names = []
    for point in series:
        name = str(point.get("display_name") or point.get("equipment_id") or "")
        if name and name not in display_names:
            display_names.append(name)
    equipment_label = (
        display_names[0] if display_names else (equipment_ids[0] if equipment_ids else "Equipment")
    )
    if max(len(display_names), len(equipment_ids)) > 1:
        equipment_label = f"{equipment_label} + {max(len(display_names), len(equipment_ids)) - 1}"
    metric_label = " + ".join(metric.replace("_", " ").title() for metric in metrics)
    return f"{equipment_label} · {metric_label or 'Telemetry'}"


def _anomaly_title(
    equipment_ids: list[str],
    events: Iterable[Mapping[str, Any]],
) -> str:
    event_rows = list(events)
    first = event_rows[0] if event_rows else {}
    label = str(
        first.get("display_name")
        or first.get("equipment_id")
        or (equipment_ids[0] if equipment_ids else "Equipment")
    )
    if len(equipment_ids) > 1:
        label = f"{label} + {len(equipment_ids) - 1}"
    return f"{label} · Alarms & Anomalies"


def _target_bands(series: Iterable[Mapping[str, Any]]) -> list[list[float]]:
    bands = []
    for point in series:
        raw_band = point.get("target_window")
        if not isinstance(raw_band, (list, tuple)) or len(raw_band) != 2:
            continue
        try:
            band = [float(raw_band[0]), float(raw_band[1])]
        except (TypeError, ValueError):
            continue
        if band not in bands:
            bands.append(band)
    return bands


def _artifact_id(artifact: Mapping[str, Any]) -> str:
    identity_payload = {
        key: value
        for key, value in artifact.items()
        if key != "artifact_id"
    }
    encoded = json.dumps(
        identity_payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"VIZ_{hashlib.sha256(encoded).hexdigest()[:16].upper()}"


def _validate_data_only(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _validate_data_only(str(key))
            _validate_data_only(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            _validate_data_only(nested)
        return
    if isinstance(value, str):
        normalized = value.casefold()
        if any(marker in normalized for marker in UNSAFE_TEXT_MARKERS):
            raise ValueError("UNSAFE_ARTIFACT_TEXT")
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    raise ValueError(f"UNSUPPORTED_ARTIFACT_VALUE:{type(value).__name__}")
