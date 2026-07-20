# -*- coding: utf-8 -*-
"""Registry for source adapters used by production ingestion jobs."""

from __future__ import annotations

from typing import Any, Dict, Iterable

from src.mes.ingestion.adapters.base import ADAPTER_INTERFACE_VERSION, SourceAdapter
from src.mes.ingestion.adapters.erp_adapter import ERPOrderLotAdapter
from src.mes.ingestion.adapters.fdc_adapter import (
    FDCEquipmentEventAdapter,
    FDCQualityEventAdapter,
)
from src.mes.ingestion.adapters.legacy_mes_adapter import (
    LegacyMESAssignmentAdapter,
    LegacyMESEquipmentAdapter,
    LegacyMESWIPAdapter,
)
from src.mes.ingestion.adapters.rms_adapter import (
    RMSRecipeAdapter,
    RMSRecipeEligibilityAdapter,
)


def _build_adapters() -> Dict[str, SourceAdapter]:
    adapters: Iterable[SourceAdapter] = (
        LegacyMESWIPAdapter(),
        LegacyMESEquipmentAdapter(),
        LegacyMESAssignmentAdapter(),
        FDCQualityEventAdapter(),
        FDCEquipmentEventAdapter(),
        RMSRecipeAdapter(),
        RMSRecipeEligibilityAdapter(),
        ERPOrderLotAdapter(),
    )
    return {adapter.adapter_id: adapter for adapter in adapters}


ADAPTERS: Dict[str, SourceAdapter] = _build_adapters()


def source_adapter_catalog() -> Dict[str, Any]:
    items = [adapter.metadata() for adapter in ADAPTERS.values()]
    return {
        "interface_version": ADAPTER_INTERFACE_VERSION,
        "count": len(items),
        "items": sorted(items, key=lambda item: item["adapter_id"]),
    }


def get_source_adapter(adapter_id: str) -> SourceAdapter:
    adapter = ADAPTERS.get(str(adapter_id))
    if adapter is None:
        raise KeyError(f"unknown source adapter: {adapter_id}")
    return adapter


def adapt_source_row(adapter_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return get_source_adapter(adapter_id).adapt(dict(row or {}))


def adapter_ids() -> tuple[str, ...]:
    return tuple(sorted(ADAPTERS.keys()))
