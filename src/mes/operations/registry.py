# -*- coding: utf-8 -*-
"""Operation and equipment registry for production-facing MES runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping


DEFAULT_SIMULATOR_OPERATIONS = ("A", "B", "C")


@dataclass(frozen=True)
class OperationDefinition:
    operation_id: str
    display_name: str
    operation_type: str
    equipment_group_id: str
    execution_boundary: str = "SIMULATOR_STAGE"
    upstream_operation_ids: List[str] = field(default_factory=list)
    downstream_operation_ids: List[str] = field(default_factory=list)
    queue_keys: Dict[str, str] = field(default_factory=dict)
    batch_size: int = 1
    process_time: int = 1
    simulator_env_attr: str = ""
    l1_policy_key: str = ""
    l2_policy_key: str = ""
    l3_policy_key: str = "meta_scheduler_L3"
    l4_policy_key: str = "objective_policy_L4"
    legacy_submission_mode: str = "SIMULATOR_ONLY"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EquipmentDefinition:
    equipment_id: str
    display_name: str
    equipment_group_id: str
    capable_operations: List[str] = field(default_factory=list)
    batch_size: int = 1
    execution_boundary: str = "SIMULATOR_STAGE"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OperationRegistry:
    """Read-only registry for operation and equipment definitions."""

    def __init__(
        self,
        operations: Iterable[OperationDefinition],
        equipment: Iterable[EquipmentDefinition],
    ) -> None:
        operations = list(operations)
        equipment = list(equipment)
        self._operations = {item.operation_id: item for item in operations}
        self._equipment = {item.equipment_id: item for item in equipment}
        self._operation_order = [item.operation_id for item in operations]
        self._equipment_order = [item.equipment_id for item in equipment]

    def operation_ids(self) -> List[str]:
        return list(self._operation_order)

    def equipment_ids(self) -> List[str]:
        return list(self._equipment_order)

    def get_operation(self, operation_id: str) -> OperationDefinition:
        key = str(operation_id)
        if key not in self._operations:
            raise KeyError(f"unknown operation: {operation_id}")
        return self._operations[key]

    def get_equipment(self, equipment_id: str) -> EquipmentDefinition:
        key = str(equipment_id)
        if key not in self._equipment:
            raise KeyError(f"unknown equipment: {equipment_id}")
        return self._equipment[key]

    def find_operation(self, operation_id: str) -> OperationDefinition | None:
        return self._operations.get(str(operation_id))

    def find_equipment(self, equipment_id: str) -> EquipmentDefinition | None:
        return self._equipment.get(str(equipment_id))

    def equipment_for_operation(self, operation_id: str) -> List[EquipmentDefinition]:
        key = str(operation_id)
        return [
            self._equipment[equipment_id]
            for equipment_id in self._equipment_order
            if key in self._equipment[equipment_id].capable_operations
        ]

    def operation_for_equipment(self, equipment_id: str) -> OperationDefinition | None:
        equipment = self.find_equipment(equipment_id)
        if equipment is None or not equipment.capable_operations:
            return None
        return self.find_operation(equipment.capable_operations[0])

    def to_payload(self) -> Dict[str, Any]:
        operations = [self._operations[key].to_dict() for key in self._operation_order]
        equipment = [self._equipment[key].to_dict() for key in self._equipment_order]
        return {
            "count": len(operations),
            "equipment_count": len(equipment),
            "items": operations,
            "equipment": equipment,
        }

    def route_graph_payload(self) -> Dict[str, Any]:
        nodes = [self._operations[key].to_dict() for key in self._operation_order]
        edges = []
        for operation in nodes:
            source = operation["operation_id"]
            for target in operation.get("downstream_operation_ids", []) or []:
                edges.append(
                    {"from_operation_id": source, "to_operation_id": str(target)}
                )
        equipment_by_operation = {
            operation_id: [
                equipment.to_dict()
                for equipment in self.equipment_for_operation(operation_id)
            ]
            for operation_id in self._operation_order
        }
        return {
            "operation_count": len(nodes),
            "equipment_count": len(self._equipment_order),
            "nodes": nodes,
            "edges": edges,
            "equipment_by_operation": equipment_by_operation,
        }


def build_default_operation_registry(config: Mapping[str, Any] | None = None) -> OperationRegistry:
    resolved = dict(config or {})
    if isinstance(resolved.get("operations"), list):
        operations = [_operation_from_config(item) for item in resolved["operations"]]
        equipment = [
            _equipment_from_config(item)
            for item in resolved.get("equipment", [])
            if isinstance(item, Mapping)
        ]
        return OperationRegistry(operations=operations, equipment=equipment)

    operations = [_default_simulator_operation(stage, resolved) for stage in DEFAULT_SIMULATOR_OPERATIONS]
    equipment: List[EquipmentDefinition] = []
    for operation in operations:
        equipment.extend(_default_simulator_equipment(operation, resolved))
    return OperationRegistry(operations=operations, equipment=equipment)


def _operation_from_config(item: Mapping[str, Any]) -> OperationDefinition:
    operation_id = str(item["operation_id"])
    return OperationDefinition(
        operation_id=operation_id,
        display_name=str(item.get("display_name") or operation_id),
        operation_type=str(item.get("operation_type") or "process"),
        equipment_group_id=str(item.get("equipment_group_id") or operation_id),
        execution_boundary=str(item.get("execution_boundary") or "LEGACY_MES_REVIEW"),
        upstream_operation_ids=[str(value) for value in item.get("upstream_operation_ids", [])],
        downstream_operation_ids=[str(value) for value in item.get("downstream_operation_ids", [])],
        queue_keys=dict(item.get("queue_keys", {}) or {}),
        batch_size=max(1, int(item.get("batch_size", 1) or 1)),
        process_time=max(1, int(item.get("process_time", 1) or 1)),
        simulator_env_attr=str(item.get("simulator_env_attr", "")),
        l1_policy_key=str(item.get("l1_policy_key", "")),
        l2_policy_key=str(item.get("l2_policy_key", "")),
        l3_policy_key=str(item.get("l3_policy_key", "meta_scheduler_L3")),
        l4_policy_key=str(item.get("l4_policy_key", "objective_policy_L4")),
        legacy_submission_mode=str(item.get("legacy_submission_mode", "OUTBOX")),
        metadata=dict(item.get("metadata", {}) or {}),
    )


def _equipment_from_config(item: Mapping[str, Any]) -> EquipmentDefinition:
    equipment_id = str(item["equipment_id"])
    return EquipmentDefinition(
        equipment_id=equipment_id,
        display_name=str(item.get("display_name") or equipment_id),
        equipment_group_id=str(item.get("equipment_group_id") or ""),
        capable_operations=[str(value) for value in item.get("capable_operations", [])],
        batch_size=max(1, int(item.get("batch_size", 1) or 1)),
        execution_boundary=str(item.get("execution_boundary") or "LEGACY_MES_REVIEW"),
        metadata=dict(item.get("metadata", {}) or {}),
    )


def _default_simulator_operation(stage: str, config: Mapping[str, Any]) -> OperationDefinition:
    display_names = dict(config.get("stage_display_names", {}) or {})
    display_name = str(display_names.get(stage) or _default_stage_display_name(stage))
    upstream = {"A": [], "B": ["A"], "C": ["B"]}[stage]
    downstream = {"A": ["B"], "B": ["C"], "C": []}[stage]
    operation_type = {"A": "process_qa", "B": "clean_qa", "C": "packing"}[stage]
    l1_policy_key = {"A": "scheduler_A", "B": "scheduler_B", "C": "packing_C"}[stage]
    l2_policy_key = {"A": "tuner_A", "B": "tuner_B", "C": "packing_quality_rule"}[stage]
    return OperationDefinition(
        operation_id=stage,
        display_name=display_name,
        operation_type=operation_type,
        equipment_group_id=stage,
        execution_boundary="SIMULATOR_STAGE",
        upstream_operation_ids=upstream,
        downstream_operation_ids=downstream,
        queue_keys=_default_queue_keys(stage),
        batch_size=max(1, int(config.get(f"batch_size_{stage}", 1) or 1)),
        process_time=max(1, int(config.get(f"process_time_{stage}", 1) or 1)),
        simulator_env_attr=f"env_{stage}",
        l1_policy_key=l1_policy_key,
        l2_policy_key=l2_policy_key,
        legacy_submission_mode="SIMULATOR_ONLY",
        metadata={"source": "default_simulator"},
    )


def _default_simulator_equipment(
    operation: OperationDefinition,
    config: Mapping[str, Any],
) -> List[EquipmentDefinition]:
    configured_names = dict(config.get("equipment_display_names", {}) or {})
    count = max(0, int(config.get(f"num_machines_{operation.operation_id}", 0) or 0))
    return [
        EquipmentDefinition(
            equipment_id=f"{operation.operation_id}_{index}",
            display_name=str(
                configured_names.get(f"{operation.operation_id}_{index}")
                or f"{operation.operation_id}_{index}"
            ),
            equipment_group_id=operation.equipment_group_id,
            capable_operations=[operation.operation_id],
            batch_size=operation.batch_size,
            execution_boundary=operation.execution_boundary,
            metadata={"source": "default_simulator"},
        )
        for index in range(count)
    ]


def _default_stage_display_name(stage: str) -> str:
    return {
        "A": "Process QA",
        "B": "Clean QA",
        "C": "Packing",
    }.get(stage, stage)


def _default_queue_keys(stage: str) -> Dict[str, str]:
    queue_keys = {
        "wait": "wait_pool_uids",
        "rework": "rework_pool_uids",
    }
    if stage == "B":
        queue_keys["incoming"] = "incoming_from_A_uids"
    elif stage == "C":
        queue_keys["incoming"] = "incoming_from_B_uids"
    return queue_keys
