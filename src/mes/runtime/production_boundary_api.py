# -*- coding: utf-8 -*-
"""FastAPI routes for production-transition registry/proposal contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.mes.action_proposals import (
    action_proposal_lifecycle_payload,
    action_proposal_lifecycle_summary,
    action_proposals_payload,
    legacy_decision_from_payload,
    outcome_record_from_payload,
)
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

    @router.post("/api/v2/action-proposals/{proposal_id}/legacy-decisions")
    def record_legacy_decision(
        proposal_id: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        decision = legacy_decision_from_payload(
            proposal_id,
            payload,
            default_run_id=context.run_id,
        )
        context.harness.store.add_legacy_decision(decision)
        return {
            "item": decision.to_dict(),
            "summary": action_proposal_lifecycle_summary(
                context.harness.store,
                proposal_id,
                run_id=decision.run_id,
            ),
        }

    @router.get("/api/v2/action-proposals/{proposal_id}/legacy-decisions")
    def legacy_decisions(
        proposal_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        decisions = context.harness.store.legacy_decisions(
            proposal_id,
            run_id=run_id,
        )
        return {
            "proposal_id": proposal_id,
            "run_id": run_id,
            "count": len(decisions),
            "items": [decision.to_dict() for decision in decisions],
        }

    @router.post("/api/v2/action-proposals/{proposal_id}/outcomes")
    def record_outcome(
        proposal_id: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        outcome = outcome_record_from_payload(
            proposal_id,
            payload,
            default_run_id=context.run_id,
        )
        context.harness.store.add_outcome_record(outcome)
        return {
            "item": outcome.to_dict(),
            "summary": action_proposal_lifecycle_summary(
                context.harness.store,
                proposal_id,
                run_id=outcome.run_id,
            ),
        }

    @router.get("/api/v2/action-proposals/{proposal_id}/outcomes")
    def outcome_records(
        proposal_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        outcomes = context.harness.store.outcome_records(
            proposal_id,
            run_id=run_id,
        )
        return {
            "proposal_id": proposal_id,
            "run_id": run_id,
            "count": len(outcomes),
            "items": [outcome.to_dict() for outcome in outcomes],
        }

    @router.get("/api/v2/action-proposals/{proposal_id}/lifecycle")
    def action_proposal_lifecycle(
        proposal_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return action_proposal_lifecycle_payload(
            context,
            proposal_id,
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
