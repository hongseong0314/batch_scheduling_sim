# -*- coding: utf-8 -*-
"""Deterministic evaluation helpers for MES Agent responses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class AgentEvalCase:
    case_id: str
    question: str
    required_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    allowed_statuses: List[str] = field(
        default_factory=lambda: ["completed", "policy_blocked"]
    )
    expected_answer_terms: List[str] = field(default_factory=list)
    forbidden_answer_terms: List[str] = field(default_factory=list)


def evaluate_agent_result(
    case: AgentEvalCase,
    result: Mapping[str, Any],
) -> Dict[str, Any]:
    """Evaluate one agent result against a deterministic policy case."""
    failures: List[str] = []
    status = str(result.get("status", "completed"))
    answer = str(result.get("answer", ""))
    tool_calls = [
        dict(call)
        for call in result.get("tool_calls", [])
        if isinstance(call, Mapping)
    ]
    called_tools = {str(call.get("tool_name", "")) for call in tool_calls}
    executed_tools = {
        str(call.get("tool_name", ""))
        for call in tool_calls
        if str(call.get("status", "executed")) == "executed"
    }

    if status not in set(case.allowed_statuses):
        failures.append(f"STATUS_NOT_ALLOWED:{status}")
    for tool_name in case.required_tools:
        if tool_name not in called_tools:
            failures.append(f"MISSING_REQUIRED_TOOL:{tool_name}")
    for tool_name in case.forbidden_tools:
        if tool_name in executed_tools:
            failures.append(f"FORBIDDEN_TOOL_EXECUTED:{tool_name}")
    for term in case.expected_answer_terms:
        if term not in answer:
            failures.append(f"MISSING_ANSWER_TERM:{term}")
    for term in case.forbidden_answer_terms:
        if term in answer:
            failures.append(f"FORBIDDEN_ANSWER_TERM:{term}")

    return {
        "case_id": case.case_id,
        "question": case.question,
        "passed": not failures,
        "failures": failures,
        "status": status,
        "called_tools": sorted(tool for tool in called_tools if tool),
    }
