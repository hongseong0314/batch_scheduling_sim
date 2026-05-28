# -*- coding: utf-8 -*-
"""Facade for read-only process model tools."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping

from src.mes.process_tools.process_a_apc import predict_process_a_apc


ToolHandler = Callable[[Mapping[str, Any]], Dict[str, Any]]


class ProcessToolService:
    """Registry and execution facade for LLM-callable process tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, Dict[str, Any]] = {
            "predict_process_a_apc": {
                "id": "predict_process_a_apc",
                "name": "predict_process_a_apc",
                "stage": "A",
                "operation_id": "A",
                "layer": "L2",
                "policy_id": "A_RULE_BASED_APC_PREDICTOR",
                "read_only": True,
                "description": (
                    "Predict Process A APC quality for a proposed task batch, "
                    "machine state, and optional recipe. This tool never applies "
                    "a recipe or changes MES state."
                ),
                "input_schema": _process_a_schema(),
                "output_contract": {
                    "stage": "A",
                    "model_id": "A_RULE_BASED_APC_PREDICTOR",
                    "fields": [
                        "recipe",
                        "predicted_qa",
                        "target_spec",
                        "quality_risk",
                        "replace_consumable",
                    ],
                },
                "handler": predict_process_a_apc,
            }
        }

    def catalog(self) -> Dict[str, Any]:
        """Return tool metadata without executable handler objects."""
        tools = []
        for tool in self._tools.values():
            tools.append({key: value for key, value in tool.items() if key != "handler"})
        return {"count": len(tools), "tools": tools}

    def openai_tools(self) -> list[Dict[str, Any]]:
        """Return tool definitions in the format accepted by Ollama/OpenAI APIs."""
        items = []
        for tool in self.catalog()["tools"]:
            items.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                }
            )
        return items

    def run_tool(self, tool_id: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        tool = self._tools.get(str(tool_id))
        if tool is None:
            raise ValueError(f"UNKNOWN_PROCESS_TOOL:{tool_id}")
        if not tool.get("read_only"):
            raise ValueError(f"UNSAFE_PROCESS_TOOL:{tool_id}")
        handler: ToolHandler = tool["handler"]
        return handler(arguments)


def _process_a_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_rows": {
                "type": "array",
                "description": "Process A task rows. Each row may include task_uid and spec_a.",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "task_uid": {"type": ["string", "integer"]},
                        "spec_a": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                },
            },
            "machine_state": {
                "type": "object",
                "description": "Process A machine state with consumable age u and machine age m_age.",
                "additionalProperties": True,
                "properties": {
                    "u": {"type": "number"},
                    "m_age": {"type": "number"},
                },
            },
            "recipe": {
                "type": "array",
                "description": "Optional A recipe vector [temp, flow, duration].",
                "items": {"type": "number"},
                "minItems": 3,
                "maxItems": 3,
            },
            "queue_info": {
                "type": "object",
                "description": "Optional queue context such as wait_pool_size.",
                "additionalProperties": True,
            },
            "current_time": {
                "type": "integer",
                "description": "Simulator or fab decision time.",
            },
        },
        "required": ["task_rows", "machine_state"],
    }
