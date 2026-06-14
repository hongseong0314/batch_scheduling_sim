"""Generic read-only visual analytics tools exposed to MES Agent Mode."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from src.mes.agent_runtime.visual_artifacts import (
    build_anomaly_artifact,
    build_process_a_spatial_quality_artifact,
    build_timeseries_artifact,
)
from src.mes.runtime.equipment_telemetry import (
    equipment_metric_catalog,
    query_equipment_anomalies,
    query_equipment_timeseries,
)
from src.mes.runtime.process_quality_maps import (
    query_process_a_spatial_quality,
)


VISUAL_TOOL_IDS = (
    "list_equipment_metrics",
    "query_equipment_timeseries",
    "query_equipment_anomalies",
    "query_process_a_spatial_quality",
)


def visual_tool_catalog() -> list[Dict[str, Any]]:
    equipment_ids = {
        "type": "array",
        "minItems": 1,
        "maxItems": 8,
        "items": {"type": "string"},
        "description": (
            "Canonical equipment ids or configured display names, for example "
            "A_0, LITHO-01, B_0, CLEAN-01, C_0, or PACK-01."
        ),
    }
    time_range = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "type": {"type": "string", "enum": ["relative"]},
            "value": {"type": "integer", "minimum": 1, "maximum": 365},
            "unit": {
                "type": "string",
                "enum": ["day", "days", "period", "periods", "step", "steps"],
            },
        },
        "required": ["type", "value", "unit"],
    }
    return [
        {
            "id": "list_equipment_metrics",
            "name": "list_equipment_metrics",
            "read_only": True,
            "description": (
                "List supported quality, utilization, throughput, alarm, and "
                "anomaly metrics for one or more MES equipment records."
            ),
            "input_schema": _object_schema(
                {"equipment_ids": equipment_ids},
                required=["equipment_ids"],
            ),
        },
        {
            "id": "query_equipment_timeseries",
            "name": "query_equipment_timeseries",
            "read_only": True,
            "description": (
                "Query read-only equipment time series and return a typed visual "
                "artifact for one or more equipment records. Simulator day requests "
                "are explicitly reported as simulation periods."
            ),
            "input_schema": _object_schema(
                {
                    "equipment_ids": equipment_ids,
                    "metrics": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "string",
                            "enum": [
                                "quality",
                                "utilization",
                                "throughput",
                                "alarm",
                                "anomaly",
                            ],
                        },
                    },
                    "time_range": time_range,
                    "aggregation": {
                        "type": "string",
                        "enum": ["raw", "hourly", "daily"],
                        "default": "daily",
                    },
                },
                required=["equipment_ids", "metrics", "time_range"],
            ),
        },
        {
            "id": "query_equipment_anomalies",
            "name": "query_equipment_anomalies",
            "read_only": True,
            "description": (
                "Query observed equipment alarms and separately derived anomalies "
                "such as quality OOS events, returning an event-timeline artifact."
            ),
            "input_schema": _object_schema(
                {
                    "equipment_ids": equipment_ids,
                    "time_range": time_range,
                    "severity": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["info", "warning", "critical"],
                        },
                    },
                },
                required=["equipment_ids", "time_range"],
            ),
        },
        {
            "id": "query_process_a_spatial_quality",
            "name": "query_process_a_spatial_quality",
            "read_only": True,
            "description": (
                "Return the latest or task-specific simulated spatial quality "
                "map for Process A equipment. Use this for product-surface, "
                "wafer-style, local OOS, edge-uniformity, or hotspot questions. "
                "At least one of equipment_id or task_uid is required."
            ),
            "input_schema": _object_schema(
                {
                    "equipment_id": {
                        "type": "string",
                        "description": (
                            "Process A canonical equipment id or display name, "
                            "for example A_0 or LITHO-01."
                        ),
                    },
                    "task_uid": {
                        "type": "integer",
                        "description": "Optional exact completed Process A task uid.",
                    },
                },
            ),
        },
    ]


def run_visual_tool(
    context: Any,
    tool_id: str,
    arguments: Mapping[str, Any],
) -> Dict[str, Any]:
    name = str(tool_id)
    equipment_ids = list(arguments.get("equipment_ids") or [])
    if name == "list_equipment_metrics":
        return equipment_metric_catalog(context, equipment_ids)
    if name == "query_equipment_timeseries":
        payload = query_equipment_timeseries(
            context,
            equipment_ids=equipment_ids,
            metrics=list(arguments.get("metrics") or []),
            time_range=_mapping(arguments.get("time_range")),
            aggregation=str(arguments.get("aggregation") or "daily"),
        )
        return {
            **payload,
            "visual_artifacts": [
                build_timeseries_artifact(payload, query_tool=name)
            ],
        }
    if name == "query_equipment_anomalies":
        payload = query_equipment_anomalies(
            context,
            equipment_ids=equipment_ids,
            time_range=_mapping(arguments.get("time_range")),
            severity=list(arguments.get("severity") or []),
        )
        return {
            **payload,
            "visual_artifacts": [
                build_anomaly_artifact(payload, query_tool=name)
            ],
        }
    if name == "query_process_a_spatial_quality":
        payload = query_process_a_spatial_quality(
            context,
            equipment_id=_optional_string(arguments.get("equipment_id")),
            task_uid=arguments.get("task_uid"),
        )
        if not payload.get("found"):
            return {**payload, "visual_artifacts": []}
        return {
            **payload,
            "visual_artifacts": [
                build_process_a_spatial_quality_artifact(
                    payload,
                    query_tool=name,
                )
            ],
        }
    raise ValueError(f"UNKNOWN_VISUAL_TOOL:{name}")


def _object_schema(
    properties: Mapping[str, Any],
    required: list[str] | None = None,
) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required or []),
    }


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _optional_string(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None
