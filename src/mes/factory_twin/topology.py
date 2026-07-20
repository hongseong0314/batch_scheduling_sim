"""Operation-registry topology helpers for deterministic spatial layout."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, Iterable, List, Tuple

from src.mes.operations.registry import OperationRegistry


def operation_depths(registry: OperationRegistry) -> Dict[str, int]:
    operation_ids = registry.operation_ids()
    indegree = {operation_id: 0 for operation_id in operation_ids}
    downstream: Dict[str, List[str]] = defaultdict(list)
    for operation_id in operation_ids:
        operation = registry.get_operation(operation_id)
        for target in operation.downstream_operation_ids:
            if target not in indegree:
                continue
            downstream[operation_id].append(target)
            indegree[target] += 1

    queue = deque(operation_id for operation_id in operation_ids if indegree[operation_id] == 0)
    depths = {operation_id: 0 for operation_id in operation_ids}
    visited = set()
    while queue:
        source = queue.popleft()
        visited.add(source)
        for target in downstream[source]:
            depths[target] = max(depths[target], depths[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    # Cyclic or disconnected registry entries still receive deterministic slots.
    next_depth = max(depths.values(), default=-1) + 1
    for operation_id in operation_ids:
        if operation_id not in visited:
            depths[operation_id] = next_depth
            next_depth += 1
    return depths


def operations_by_depth(
    registry: OperationRegistry,
) -> Dict[int, List[str]]:
    grouped: Dict[int, List[str]] = defaultdict(list)
    for operation_id, depth in operation_depths(registry).items():
        grouped[depth].append(operation_id)
    order = {operation_id: index for index, operation_id in enumerate(registry.operation_ids())}
    return {
        depth: sorted(items, key=lambda operation_id: order[operation_id])
        for depth, items in grouped.items()
    }


def route_edges(registry: OperationRegistry) -> Iterable[Tuple[str, str]]:
    for operation_id in registry.operation_ids():
        operation = registry.get_operation(operation_id)
        for target in operation.downstream_operation_ids:
            if registry.find_operation(target) is not None:
                yield operation_id, target


__all__ = ["operation_depths", "operations_by_depth", "route_edges"]
