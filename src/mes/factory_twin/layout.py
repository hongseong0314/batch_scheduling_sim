"""Deterministic spatial layout derived from the operation registry."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, Mapping

from src.mes.factory_twin.contracts import (
    FactoryTwinLayoutV1,
    RouteLayoutV1,
    SpatialEntityV1,
)
from src.mes.factory_twin.topology import operation_depths, operations_by_depth, route_edges
from src.mes.operations.registry import OperationRegistry


ARCHETYPES = {
    "process_qa": "lithography_cell",
    "clean_qa": "wet_clean_cell",
    "packing": "packing_cell",
}


def build_factory_twin_layout(
    registry: OperationRegistry,
    config: Mapping[str, Any] | None = None,
) -> FactoryTwinLayoutV1:
    resolved = dict(config or {})
    spacing = float(resolved.get("operation_spacing", 28) or 28)
    equipment_spacing = float(resolved.get("equipment_spacing", 5) or 5)
    grouped = operations_by_depth(registry)
    depths = operation_depths(registry)
    configured_count = 0
    operation_positions: Dict[str, list[float]] = {}
    operation_archetypes: Dict[str, str] = {}
    operations = []

    for depth in sorted(grouped):
        siblings = grouped[depth]
        for sibling_index, operation_id in enumerate(siblings):
            operation = registry.get_operation(operation_id)
            visual = dict(operation.metadata.get("visual", {}) or {})
            configured_position = visual.get("position")
            if isinstance(configured_position, (list, tuple)) and len(configured_position) == 3:
                position = [float(value) for value in configured_position]
                configured_count += 1
            else:
                z = (sibling_index - (len(siblings) - 1) / 2.0) * 22.0
                position = [float(depth) * spacing, 0.0, z]
            operation_positions[operation_id] = position
            operation_archetypes[operation_id] = str(
                visual.get("archetype")
                or ARCHETYPES.get(operation.operation_type, "generic_process_cell")
            )
            footprint = visual.get("footprint", [20, 16])
            operations.append(
                SpatialEntityV1(
                    id=operation_id,
                    entity_type="operation",
                    display_name=operation.display_name,
                    position=position,
                    size=[float(footprint[0]), 0.15, float(footprint[1])],
                    operation_id=operation_id,
                    archetype=operation_archetypes[operation_id],
                    metadata={
                        "operation_type": operation.operation_type,
                        "batch_size": operation.batch_size,
                        "process_time": operation.process_time,
                        "route_depth": depth,
                    },
                )
            )

    equipment = []
    queues = []
    for operation_id in registry.operation_ids():
        operation = registry.get_operation(operation_id)
        origin = operation_positions[operation_id]
        tools = registry.equipment_for_operation(operation_id)
        columns = max(1, min(3, math.ceil(math.sqrt(max(1, len(tools))))))
        for index, tool in enumerate(tools):
            visual = dict(tool.metadata.get("visual", {}) or {})
            slot = int(visual.get("slot", index) or 0)
            row, column = divmod(slot, columns)
            x = origin[0] + (column - (columns - 1) / 2.0) * equipment_spacing
            z = origin[2] + (row - 0.5) * equipment_spacing
            equipment.append(
                SpatialEntityV1(
                    id=tool.equipment_id,
                    entity_type="equipment",
                    display_name=tool.display_name,
                    position=[x, 1.45, z],
                    rotation=[0.0, float(visual.get("rotation_y", 0) or 0), 0.0],
                    size=[3.8, 2.9, 3.1],
                    operation_id=operation_id,
                    archetype=operation_archetypes[operation_id],
                    metadata={"batch_size": tool.batch_size, "slot": slot},
                )
            )
        queue_keys = dict(operation.queue_keys or {})
        queue_keys.setdefault("output", "output_uids")
        queue_order = [
            (queue_type, state_key)
            for queue_type, state_key in queue_keys.items()
            if not (
                queue_type == "incoming"
                and str(state_key).startswith("incoming_from_")
            )
        ]
        for index, (queue_type, state_key) in enumerate(queue_order):
            x_offset = -8.0 if queue_type in {"wait", "incoming", "rework", "hold"} else 8.0
            display_suffix = "Finish" if queue_type == "output" else queue_type.title()
            queues.append(
                SpatialEntityV1(
                    id=f"QUEUE_{operation_id}_{queue_type.upper()}",
                    entity_type="queue",
                    display_name=f"{operation.display_name} {display_suffix}",
                    position=[origin[0] + x_offset, 0.45, origin[2] + (index - 1) * 2.7],
                    size=[4.6, 0.9, 2.2],
                    operation_id=operation_id,
                    archetype="finish_buffer" if queue_type == "output" else "wait_pool",
                    metadata={"queue_type": queue_type, "state_key": state_key},
                )
            )

    travel_times = dict(resolved.get("route_travel_time", {}) or {})
    routes = []
    for source, target in route_edges(registry):
        start = operation_positions[source]
        end = operation_positions[target]
        route_id = f"ROUTE_{source}_{target}"
        rail_height = 7.0
        routes.append(
            RouteLayoutV1(
                id=route_id,
                display_name=f"{source} to {target} OHT",
                from_operation_id=source,
                to_operation_id=target,
                points=[
                    [start[0] + 7.5, rail_height, start[2]],
                    [(start[0] + end[0]) / 2.0, rail_height, start[2]],
                    [(start[0] + end[0]) / 2.0, rail_height, end[2]],
                    [end[0] - 7.5, rail_height, end[2]],
                ],
                travel_time=max(0, int(travel_times.get(f"{source}>{target}", 0) or 0)),
            )
        )

    max_depth = max(depths.values(), default=0)
    warehouse_position = [(max_depth + 1) * spacing, 1.8, 0.0]
    warehouse = SpatialEntityV1(
        id="WAREHOUSE_FINISHED",
        entity_type="warehouse",
        display_name="Finished Goods Warehouse",
        position=warehouse_position,
        size=[12.0, 3.6, 13.0],
        archetype="warehouse",
        metadata={"terminal_operations": [
            operation_id
            for operation_id in registry.operation_ids()
            if not registry.get_operation(operation_id).downstream_operation_ids
        ]},
    )
    xs = [entity.position[0] for entity in [*operations, *equipment, *queues, warehouse]]
    zs = [entity.position[2] for entity in [*operations, *equipment, *queues, warehouse]]
    bounds = {
        "min": [min(xs, default=-10) - 12, 0.0, min(zs, default=-10) - 12],
        "max": [max(xs, default=10) + 12, 10.0, max(zs, default=10) + 12],
    }
    identity_payload = {
        "registry": registry.to_payload(),
        "layout": resolved,
        "positions": operation_positions,
    }
    digest = hashlib.sha256(
        json.dumps(identity_payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16].upper()
    return FactoryTwinLayoutV1(
        layout_id=f"LAYOUT_{digest}",
        spatial_source="CONFIGURED"
        if configured_count == len(operations) and operations
        else "AUTO_LAYOUT",
        operations=operations,
        equipment=equipment,
        queues=queues,
        routes=routes,
        warehouse=warehouse,
        bounds=bounds,
        diagnostics={
            "configured_operation_count": configured_count,
            "auto_layout_operation_count": len(operations) - configured_count,
        },
    )


__all__ = ["build_factory_twin_layout"]
