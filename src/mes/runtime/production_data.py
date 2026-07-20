# -*- coding: utf-8 -*-
"""Runtime payload builders for production data contracts and diagnostics."""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.mes.persistence.sqlite_schema import INDEX_TABLES, SCHEMA_VERSION, TABLES
from src.mes.production_data import canonical_schema_contract
from src.mes.runtime.data_quality import production_data_quality_payload


def production_schema_payload(context: Any, run_id: Optional[str] = None) -> Dict[str, Any]:
    store = context.harness.store
    return canonical_schema_contract(
        sqlite_schema_version=SCHEMA_VERSION,
        sqlite_tables=dict(TABLES),
        normalized_indexes=list(INDEX_TABLES),
        normalized_index_counts=store.normalized_index_counts(run_id=run_id),
    )


__all__ = ["production_schema_payload", "production_data_quality_payload"]
