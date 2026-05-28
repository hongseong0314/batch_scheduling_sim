# -*- coding: utf-8 -*-
"""FastAPI routes for the legacy-compatible MES v1 API."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from src.mes.domain import AIRecommendation
from src.mes.runtime.common import normalize_target_stage
from src.mes.runtime.live_state import fab_kpis, mes_state
from src.mes.runtime.simulation_control import ready_stages, run_auto_cycle, run_single_cycle


def build_v1_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v1/decision-state")
    def get_decision_state() -> Dict[str, Any]:
        return context.env.get_decision_state()

    @router.get("/api/v1/kpis/fab")
    def get_fab_kpis() -> Dict[str, Any]:
        return fab_kpis(context)

    @router.get("/api/v1/wip")
    def get_wip() -> Dict[str, Any]:
        state = mes_state(context)
        return {"time": state.get("time", 0), "wip": state.get("wip", {})}

    @router.get("/api/v1/equipment")
    def get_equipment() -> Dict[str, Any]:
        state = mes_state(context)
        items = context.harness.store.equipment()
        return {
            "time": state.get("time", 0),
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/lots")
    def get_lots() -> Dict[str, Any]:
        state = mes_state(context)
        items = context.harness.store.lots()
        return {
            "time": state.get("time", 0),
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/wafers")
    def get_wafers(lot_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        state = mes_state(context)
        items = context.harness.store.wafers(lot_id)
        return {
            "time": state.get("time", 0),
            "lot_id": lot_id,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/recipes")
    def get_recipes(operation_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        state = mes_state(context)
        items = context.harness.store.recipes(operation_id)
        return {
            "time": state.get("time", 0),
            "operation_id": operation_id,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/dispatch/candidates")
    def get_dispatch_candidates(stage: str = Query("A")) -> Dict[str, Any]:
        target_stage = normalize_target_stage(stage, default="A")
        if target_stage == "AUTO":
            raise HTTPException(status_code=400, detail="stage must be A, B, or C")
        items = context.harness.service.dispatch_candidates(
            context.env.get_decision_state(),
            stage=target_stage,
        )
        return {
            "time": context.env.time,
            "stage": target_stage,
            "count": len(items),
            "items": items,
        }

    @router.post("/api/v1/harness/run")
    def harness_run(target_stage: str = Query("A")) -> Dict[str, Any]:
        target = normalize_target_stage(target_stage, default="A")
        if target == "AUTO":
            return run_auto_cycle(context)
        return run_single_cycle(context, target, execute=False)

    @router.get("/api/v1/ai/recommendations")
    def get_recommendations(
        correlation_id: Optional[str] = Query(None),
    ) -> Dict[str, Any]:
        items = context.harness.store.recommendations(correlation_id)
        return {
            "time": context.env.time,
            "correlation_id": correlation_id,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/events")
    def get_events(correlation_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        items = context.harness.store.events(correlation_id)
        return {
            "time": context.env.time,
            "correlation_id": correlation_id,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.get("/api/v1/commands")
    def get_commands(correlation_id: Optional[str] = Query(None)) -> Dict[str, Any]:
        items = context.harness.store.commands(correlation_id)
        return {
            "time": context.env.time,
            "correlation_id": correlation_id,
            "count": len(items),
            "items": [item.to_dict() for item in items],
        }

    @router.post("/api/v1/rules/validate")
    def validate_rules(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        recommendations = [
            AIRecommendation(**item)
            for item in payload.get("recommendations", [])
        ]
        validation = context.harness.service.validate_recommendations(
            context.env.get_decision_state(),
            recommendations,
        )
        return validation.to_dict()

    @router.post("/api/v1/commands/track-in/preview")
    def preview_track_in(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        target = normalize_target_stage(payload.get("target_stage"), default="A")
        if target == "AUTO":
            stages = ready_stages(context, "AUTO")
            target = stages[0] if stages else "A"
        return run_single_cycle(context, target, execute=False)

    @router.post("/api/v1/commands/track-in/execute")
    def execute_track_in(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        target = normalize_target_stage(payload.get("target_stage"), default="A")
        if target == "AUTO":
            return run_auto_cycle(context)
        return run_single_cycle(context, target, execute=True)

    return router

