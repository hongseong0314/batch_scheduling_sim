# -*- coding: utf-8 -*-
"""FastAPI routes for run and ledger index inspection."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.mes.runtime.run_ledger import ledger_index_payload, runs_payload


def build_run_ledger_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v2/runs")
    def runs() -> Dict[str, Any]:
        return runs_payload(context)

    @router.get("/api/v2/ledger-index/{index_name}")
    def ledger_index(
        index_name: str,
        run_id: Optional[str] = Query(None),
        limit: int = Query(200, ge=1, le=1000),
    ) -> Dict[str, Any]:
        try:
            return ledger_index_payload(context, index_name, run_id=run_id, limit=limit)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router

