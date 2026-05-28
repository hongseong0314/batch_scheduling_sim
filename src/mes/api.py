# -*- coding: utf-8 -*-
"""FastAPI app wiring for the simulator-backed MES runtime."""

from __future__ import annotations

from fastapi import FastAPI

from src.mes.agent_runtime.api import (
    configure_process_chat_context,
    router as process_chat_router,
)
from src.mes.process_tools.api import router as process_tools_router
from src.mes.runtime.ai_dev_api import build_ai_dev_router
from src.mes.runtime.app_shell_api import build_app_shell_router
from src.mes.runtime.context import MESAPIContext
from src.mes.runtime.control_api import build_control_router
from src.mes.runtime.production_boundary_api import build_production_boundary_router
from src.mes.runtime.run_ledger_api import build_run_ledger_router
from src.mes.runtime.trace_api import build_trace_router
from src.mes.runtime.v1_api import build_v1_router


context = MESAPIContext()
app = FastAPI(title="Manufacturing AI MES MVP API", version="0.2.0")
app.state.context = context

configure_process_chat_context(context)
app.include_router(build_app_shell_router())
app.include_router(build_v1_router(context))
app.include_router(build_control_router(context))
app.include_router(build_trace_router(context))
app.include_router(build_ai_dev_router(context))
app.include_router(build_production_boundary_router(context))
app.include_router(build_run_ledger_router(context))
app.include_router(process_chat_router)
app.include_router(process_tools_router)
