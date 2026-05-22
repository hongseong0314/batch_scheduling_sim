from pathlib import Path

import pytest

from src.mes.agent_runtime.factory import build_runtime_from_config
from src.mes.agent_runtime.mcp_client import MCPProcessToolClient
from src.mes.agent_runtime.mes_tools import MESAgentToolService
from src.mes.agent_runtime.openai_client import OpenAIChatClient


class NoopLLMClient:
    def chat(self, messages, tools):
        return {"message": {"role": "assistant", "content": "ok"}}


def test_runtime_factory_uses_mcp_backend_from_continue_style_config(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: MES Process AI
version: 0.1.0
schema: v1
models:
  - name: Gemma4 Remote
    provider: ollama
    model: gemma4:latest
mcpServers:
  - name: mes-process-tools
    type: stdio
    command: .venv/bin/python
    args:
      - -m
      - src.mes.mcp.process_apc_server
""".strip(),
        encoding="utf-8",
    )

    runtime = build_runtime_from_config(
        config_path,
        llm_client=NoopLLMClient(),
        prefer_mcp=True,
        cwd="/tmp/project",
    )

    assert runtime.model_name == "gemma4:latest"
    assert isinstance(runtime.tool_service, MCPProcessToolClient)
    assert runtime.tool_service.cwd == "/tmp/project"


def test_runtime_factory_selects_openai_provider_by_model_name(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: Gemma4 Remote
    provider: ollama
    model: gemma4:latest
    roles:
      - chat
  - name: OpenAI GPT
    provider: openai
    model: gpt-4.1-mini
    apiKey: sk-test
    roles:
      - chat
""".strip(),
        encoding="utf-8",
    )

    runtime = build_runtime_from_config(
        config_path,
        model_name="OpenAI GPT",
        prefer_mcp=False,
    )

    assert runtime.model_name == "gpt-4.1-mini"
    assert isinstance(runtime.llm_client, OpenAIChatClient)


def test_runtime_factory_rejects_non_chat_model_for_chat_runtime(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: Qwen Autocomplete
    provider: ollama
    model: qwen2.5-coder:1.5b-base
    roles:
      - autocomplete
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="MODEL_ROLE_NOT_SUPPORTED"):
        build_runtime_from_config(
            config_path,
            model_name="Qwen Autocomplete",
            prefer_mcp=False,
        )


def test_runtime_factory_enables_tools_from_effective_capabilities(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: OpenAI GPT
    provider: openai
    model: gpt-4o
    roles:
      - chat
    capabilities: []
""".strip(),
        encoding="utf-8",
    )

    runtime = build_runtime_from_config(
        config_path,
        llm_client=NoopLLMClient(),
        prefer_mcp=False,
    )

    assert runtime.tools_enabled is True


def test_runtime_factory_uses_system_message_tools_when_model_lacks_native_tool_use(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: Basic Chat
    provider: ollama
    model: basic-chat:latest
    roles:
      - chat
    capabilities: []
""".strip(),
        encoding="utf-8",
    )

    runtime = build_runtime_from_config(
        config_path,
        llm_client=NoopLLMClient(),
        prefer_mcp=False,
    )

    assert runtime.tools_enabled is True
    assert runtime.native_tools_enabled is False
    assert runtime.system_message_tools_enabled is True


def test_runtime_factory_accepts_mes_tool_service_override(tmp_path: Path) -> None:
    config_path = tmp_path / "agent.yaml"
    config_path.write_text(
        """
name: Local Config
version: 1.0.0
schema: v1
models:
  - name: OpenAI GPT
    provider: openai
    model: gpt-4o
    roles:
      - chat
""".strip(),
        encoding="utf-8",
    )
    tool_service = MESAgentToolService()

    runtime = build_runtime_from_config(
        config_path,
        llm_client=NoopLLMClient(),
        prefer_mcp=False,
        tool_service=tool_service,
    )

    assert runtime.tool_service is tool_service
