# -*- coding: utf-8 -*-
"""Runtime payload builders for production data contracts and diagnostics."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.persistence.sqlite_schema import INDEX_TABLES, SCHEMA_VERSION, TABLES
from src.mes.production_data import (
    canonical_schema_contract,
    data_quality_diagnostics,
)


def production_schema_payload(context: Any, run_id: Optional[str] = None) -> Dict[str, Any]:
    store = context.harness.store
    return canonical_schema_contract(
        sqlite_schema_version=SCHEMA_VERSION,
        sqlite_tables=dict(TABLES),
        normalized_indexes=list(INDEX_TABLES),
        normalized_index_counts=store.normalized_index_counts(run_id=run_id),
    )


def production_data_quality_payload(
    context: Any,
    run_id: Optional[str] = None,
    at_time: Optional[int] = None,
) -> Dict[str, Any]:
    resolved_run_id = str(run_id or getattr(context, "run_id", "") or "")
    registry = getattr(context, "operation_registry", None)
    operation_ids = registry.operation_ids() if registry is not None else []
    return data_quality_diagnostics(
        context.harness.store.raw_source_records(run_id=resolved_run_id),
        context.harness.store.canonical_ingestion_records(run_id=resolved_run_id),
        context.harness.store.source_key_mappings(run_id=resolved_run_id),
        operation_ids=operation_ids,
        at_time=at_time,
    )
