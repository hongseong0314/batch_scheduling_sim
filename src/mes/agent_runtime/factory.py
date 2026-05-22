# -*- coding: utf-8 -*-
"""Factory for constructing the local MES process agent runtime."""

from __future__ import annotations

from pathlib import Path
from src.mes.agent_runtime.agent_loop import ChatClient, MESAgentRuntime, ProcessToolBackend
from src.mes.agent_runtime.config import (
    AgentConfig,
    ModelConfig,
    load_agent_config,
    model_effective_capabilities,
    model_supports_role,
)
from src.mes.agent_runtime.mcp_client import MCPProcessToolClient
from src.mes.agent_runtime.ollama_client import OllamaChatClient
from src.mes.agent_runtime.openai_client import OpenAIChatClient
from src.mes.process_tools.service import ProcessToolService


def build_runtime_from_config(
    config_path: str | Path,
    llm_client: ChatClient | None = None,
    prefer_mcp: bool = True,
    cwd: str | None = None,
    model_name: str | None = None,
    tool_service: ProcessToolBackend | None = None,
) -> MESAgentRuntime:
    config = load_agent_config(config_path)
    model = select_model(config, model_name=model_name)
    if not model_supports_role(model, "chat"):
        raise ValueError(f"MODEL_ROLE_NOT_SUPPORTED:{model.name}:chat")
    resolved_llm = llm_client or build_chat_client(model)
    effective_capabilities = model_effective_capabilities(model)
    native_tools_enabled = "tool_use" in effective_capabilities
    return MESAgentRuntime(
        llm_client=resolved_llm,
        tool_service=tool_service or _tool_backend(config, prefer_mcp=prefer_mcp, cwd=cwd),
        model_name=model.model,
        tools_enabled=True,
        native_tools_enabled=native_tools_enabled,
        system_message_tools_enabled=not native_tools_enabled,
    )


def build_chat_client(model: ModelConfig) -> ChatClient:
    provider = model.provider.lower()
    if provider == "ollama":
        return OllamaChatClient(
            model=model.model,
            api_base=model.api_base,
            default_completion_options=model.default_completion_options,
            request_options=model.request_options,
        )
    if provider == "openai":
        return OpenAIChatClient(
            model=model.model,
            api_base=model.api_base,
            api_key=model.api_key,
            default_completion_options=model.default_completion_options,
            request_options=model.request_options,
        )
    raise ValueError(f"UNSUPPORTED_MODEL_PROVIDER:{model.provider}")


def select_model(config: AgentConfig, model_name: str | None = None) -> ModelConfig:
    if not config.models:
        raise ValueError("NO_MODELS_CONFIGURED")
    if model_name:
        for model in config.models:
            if model.name == model_name or model.model == model_name:
                return model
        raise ValueError(f"UNKNOWN_MODEL:{model_name}")
    for model in config.models:
        if "chat" in model.roles:
            return model
    return config.models[0]


def _tool_backend(
    config: AgentConfig,
    prefer_mcp: bool,
    cwd: str | None,
) -> ProcessToolBackend:
    if prefer_mcp and config.mcp_servers:
        server = config.mcp_servers[0]
        if server.type != "stdio":
            raise ValueError(f"UNSUPPORTED_MCP_TRANSPORT:{server.type}")
        return MCPProcessToolClient(
            command=server.command,
            args=server.args,
            cwd=cwd or server.cwd or None,
            env=server.env,
        )
    return ProcessToolService()
