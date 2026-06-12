"""Generic read-only equipment telemetry for MES agent visual analytics."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence

from src.mes.runtime.common import stage_env
from src.mes.runtime.naming import equipment_display_name, stage_display_name


METRIC_IDS = ("quality", "utilization", "throughput", "alarm", "anomaly")
MAX_EQUIPMENT = 8
MAX_PERIODS = 365
MAX_POINTS = 2_000
ALARM_EVENT_TYPES = {"alarm", "equipment_alarm", "fdc_alarm"}


def resolve_equipment_ids(context: Any, equipment_ids: Sequence[Any]) -> List[str]:
    requested = [str(value or "").strip() for value in equipment_ids]
    if len(requested) > MAX_EQUIPMENT:
        raise ValueError(f"TOO_MANY_EQUIPMENT:max={MAX_EQUIPMENT}")

    available = _available_equipment(context)
    aliases: Dict[str, str] = {}
    for equipment_id in available:
        aliases[equipment_id.casefold()] = equipment_id
        aliases[equipment_display_name(context, equipment_id).casefold()] = equipment_id

    resolved: List[str] = []
    for value in requested:
        equipment_id = aliases.get(value.casefold())
        if equipment_id is None:
            raise ValueError(f"UNKNOWN_EQUIPMENT:{value}")
        if equipment_id not in resolved:
            resolved.append(equipment_id)
    if not resolved:
        raise ValueError("MISSING_EQUIPMENT_IDS")
    return resolved


def equipment_metric_catalog(
    context: Any,
    equipment_ids: Sequence[Any],
) -> Dict[str, Any]:
    resolved = resolve_equipment_ids(context, equipment_ids)
    return {
        "read_only": True,
        "source": "SIMULATOR",
        "time_basis": "SIMULATION_STEP",
        "equipment_count": len(resolved),
        "equipment": [
            {
                "equipment_id": equipment_id,
                "display_name": equipment_display_name(context, equipment_id),
                "stage": equipment_id.split("_", 1)[0],
                "stage_label": stage_display_name(context, equipment_id.split("_", 1)[0]),
                "metrics": list(METRIC_IDS),
            }
            for equipment_id in resolved
        ],
        "metrics": list(METRIC_IDS),
        "limits": {
            "max_equipment": MAX_EQUIPMENT,
            "max_periods": MAX_PERIODS,
            "max_points": MAX_POINTS,
        },
    }


def query_equipment_timeseries(
    context: Any,
    equipment_ids: Sequence[Any],
    metrics: Sequence[Any],
    time_range: Mapping[str, Any] | None,
    aggregation: str = "daily",
) -> Dict[str, Any]:
    resolved = resolve_equipment_ids(context, equipment_ids)
    metric_ids = _normalize_metrics(metrics)
    window = _normalize_time_range(context, time_range)
    series: List[Dict[str, Any]] = []
    summary: Dict[str, Dict[str, Any]] = {}

    for equipment_id in resolved:
        events = _equipment_events(context, equipment_id, window)
        equipment_summary: Dict[str, Any] = {}
        for metric in metric_ids:
            points, metric_summary = _metric_series(
                context,
                equipment_id,
                metric,
                events,
                window,
            )
            series.extend(points)
            equipment_summary[metric] = metric_summary
        summary[equipment_id] = equipment_summary

    if len(series) > MAX_POINTS:
        raise ValueError(f"TOO_MANY_POINTS:max={MAX_POINTS}")
    series.sort(key=lambda point: (int(point.get("time", 0)), point["equipment_id"], point["metric"]))
    return {
        "read_only": True,
        "source": "SIMULATOR",
        "time_basis": "SIMULATION_STEP",
        "timezone": None,
        "equipment_ids": resolved,
        "metrics": metric_ids,
        "aggregation": str(aggregation or "daily"),
        "requested_range": window["requested_range"],
        "effective_range": window["effective_range"],
        "window": {"start": window["start"], "end": window["end"]},
        "series": series,
        "summary": summary,
    }


def query_equipment_anomalies(
    context: Any,
    equipment_ids: Sequence[Any],
    time_range: Mapping[str, Any] | None,
    severity: Sequence[Any] | None = None,
) -> Dict[str, Any]:
    resolved = resolve_equipment_ids(context, equipment_ids)
    window = _normalize_time_range(context, time_range)
    allowed_severity = {
        str(value).strip().lower()
        for value in (severity or ("info", "warning", "critical"))
        if str(value).strip()
    }
    evidence: List[Dict[str, Any]] = []
    for equipment_id in resolved:
        events = _equipment_events(context, equipment_id, window)
        for index, event in enumerate(events):
            event_type = str(event.get("event_type", "")).lower()
            if event_type in ALARM_EVENT_TYPES:
                item = _observed_alarm(context, equipment_id, event, index)
                if item["severity"] in allowed_severity:
                    evidence.append(item)
            if event_type in {"task_completed", "pack_completed"}:
                derived = _quality_anomaly(context, equipment_id, event, index)
                if derived is not None and derived["severity"] in allowed_severity:
                    evidence.append(derived)

    evidence.sort(key=lambda item: (item["time"], item["equipment_id"], item["event_id"]))
    observed_count = sum(
        item["evidence_class"] == "OBSERVED_ALARM" for item in evidence
    )
    return {
        "read_only": True,
        "source": "SIMULATOR",
        "time_basis": "SIMULATION_STEP",
        "equipment_ids": resolved,
        "requested_range": window["requested_range"],
        "effective_range": window["effective_range"],
        "window": {"start": window["start"], "end": window["end"]},
        "events": evidence,
        "observed_alarm_count": observed_count,
        "derived_anomaly_count": len(evidence) - observed_count,
    }


def _available_equipment(context: Any) -> List[str]:
    decision_state = context.env.get_decision_state()
    equipment_ids: List[str] = []
    for stage in ("A", "B", "C"):
        machines = decision_state.get(stage, {}).get("machines", {})
        if isinstance(machines, Mapping):
            equipment_ids.extend(str(key) for key in machines)
    return sorted(set(equipment_ids))


def _normalize_metrics(metrics: Sequence[Any]) -> List[str]:
    normalized: List[str] = []
    for value in metrics:
        metric = str(value or "").strip().lower()
        if metric not in METRIC_IDS:
            raise ValueError(f"UNKNOWN_METRIC:{metric}")
        if metric not in normalized:
            normalized.append(metric)
    if not normalized:
        raise ValueError("MISSING_METRICS")
    return normalized


def _normalize_time_range(
    context: Any,
    time_range: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    payload = dict(time_range or {})
    range_type = str(payload.get("type") or "relative").lower()
    unit = str(payload.get("unit") or "day").lower()
    if range_type in {"day", "days", "period", "periods", "step", "steps"}:
        if "unit" not in payload:
            unit = range_type
        range_type = "relative"
    if range_type != "relative":
        raise ValueError(f"UNSUPPORTED_TIME_RANGE_TYPE:{range_type}")
    try:
        value = int(payload.get("value", 15))
    except (TypeError, ValueError) as exc:
        raise ValueError("INVALID_TIME_RANGE_VALUE") from exc
    if value <= 0:
        raise ValueError("INVALID_TIME_RANGE_VALUE")
    if value > MAX_PERIODS:
        raise ValueError(f"TIME_RANGE_TOO_LARGE:max={MAX_PERIODS}")
    if unit not in {"day", "days", "period", "periods", "step", "steps"}:
        raise ValueError(f"UNSUPPORTED_TIME_RANGE_UNIT:{unit}")

    end = max(0, int(getattr(context.env, "time", 0)))
    start = max(0, end - value)
    requested_unit = "day" if unit in {"day", "days"} else "period"
    requested_label = f"{value} {requested_unit}{'' if value == 1 else 's'}"
    return {
        "start": start,
        "end": end,
        "periods": value,
        "requested_range": requested_label,
        "effective_range": f"last {value} simulation periods",
    }


def _equipment_events(
    context: Any,
    equipment_id: str,
    window: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    stage = equipment_id.split("_", 1)[0]
    events = []
    for raw_event in getattr(stage_env(context, stage), "event_log", []) or []:
        event = dict(raw_event)
        if str(event.get("machine_id", "")) != equipment_id:
            continue
        timestamp = int(event.get("timestamp", event.get("event_time", 0)) or 0)
        event_type = str(event.get("event_type", "")).lower()
        interval_end = int(event.get("end_time", timestamp) or timestamp)
        overlaps_window = (
            event_type in {"task_assigned", "pack_started"}
            and interval_end > int(window["start"])
            and timestamp <= int(window["end"])
        )
        if not overlaps_window and (
            timestamp < int(window["start"]) or timestamp > int(window["end"])
        ):
            continue
        event["timestamp"] = timestamp
        events.append(event)
    return sorted(events, key=lambda item: int(item.get("timestamp", 0)))


def _metric_series(
    context: Any,
    equipment_id: str,
    metric: str,
    events: Sequence[Mapping[str, Any]],
    window: Mapping[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if metric == "quality":
        return _quality_series(context, equipment_id, events)
    if metric == "throughput":
        return _throughput_series(context, equipment_id, events)
    if metric == "utilization":
        return _utilization_series(context, equipment_id, events, window)
    if metric == "alarm":
        return _evidence_count_series(context, equipment_id, events, observed=True)
    return _evidence_count_series(context, equipment_id, events, observed=False)


def _quality_series(
    context: Any,
    equipment_id: str,
    events: Sequence[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = []
    samples: List[float] = []
    oos_count = 0
    for event in events:
        if str(event.get("event_type", "")).lower() not in {
            "task_completed",
            "pack_completed",
        }:
            continue
        values = _quality_values(event)
        if not values:
            continue
        samples.extend(values)
        target_specs = list(event.get("target_specs") or [])
        oos_count += _oos_count(values, target_specs)
        point = _base_point(context, equipment_id, "quality", event)
        point.update(
            {
                "value": round(
                    float(
                        event.get(
                            "avg_quality",
                            event.get("pack_quality", sum(values) / len(values)),
                        )
                    ),
                    4,
                ),
                "unit": "quality",
                "sample_count": len(values),
                "target_window": _target_window(target_specs, equipment_id),
            }
        )
        points.append(point)
    return points, {
        "sample_count": len(samples),
        "average": round(sum(samples) / len(samples), 4) if samples else None,
        "minimum": round(min(samples), 4) if samples else None,
        "maximum": round(max(samples), 4) if samples else None,
        "oos_count": oos_count,
    }


def _throughput_series(
    context: Any,
    equipment_id: str,
    events: Sequence[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = []
    total = 0
    for event in events:
        if str(event.get("event_type", "")).lower() not in {
            "task_completed",
            "pack_completed",
        }:
            continue
        count = len(event.get("task_uids") or [])
        total += count
        point = _base_point(context, equipment_id, "throughput", event)
        point.update({"value": float(count), "unit": "unit", "sample_count": count})
        points.append(point)
    return points, {"event_count": len(points), "total": total}


def _utilization_series(
    context: Any,
    equipment_id: str,
    events: Sequence[Mapping[str, Any]],
    window: Mapping[str, Any],
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    intervals = []
    for event in events:
        if str(event.get("event_type", "")).lower() not in {"task_assigned", "pack_started"}:
            continue
        start = max(int(window["start"]), int(event.get("start_time", event["timestamp"])))
        end = min(int(window["end"]), int(event.get("end_time", start)))
        if end > start:
            intervals.append((start, end))
    busy_duration = sum(end - start for start, end in _merge_intervals(intervals))
    observed_duration = max(1, int(window["end"]) - int(window["start"]))
    value = round(busy_duration / observed_duration, 4)
    point = {
        "equipment_id": equipment_id,
        "display_name": equipment_display_name(context, equipment_id),
        "metric": "utilization",
        "time": int(window["end"]),
        "value": value,
        "unit": "ratio",
        "sample_count": len(intervals),
    }
    return [point], {
        "busy_duration": busy_duration,
        "observed_duration": observed_duration,
        "average": value,
    }


def _evidence_count_series(
    context: Any,
    equipment_id: str,
    events: Sequence[Mapping[str, Any]],
    *,
    observed: bool,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    points = []
    for index, event in enumerate(events):
        event_type = str(event.get("event_type", "")).lower()
        if observed and event_type in ALARM_EVENT_TYPES:
            evidence = _observed_alarm(context, equipment_id, event, index)
        elif not observed and event_type in {"task_completed", "pack_completed"}:
            evidence = _quality_anomaly(context, equipment_id, event, index)
        else:
            evidence = None
        if evidence is None:
            continue
        point = _base_point(
            context,
            equipment_id,
            "alarm" if observed else "anomaly",
            event,
        )
        point.update(
            {
                "value": 1.0,
                "unit": "event",
                "sample_count": 1,
                "event": evidence,
            }
        )
        points.append(point)
    return points, {"event_count": len(points), "total": len(points)}


def _quality_values(event: Mapping[str, Any]) -> List[float]:
    raw_values = list(event.get("quality_values") or [])
    if not raw_values:
        raw = event.get("pack_quality", event.get("avg_quality"))
        raw_values = [] if raw is None else [raw]
    values = []
    for raw in raw_values:
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
    return values


def _oos_count(
    values: Sequence[float],
    target_specs: Sequence[Mapping[str, Any]],
) -> int:
    if not target_specs:
        return 0
    count = 0
    for index, value in enumerate(values):
        spec = target_specs[min(index, len(target_specs) - 1)]
        try:
            low = float(spec["low"])
            high = float(spec["high"])
        except (KeyError, TypeError, ValueError):
            continue
        if value < low or value > high:
            count += 1
    return count


def _target_window(
    target_specs: Sequence[Mapping[str, Any]],
    equipment_id: str,
) -> List[float] | None:
    lows = []
    highs = []
    for spec in target_specs:
        try:
            lows.append(float(spec["low"]))
            highs.append(float(spec["high"]))
        except (KeyError, TypeError, ValueError):
            continue
    if lows and highs:
        return [round(sum(lows) / len(lows), 4), round(sum(highs) / len(highs), 4)]
    return [0.0, 100.0] if equipment_id.startswith("C_") else None


def _observed_alarm(
    context: Any,
    equipment_id: str,
    event: Mapping[str, Any],
    index: int,
) -> Dict[str, Any]:
    timestamp = int(event.get("timestamp", 0) or 0)
    return {
        "event_id": str(event.get("event_id") or f"ALARM-{equipment_id}-{timestamp}-{index}"),
        "equipment_id": equipment_id,
        "display_name": equipment_display_name(context, equipment_id),
        "time": timestamp,
        "evidence_class": "OBSERVED_ALARM",
        "code": str(event.get("alarm_code") or event.get("code") or "EQUIPMENT_ALARM"),
        "severity": str(event.get("severity") or "warning").lower(),
        "message": str(event.get("message") or "Observed equipment alarm"),
    }


def _quality_anomaly(
    context: Any,
    equipment_id: str,
    event: Mapping[str, Any],
    index: int,
) -> Dict[str, Any] | None:
    values = _quality_values(event)
    target_specs = list(event.get("target_specs") or [])
    if not values or _oos_count(values, target_specs) == 0:
        return None
    timestamp = int(event.get("timestamp", 0) or 0)
    return {
        "event_id": f"ANOMALY-{equipment_id}-{timestamp}-{index}",
        "equipment_id": equipment_id,
        "display_name": equipment_display_name(context, equipment_id),
        "time": timestamp,
        "evidence_class": "DERIVED_ANOMALY",
        "code": "QUALITY_OOS",
        "severity": "warning",
        "message": "One or more quality samples were outside the target window.",
        "values": values,
        "target_window": _target_window(target_specs, equipment_id),
    }


def _base_point(
    context: Any,
    equipment_id: str,
    metric: str,
    event: Mapping[str, Any],
) -> Dict[str, Any]:
    return {
        "equipment_id": equipment_id,
        "display_name": equipment_display_name(context, equipment_id),
        "metric": metric,
        "time": int(event.get("timestamp", 0) or 0),
    }


def _merge_intervals(intervals: Iterable[tuple[int, int]]) -> List[tuple[int, int]]:
    merged: List[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged
