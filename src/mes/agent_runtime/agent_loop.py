# -*- coding: utf-8 -*-
"""Continue-inspired agent loop for MES read-only tool calling."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Protocol

from src.mes.agent_runtime.visual_artifacts import validate_visual_artifact
from src.mes.process_tools.service import ProcessToolService


class ChatClient(Protocol):
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Return a chat response with an optional message.tool_calls field."""


class ProcessToolBackend(Protocol):
    def catalog(self) -> Dict[str, Any]:
        """Return tool metadata including read-only policy flags."""

    def openai_tools(self) -> List[Dict[str, Any]]:
        """Return callable tool schemas for the LLM."""

    def run_tool(self, tool_id: str, arguments: Mapping[str, Any]) -> Dict[str, Any]:
        """Run one read-only process tool."""


class MESAgentRuntime:
    """Run one user question through an LLM and read-only MES tools.

    The loop mirrors Continue's agent shape at a small scale:
    assistant response -> tool call extraction -> policy evaluation -> tool
    result message -> next assistant response. Only read-only tools are
    auto-executed in this MES runtime.
    """

    def __init__(
        self,
        llm_client: ChatClient,
        tool_service: ProcessToolBackend | None = None,
        model_name: str = "gemma4:latest",
        tools_enabled: bool = True,
        native_tools_enabled: bool | None = None,
        system_message_tools_enabled: bool = False,
    ) -> None:
        self.llm_client = llm_client
        self.tool_service = tool_service or ProcessToolService()
        self.model_name = model_name
        self.tools_enabled = tools_enabled
        self.native_tools_enabled = tools_enabled if native_tools_enabled is None else native_tools_enabled
        self.system_message_tools_enabled = system_message_tools_enabled

    def ask(self, question: str) -> Dict[str, Any]:
        return self.run(question, mode="agent", max_steps=2)

    def run(
        self,
        question: str,
        mode: str = "agent",
        max_steps: int = 5,
    ) -> Dict[str, Any]:
        normalized_mode = str(mode or "agent").lower()
        if normalized_mode not in {"agent", "chat"}:
            raise ValueError(f"UNKNOWN_AGENT_MODE:{mode}")

        messages = [
            {"role": "system", "content": self._system_prompt(normalized_mode)},
            {"role": "user", "content": question},
        ]
        max_steps = max(1, int(max_steps or 1))
        executed_calls: List[Dict[str, Any]] = []
        visual_artifacts: List[Dict[str, Any]] = []
        agent_trace: List[Dict[str, Any]] = []
        last_response: Dict[str, Any] = {}
        last_answer = ""

        for step in range(1, max_steps + 1):
            tools = self._native_tools_for_step(normalized_mode)
            response = self.llm_client.chat(messages=messages, tools=tools)
            last_response = response
            assistant_message = dict(response.get("message", {}) or {})
            last_answer = str(assistant_message.get("content", "") or "").strip()
            tool_calls = (
                _extract_tool_calls(assistant_message)
                if self.tools_enabled and normalized_mode == "agent"
                else []
            )
            agent_trace.append(
                {
                    "type": "llm_response",
                    "step": step,
                    "tool_call_count": len(tool_calls),
                    "content": last_answer,
                }
            )

            if normalized_mode == "chat" or not tool_calls:
                answer = last_answer or _fallback_answer(executed_calls)
                return {
                    "mode": normalized_mode,
                    "status": "completed",
                    "model": self.model_name,
                    "answer": answer,
                    "tool_calls": executed_calls,
                    "visual_artifacts": visual_artifacts,
                    "agent_trace": agent_trace,
                    "raw_response": response,
                }

            messages.append(assistant_message)
            for call in tool_calls:
                tool_name = call["tool_name"]
                arguments = call["arguments"]
                policy = self._evaluate_tool_policy(tool_name)
                if policy["action"] != "execute":
                    rejected = {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "status": "rejected",
                        "policy": policy["policy"],
                        "layer": policy.get("layer", ""),
                        "policy_id": policy.get("policy_id", ""),
                        "error": policy["reason"],
                    }
                    executed_calls.append(rejected)
                    agent_trace.append(
                        {
                            "type": "tool_call",
                            "step": step,
                            "tool_name": tool_name,
                            "status": "rejected",
                            "policy": policy["policy"],
                            "layer": policy.get("layer", ""),
                            "policy_id": policy.get("policy_id", ""),
                            "error": policy["reason"],
                        }
                    )
                    return {
                        "mode": normalized_mode,
                        "status": "policy_blocked",
                        "model": self.model_name,
                        "answer": (
                            "요청한 도구는 현재 MES Agent Mode에서 자동 실행할 수 없습니다. "
                            "읽기 전용 조회/예측 도구만 허용됩니다."
                        ),
                        "tool_calls": executed_calls,
                        "visual_artifacts": visual_artifacts,
                        "agent_trace": agent_trace,
                        "raw_response": response,
                    }

                try:
                    result = self.tool_service.run_tool(tool_name, arguments)
                    status = "executed"
                    error = ""
                except Exception as exc:
                    result = {}
                    status = "failed"
                    error = f"{type(exc).__name__}: {exc}"
                executed = {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                    "status": status,
                    "policy": policy["policy"],
                    "layer": policy.get("layer", ""),
                    "operation_id": policy.get("operation_id", ""),
                    "policy_id": policy.get("policy_id", ""),
                }
                if error:
                    executed["error"] = error
                executed_calls.append(executed)
                if status == "executed":
                    _append_visual_artifacts(visual_artifacts, result)
                agent_trace.append(
                    {
                        "type": "tool_call",
                        "step": step,
                        "tool_name": tool_name,
                        "status": status,
                        "policy": policy["policy"],
                        "layer": policy.get("layer", ""),
                        "operation_id": policy.get("operation_id", ""),
                        "policy_id": policy.get("policy_id", ""),
                        "result": result,
                        "error": error,
                    }
                )
                if status == "failed":
                    return {
                        "mode": normalized_mode,
                        "status": "tool_failed",
                        "model": self.model_name,
                        "answer": f"{tool_name} 실행 중 오류가 발생했습니다: {error}",
                        "tool_calls": executed_calls,
                        "visual_artifacts": visual_artifacts,
                        "agent_trace": agent_trace,
                        "raw_response": response,
                    }
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.get("tool_call_id", f"call_{step}"),
                        "name": tool_name,
                        "content": json.dumps(
                            _compact_tool_result_for_llm(result),
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    }
                )

        answer = last_answer or _fallback_answer(executed_calls)
        return {
            "mode": normalized_mode,
            "status": "max_steps_reached",
            "model": self.model_name,
            "answer": answer,
            "tool_calls": executed_calls,
            "visual_artifacts": visual_artifacts,
            "agent_trace": agent_trace,
            "raw_response": last_response,
        }

    def _native_tools_for_step(self, mode: str) -> List[Dict[str, Any]]:
        if mode != "agent" or not self.tools_enabled or not self.native_tools_enabled:
            return []
        return self.tool_service.openai_tools()

    def _evaluate_tool_policy(self, tool_name: str) -> Dict[str, str]:
        tool = self._tool_metadata().get(tool_name)
        if tool is None:
            return {
                "action": "block",
                "policy": "excluded",
                "layer": "",
                "operation_id": "",
                "policy_id": "",
                "reason": f"UNKNOWN_TOOL:{tool_name}",
            }
        if not bool(tool.get("read_only", False)):
            return {
                "action": "block",
                "policy": "excluded",
                "layer": str(tool.get("layer", "")),
                "operation_id": str(tool.get("operation_id") or tool.get("stage") or ""),
                "policy_id": str(tool.get("policy_id", "")),
                "reason": f"NON_READ_ONLY_TOOL:{tool_name}",
            }
        return {
            "action": "execute",
            "policy": "allowedWithoutPermission",
            "layer": str(tool.get("layer", "")),
            "operation_id": str(tool.get("operation_id") or tool.get("stage") or ""),
            "policy_id": str(tool.get("policy_id", "")),
            "reason": "READ_ONLY_TOOL",
        }

    def _tool_metadata(self) -> Dict[str, Dict[str, Any]]:
        catalog = self.tool_service.catalog()
        tools = catalog.get("tools", []) if isinstance(catalog, Mapping) else []
        metadata = {}
        for tool in tools:
            if not isinstance(tool, Mapping):
                continue
            name = str(tool.get("name") or tool.get("id") or "")
            if name:
                metadata[name] = dict(tool)
        return metadata

    def _system_prompt(self, mode: str) -> str:
        prompt = (
            "You are a manufacturing process AI assistant for a semiconductor MES. "
            "Answer process-engineer questions using the current MES state and "
            "read-only prediction/inspection tools when needed. Never claim that "
            "a recipe, dispatch, equipment state, or MES record was changed. "
            "Use L1 tools to inspect local candidate generation, L2 tools to inspect "
            "APC/process annotations, and runtime tools to inspect L3/L4 policy context. "
            "Write concise Korean answers unless the user asks otherwise."
        )
        if (
            mode == "agent"
            and self.tools_enabled
            and self.system_message_tools_enabled
            and not self.native_tools_enabled
        ):
            prompt = f"{prompt}\n\n{self._system_message_tool_instructions()}"
        return prompt

    def _system_message_tool_instructions(self) -> str:
        lines = [
            "Available MES tools:",
            "Return exactly one JSON object to call a tool, with no markdown:",
            '{"tool":"tool_name","arguments":{...}}',
            "After tool results are provided, answer the user directly.",
        ]
        for tool in self._tool_metadata().values():
            schema = tool.get("input_schema", {"type": "object"})
            lines.append(
                "- "
                f"{tool.get('name')}: {tool.get('description', '')} "
                f"read_only={bool(tool.get('read_only', False))} "
                f"schema={json.dumps(schema, ensure_ascii=False, sort_keys=True)}"
            )
        return "\n".join(lines)


