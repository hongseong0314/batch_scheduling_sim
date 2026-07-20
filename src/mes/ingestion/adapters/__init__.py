# -*- coding: utf-8 -*-
"""Production source adapter package."""

from src.mes.ingestion.adapters.registry import (
    ADAPTERS,
    adapt_source_row,
    adapter_ids,
    get_source_adapter,
    source_adapter_catalog,
)

__all__ = [
    "ADAPTERS",
    "adapt_source_row",
    "adapter_ids",
    "get_source_adapter",
    "source_adapter_catalog",
]
