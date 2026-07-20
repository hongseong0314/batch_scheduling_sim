# -*- coding: utf-8 -*-
"""Scheduled and backfill ingestion job runners.

These helpers are intentionally framework-neutral. Airflow, cron, or an
internal scheduler can call the same functions with adapter rows.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.mes.ingestion.adapters.registry import (
    adapt_source_row,
    get_source_adapter,
    source_adapter_catalog,
)
from src.mes.recommendations import make_id
from src.mes.runtime.legacy_ingestion import ingest_source_record_payload


def ingestion_job_catalog(context: Any | None = None) -> Dict[str, Any]:
    adapters = source_adapter_catalog()["items"]
    runs = ingestion_job_runs_payload(context)["items"] if context is not None else []
    return {
        "scheduler_contract": "framework-neutral-airflow-cron-wrapper-v1",
        "available_adapters": adapters,
        "recommended_modes": ["DELTA", "BACKFILL", "REPROCESS"],
        "job_run_count": len(runs),
        "recent_job_runs": runs[-20:],
    }


def run_ingestion_batch(
    context: Any,
    adapter_id: str,
    rows: Iterable[Dict[str, Any]],
    job_id: str = "",
    mode: str = "DELTA",
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    adapter = get_source_adapter(adapter_id)
    run_id = str(getattr(context, "run_id", "") or "")
    row_items = [dict(row or {}) for row in rows]
    job_run_id = make_id("IJOB")
    raw_count = 0
    canonical_count = 0
    errors: List[Dict[str, Any]] = []
    ingested: List[Dict[str, Any]] = []

    for index, row in enumerate(row_items):
        try:
            payload = adapter.adapt(row)
            result = ingest_source_record_payload(context, payload)
            raw_count += 1 if result.get("raw_record") else 0
            canonical_count += 1 if result.get("canonical_record") else 0
            ingested.append(
                {
                    "index": index,
                    "raw_record_id": (result.get("raw_record") or {}).get("record_id"),
                    "canonical_record_id": (result.get("canonical_record") or {}).get("record_id"),
                }
            )
        except Exception as exc:  # pragma: no cover - defensive job boundary
            errors.append({"index": index, "error": str(exc), "row": row})

    status = "COMPLETED" if not errors else "COMPLETED_WITH_ERRORS"
    result = {
        "job_run_id": job_run_id,
        "job_id": str(job_id or f"{adapter_id}_{mode.lower()}"),
        "run_id": run_id,
        "adapter_id": adapter.adapter_id,
        "mode": str(mode or "DELTA").upper(),
        "status": status,
        "row_count": len(row_items),
        "raw_count": raw_count,
        "canonical_count": canonical_count,
        "error_count": len(errors),
        "errors": errors,
        "ingested": ingested,
        "window": {"start": window_start, "end": window_end},
        "metadata": dict(metadata or {}),
    }
    _record_job_run(context, result)
    return result


def backfill_ingestion(
    context: Any,
    adapter_id: str,
    rows: Iterable[Dict[str, Any]],
    job_id: str = "",
    window_start: Optional[int] = None,
    window_end: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return run_ingestion_batch(
        context,
        adapter_id=adapter_id,
        rows=rows,
        job_id=job_id or f"{adapter_id}_backfill",
        mode="BACKFILL",
        window_start=window_start,
        window_end=window_end,
        metadata=metadata,
    )


def ingestion_job_runs_payload(context: Any | None) -> Dict[str, Any]:
    runs = list(getattr(context, "_ingestion_job_runs", []) if context is not None else [])
    return {"count": len(runs), "items": runs}


def adapt_rows(adapter_id: str, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [adapt_source_row(adapter_id, row) for row in rows]


def _record_job_run(context: Any, result: Dict[str, Any]) -> None:
    runs = getattr(context, "_ingestion_job_runs", None)
    if runs is None:
        runs = []
        setattr(context, "_ingestion_job_runs", runs)
    runs.append(dict(result))
