# -*- coding: utf-8 -*-
"""FastAPI router for read-only process model tools."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from src.mes.process_tools.service import ProcessToolService


router = APIRouter(prefix="/api/v2/process-tools", tags=["process-tools"])
service = ProcessToolService()


@router.get("/catalog")
def process_tool_catalog() -> Dict[str, Any]:
    return service.catalog()


@router.post("/{tool_id}/run")
def run_process_tool(
    tool_id: str,
    payload: Dict[str, Any] = Body(default_factory=dict),
) -> Dict[str, Any]:
    try:
        return service.run_tool(tool_id, payload)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail.startswith("UNKNOWN_PROCESS_TOOL") else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
