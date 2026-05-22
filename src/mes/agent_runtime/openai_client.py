# -*- coding: utf-8 -*-
"""OpenAI-compatible chat client for the MES local agent runtime."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Mapping

import httpx


class OpenAIChatClient:
    """Wrapper around OpenAI-compatible `/chat/completions` endpoints."""

    def __init__(
        self,
        model: str,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        default_completion_options: Mapping[str, Any] | None = None,
        request_options: Mapping[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.api_base = api_base.rstrip("/")
        self.api_key = _resolve_api_key(api_key)
        self.default_completion_options = dict(default_completion_options or {})
        self.request_options = dict(request_options or {})
        self.http_client = http_client or httpx.Client(
            timeout=_request_timeout(self.request_options),
            verify=_verify_ssl(self.request_options),
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [_normalize_message(message) for message in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["parallel_tool_calls"] = False
        payload.update(_openai_options(self.default_completion_options))
        payload.update(_extra_body_properties(self.request_options))
        response = self.http_client.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=self._headers(),
        )
        response.raise_for_status()
        body = response.json()
        return {"message": dict(body["choices"][0]["message"])}

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        headers.update(_request_headers(self.request_options))
        return headers


def _normalize_message(message: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = {
        "role": message.get("role", "user"),
        "content": message.get("content", ""),
    }
    if message.get("role") == "tool":
        normalized["tool_call_id"] = message.get("tool_call_id", message.get("id", "call_0"))
        return normalized
    if message.get("tool_calls"):
        normalized["tool_calls"] = [_normalize_tool_call(call) for call in message["tool_calls"]]
    return normalized


def _normalize_tool_call(call: Mapping[str, Any]) -> Dict[str, Any]:
    function = dict(call.get("function", {}) or {})
    arguments = function.get("arguments", {})
    if not isinstance(arguments, str):
        arguments = json.dumps(arguments or {}, ensure_ascii=False)
    return {
        "id": call.get("id", "call_0"),
        "type": call.get("type", "function"),
        "function": {
            "name": function.get("name", ""),
            "arguments": arguments,
        },
    }


def _openai_options(options: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = {
        "temperature": "temperature",
        "topP": "top_p",
        "top_p": "top_p",
        "maxTokens": "max_tokens",
        "max_tokens": "max_tokens",
        "stop": "stop",
    }
    converted = {}
    for key, value in options.items():
        target = allowed.get(str(key))
        if target is not None:
            converted[target] = value
    return converted


def _resolve_api_key(api_key: str) -> str:
    if not api_key:
        return os.getenv("OPENAI_API_KEY", "")
    secret_match = re_match_secret(api_key)
    if secret_match:
        return os.getenv(secret_match, "")
    if api_key.startswith("${") and api_key.endswith("}"):
        return os.getenv(api_key[2:-1], "")
    if api_key.startswith("$"):
        return os.getenv(api_key[1:], "")
    return api_key


def re_match_secret(value: str) -> str:
    if value.startswith("${{") and value.endswith("}}"):
        inner = value[3:-2].strip()
        if inner.startswith("secrets."):
            return inner.split(".", 1)[1]
    return ""


def _request_headers(request_options: Mapping[str, Any]) -> Dict[str, str]:
    return {str(key): str(value) for key, value in dict(request_options.get("headers", {}) or {}).items()}


def _extra_body_properties(request_options: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(request_options.get("extraBodyProperties", {}) or {})


def _request_timeout(request_options: Mapping[str, Any]) -> float:
    return float(request_options.get("timeout", 60.0) or 60.0)


def _verify_ssl(request_options: Mapping[str, Any]) -> bool:
    return bool(request_options.get("verifySsl", True))
