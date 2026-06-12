# -*- coding: utf-8 -*-
"""Read-only MES tool registry for chat Agent Mode."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from src.mes.agent_runtime.layered_process_tools import (
    LAYERED_PROCESS_TOOL_IDS,
    layered_process_tool_catalog,
    run_layered_process_tool,
)
from src.mes.agent_runtime.visual_tools import (
    VISUAL_TOOL_IDS,
    run_visual_tool,
    visual_tool_catalog,
)
from src.mes.process_tools.service import ProcessToolService
from src.mes.runtime.ai_dev import policy_stack_payload
from src.mes.runtime.assignment_trace import assignment_trace
from src.mes.runtime.candidate_portfolio import latest_candidate_portfolio
from src.mes.runtime.equipment_detail import equipment_detail
from src.mes.runtime.live_state import live_fab_state


class MESAgentToolService:
    """Expose process-model and MES runtime inspection tools to an LLM agent."""

    def __init__(
        self,
        context: Any | None = None,
        process_tools: ProcessToolService | None = None,
    ) -> None:
        self.context = context
        self.process_tools = process_tools or ProcessToolService()

    def catalog(self) -> Dict[str, Any]:
        tools = list(self.process_tools.catalog()["tools"])
        if self.context is not None:
            tools.extend(layered_process_tool_catalog(self.context))
            tools.extend(visual_tool_catalog())
        tools.extend(self._runtime_tool_catalog())
        return {"count": len(tools), "tools": tools}

    def openai_tools(self) -> list[Dict[str, Any]]:
        items = []
        for tool in self.catalog()["tools"]:
            items.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {"type": "object"}),
                    },
                }
            )
        return items

    def run_tool(self, tool_id: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        name = str(tool_id)
        if name in self._process_tool_names():
            return self.process_tools.run_tool(name, arguments)
        if name in LAYERED_PROCESS_TOOL_IDS:
            if self.context is None:
                raise ValueError(f"MES_RUNTIME_CONTEXT_NOT_CONFIGURED:{name}")
            return run_layered_process_tool(self.context, name, arguments)
        if name in VISUAL_TOOL_IDS:
            if self.context is None:
                raise ValueError(f"MES_RUNTIME_CONTEXT_NOT_CONFIGURED:{name}")
            return run_visual_tool(self.context, name, arguments)
        if self.context is None:
            raise ValueError(f"MES_RUNTIME_CONTEXT_NOT_CONFIGURED:{name}")
        if name == "get_fab_snapshot":
            return self._get_fab_snapshot()
        if name == "get_policy_stack":
            return policy_stack_payload(self.context)
        if name == "get_candidate_portfolio_latest":
            return latest_candidate_portfolio(self.context)
        if name == "get_equipment_detail":
            equipment_id = str(arguments.get("equipment_id", "") or "").strip()
            if not equipment_id:
                raise ValueError("MISSING_EQUIPMENT_ID")
            return equipment_detail(self.context, equipment_id)
        if name == "get_assignment_trace":
            return assignment_trace(
                self.context,
                equipment_id=_optional_string(arguments.get("equipment_id")),
                task_uid=_optional_int(arguments.get("task_uid")),
                correlation_id=_optional_string(arguments.get("correlation_id")),
                candidate_id=_optional_string(arguments.get("candidate_id")),
                run_id=_optional_string(arguments.get("run_id")),
            )
        raise ValueError(f"UNKNOWN_MES_AGENT_TOOL:{name}")

    def _runtime_tool_catalog(self) -> list[Dict[str, Any]]:
        if self.context is None:
            return []
        return [
            {
                "id": "get_fab_snapshot",
                "name": "get_fab_snapshot",
                "read_only": True,
                "description": (
                    "Return a compact live MES fab snapshot: time, KPIs, "
                    "A/B/C stage WIP, machine counts, active correlation, and last cycle."
                ),
                "input_schema": _object_schema({}),
            },
            {
                "id": "get_policy_stack",
                "name": "get_policy_stack",
                "read_only": True,
                "description": "Return the active L1/L2/L3/L4 MES policy stack and policy ids.",
                "input_schema": _object_schema({}),
            },
            {
                "id": "get_candidate_portfolio_latest",
                "name": "get_candidate_portfolio_latest",
                "read_only": True,
                "description": (
                    "Return the latest actionable candidate portfolio with selected and "
                    "rejected candidates, score components, and L2 annotations."
                ),
                "input_schema": _object_schema({}),
            },
            {
                "id": "get_equipment_detail",
                "name": "get_equipment_detail",
                "read_only": True,
                "description": "Return machine-level detail for one equipment id such as A_0, B_1, or C_0.",
                "input_schema": _object_schema(
                    {
                        "equipment_id": {
                            "type": "string",
                            "description": "Equipment id, for example A_0, B_1, C_0.",
                        }
                    },
                    required=["equipment_id"],
                ),
            },
            {
                "id": "get_assignment_trace",
                "name": "get_assignment_trace",
                "read_only": True,
                "description": (
                    "Resolve an executed assignment back to L4, L3, L1, L2, "
                    "Rule Engine, Command, portfolio, and simulator action."
                ),
                "input_schema": _object_schema(
                    {
                        "equipment_id": {"type": "string"},
                        "task_uid": {"type": ["integer", "string"]},
                        "correlation_id": {"type": "string"},
                        "candidate_id": {"type": "string"},
                        "run_id": {"type": "string"},
                    }
                ),
            },
        ]

    def _get_fab_snapshot(self) -> Dict[str, Any]:
        payload = live_fab_state(self.context)
        stages = {}
        for stage, stage_payload in dict(payload.get("stages") or {}).items():
            stages[stage] = {
                "label": stage_payload.get("label"),
                "wait": stage_payload.get("wait", 0),
                "incoming": stage_payload.get("incoming", 0),
                "rework": stage_payload.get("rework", 0),
                "running": stage_payload.get("running", 0),
                "idle": stage_payload.get("idle", 0),
                "total_wip": stage_payload.get("total_wip", 0),
                "status": stage_payload.get("status"),
            }
        active_chain = dict(payload.get("active_chain") or {})
        return {
            "run_id": payload.get("run_id"),
            "time": payload.get("time", 0),
            "kpis": payload.get("kpis", {}),
            "stages": stages,
            "active_correlation_id": active_chain.get("correlation_id"),
            "candidate_portfolio_summary": dict(
                (payload.get("candidate_portfolio") or {}).get("summary") or {}
            ),
            "last_cycle": payload.get("last_cycle"),
        }

    def _process_tool_names(self) -> set[str]:
        return {
            str(tool.get("name") or tool.get("id"))
            for tool in self.process_tools.catalog()["tools"]
        }


def _object_schema(
    properties: Mapping[str, Any],
    required: list[str] | None = None,
) -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": dict(properties),
        "required": list(required or []),
    }


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
