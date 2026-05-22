# -*- coding: utf-8 -*-
"""Chat facade for process-engineer APC questions."""

from __future__ import annotations

import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Mapping

from src.mes.agent_runtime.config import (
    ModelConfig,
    load_agent_config,
    model_effective_capabilities,
    model_supports_role,
)
from src.mes.agent_runtime.factory import build_runtime_from_config, select_model
from src.mes.agent_runtime.mes_tools import MESAgentToolService
from src.mes.agent_runtime.run_store import AgentRunStore
from src.mes.agent_runtime.sqlite_run_store import SQLiteAgentRunStore
from src.mes.process_tools.service import ProcessToolService


DEFAULT_AGENT_CONFIG = Path("config/mes-process-agent.yaml")
AGENT_PROMPT_ID = "MES_AGENT_SYSTEM_PROMPT"
AGENT_PROMPT_VERSION = "0.1.0"
TOOL_CATALOG_VERSION = "mes-agent-tools-v1"


class ProcessChatService:
    """Answer chat messages with LLM tool calling or a local APC fallback."""

    def __init__(
        self,
        tool_service: MESAgentToolService | None = None,
        runtime_context: Any | None = None,
    ) -> None:
        self.process_tools = ProcessToolService()
        self.runtime_context = runtime_context
        self.tool_service = tool_service or MESAgentToolService(
            runtime_context,
            process_tools=self.process_tools,
        )
        self.agent_runs = _agent_run_store_for_context(runtime_context)

    def set_runtime_context(self, runtime_context: Any) -> None:
        self.runtime_context = runtime_context
        if isinstance(self.tool_service, MESAgentToolService):
            self.tool_service.context = runtime_context
        self.agent_runs = _agent_run_store_for_context(runtime_context)

    def ask(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        message = str(payload.get("message", "") or "").strip()
        if not message:
            raise ValueError("EMPTY_CHAT_MESSAGE")
        use_llm = bool(payload.get("use_llm", True))
        model_name = str(payload.get("model_name", "") or "").strip() or None
        mode = str(payload.get("mode", "agent") or "agent").strip().lower()
        if mode not in {"agent", "chat"}:
            raise ValueError(f"UNKNOWN_CHAT_MODE:{mode}")
        max_steps = int(payload.get("max_steps", 5) or 5)
        if use_llm:
            llm_result = self._try_llm(
                message,
                model_name=model_name,
                mode=mode,
                max_steps=max_steps,
            )
            if llm_result is not None:
                return llm_result
        return self._local_process_answer(message)

    def model_catalog(self) -> Dict[str, Any]:
        config_path = Path(os.getenv("MES_PROCESS_AGENT_CONFIG", str(DEFAULT_AGENT_CONFIG)))
        if not config_path.exists():
            return {"count": 0, "items": []}
        config = load_agent_config(config_path)
        items = [
            {
                "name": model.name,
                "provider": model.provider,
                "model": model.model,
                "roles": model.roles,
                "capabilities": model_effective_capabilities(model),
                "configured_capabilities": model.capabilities,
                "api_base": model.api_base,
            }
            for model in config.models
            if model_supports_role(model, "chat")
        ]
        return {"count": len(items), "items": items}

    def _try_llm(
        self,
        message: str,
        model_name: str | None,
        mode: str,
        max_steps: int,
    ) -> Dict[str, Any] | None:
        config_path = Path(os.getenv("MES_PROCESS_AGENT_CONFIG", str(DEFAULT_AGENT_CONFIG)))
        if not config_path.exists():
            return None
        try:
            config = load_agent_config(config_path)
            model = select_model(config, model_name=model_name)
            started_at = time.perf_counter()
            run = self.agent_runs.start_run(
                question=message,
                mode=mode,
                model_name=model.model,
                provider=model.provider,
                max_steps=max_steps,
                prompt_id=AGENT_PROMPT_ID,
                prompt_version=AGENT_PROMPT_VERSION,
                tool_catalog_version=TOOL_CATALOG_VERSION,
                model_config=_model_config_snapshot(model),
                requested_think=bool(model.default_completion_options.get("reasoning", False)),
                mes_run_id=_mes_run_id(self.runtime_context),
            )
            runtime = build_runtime_from_config(
                config_path,
                prefer_mcp=False,
                cwd=str(Path.cwd()),
                model_name=model_name,
                tool_service=self.tool_service,
            )
            result = runtime.run(message, mode=mode, max_steps=max_steps)
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            self.agent_runs.complete_run(
                run.agent_run_id,
                status=str(result.get("status", "completed")),
                answer=str(result.get("answer", "")),
                tool_calls=list(result.get("tool_calls", [])),
                agent_trace=list(result.get("agent_trace", [])),
                duration_ms=duration_ms,
            )
            return {
                "agent_run_id": run.agent_run_id,
                "mode": "llm_agent" if mode == "agent" else "llm_chat",
                "status": result.get("status", "completed"),
                "answer": result.get("answer", ""),
                "tool_calls": result.get("tool_calls", []),
                "agent_trace": result.get("agent_trace", []),
                "model": result.get("model", "-"),
                "fallback_used": False,
            }
        except Exception as exc:
            fallback = self._local_process_answer(message)
            fallback["mode"] = "local_process_tool_fallback"
            fallback["llm_error"] = f"{type(exc).__name__}: {exc}"
            fallback["fallback_used"] = True
            return fallback

    def _local_process_answer(self, message: str) -> Dict[str, Any]:
        started_at = time.perf_counter()
        run = self.agent_runs.start_run(
            question=message,
            mode="local_process_tool",
            model_name="local-parser",
            provider="local",
            max_steps=0,
            prompt_id="LOCAL_APC_PARSER",
            prompt_version="0.1.0",
            tool_catalog_version=TOOL_CATALOG_VERSION,
            model_config={"name": "local-parser", "provider": "local"},
            requested_think=False,
            mes_run_id=_mes_run_id(self.runtime_context),
        )
        parsed = _parse_a_apc_question(message)
        if parsed is None:
            result = {
                "mode": "local_process_tool",
                "status": "completed",
                "answer": (
                    "현재 chat V1은 A 공정 APC 예측 질문을 지원합니다. "
                    "예: spec_a 48~53, u=6, m_age=12, recipe=[10,2,1]"
                ),
                "tool_calls": [],
                "agent_trace": [],
                "model": "local-parser",
                "fallback_used": False,
            }
            self.agent_runs.complete_run(
                run.agent_run_id,
                status="completed",
                answer=result["answer"],
                tool_calls=[],
                agent_trace=[],
                duration_ms=int((time.perf_counter() - started_at) * 1000),
            )
            result["agent_run_id"] = run.agent_run_id
            return result
        result = self.process_tools.run_tool("predict_process_a_apc", parsed)
        answer = (
            "A 공정 APC 예측 결과 "
            f"predicted_qa={result['predicted_qa']}이고 "
            f"target_spec={result['target_spec']['low']}~{result['target_spec']['high']} 기준 "
            f"quality_risk={result['quality_risk']}입니다. "
            f"recipe={result['recipe']}, replace_consumable={result['replace_consumable']}."
        )
        payload = {
            "agent_run_id": run.agent_run_id,
            "mode": "local_process_tool",
            "status": "completed",
            "answer": answer,
            "tool_calls": [
                {
                    "tool_name": "predict_process_a_apc",
                    "arguments": parsed,
                    "result": result,
                    "status": "executed",
                    "policy": "local_process_tool",
                }
            ],
            "agent_trace": [],
            "model": "local-parser",
            "fallback_used": False,
        }
        self.agent_runs.complete_run(
            run.agent_run_id,
            status="completed",
            answer=answer,
            tool_calls=payload["tool_calls"],
            agent_trace=[],
            duration_ms=int((time.perf_counter() - started_at) * 1000),
        )
        return payload

    def list_agent_runs(self, limit: int = 50) -> Dict[str, Any]:
        return self.agent_runs.list_runs(limit=limit)

    def agent_run_detail(self, agent_run_id: str) -> Dict[str, Any]:
        return self.agent_runs.get_run(agent_run_id)


def _parse_a_apc_question(message: str) -> Dict[str, Any] | None:
    if not re.search(r"\bA\b|A\s*공정|process\s*A", message, flags=re.IGNORECASE):
        return None
    spec = _extract_spec(message)
    machine_state = {
        "u": _extract_number(message, r"\bu\s*=\s*(-?\d+(?:\.\d+)?)"),
        "m_age": _extract_number(message, r"\bm_age\s*=\s*(-?\d+(?:\.\d+)?)"),
    }
    if spec is None or machine_state["u"] is None or machine_state["m_age"] is None:
        return None
    arguments: Dict[str, Any] = {
        "task_rows": [{"task_uid": "CHAT_T0", "spec_a": spec}],
        "machine_state": machine_state,
        "queue_info": {},
        "current_time": int(_extract_number(message, r"\btime\s*=\s*(\d+)") or 0),
    }
    recipe = _extract_recipe(message)
    if recipe:
        arguments["recipe"] = recipe
    return arguments


def _extract_spec(message: str) -> list[float] | None:
    patterns = [
        r"spec_a\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*(?:~|–|-|to)\s*(-?\d+(?:\.\d+)?)",
        r"spec\s*[:=]?\s*(-?\d+(?:\.\d+)?)\s*(?:~|–|-|to)\s*(-?\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message, flags=re.IGNORECASE)
        if match:
            return [float(match.group(1)), float(match.group(2))]
    return None


def _extract_recipe(message: str) -> list[float] | None:
    match = re.search(r"recipe\s*=\s*\[([^\]]+)\]", message, flags=re.IGNORECASE)
    if not match:
        return None
    values = [float(value.strip()) for value in match.group(1).split(",") if value.strip()]
    return values if len(values) == 3 else None


def _extract_number(message: str, pattern: str) -> float | None:
    match = re.search(pattern, message, flags=re.IGNORECASE)
    return float(match.group(1)) if match else None


def _model_config_snapshot(model: ModelConfig) -> Dict[str, Any]:
    return {
        "name": model.name,
        "provider": model.provider,
        "model": model.model,
        "api_base": model.api_base,
        "roles": list(model.roles),
        "capabilities": model_effective_capabilities(model),
        "configured_capabilities": list(model.capabilities),
        "default_completion_options": dict(model.default_completion_options),
        "request_options": dict(model.request_options),
    }


def _mes_run_id(runtime_context: Any | None) -> str:
    if runtime_context is None:
        return ""
    direct = getattr(runtime_context, "run_id", "")
    if direct:
        return str(direct)
    store = getattr(getattr(runtime_context, "harness", None), "store", None)
    return str(getattr(store, "current_run_id", "") or "")


def _agent_run_store_for_context(runtime_context: Any | None) -> AgentRunStore:
    store = getattr(runtime_context, "store", None)
    db_path = getattr(store, "db_path", None)
    if db_path:
        return SQLiteAgentRunStore(db_path)
    return AgentRunStore()