def _extract_tool_calls(message: Mapping[str, Any]) -> List[Dict[str, Any]]:
    calls = []
    for raw_call in message.get("tool_calls", []) or []:
        function = raw_call.get("function", {}) if isinstance(raw_call, Mapping) else {}
        name = function.get("name")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            arguments = json.loads(arguments or "{}")
        if name:
            calls.append(
                {
                    "tool_name": str(name),
                    "arguments": dict(arguments or {}),
                    "tool_call_id": str(raw_call.get("id", "call_0")),
                }
            )
    if calls:
        return calls

    content = str(message.get("content", "") or "").strip()
    if not content:
        return []
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, Mapping):
        return []
    if parsed.get("tool") and isinstance(parsed.get("arguments"), Mapping):
        return [
            {
                "tool_name": str(parsed["tool"]),
                "arguments": dict(parsed["arguments"]),
            }
        ]
    return []


def _compact_tool_result_for_llm(result: Mapping[str, Any]) -> Dict[str, Any]:
    """Keep visual payloads in the API result without echoing them into the LLM."""
    payload = dict(result)
    payload.pop("visual_artifacts", None)
    spatial_quality = payload.get("spatial_quality")
    if isinstance(spatial_quality, Mapping):
        compact_spatial = dict(spatial_quality)
        cells = compact_spatial.pop("cells", [])
        compact_spatial["cell_count"] = len(cells) if isinstance(cells, list) else 0
        payload["spatial_quality"] = compact_spatial
    return payload


def _append_visual_artifacts(
    collected: List[Dict[str, Any]],
    tool_result: Mapping[str, Any],
) -> None:
    known_ids = {str(item.get("artifact_id", "")) for item in collected}
    for raw_artifact in tool_result.get("visual_artifacts", []) or []:
        if not isinstance(raw_artifact, Mapping):
            continue
        try:
            artifact = validate_visual_artifact(raw_artifact)
        except ValueError:
            continue
        artifact_id = str(artifact.get("artifact_id", ""))
        if not artifact_id or artifact_id in known_ids:
            continue
        collected.append(artifact)
        known_ids.add(artifact_id)


def _fallback_answer(executed_calls: List[Dict[str, Any]]) -> str:
    if not executed_calls:
        return ""
    result = executed_calls[-1].get("result", {})
    return (
        f"{result.get('stage')} 공정 APC 예측 결과 predicted_qa="
        f"{result.get('predicted_qa')}, quality_risk={result.get('quality_risk')}입니다."
    )
