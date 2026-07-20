# -*- coding: utf-8 -*-
"""Compatibility facade for source-specific legacy adapters.

The production-ready adapter implementations live under
``src.mes.ingestion.adapters``. This module keeps the V1 API surface stable for
existing tests and routes.
"""

from __future__ import annotations

from typing import Any, Dict

from src.mes.ingestion.adapters.registry import (
    adapt_source_row,
    adapter_ids,
    source_adapter_catalog,
)


ADAPTER_IDS = adapter_ids()


def legacy_adapter_catalog() -> Dict[str, Any]:
    return source_adapter_catalog()


def legacy_adapter_payload(adapter_id: str, row: Dict[str, Any]) -> Dict[str, Any]:
    return adapt_source_row(adapter_id, row)
