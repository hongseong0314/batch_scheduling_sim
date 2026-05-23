# -*- coding: utf-8 -*-
"""FastAPI routes for production-transition registry/proposal contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query

from src.mes.action_proposals import action_proposals_payload
from src.mes.runtime.operations import operations_payload


def build_production_boundary_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v2/operations")
    def operations() -> Dict[str, Any]:
        return operations_payload(context)

    @router.get("/api/v2/action-proposals")
    def action_proposals(
        correlation_id: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return action_proposals_payload(
            context,
            correlation_id=correlation_id,
            run_id=run_id,
        )

    return router

