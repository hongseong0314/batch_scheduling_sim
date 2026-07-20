# -*- coding: utf-8 -*-
"""Runtime payload builders for production data quality diagnostics."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.production_data import data_quality_diagnostics


def production_data_quality_payload(
    context: Any,
    run_id: Optional[str] = None,
    at_time: Optional[int] = None,
    late_threshold: int = 24,
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
        late_threshold=late_threshold,
    )
