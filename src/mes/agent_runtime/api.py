# -*- coding: utf-8 -*-
"""FastAPI router for MES process chat."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from src.mes.agent_runtime.process_chat import ProcessChatService


router = APIRouter(prefix="/api/v2", tags=["process-chat"])
service = ProcessChatService()


def configure_process_chat_context(context: Any) -> None:
    service.set_runtime_context(context)


@router.post("/process-chat")
def process_chat(payload: Dict[str, Any] = Body(default_factory=dict)) -> Dict[str, Any]:
    try:
        return service.ask(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/process-chat/models")
def process_chat_models() -> Dict[str, Any]:
    return service.model_catalog()


@router.get("/agent-runs")
def agent_runs(limit: int = Query(50, ge=1, le=200)) -> Dict[str, Any]:
    return service.list_agent_runs(limit=limit)


@router.get("/agent-runs/{agent_run_id}")
def agent_run_detail(agent_run_id: str) -> Dict[str, Any]:
    payload = service.agent_run_detail(agent_run_id)
    if not payload.get("found", False):
        raise HTTPException(status_code=404, detail=payload)
    return payload
