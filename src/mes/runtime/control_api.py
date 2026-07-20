# -*- coding: utf-8 -*-
"""FastAPI routes for simulator control and live control-room payloads."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, Query

from src.mes.runtime.common import normalize_target_stage
from src.mes.runtime.equipment_detail import equipment_detail as build_equipment_detail
from src.mes.runtime.gantt import gantt_state
from src.mes.runtime.live_state import live_fab_state
from src.mes.runtime.simulation_control import (
    generate_tasks as generate_runtime_tasks,
    run_auto_cycle,
    run_single_cycle,
    run_until as run_until_cycles,
    tick_once,
)


def build_control_router(context: Any) -> APIRouter:
    router = APIRouter()

    @router.post("/api/v2/tasks/generate")
    def generate_tasks(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        time_point = payload.get("time_point")
        with context.runtime_lock:
            return generate_runtime_tasks(context, None if time_point is None else int(time_point))

    @router.post("/api/v2/harness/run-cycle")
    def run_cycle(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        target = normalize_target_stage(payload.get("target_stage"), default="AUTO")
        with context.runtime_lock:
            if target == "AUTO":
                return run_auto_cycle(context)
            return run_single_cycle(context, target, execute=True)

    @router.post("/api/v2/harness/run-until")
    def run_until(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        target = normalize_target_stage(payload.get("target_stage"), default="AUTO")
        max_cycles = max(1, min(500, int(payload.get("max_cycles", 25))))
        with context.runtime_lock:
            return run_until_cycles(context, target, max_cycles)

    @router.get("/api/v2/equipment/{equipment_id}/detail")
    def equipment_detail(equipment_id: str) -> Dict[str, Any]:
        return build_equipment_detail(context, equipment_id)

    @router.get("/api/v2/gantt")
    def gantt(
        lookback: int = Query(36, ge=6, le=240),
        lookahead: int = Query(12, ge=4, le=120),
    ) -> Dict[str, Any]:
        return gantt_state(context, lookback=lookback, lookahead=lookahead)

    @router.post("/api/v2/simulation/reset")
    def reset_simulation() -> Dict[str, Any]:
        with context.runtime_lock:
            context.reset_runtime()
            return live_fab_state(context)

    @router.post("/api/v2/simulation/autoplay/start")
    def autoplay_start(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
        with context.runtime_lock:
            context.autoplay_enabled = True
            context.autoplay_target_stage = normalize_target_stage(
                payload.get("target_stage"),
                default="AUTO",
            )
            context.autoplay_generate_every = max(1, int(payload.get("generate_every", 20)))
            cycles = max(0, min(50, int(payload.get("bootstrap_cycles", 1))))
            last = None
            for _ in range(cycles):
                last = tick_once(context, context.autoplay_target_stage)
            return {
                "enabled": True,
                "target_stage": context.autoplay_target_stage,
                "generate_every": context.autoplay_generate_every,
                "time": context.env.time,
                "last_cycle": last,
            }

    @router.post("/api/v2/simulation/autoplay/stop")
    def autoplay_stop() -> Dict[str, Any]:
        with context.runtime_lock:
            context.autoplay_enabled = False
            return {"enabled": False, "time": context.env.time}

    @router.get("/api/v2/simulation/autoplay/status")
    def autoplay_status(step_cycles: int = Query(0, ge=0, le=100)) -> Dict[str, Any]:
        with context.runtime_lock:
            stepped = 0
            if context.autoplay_enabled and step_cycles > 0:
                for _ in range(step_cycles):
                    tick_once(context, context.autoplay_target_stage)
                    stepped += 1
            return {
                "enabled": context.autoplay_enabled,
                "target_stage": context.autoplay_target_stage,
                "time": context.env.time,
                "stepped_cycles": stepped,
                "live": live_fab_state(context),
            }

    @router.get("/api/v2/fab/live")
    def fab_live() -> Dict[str, Any]:
        with context.runtime_lock:
            return live_fab_state(context)

    return router
