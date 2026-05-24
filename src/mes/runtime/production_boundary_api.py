# -*- coding: utf-8 -*-
"""FastAPI routes for production-transition registry/proposal contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.mes.action_proposals import action_proposals_payload
from src.mes.runtime.operations import operations_payload
from src.mes.runtime.source_key_mappings import (
    resolve_source_key_mapping_payload,
    source_key_mappings_payload,
    upsert_source_key_mapping_payload,
)


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

    @router.post("/api/v2/source-key-mappings")
    def upsert_source_key_mapping(
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        return upsert_source_key_mapping_payload(context, payload)

    @router.get("/api/v2/source-key-mappings")
    def source_key_mappings(
        source_system: Optional[str] = Query(None),
        entity_type: Optional[str] = Query(None),
        canonical_id: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return source_key_mappings_payload(
            context,
            source_system=source_system,
            entity_type=entity_type,
            canonical_id=canonical_id,
            run_id=run_id,
        )

    @router.get("/api/v2/source-key-mappings/resolve")
    def resolve_source_key_mapping(
        source_system: str = Query(...),
        source_table: str = Query(...),
        source_pk: str = Query(...),
        entity_type: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return resolve_source_key_mapping_payload(
            context,
            source_system=source_system,
            source_table=source_table,
            source_pk=source_pk,
            entity_type=entity_type,
            run_id=run_id,
        )

    return router
