# -*- coding: utf-8 -*-
"""FastAPI routes for the MES HTML shell and health check."""

from __future__ import annotations

from typing import Dict

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.mes.ui.assets import control_room_html


def build_app_shell_router() -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    def root() -> HTMLResponse:
        return HTMLResponse(control_room_html())

    @router.get("/mes", response_class=HTMLResponse)
    def mes_screen() -> HTMLResponse:
        return HTMLResponse(control_room_html())

    @router.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    return router

