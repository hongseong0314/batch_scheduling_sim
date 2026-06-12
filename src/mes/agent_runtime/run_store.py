# -*- coding: utf-8 -*-
"""In-memory agent run records for MES Agent Mode inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentRunRecord:
    agent_run_id: str
    question: str
    mode: str
    model_name: str
    provider: str
    max_steps: int
    prompt_id: str
    prompt_version: str
    tool_catalog_version: str
    model_config: Dict[str, Any]
    requested_think: bool = False
    mes_run_id: str = ""
    status: str = "running"
    answer: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    agent_trace: List[Dict[str, Any]] = field(default_factory=list)
    visual_artifacts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=_now_iso)
    completed_at: str = ""
    duration_ms: int = 0

    def to_dict(self, include_steps: bool = True) -> Dict[str, Any]:
        payload = {
            "found": True,
            "agent_run_id": self.agent_run_id,
            "mes_run_id": self.mes_run_id,
            "question": self.question,
            "mode": self.mode,
            "status": self.status,
            "answer": self.answer,
            "tool_count": len(self.tool_calls),
            "step_count": len(self.agent_trace),
            "artifact_count": len(self.visual_artifacts),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "duration_ms": self.duration_ms,
            "metadata": {
                "model_name": self.model_name,
                "provider": self.provider,
                "max_steps": self.max_steps,
                "prompt_id": self.prompt_id,
                "prompt_version": self.prompt_version,
                "tool_catalog_version": self.tool_catalog_version,
                "requested_think": self.requested_think,
                "model_config": dict(self.model_config),
            },
        }
        if include_steps:
            payload["tool_calls"] = list(self.tool_calls)
            payload["agent_trace"] = list(self.agent_trace)
            payload["visual_artifacts"] = list(self.visual_artifacts)
        return payload


class AgentRunStore:
    """Bounded in-memory store for recent agent runs."""

    def __init__(self, max_records: int = 100) -> None:
        self.max_records = max(1, int(max_records or 1))
        self._records: Dict[str, AgentRunRecord] = {}
        self._order: List[str] = []

    def start_run(
        self,
        *,
        question: str,
        mode: str,
        model_name: str,
        provider: str,
        max_steps: int,
        prompt_id: str,
        prompt_version: str,
        tool_catalog_version: str,
        model_config: Mapping[str, Any],
        requested_think: bool = False,
        mes_run_id: str = "",
    ) -> AgentRunRecord:
        record = AgentRunRecord(
            agent_run_id=f"ARUN_{uuid4().hex[:12].upper()}",
            question=str(question),
            mode=str(mode),
            model_name=str(model_name),
            provider=str(provider),
            max_steps=int(max_steps),
            prompt_id=str(prompt_id),
            prompt_version=str(prompt_version),
            tool_catalog_version=str(tool_catalog_version),
            model_config=dict(model_config),
            requested_think=bool(requested_think),
            mes_run_id=str(mes_run_id or ""),
        )
        self._records[record.agent_run_id] = record
        self._order.append(record.agent_run_id)
        self._enforce_retention()
        return record

    def complete_run(
        self,
        agent_run_id: str,
        *,
        status: str,
        answer: str,
        tool_calls: List[Dict[str, Any]],
        agent_trace: List[Dict[str, Any]],
        duration_ms: int,
        visual_artifacts: List[Dict[str, Any]] | None = None,
    ) -> None:
        record = self._records[str(agent_run_id)]
        record.status = str(status)
        record.answer = str(answer)
        record.tool_calls = [dict(item) for item in tool_calls]
        record.agent_trace = [dict(item) for item in agent_trace]
        record.visual_artifacts = [
            dict(item) for item in (visual_artifacts or [])
        ]
        record.completed_at = _now_iso()
        record.duration_ms = int(duration_ms)

    def fail_run(
        self,
        agent_run_id: str,
        *,
        error: str,
        duration_ms: int,
    ) -> None:
        record = self._records[str(agent_run_id)]
        record.status = "failed"
        record.answer = str(error)
        record.completed_at = _now_iso()
        record.duration_ms = int(duration_ms)
        record.agent_trace.append({"type": "error", "error": str(error)})

    def list_runs(self, limit: int = 50) -> Dict[str, Any]:
        ids = list(reversed(self._order))[: max(1, int(limit or 1))]
        items = [self._records[record_id].to_dict(include_steps=False) for record_id in ids]
        return {"count": len(items), "items": items}

    def get_run(self, agent_run_id: str) -> Dict[str, Any]:
        record = self._records.get(str(agent_run_id))
        if record is None:
            return {
                "found": False,
                "agent_run_id": str(agent_run_id),
                "reason": "AGENT_RUN_NOT_FOUND",
            }
        return record.to_dict(include_steps=True)

    def _enforce_retention(self) -> None:
        while len(self._order) > self.max_records:
            old_id = self._order.pop(0)
            self._records.pop(old_id, None)
