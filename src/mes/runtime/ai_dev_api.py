# -*- coding: utf-8 -*-
"""FastAPI routes for AI developer console payloads."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from src.mes.runtime.ai_dev import (
    ai_dev_candidate_portfolio,
    decision_cycles_payload,
    policy_stack_payload,
)
from src.mes.runtime.experiments import (
    capture_scenario,
    get_experiment,
    list_experiments,
    list_policy_variants,
    list_scenarios,
    run_experiment,
)


def build_ai_dev_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.get("/api/v2/ai-dev/policy-stack")
    def ai_dev_policy_stack() -> Dict[str, Any]:
        return policy_stack_payload(context)

    @router.get("/api/v2/ai-dev/decision-cycles")
    def ai_dev_decision_cycles(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
        return decision_cycles_payload(context, limit=limit)

    @router.get("/api/v2/ai-dev/candidate-portfolio/{correlation_id}")
    def ai_dev_portfolio(correlation_id: str) -> Dict[str, Any]:
        return ai_dev_candidate_portfolio(context, correlation_id)

    @router.post("/api/v2/ai-dev/scenarios/capture")
    def ai_dev_capture_scenario() -> Dict[str, Any]:
        return capture_scenario(context)

    @router.get("/api/v2/ai-dev/scenarios")
    def ai_dev_scenarios() -> Dict[str, Any]:
        return list_scenarios(context)

    @router.get("/api/v2/ai-dev/policy-variants")
    def ai_dev_policy_variants() -> Dict[str, Any]:
        return list_policy_variants()

    @router.post("/api/v2/ai-dev/experiments/run")
    def ai_dev_run_experiment(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        try:
            return run_experiment(context, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/v2/ai-dev/experiments")
    def ai_dev_experiments() -> Dict[str, Any]:
        return list_experiments(context)

    @router.get("/api/v2/ai-dev/experiments/{experiment_id}")
    def ai_dev_experiment(experiment_id: str) -> Dict[str, Any]:
        try:
            return get_experiment(context, experiment_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router

