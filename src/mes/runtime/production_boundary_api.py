# -*- coding: utf-8 -*-
"""FastAPI routes for production-transition registry/proposal contracts."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query

from src.mes.action_proposals import (
    action_proposal_approval_queue_payload,
    action_proposal_lifecycle_payload,
    action_proposal_lifecycle_summary,
    action_proposal_review_from_payload,
    action_proposal_feedback_summary,
    action_proposal_workflow_payload,
    action_proposals_payload,
    legacy_decision_from_payload,
    outcome_record_from_payload,
)
from src.mes.legacy_adapters import legacy_adapter_catalog, legacy_adapter_payload
from src.mes.runtime.legacy_ingestion import (
    canonical_ingestion_records_payload,
    ingest_source_record_payload,
    raw_source_records_payload,
)
from src.mes.runtime.operations import operations_payload, route_graph_payload
from src.mes.runtime.production_data import (
    production_data_quality_payload,
    production_schema_payload,
)
from src.mes.runtime.production_readiness import production_readiness_payload
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

    @router.get("/api/v2/operations/route-graph")
    def route_graph() -> Dict[str, Any]:
        return route_graph_payload(context)

    @router.get("/api/v2/production-readiness")
    def production_readiness() -> Dict[str, Any]:
        return production_readiness_payload(context)

    @router.get("/api/v2/production/schema")
    def production_schema(run_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        return production_schema_payload(context, run_id=run_id)

    @router.get("/api/v2/production/data-quality")
    def production_data_quality(
        run_id: Optional[str] = Query(None),
        at_time: Optional[int] = Query(None, ge=0),
    ) -> Dict[str, Any]:
        return production_data_quality_payload(
            context,
            run_id=run_id,
            at_time=at_time,
        )

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

    @router.get("/api/v2/action-proposals/approval-queue")
    def action_proposal_approval_queue(
        status: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return action_proposal_approval_queue_payload(
            context,
            status=status,
            run_id=run_id,
        )

    @router.post("/api/v2/action-proposals/{proposal_id}/reviews")
    def record_action_proposal_review(
        proposal_id: str,
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        workflow = action_proposal_workflow_payload(context, proposal_id)
        if not workflow.get("found"):
            return workflow
        proposal = workflow["proposal"]
        review = action_proposal_review_from_payload(
            proposal_id,
            payload,
            default_run_id=proposal.get("run_id") or context.run_id,
            default_correlation_id=proposal.get("correlation_id") or "",
        )
        context.harness.store.add_action_proposal_review(review)
        return {
            "item": review.to_dict(),
            "workflow": action_proposal_workflow_payload(
                context,
                proposal_id,
                run_id=review.run_id,
            ),
        }

    @router.get("/api/v2/action-proposals/{proposal_id}/workflow")
    def action_proposal_workflow(
        proposal_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return action_proposal_workflow_payload(context, proposal_id, run_id=run_id)

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

    @router.get("/api/v2/action-proposals/{proposal_id}/feedback-summary")
    def action_proposal_feedback(
        proposal_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return action_proposal_feedback_summary(
            context,
            proposal_id,
            run_id=run_id,
        )

    @router.get("/api/v2/legacy-adapters")
    def legacy_adapters() -> Dict[str, Any]:
        return legacy_adapter_catalog()

    @router.post("/api/v2/legacy-adapters/{adapter_id}/ingest")
    def ingest_legacy_adapter_row(
        adapter_id: str,
        row: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        payload = legacy_adapter_payload(adapter_id, row)
        result = ingest_source_record_payload(context, payload)
        result["adapter_id"] = adapter_id
        result["adapted_payload"] = payload
        return result

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

    @router.post("/api/v2/ingestion/source-records")
    def ingest_source_record(
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        return ingest_source_record_payload(context, payload)

    @router.get("/api/v2/ingestion/source-records")
    def raw_source_records(
        source_system: Optional[str] = Query(None),
        entity_type: Optional[str] = Query(None),
        record_id: Optional[str] = Query(None),
        source_table: Optional[str] = Query(None),
        source_pk: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return raw_source_records_payload(
            context,
            source_system=source_system,
            entity_type=entity_type,
            record_id=record_id,
            source_table=source_table,
            source_pk=source_pk,
            run_id=run_id,
        )

    @router.get("/api/v2/ingestion/canonical-records")
    def canonical_ingestion_records(
        entity_type: Optional[str] = Query(None),
        canonical_id: Optional[str] = Query(None),
        raw_record_id: Optional[str] = Query(None),
        record_id: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return canonical_ingestion_records_payload(
            context,
            entity_type=entity_type,
            canonical_id=canonical_id,
            raw_record_id=raw_record_id,
            record_id=record_id,
            run_id=run_id,
        )

    return router
