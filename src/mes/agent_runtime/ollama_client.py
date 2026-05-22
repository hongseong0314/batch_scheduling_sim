# -*- coding: utf-8 -*-
"""Ollama chat client used by the MES local agent runtime."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

import httpx


class OllamaChatClient:
    """Small wrapper around Ollama's `/api/chat` tool-calling endpoint."""

    def __init__(
        self,
        model: str,
        api_base: str = "http://localhost:11434",
        default_completion_options: Mapping[str, Any] | None = None,
        request_options: Mapping[str, Any] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.api_base = api_base.rstrip("/")
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
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        options = _ollama_options(self.default_completion_options)
        if options:
            payload["options"] = options
        payload.update(_ollama_top_level_options(self.default_completion_options))
        payload.update(_extra_body_properties(self.request_options))
        response = self.http_client.post(
            f"{self.api_base}/api/chat",
            json=payload,
            headers=_request_headers(self.request_options),
        )
        response.raise_for_status()
        return dict(response.json())


def _ollama_options(options: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = {
        "temperature": "temperature",
        "topP": "top_p",
        "top_p": "top_p",
        "topK": "top_k",
        "top_k": "top_k",
        "numCtx": "num_ctx",
        "contextLength": "num_ctx",
        "maxTokens": "num_predict",
        "numPredict": "num_predict",
        "stop": "stop",
    }
    converted = {}
    for key, value in options.items():
        target = allowed.get(str(key))
        if target is not None:
            converted[target] = value
    return converted


def _ollama_top_level_options(options: Mapping[str, Any]) -> Dict[str, Any]:
    converted = {}
    if "reasoning" in options:
        converted["think"] = bool(options["reasoning"])
    if "keepAlive" in options:
        converted["keep_alive"] = options["keepAlive"]
    if "keep_alive" in options:
        converted["keep_alive"] = options["keep_alive"]
    return converted


def _request_headers(request_options: Mapping[str, Any]) -> Dict[str, str]:
    return {str(key): str(value) for key, value in dict(request_options.get("headers", {}) or {}).items()}


def _extra_body_properties(request_options: Mapping[str, Any]) -> Dict[str, Any]:
    return dict(request_options.get("extraBodyProperties", {}) or {})


def _request_timeout(request_options: Mapping[str, Any]) -> float:
    return float(request_options.get("timeout", 60.0) or 60.0)


def _verify_ssl(request_options: Mapping[str, Any]) -> bool:
    return bool(request_options.get("verifySsl", True))
