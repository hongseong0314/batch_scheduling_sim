# -*- coding: utf-8 -*-
"""FastAPI routes for decision, assignment, and genealogy traceability."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from fastapi import Body

from src.mes.runtime.assignment_trace import assignment_trace as build_assignment_trace
from src.mes.runtime.candidate_portfolio import (
    candidate_portfolio as build_candidate_portfolio,
    latest_candidate_portfolio,
)
from src.mes.runtime.decision_trace import decision_chain as build_decision_chain
from src.mes.runtime.digital_twin import (
    canonical_candidate_preview_payload,
    canonical_decision_state_payload,
    canonical_genealogy_payload,
    canonical_twin_state_payload,
    run_canonical_recommendation_payload,
)
from src.mes.runtime.genealogy import (
    digital_twin_state_at as build_digital_twin_state_at,
    equipment_genealogy as build_equipment_genealogy,
    execution_ledger as build_execution_ledger,
    lot_genealogy as build_lot_genealogy,
    task_genealogy as build_task_genealogy,
)


def build_trace_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v2/decision-chain/{correlation_id}")
    def decision_chain(
        correlation_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return build_decision_chain(context, correlation_id, run_id=run_id)

    @router.get("/api/v2/candidate-portfolio/latest")
    def candidate_portfolio_latest() -> Dict[str, Any]:
        return latest_candidate_portfolio(context)

    @router.get("/api/v2/candidate-portfolio/{correlation_id}")
    def candidate_portfolio(
        correlation_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return build_candidate_portfolio(context, correlation_id, run_id=run_id)

    @router.get("/api/v2/assignment-trace")
    def assignment_trace(
        equipment_id: Optional[str] = Query(None),
        task_uid: Optional[int] = Query(None),
        correlation_id: Optional[str] = Query(None),
        candidate_id: Optional[str] = Query(None),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return build_assignment_trace(
            context,
            equipment_id=equipment_id,
            task_uid=task_uid,
            correlation_id=correlation_id,
            candidate_id=candidate_id,
            run_id=run_id,
        )

    @router.get("/api/v2/genealogy/task/{task_uid}")
    def genealogy_task(task_uid: int, run_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        return build_task_genealogy(context, task_uid, run_id=run_id)

    @router.get("/api/v2/genealogy/equipment/{equipment_id}")
    def genealogy_equipment(equipment_id: str, run_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        return build_equipment_genealogy(context, equipment_id, run_id=run_id)

    @router.get("/api/v2/genealogy/lot/{lot_id}")
    def genealogy_lot(lot_id: str, run_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        return build_lot_genealogy(context, lot_id, run_id=run_id)

    @router.get("/api/v2/genealogy/canonical/{entity_type}/{canonical_id}")
    def genealogy_canonical(
        entity_type: str,
        canonical_id: str,
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return canonical_genealogy_payload(
            context,
            entity_type,
            canonical_id,
            run_id=run_id,
        )

    @router.get("/api/v2/execution-ledger/{correlation_id}")
    def execution_ledger(correlation_id: str, run_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        return build_execution_ledger(context, correlation_id, run_id=run_id)

    @router.get("/api/v2/digital-twin/state-at")
    def digital_twin_state_at(
        time: int = Query(..., ge=0),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return build_digital_twin_state_at(context, time, run_id=run_id)

    @router.get("/api/v2/digital-twin/canonical-state")
    def canonical_twin_state(
        at_time: Optional[int] = Query(None, ge=0),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return canonical_twin_state_payload(context, at_time=at_time, run_id=run_id)

    @router.get("/api/v2/digital-twin/canonical-decision-state")
    def canonical_decision_state(
        at_time: Optional[int] = Query(None, ge=0),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return canonical_decision_state_payload(context, at_time=at_time, run_id=run_id)

    @router.get("/api/v2/digital-twin/candidate-preview")
    def canonical_candidate_preview(
        stage: str = Query("AUTO"),
        at_time: Optional[int] = Query(None, ge=0),
        run_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        return canonical_candidate_preview_payload(
            context,
            stage=stage,
            at_time=at_time,
            run_id=run_id,
        )

    @router.post("/api/v2/digital-twin/recommendation-run")
    def canonical_recommendation_run(
        payload: Dict[str, Any] = Body(default_factory=dict),
    ) -> Dict[str, Any]:
        return run_canonical_recommendation_payload(context, payload)

    return router
