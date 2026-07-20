"""Versioned public contracts for the spatial factory twin."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA_VERSION = "factory-twin.v1"


class TwinModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SpatialEntityV1(TwinModel):
    id: str
    entity_type: str
    display_name: str
    position: List[float] = Field(min_length=3, max_length=3)
    rotation: List[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    size: List[float] = Field(min_length=3, max_length=3)
    operation_id: Optional[str] = None
    archetype: str = "generic_process_cell"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RouteLayoutV1(TwinModel):
    id: str
    entity_type: Literal["route"] = "route"
    display_name: str
    from_operation_id: str
    to_operation_id: str
    points: List[List[float]]
    travel_time: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FactoryTwinLayoutV1(TwinModel):
    schema_version: Literal["factory-twin.v1"] = SCHEMA_VERSION
    layout_id: str
    spatial_source: Literal["CONFIGURED", "AUTO_LAYOUT"]
    operations: List[SpatialEntityV1]
    equipment: List[SpatialEntityV1]
    queues: List[SpatialEntityV1]
    routes: List[RouteLayoutV1]
    warehouse: SpatialEntityV1
    bounds: Dict[str, List[float]]
    diagnostics: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> "FactoryTwinLayoutV1":
        operation_ids = {item.id for item in self.operations}
        for item in [*self.equipment, *self.queues]:
            if item.operation_id and item.operation_id not in operation_ids:
                raise ValueError(f"unknown operation reference: {item.operation_id}")
        for route in self.routes:
            if route.from_operation_id not in operation_ids:
                raise ValueError(f"unknown route source: {route.from_operation_id}")
            if route.to_operation_id not in operation_ids:
                raise ValueError(f"unknown route target: {route.to_operation_id}")
        return self


class EquipmentStateV1(TwinModel):
    equipment_id: str
    operation_id: str
    status: str
    batch_size: int
    task_uids: List[int] = Field(default_factory=list)
    start_time: Optional[int] = None
    finish_time: Optional[int] = None
    progress: Optional[float] = None
    recipe_summary: Optional[Dict[str, Any]] = None
    health_summary: Optional[Dict[str, Any]] = None
    evidence_source: str = "OBSERVED"


class QueueStateV1(TwinModel):
    queue_id: str
    operation_id: str
    queue_type: str
    task_uids: List[int] = Field(default_factory=list)
    count: int = 0
    visible_task_uids: List[int] = Field(default_factory=list)


class WorkItemStateV1(TwinModel):
    task_uid: int
    lot_id: str
    carrier_id: Optional[str] = None
    operation_id: Optional[str] = None
    location_type: str
    location_id: str
    status: str
    due_date: Optional[int] = None
    customer_id: Optional[str] = None
    quality_summary: Dict[str, Any] = Field(default_factory=dict)


class CarrierStateV1(TwinModel):
    carrier_id: str
    transfer_id: str
    task_uids: List[int]
    route_id: str
    from_operation_id: str
    to_operation_id: str
    dispatch_time: int
    arrival_time: int
    status: str
    progress: float


class TransferStateV1(TwinModel):
    transfer_id: str
    carrier_id: str
    task_uids: List[int]
    from_operation_id: str
    to_operation_id: str
    route_id: str
    dispatch_time: int
    arrival_time: int
    status: str
    progress: float


class WarehouseStateV1(TwinModel):
    warehouse_id: str = "WAREHOUSE_FINISHED"
    completed_count: int = 0
    recent_task_uids: List[int] = Field(default_factory=list)
    visible_slots: int = 48


class FactoryTwinSnapshotV1(TwinModel):
    schema_version: Literal["factory-twin.v1"] = SCHEMA_VERSION
    run_id: str
    snapshot_id: str
    sequence: int
    time: int
    state_source: Literal["SIMULATOR", "CANONICAL_TWIN"]
    spatial_source: Literal["CONFIGURED", "AUTO_LAYOUT"]
    transport_source: Literal["OBSERVED", "SIMULATED", "INFERRED_VISUAL"]
    layout_id: str
    equipment: List[EquipmentStateV1]
    queues: List[QueueStateV1]
    work_items: List[WorkItemStateV1]
    carriers: List[CarrierStateV1]
    transfers: List[TransferStateV1]
    warehouse: WarehouseStateV1
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class FactoryTwinDeltaV1(TwinModel):
    schema_version: Literal["factory-twin.v1"] = SCHEMA_VERSION
    run_id: str
    base_sequence: int
    sequence: int
    time: int
    state_source: Literal["SIMULATOR", "CANONICAL_TWIN"]
    upsert: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    remove: Dict[str, List[str]] = Field(default_factory=dict)


__all__ = [
    "CarrierStateV1",
    "EquipmentStateV1",
    "FactoryTwinDeltaV1",
    "FactoryTwinLayoutV1",
    "FactoryTwinSnapshotV1",
    "QueueStateV1",
    "RouteLayoutV1",
    "SCHEMA_VERSION",
    "SpatialEntityV1",
    "TransferStateV1",
    "WarehouseStateV1",
    "WorkItemStateV1",
]
